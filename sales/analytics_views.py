"""
sales/analytics_views.py
────────────────────────
Analytics dashboard and data API endpoints.
All chart data is served as JSON from dedicated endpoints so the
template can use Chart.js without any server-side charting library.
"""
import csv
import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q, F
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone

from .models import Sale, SaleItem
from inventory.models import Product, Joint, Stock


def _require_manager(request):
    if not request.user.is_manager_role:
        messages.error(request, 'Managers and above only.')
        return True
    return False


# ── MAIN DASHBOARD ────────────────────────────────────────────────────────────

@login_required
def analytics_dashboard(request):
    if _require_manager(request):
        return redirect('sales:dashboard')

    today       = timezone.now().date()
    month_start = today.replace(day=1)
    week_start  = today - timedelta(days=today.weekday())
    year_start  = today.replace(month=1, day=1)

    completed = Sale.objects.filter(is_held=False)

    # ── Headline KPIs ─────────────────────────────────────────────────────────
    def sales_for_period(qs):
        items = SaleItem.objects.filter(sale__in=qs, is_free_gift=False)
        revenue = items.aggregate(t=Sum(F('quantity') * F('unit_price')))['t'] or Decimal('0')
        count   = qs.count()
        discount = qs.aggregate(d=Sum('discount_amount'))['d'] or Decimal('0')
        net     = revenue - discount
        return {'revenue': revenue, 'net': net, 'count': count}

    today_qs  = completed.filter(sale_date__date=today)
    week_qs   = completed.filter(sale_date__date__gte=week_start)
    month_qs  = completed.filter(sale_date__date__gte=month_start)

    kpis = {
        'today':  sales_for_period(today_qs),
        'week':   sales_for_period(week_qs),
        'month':  sales_for_period(month_qs),
    }

    # ── Low stock alerts ─────────────────────────────────────────────────────
    from django.conf import settings as django_settings
    threshold = getattr(django_settings, 'LOW_STOCK_THRESHOLD', 3)
    low_stock = Product.objects.select_related('stock', 'joint').filter(
        is_active=True, stock__quantity__lte=threshold
    ).order_by('stock__quantity')[:20]

    # ── Top 10 products this month ────────────────────────────────────────────
    top_products = (
        SaleItem.objects
        .filter(sale__sale_date__date__gte=month_start, sale__is_held=False, is_free_gift=False)
        .values('product__name', 'product__joint__display_name')
        .annotate(
            total_qty=Sum('quantity'),
            total_revenue=Sum(F('quantity') * F('unit_price'))
        )
        .order_by('-total_revenue')[:10]
    )

    # ── Payment breakdown this month ─────────────────────────────────────────
    payment_breakdown = {}
    for method, label in Sale.PAYMENT_CHOICES:
        qs_m = month_qs.filter(payment_method=method)
        cnt  = qs_m.count()
        items_m = SaleItem.objects.filter(sale__in=qs_m, is_free_gift=False)
        rev  = items_m.aggregate(t=Sum(F('quantity') * F('unit_price')))['t'] or Decimal('0')
        payment_breakdown[label] = {'count': cnt, 'revenue': rev}

    # ── Per-cashier performance this month ───────────────────────────────────
    from users.models import User
    staff_perf = []
    for user in User.objects.filter(is_active=True):
        user_sales = month_qs.filter(sold_by=user)
        cnt = user_sales.count()
        if cnt == 0:
            continue
        items_u = SaleItem.objects.filter(sale__in=user_sales, is_free_gift=False)
        rev = items_u.aggregate(t=Sum(F('quantity') * F('unit_price')))['t'] or Decimal('0')
        staff_perf.append({'user': user, 'count': cnt, 'revenue': rev})
    staff_perf.sort(key=lambda x: x['revenue'], reverse=True)

    # ── Returns summary ───────────────────────────────────────────────────────
    try:
        from returns.models import Return
        returns_this_month = Return.objects.filter(
            status=Return.STATUS_COMPLETED,
            created_at__date__gte=month_start,
        )
        return_count = returns_this_month.count()
        return_value = returns_this_month.aggregate(
            t=Sum('total_refund_amount')
        )['t'] or Decimal('0')
    except Exception:
        return_count = 0
        return_value = Decimal('0')

    return render(request, 'analytics/dashboard.html', {
        'kpis':              kpis,
        'low_stock':         low_stock,
        'top_products':      top_products,
        'payment_breakdown': payment_breakdown,
        'staff_perf':        staff_perf,
        'return_count':      return_count,
        'return_value':      return_value,
        'month':             today.strftime('%B %Y'),
        'joints':            Joint.objects.all(),
    })


# ── JSON: revenue over last N days (for line chart) ──────────────────────────

@login_required
def analytics_api_revenue(request):
    if not request.user.is_manager_role:
        return JsonResponse({'error': 'forbidden'}, status=403)

    days     = int(request.GET.get('days', 30))
    joint_id = request.GET.get('joint_id', '')
    today    = timezone.now().date()
    start    = today - timedelta(days=days - 1)

    qs = SaleItem.objects.filter(
        sale__sale_date__date__gte=start,
        sale__is_held=False,
        is_free_gift=False,
    )
    if joint_id:
        qs = qs.filter(sale__joint_id=joint_id)

    # Group by date
    daily = (
        qs.values('sale__sale_date__date')
          .annotate(
              revenue=Sum(F('quantity') * F('unit_price')),
              count=Count('sale', distinct=True),
          )
          .order_by('sale__sale_date__date')
    )

    date_map = {row['sale__sale_date__date']: row for row in daily}
    labels, revenues, counts = [], [], []

    current = start
    while current <= today:
        labels.append(current.strftime('%d %b'))
        row = date_map.get(current)
        revenues.append(float(row['revenue']) if row else 0)
        counts.append(row['count'] if row else 0)
        current += timedelta(days=1)

    return JsonResponse({'labels': labels, 'revenues': revenues, 'counts': counts})


# ── JSON: top products (for bar chart) ───────────────────────────────────────

@login_required
def analytics_api_top_products(request):
    if not request.user.is_manager_role:
        return JsonResponse({'error': 'forbidden'}, status=403)

    days     = int(request.GET.get('days', 30))
    joint_id = request.GET.get('joint_id', '')
    limit    = int(request.GET.get('limit', 10))
    today    = timezone.now().date()
    start    = today - timedelta(days=days - 1)

    qs = SaleItem.objects.filter(
        sale__sale_date__date__gte=start,
        sale__is_held=False,
        is_free_gift=False,
    )
    if joint_id:
        qs = qs.filter(sale__joint_id=joint_id)

    rows = (
        qs.values('product__name')
          .annotate(
              total_qty=Sum('quantity'),
              total_revenue=Sum(F('quantity') * F('unit_price')),
          )
          .order_by('-total_revenue')[:limit]
    )

    return JsonResponse({
        'labels':   [r['product__name'] or '(deleted)' for r in rows],
        'revenues': [float(r['total_revenue']) for r in rows],
        'quantities': [r['total_qty'] for r in rows],
    })


# ── JSON: payment method breakdown ───────────────────────────────────────────

@login_required
def analytics_api_payment_breakdown(request):
    if not request.user.is_manager_role:
        return JsonResponse({'error': 'forbidden'}, status=403)

    days     = int(request.GET.get('days', 30))
    joint_id = request.GET.get('joint_id', '')
    today    = timezone.now().date()
    start    = today - timedelta(days=days - 1)

    qs = Sale.objects.filter(
        sale_date__date__gte=start, is_held=False,
    )
    if joint_id:
        qs = qs.filter(joint_id=joint_id)

    rows = (
        qs.values('payment_method')
          .annotate(count=Count('id'))
          .order_by('-count')
    )

    method_labels = dict(Sale.PAYMENT_CHOICES)
    return JsonResponse({
        'labels': [method_labels.get(r['payment_method'], r['payment_method']) for r in rows],
        'counts': [r['count'] for r in rows],
    })


# ── CSV EXPORT ────────────────────────────────────────────────────────────────

@login_required
def analytics_export_csv(request):
    if not request.user.is_manager_role:
        messages.error(request, 'Managers and above only.')
        return redirect('sales:analytics_dashboard')

    report_type = request.GET.get('report', 'sales')
    date_from   = request.GET.get('date_from', str(timezone.now().date().replace(day=1)))
    date_to     = request.GET.get('date_to', str(timezone.now().date()))
    joint_id    = request.GET.get('joint_id', '')

    response = HttpResponse(content_type='text/csv')

    if report_type == 'sales':
        response['Content-Disposition'] = f'attachment; filename="sales_{date_from}_{date_to}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Receipt #', 'Date', 'Joint', 'Cashier', 'Customer',
                         'Payment Method', 'Subtotal', 'Discount', 'Total'])

        qs = Sale.objects.filter(
            is_held=False,
            sale_date__date__gte=date_from,
            sale_date__date__lte=date_to,
        ).select_related('joint', 'sold_by', 'customer').order_by('-sale_date')
        if joint_id:
            qs = qs.filter(joint_id=joint_id)

        for sale in qs:
            cashier  = sale.sold_by.get_full_name() if sale.sold_by else ''
            customer = sale.customer.name if sale.customer else sale.customer_name
            writer.writerow([
                sale.receipt_number,
                sale.sale_date.strftime('%Y-%m-%d %H:%M'),
                sale.joint.display_name,
                cashier,
                customer,
                sale.get_payment_method_display(),
                sale.subtotal,
                sale.discount_amount,
                sale.total_amount,
            ])

    elif report_type == 'products':
        response['Content-Disposition'] = f'attachment; filename="product_performance_{date_from}_{date_to}.csv"'
        writer = csv.writer(response)
        writer.writerow(['Product', 'Joint', 'Qty Sold', 'Revenue'])

        qs = SaleItem.objects.filter(
            sale__is_held=False,
            sale__sale_date__date__gte=date_from,
            sale__sale_date__date__lte=date_to,
            is_free_gift=False,
        )
        if joint_id:
            qs = qs.filter(sale__joint_id=joint_id)

        rows = (
            qs.values('product__name', 'product__joint__display_name')
              .annotate(
                  total_qty=Sum('quantity'),
                  total_revenue=Sum(F('quantity') * F('unit_price')),
              )
              .order_by('-total_revenue')
        )
        for r in rows:
            writer.writerow([
                r['product__name'] or '(deleted)',
                r['product__joint__display_name'] or '',
                r['total_qty'],
                f"{r['total_revenue']:.2f}",
            ])

    elif report_type == 'inventory':
        response['Content-Disposition'] = 'attachment; filename="inventory_snapshot.csv"'
        writer = csv.writer(response)
        writer.writerow(['Product', 'SKU', 'Joint', 'Category', 'Stock Qty',
                         'Min Stock', 'Selling Price', 'Stock Value'])

        stocks = (
            Stock.objects
            .select_related('product__joint', 'product__category')
            .filter(product__is_active=True)
            .order_by('product__joint__name', 'product__name')
        )
        if joint_id:
            stocks = stocks.filter(product__joint_id=joint_id)

        for stock in stocks:
            p = stock.product
            writer.writerow([
                p.name,
                p.code or p.barcode or '',
                p.joint.display_name,
                p.category.name if p.category else '',
                stock.quantity,
                stock.min_quantity,
                p.price,
                f"{stock.quantity * p.price:.2f}",
            ])

    return response