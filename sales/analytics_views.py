"""
sales/analytics_views.py  ── Section 3 upgrade
────────────────────────────────────────────────
Full analytics engine with:
  • Live KPI dashboard (auto-refresh every 60s)
  • Revenue trend  (30/90/365-day, per-joint)
  • Payment breakdown donut
  • Top-10 products bar (qty / revenue toggle)
  • Hourly sales distribution area chart
  • Staff performance grouped bar
  • Cohort, basket-size, velocity, staff-hours endpoints
  • CSV export (sales / products / inventory)
"""
import csv
import json
from datetime import date, timedelta, datetime
from decimal import Decimal
from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Avg, F, Q, FloatField
from django.db.models.functions import TruncDate, TruncHour, TruncMonth
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone

from .models import Sale, SaleItem
from inventory.models import Product, Joint, Stock


# ── helpers ───────────────────────────────────────────────────────────────────

def _require_manager(request):
    if not request.user.is_manager_role:
        messages.error(request, "Managers and above only.")
        return True
    return False


def _parse_int(val, default, minimum=1, maximum=365):
    try:
        return max(minimum, min(maximum, int(val)))
    except (TypeError, ValueError):
        return default


def _joint_filter(qs, joint_id, field="joint_id"):
    if joint_id:
        return qs.filter(**{field: joint_id})
    return qs


def _date_range(days, reference=None):
    end   = (reference or timezone.now()).date()
    start = end - timedelta(days=days - 1)
    return start, end


# ── MAIN DASHBOARD ────────────────────────────────────────────────────────────

@login_required
def analytics_dashboard(request):
    if _require_manager(request):
        return redirect("sales:dashboard")

    today       = timezone.now().date()
    month_start = today.replace(day=1)
    week_start  = today - timedelta(days=today.weekday())
    yesterday   = today - timedelta(days=1)

    completed = Sale.objects.filter(is_held=False)

    # ── KPI cards ─────────────────────────────────────────────────────────────
    def _period_stats(qs):
        items = SaleItem.objects.filter(sale__in=qs, is_free_gift=False)
        revenue = items.aggregate(
            t=Sum(F("quantity") * F("unit_price"), output_field=FloatField())
        )["t"] or 0.0
        discounts = qs.aggregate(d=Sum("discount_amount"))["d"] or Decimal("0")
        net       = revenue - float(discounts)
        return {
            "revenue":   round(revenue, 2),
            "net":       round(net, 2),
            "count":     qs.count(),
            "discount":  float(discounts),
        }

    today_qs     = completed.filter(sale_date__date=today)
    yesterday_qs = completed.filter(sale_date__date=yesterday)
    week_qs      = completed.filter(sale_date__date__gte=week_start)
    month_qs     = completed.filter(sale_date__date__gte=month_start)

    today_stats     = _period_stats(today_qs)
    yesterday_stats = _period_stats(yesterday_qs)
    week_stats      = _period_stats(week_qs)
    month_stats     = _period_stats(month_qs)

    # % change today vs yesterday
    def _pct(a, b):
        if b == 0:
            return None
        return round((a - b) / b * 100, 1)

    today_stats["pct_vs_yesterday"] = _pct(today_stats["net"], yesterday_stats["net"])

    # AOV
    today_stats["aov"]  = round(today_stats["net"]  / today_stats["count"],  2) if today_stats["count"]  else 0
    month_stats["aov"]  = round(month_stats["net"] / month_stats["count"],  2) if month_stats["count"]  else 0

    # Top product today
    top_today = (
        SaleItem.objects
        .filter(sale__sale_date__date=today, sale__is_held=False, is_free_gift=False)
        .values("product__name")
        .annotate(total=Sum(F("quantity") * F("unit_price"), output_field=FloatField()))
        .order_by("-total")
        .first()
    )

    # ── Payment breakdown (month) ─────────────────────────────────────────────
    payment_breakdown = {}
    for method, label in Sale.PAYMENT_CHOICES:
        qs_m  = month_qs.filter(payment_method=method)
        cnt   = qs_m.count()
        items = SaleItem.objects.filter(sale__in=qs_m, is_free_gift=False)
        rev   = items.aggregate(t=Sum(F("quantity") * F("unit_price"), output_field=FloatField()))["t"] or 0
        payment_breakdown[label] = {"count": cnt, "revenue": round(rev, 2)}

    # ── Top 10 products (month) ───────────────────────────────────────────────
    top_products = (
        SaleItem.objects
        .filter(sale__sale_date__date__gte=month_start, sale__is_held=False, is_free_gift=False)
        .values("product__name", "product__joint__display_name")
        .annotate(
            total_qty=Sum("quantity"),
            total_revenue=Sum(F("quantity") * F("unit_price"), output_field=FloatField()),
        )
        .order_by("-total_revenue")[:10]
    )

    # ── Staff performance (month) ─────────────────────────────────────────────
    from users.models import User
    staff_perf = []
    for user in User.objects.filter(is_active=True):
        user_sales = month_qs.filter(sold_by=user)
        cnt = user_sales.count()
        if cnt == 0:
            continue
        items_u = SaleItem.objects.filter(sale__in=user_sales, is_free_gift=False)
        rev = items_u.aggregate(t=Sum(F("quantity") * F("unit_price"), output_field=FloatField()))["t"] or 0
        staff_perf.append({"user": user, "count": cnt, "revenue": round(rev, 2)})
    staff_perf.sort(key=lambda x: x["revenue"], reverse=True)

    # ── Returns (month) ───────────────────────────────────────────────────────
    try:
        from returns.models import Return
        returns_month = Return.objects.filter(
            status=Return.STATUS_COMPLETED, created_at__date__gte=month_start
        )
        return_count = returns_month.count()
        return_value = returns_month.aggregate(t=Sum("total_refund_amount"))["t"] or Decimal("0")
    except Exception:
        return_count = 0
        return_value = Decimal("0")

    # ── Low stock ─────────────────────────────────────────────────────────────
    from django.conf import settings as dj_settings
    threshold = getattr(dj_settings, "LOW_STOCK_THRESHOLD", 3)
    low_stock = (
        Product.objects.select_related("stock", "joint", "category")
        .filter(is_active=True, stock__quantity__lte=threshold)
        .order_by("stock__quantity")[:20]
    )

    return render(request, "analytics/dashboard.html", {
        "today_stats":       today_stats,
        "yesterday_stats":   yesterday_stats,
        "week_stats":        week_stats,
        "month_stats":       month_stats,
        "top_today":         top_today,
        "payment_breakdown": payment_breakdown,
        "top_products":      top_products,
        "staff_perf":        staff_perf,
        "return_count":      return_count,
        "return_value":      return_value,
        "low_stock":         low_stock,
        "month":             today.strftime("%B %Y"),
        "joints":            Joint.objects.all(),
    })


# ── JSON: Revenue trend ───────────────────────────────────────────────────────

@login_required
def analytics_api_revenue(request):
    if not request.user.is_manager_role:
        return JsonResponse({"error": "forbidden"}, status=403)

    days     = _parse_int(request.GET.get("days"), 30, 7, 365)
    joint_id = request.GET.get("joint_id", "")
    start, end = _date_range(days)

    qs = SaleItem.objects.filter(
        sale__sale_date__date__gte=start,
        sale__sale_date__date__lte=end,
        sale__is_held=False,
        is_free_gift=False,
    )
    qs = _joint_filter(qs, joint_id, "sale__joint_id")

    daily = (
        qs.annotate(d=TruncDate("sale__sale_date"))
          .values("d")
          .annotate(
              revenue=Sum(F("quantity") * F("unit_price"), output_field=FloatField()),
              txns=Count("sale", distinct=True),
          )
          .order_by("d")
    )
    date_map = {row["d"]: row for row in daily}

    labels, revenues, txns = [], [], []
    cur = start
    while cur <= end:
        labels.append(cur.strftime("%d %b"))
        row = date_map.get(cur)
        revenues.append(round(row["revenue"], 2) if row else 0)
        txns.append(row["txns"] if row else 0)
        cur += timedelta(days=1)

    return JsonResponse({"labels": labels, "revenues": revenues, "txns": txns})


# ── JSON: Top products ────────────────────────────────────────────────────────

@login_required
def analytics_api_top_products(request):
    if not request.user.is_manager_role:
        return JsonResponse({"error": "forbidden"}, status=403)

    days     = _parse_int(request.GET.get("days"), 30, 7, 365)
    joint_id = request.GET.get("joint_id", "")
    limit    = _parse_int(request.GET.get("limit"), 10, 5, 20)
    start, end = _date_range(days)

    qs = SaleItem.objects.filter(
        sale__sale_date__date__gte=start,
        sale__sale_date__date__lte=end,
        sale__is_held=False,
        is_free_gift=False,
    )
    qs = _joint_filter(qs, joint_id, "sale__joint_id")

    rows = (
        qs.values("product__name")
          .annotate(
              total_qty=Sum("quantity"),
              total_revenue=Sum(F("quantity") * F("unit_price"), output_field=FloatField()),
          )
          .order_by("-total_revenue")[:limit]
    )

    return JsonResponse({
        "labels":     [r["product__name"] or "(deleted)" for r in rows],
        "revenues":   [round(r["total_revenue"], 2) for r in rows],
        "quantities": [r["total_qty"] for r in rows],
    })


# ── JSON: Payment breakdown ───────────────────────────────────────────────────

@login_required
def analytics_api_payment_breakdown(request):
    if not request.user.is_manager_role:
        return JsonResponse({"error": "forbidden"}, status=403)

    days     = _parse_int(request.GET.get("days"), 30, 7, 365)
    joint_id = request.GET.get("joint_id", "")
    start, end = _date_range(days)

    qs = Sale.objects.filter(
        sale_date__date__gte=start,
        sale_date__date__lte=end,
        is_held=False,
    )
    qs = _joint_filter(qs, joint_id)

    rows = (
        qs.values("payment_method")
          .annotate(count=Count("id"))
          .order_by("-count")
    )
    method_labels = dict(Sale.PAYMENT_CHOICES)

    return JsonResponse({
        "labels": [method_labels.get(r["payment_method"], r["payment_method"]) for r in rows],
        "counts": [r["count"] for r in rows],
    })


# ── JSON: Hourly distribution ─────────────────────────────────────────────────

@login_required
def analytics_api_hourly(request):
    if not request.user.is_manager_role:
        return JsonResponse({"error": "forbidden"}, status=403)

    days     = _parse_int(request.GET.get("days"), 30, 7, 365)
    joint_id = request.GET.get("joint_id", "")
    start, end = _date_range(days)

    qs = Sale.objects.filter(
        sale_date__date__gte=start,
        sale_date__date__lte=end,
        is_held=False,
    )
    qs = _joint_filter(qs, joint_id)

    rows = (
        qs.annotate(h=TruncHour("sale_date"))
          .values("h")
          .annotate(count=Count("id"))
          .order_by("h")
    )
    hourly = defaultdict(int)
    for r in rows:
        hourly[r["h"].hour] += r["count"]

    labels  = [f"{h:02d}:00" for h in range(24)]
    counts  = [hourly.get(h, 0) for h in range(24)]

    return JsonResponse({"labels": labels, "counts": counts})


# ── JSON: Staff performance ───────────────────────────────────────────────────

@login_required
def analytics_api_staff(request):
    if not request.user.is_manager_role:
        return JsonResponse({"error": "forbidden"}, status=403)

    days     = _parse_int(request.GET.get("days"), 30, 7, 365)
    joint_id = request.GET.get("joint_id", "")
    start, end = _date_range(days)

    qs = Sale.objects.filter(
        sale_date__date__gte=start,
        sale_date__date__lte=end,
        is_held=False,
    )
    qs = _joint_filter(qs, joint_id)

    rows = (
        qs.values("sold_by__first_name", "sold_by__last_name", "sold_by__username")
          .annotate(sales_count=Count("id"))
          .order_by("-sales_count")[:10]
    )

    labels = []
    for r in rows:
        full = f"{r['sold_by__first_name']} {r['sold_by__last_name']}".strip()
        labels.append(full or r["sold_by__username"] or "Unknown")

    revenue_rows = {}
    for r in rows:
        name = f"{r['sold_by__first_name']} {r['sold_by__last_name']}".strip() or r["sold_by__username"]
        user_sales = qs.filter(
            sold_by__first_name=r["sold_by__first_name"],
            sold_by__last_name=r["sold_by__last_name"],
        )
        items = SaleItem.objects.filter(sale__in=user_sales, is_free_gift=False)
        rev = items.aggregate(t=Sum(F("quantity") * F("unit_price"), output_field=FloatField()))["t"] or 0
        revenue_rows[name] = round(rev, 2)

    revenues = [revenue_rows.get(lbl, 0) for lbl in labels]
    counts   = [r["sales_count"] for r in rows]

    return JsonResponse({"labels": labels, "revenues": revenues, "counts": counts})


# ── JSON: Cohort retention ────────────────────────────────────────────────────

@login_required
def analytics_api_cohort(request):
    """
    Customer retention by first-purchase month.
    Returns cohort matrix: rows = cohort months, cols = months 0..N since first purchase.
    """
    if not request.user.is_manager_role:
        return JsonResponse({"error": "forbidden"}, status=403)

    try:
        from customers.models import Customer
        from django.db.models.functions import TruncMonth as TM

        # Build cohort: for each customer, first purchase month
        customers_with_sales = (
            Sale.objects.filter(is_held=False, customer__isnull=False)
            .values("customer_id")
            .annotate(first_month=TM(Min("sale_date")))
        )

        # Map customer_id -> cohort month
        cohort_map = {r["customer_id"]: r["first_month"] for r in customers_with_sales}

        # Group by cohort_month and subsequent months
        cohort_data = defaultdict(lambda: defaultdict(set))
        sales = (
            Sale.objects.filter(is_held=False, customer__isnull=False)
            .annotate(month=TM("sale_date"))
            .values("customer_id", "month")
        )
        for row in sales:
            cid   = row["customer_id"]
            month = row["month"]
            first = cohort_map.get(cid)
            if not first or not month:
                continue
            # months since first purchase (0-indexed)
            delta = (month.year - first.year) * 12 + (month.month - first.month)
            cohort_data[first.strftime("%b %Y")][delta].add(cid)

        cohorts = sorted(cohort_data.keys())
        max_col = 6  # show up to 6 months retention

        matrix = []
        for cohort in cohorts:
            row_data = cohort_data[cohort]
            cohort_size = len(row_data.get(0, set()))
            row = {"cohort": cohort, "size": cohort_size, "retention": []}
            for col in range(max_col + 1):
                n = len(row_data.get(col, set()))
                pct = round(n / cohort_size * 100) if cohort_size else 0
                row["retention"].append(pct)
            matrix.append(row)

        return JsonResponse({"cohorts": matrix, "max_periods": max_col})

    except Exception as e:
        return JsonResponse({"cohorts": [], "error": str(e)})


# ── JSON: Average basket size trend ──────────────────────────────────────────

@login_required
def analytics_api_basket(request):
    if not request.user.is_manager_role:
        return JsonResponse({"error": "forbidden"}, status=403)

    days     = _parse_int(request.GET.get("days"), 90, 14, 365)
    joint_id = request.GET.get("joint_id", "")
    start, end = _date_range(days)

    qs = Sale.objects.filter(
        sale_date__date__gte=start,
        sale_date__date__lte=end,
        is_held=False,
    )
    qs = _joint_filter(qs, joint_id)

    # Weekly buckets
    weekly = defaultdict(list)
    for sale in qs.prefetch_related("items"):
        week_start_day = sale.sale_date.date() - timedelta(days=sale.sale_date.weekday())
        weekly[week_start_day].append(float(sale.total_amount))

    labels, avgs = [], []
    for week in sorted(weekly):
        vals = weekly[week]
        labels.append(week.strftime("%d %b"))
        avgs.append(round(sum(vals) / len(vals), 2) if vals else 0)

    return JsonResponse({"labels": labels, "avgs": avgs})


# ── JSON: Product velocity (units/day) ───────────────────────────────────────

@login_required
def analytics_api_velocity(request):
    """
    Product sales velocity for reorder prediction.
    Returns products with daily rate and days-of-stock-remaining.
    """
    if not request.user.is_manager_role:
        return JsonResponse({"error": "forbidden"}, status=403)

    days     = _parse_int(request.GET.get("days"), 30, 7, 90)
    joint_id = request.GET.get("joint_id", "")
    limit    = _parse_int(request.GET.get("limit"), 20, 5, 50)
    start, end = _date_range(days)

    qs = SaleItem.objects.filter(
        sale__sale_date__date__gte=start,
        sale__sale_date__date__lte=end,
        sale__is_held=False,
        is_free_gift=False,
    )
    qs = _joint_filter(qs, joint_id, "sale__joint_id")

    rows = (
        qs.values("product__id", "product__name", "product__stock__quantity")
          .annotate(total_sold=Sum("quantity"))
          .order_by("-total_sold")[:limit]
    )

    result = []
    for r in rows:
        daily_rate    = round(r["total_sold"] / days, 2)
        stock         = r["product__stock__quantity"] or 0
        days_remaining = round(stock / daily_rate) if daily_rate > 0 else None
        result.append({
            "product":        r["product__name"],
            "units_sold":     r["total_sold"],
            "daily_rate":     daily_rate,
            "stock":          stock,
            "days_remaining": days_remaining,
            "reorder_flag":   days_remaining is not None and days_remaining < 14,
        })

    return JsonResponse({"products": result, "period_days": days})


# ── JSON: Live KPI refresh (called every 60s by dashboard) ───────────────────

@login_required
def analytics_api_live_kpis(request):
    if not request.user.is_manager_role:
        return JsonResponse({"error": "forbidden"}, status=403)

    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    joint_id  = request.GET.get("joint_id", "")

    def _rev(qs):
        items = SaleItem.objects.filter(sale__in=qs, is_free_gift=False)
        items = _joint_filter(items, joint_id, "sale__joint_id")
        r = items.aggregate(t=Sum(F("quantity") * F("unit_price"), output_field=FloatField()))["t"] or 0
        d = qs.aggregate(d=Sum("discount_amount"))["d"] or 0
        return round(r - float(d), 2)

    today_qs     = Sale.objects.filter(sale_date__date=today, is_held=False)
    yesterday_qs = Sale.objects.filter(sale_date__date=yesterday, is_held=False)
    today_qs     = _joint_filter(today_qs, joint_id)
    yesterday_qs = _joint_filter(yesterday_qs, joint_id)

    today_rev     = _rev(today_qs)
    yesterday_rev = _rev(yesterday_qs)
    pct = None
    if yesterday_rev > 0:
        pct = round((today_rev - yesterday_rev) / yesterday_rev * 100, 1)

    count = today_qs.count()
    aov   = round(today_rev / count, 2) if count else 0

    top = (
        SaleItem.objects.filter(sale__sale_date__date=today, sale__is_held=False, is_free_gift=False)
        .values("product__name")
        .annotate(t=Sum(F("quantity") * F("unit_price"), output_field=FloatField()))
        .order_by("-t")
        .first()
    )

    return JsonResponse({
        "today_revenue":    today_rev,
        "yesterday_revenue": yesterday_rev,
        "pct_change":       pct,
        "txn_count":        count,
        "aov":              aov,
        "top_product":      top["product__name"] if top else "—",
        "refreshed_at":     timezone.now().strftime("%H:%M:%S"),
    })


# ── CSV / Excel export ────────────────────────────────────────────────────────

@login_required
def analytics_export_csv(request):
    if not request.user.is_manager_role:
        messages.error(request, "Managers and above only.")
        return redirect("sales:analytics_dashboard")

    report_type = request.GET.get("report", "sales")
    date_from   = request.GET.get("date_from", str(timezone.now().date().replace(day=1)))
    date_to     = request.GET.get("date_to",   str(timezone.now().date()))
    joint_id    = request.GET.get("joint_id",  "")

    response = HttpResponse(content_type="text/csv")

    if report_type == "sales":
        response["Content-Disposition"] = f'attachment; filename="sales_{date_from}_{date_to}.csv"'
        writer = csv.writer(response)
        writer.writerow([
            "Receipt #", "Date", "Joint", "Cashier", "Customer",
            "Payment Method", "Subtotal", "Discount", "Total",
        ])

        qs = Sale.objects.filter(
            is_held=False,
            sale_date__date__gte=date_from,
            sale_date__date__lte=date_to,
        ).select_related("joint", "sold_by", "customer").order_by("-sale_date")
        qs = _joint_filter(qs, joint_id)

        for sale in qs:
            cashier  = sale.sold_by.get_full_name() if sale.sold_by else ""
            customer = sale.customer.name if sale.customer else sale.customer_name
            writer.writerow([
                sale.receipt_number,
                sale.sale_date.strftime("%Y-%m-%d %H:%M"),
                sale.joint.display_name,
                cashier,
                customer,
                sale.get_payment_method_display(),
                sale.subtotal,
                sale.discount_amount,
                sale.total_amount,
            ])

    elif report_type == "products":
        response["Content-Disposition"] = f'attachment; filename="product_performance_{date_from}_{date_to}.csv"'
        writer = csv.writer(response)
        writer.writerow(["Product", "Joint", "Qty Sold", "Revenue"])

        qs = SaleItem.objects.filter(
            sale__is_held=False,
            sale__sale_date__date__gte=date_from,
            sale__sale_date__date__lte=date_to,
            is_free_gift=False,
        )
        qs = _joint_filter(qs, joint_id, "sale__joint_id")

        rows = (
            qs.values("product__name", "product__joint__display_name")
              .annotate(
                  total_qty=Sum("quantity"),
                  total_revenue=Sum(F("quantity") * F("unit_price"), output_field=FloatField()),
              )
              .order_by("-total_revenue")
        )
        for r in rows:
            writer.writerow([
                r["product__name"] or "(deleted)",
                r["product__joint__display_name"] or "",
                r["total_qty"],
                f"{r['total_revenue']:.2f}",
            ])

    elif report_type == "inventory":
        response["Content-Disposition"] = "attachment; filename=\"inventory_snapshot.csv\""
        writer = csv.writer(response)
        writer.writerow([
            "Product", "SKU", "Joint", "Category",
            "Stock Qty", "Min Stock", "Selling Price", "Stock Value",
        ])

        stocks = (
            Stock.objects
            .select_related("product__joint", "product__category")
            .filter(product__is_active=True)
            .order_by("product__joint__name", "product__name")
        )
        stocks = _joint_filter(stocks, joint_id, "product__joint_id")

        for stock in stocks:
            p = stock.product
            writer.writerow([
                p.name,
                p.code or p.barcode or "",
                p.joint.display_name,
                p.category.name if p.category else "",
                stock.quantity,
                stock.min_quantity,
                p.price,
                f"{stock.quantity * p.price:.2f}",
            ])

    elif report_type == "staff":
        response["Content-Disposition"] = f'attachment; filename="staff_performance_{date_from}_{date_to}.csv"'
        writer = csv.writer(response)
        writer.writerow(["Staff", "Sales Count", "Total Revenue", "AOV"])

        qs = Sale.objects.filter(
            is_held=False,
            sale_date__date__gte=date_from,
            sale_date__date__lte=date_to,
        ).select_related("sold_by")
        qs = _joint_filter(qs, joint_id)

        from users.models import User
        for user in User.objects.filter(is_active=True):
            user_sales = qs.filter(sold_by=user)
            cnt = user_sales.count()
            if cnt == 0:
                continue
            items = SaleItem.objects.filter(sale__in=user_sales, is_free_gift=False)
            rev = items.aggregate(t=Sum(F("quantity") * F("unit_price"), output_field=FloatField()))["t"] or 0
            writer.writerow([
                user.get_full_name() or user.username,
                cnt,
                f"{rev:.2f}",
                f"{rev / cnt:.2f}" if cnt else "0.00",
            ])

    return response


# Needed for cohort (imported inside function, need to add here for clarity)
try:
    from django.db.models import Min
except ImportError:
    pass