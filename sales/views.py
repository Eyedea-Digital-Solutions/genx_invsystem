from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.conf import settings

from .models import Sale, SaleItem, SaleAuditLog
from .forms import SaleForm, ManualSaleForm, SaleFilterForm
from inventory.models import Joint, Product


@login_required
def dashboard(request):
    """
    Main dashboard showing:
    - Today's sales summary
    - Low stock alerts
    - Recent sales
    - Quick stats per joint
    """
    today = timezone.now().date()
    
    # Today's sales
    today_sales = Sale.objects.filter(sale_date__date=today)
    today_total = sum(sale.total_amount for sale in today_sales)
    today_count = today_sales.count()

    # This month's sales
    month_start = today.replace(day=1)
    month_sales = Sale.objects.filter(sale_date__date__gte=month_start)
    month_total = sum(sale.total_amount for sale in month_sales)

    # Low stock items
    low_stock = Product.objects.select_related('stock', 'joint').filter(
        is_active=True,
        stock__quantity__lte=settings.LOW_STOCK_THRESHOLD
    )

    # Recent sales (last 10)
    recent_sales = Sale.objects.select_related('joint', 'sold_by').prefetch_related('items').order_by('-created_at')[:10]

    # Per-joint stats today
    joint_stats = []
    for joint in Joint.objects.all():
        joint_today_sales = today_sales.filter(joint=joint)
        joint_today_total = sum(sale.total_amount for sale in joint_today_sales)
        joint_stats.append({
            'joint': joint,
            'count': joint_today_sales.count(),
            'total': joint_today_total,
        })

    context = {
        'today_total': today_total,
        'today_count': today_count,
        'month_total': month_total,
        'month_count': month_sales.count(),
        'low_stock': low_stock,
        'low_stock_count': low_stock.count(),
        'recent_sales': recent_sales,
        'joint_stats': joint_stats,
    }
    return render(request, 'dashboard.html', context)


@login_required
def make_sale(request):
    """
    The main sale creation page.
    Staff selects a joint, adds products, and the system:
    1. Creates a Sale record
    2. Deducts stock automatically
    3. Creates an audit log entry
    4. Redirects to receipt page
    """
    joints = Joint.objects.all()

    if request.method == 'POST':
        sale_form = SaleForm(request.POST)

        if sale_form.is_valid():
            with transaction.atomic():
                # Save the sale (don't commit yet — need to add items)
                sale = sale_form.save(commit=False)
                sale.sold_by = request.user
                sale.sale_type = 'system'
                sale.save()

                # Process sale items from POST data
                items_data = []
                i = 0
                errors = []
                while f'product_{i}' in request.POST:
                    product_id = request.POST.get(f'product_{i}')
                    quantity = request.POST.get(f'quantity_{i}')
                    unit_price = request.POST.get(f'unit_price_{i}')

                    if product_id and quantity and unit_price:
                        try:
                            product = Product.objects.select_related('stock').get(pk=product_id)
                            qty = int(quantity)
                            price = float(unit_price)

                            # Check stock availability
                            if product.current_stock < qty:
                                errors.append(
                                    f"Not enough stock for '{product.name}'. "
                                    f"Available: {product.current_stock}, Requested: {qty}"
                                )
                            else:
                                items_data.append({
                                    'product': product,
                                    'quantity': qty,
                                    'unit_price': price,
                                })
                        except Product.DoesNotExist:
                            errors.append(f"Product not found.")
                    i += 1

                if errors:
                    # Roll back and show errors
                    sale.delete()
                    for err in errors:
                        messages.error(request, err)
                    return render(request, 'make_sale.html', {
                        'sale_form': sale_form,
                        'joints': joints,
                    })

                if not items_data:
                    sale.delete()
                    messages.error(request, "Please add at least one product to the sale.")
                    return render(request, 'make_sale.html', {
                        'sale_form': sale_form,
                        'joints': joints,
                    })

                # Create SaleItems and deduct stock
                sale_items_snapshot = []
                for item_data in items_data:
                    SaleItem.objects.create(
                        sale=sale,
                        product=item_data['product'],
                        quantity=item_data['quantity'],
                        unit_price=item_data['unit_price'],
                    )
                    # AUTO-DEDUCT STOCK — This is the key feature!
                    item_data['product'].stock.deduct(item_data['quantity'])

                    sale_items_snapshot.append({
                        'product_id': item_data['product'].pk,
                        'product_name': item_data['product'].name,
                        'quantity': item_data['quantity'],
                        'unit_price': str(item_data['unit_price']),
                    })

                # Create immutable audit log
                SaleAuditLog.objects.create(
                    sale=sale,
                    action='created',
                    performed_by=request.user,
                    details={
                        'items': sale_items_snapshot,
                        'total': str(sale.total_amount),
                        'payment_method': sale.payment_method,
                        'joint': sale.joint.name,
                    }
                )

                # If EcoCash or mixed payment, create the EcoCash transaction record
                if sale.payment_method in ['ecocash', 'mixed']:
                    from ecocash.services import create_ecocash_payment
                    create_ecocash_payment(sale)

                messages.success(request, f"Sale recorded! Receipt: {sale.receipt_number}")
                return redirect('sales:sale_receipt', pk=sale.pk)

    else:
        sale_form = SaleForm()

    return render(request, 'make_sale.html', {
        'sale_form': sale_form,
        'joints': joints,
    })


@login_required
def manual_sale(request):
    """
    Record a sale that was made manually (with a physical receipt).
    Staff uploads a photo of the receipt. Stock can be manually specified.
    """
    if request.method == 'POST':
        form = ManualSaleForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                sale = form.save(commit=False)
                sale.sold_by = request.user
                sale.sale_type = 'manual'
                sale.save()

                # For manual sales, still try to record items if provided
                i = 0
                while f'product_{i}' in request.POST:
                    product_id = request.POST.get(f'product_{i}')
                    quantity = request.POST.get(f'quantity_{i}')
                    unit_price = request.POST.get(f'unit_price_{i}')

                    if product_id and quantity and unit_price:
                        try:
                            product = Product.objects.get(pk=product_id)
                            qty = int(quantity)
                            SaleItem.objects.create(
                                sale=sale,
                                product=product,
                                quantity=qty,
                                unit_price=float(unit_price),
                            )
                            # Deduct stock even for manual sales
                            product.stock.deduct(qty)
                        except (Product.DoesNotExist, ValueError):
                            pass
                    i += 1

                # Audit log
                SaleAuditLog.objects.create(
                    sale=sale,
                    action='manual_sale_recorded',
                    performed_by=request.user,
                    details={
                        'receipt_image': sale.manual_receipt_image.name if sale.manual_receipt_image else None,
                        'notes': sale.notes,
                        'joint': sale.joint.name,
                    }
                )

                # If EcoCash payment, create the EcoCash transaction record
                if sale.payment_method in ['ecocash', 'mixed']:
                    from ecocash.services import create_ecocash_payment
                    create_ecocash_payment(sale)

                messages.success(request, f"Manual sale recorded! Receipt: {sale.receipt_number}")
                return redirect('sales:sale_receipt', pk=sale.pk)
    else:
        form = ManualSaleForm()

    joints = Joint.objects.all()
    return render(request, 'manual_sale.html', {'form': form, 'joints': joints})


@login_required
def sale_receipt(request, pk):
    """
    Shows the receipt for a completed sale.
    Can be printed by the user.
    """
    sale = get_object_or_404(
        Sale.objects.select_related('joint', 'sold_by').prefetch_related('items__product'),
        pk=pk
    )
    return render(request, 'receipt.html', {'sale': sale})


@login_required
def sale_list(request):
    """
    Shows all sales with filtering options.
    Admin/Manager can see all; Staff only sees their own sales.
    """
    sales = Sale.objects.select_related('joint', 'sold_by').prefetch_related('items').order_by('-sale_date')

    # Staff only see their own sales
    if not request.user.is_manager_role:
        sales = sales.filter(sold_by=request.user)

    form = SaleFilterForm(request.GET or None)
    if form.is_valid():
        if form.cleaned_data.get('joint'):
            sales = sales.filter(joint=form.cleaned_data['joint'])
        if form.cleaned_data.get('payment_method'):
            sales = sales.filter(payment_method=form.cleaned_data['payment_method'])
        if form.cleaned_data.get('date_from'):
            sales = sales.filter(sale_date__date__gte=form.cleaned_data['date_from'])
        if form.cleaned_data.get('date_to'):
            sales = sales.filter(sale_date__date__lte=form.cleaned_data['date_to'])
        if form.cleaned_data.get('sold_by'):
            sales = sales.filter(
                Q(sold_by__first_name__icontains=form.cleaned_data['sold_by']) |
                Q(sold_by__last_name__icontains=form.cleaned_data['sold_by']) |
                Q(sold_by__username__icontains=form.cleaned_data['sold_by'])
            )

    # Evaluate the queryset once to avoid hitting DB twice (once for total, once for template)
    sales_list = list(sales)
    context = {
        'sales': sales_list,
        'filter_form': form,
        'total': sum(sale.total_amount for sale in sales_list),
    }
    return render(request, 'sale_list.html', context)


@login_required
def sale_detail(request, pk):
    """View details of a single sale."""
    sale = get_object_or_404(
        Sale.objects.select_related('joint', 'sold_by').prefetch_related('items__product'),
        pk=pk
    )
    # Staff can only view their own sales
    if not request.user.is_manager_role and sale.sold_by != request.user:
        messages.error(request, "You can only view your own sales.")
        return redirect('sales:sale_list')

    try:
        audit_log = sale.audit_log
    except SaleAuditLog.DoesNotExist:
        audit_log = None

    return render(request, 'sale_detail.html', {'sale': sale, 'audit_log': audit_log})


@login_required
def reports(request):
    """
    Generates sales and stock reports.
    Only accessible to managers and admins.
    """
    if not request.user.is_manager_role:
        messages.error(request, "You don't have permission to view reports.")
        return redirect('sales:dashboard')

    today = timezone.now().date()
    month_start = today.replace(day=1)

    # Monthly sales by joint
    joints = Joint.objects.all()
    joint_reports = []
    for joint in joints:
        month_joint_sales = Sale.objects.filter(joint=joint, sale_date__date__gte=month_start)
        joint_reports.append({
            'joint': joint,
            'count': month_joint_sales.count(),
            'total': sum(sale.total_amount for sale in month_joint_sales),
        })

    # Sales by payment method this month
    payment_breakdown = {}
    for method, label in Sale.PAYMENT_CHOICES:
        count = Sale.objects.filter(
            sale_date__date__gte=month_start,
            payment_method=method
        ).count()
        payment_breakdown[label] = count

    # Top selling products this month
    from django.db.models import Sum as DjSum
    top_products = SaleItem.objects.filter(
        sale__sale_date__date__gte=month_start
    ).values('product__name', 'product__joint__display_name').annotate(
        total_qty=DjSum('quantity')
    ).order_by('-total_qty')[:10]

    # Staff performance this month
    from users.models import User
    staff_performance = []
    for user in User.objects.filter(is_active=True):
        user_sales = Sale.objects.filter(sold_by=user, sale_date__date__gte=month_start)
        if user_sales.exists():
            staff_performance.append({
                'user': user,
                'count': user_sales.count(),
                'total': sum(sale.total_amount for sale in user_sales),
            })
    staff_performance.sort(key=lambda x: x['total'], reverse=True)

    context = {
        'joint_reports': joint_reports,
        'payment_breakdown': payment_breakdown,
        'top_products': top_products,
        'staff_performance': staff_performance,
        'month': today.strftime('%B %Y'),
        'month_count': Sale.objects.filter(sale_date__date__gte=month_start).count(),
    }
    return render(request, 'reports.html', context)
