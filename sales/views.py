import json
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import Sale, SaleItem, SaleAuditLog
from .forms import SaleForm, ManualSaleForm, SaleFilterForm
from inventory.models import Joint, Product, ProductFreeAccessory


@login_required
def dashboard(request):
    today = timezone.now().date()

    today_sales = Sale.objects.filter(
        sale_date__date=today, is_held=False
    ).prefetch_related('items')
    today_total = sum(sale.total_amount for sale in today_sales)
    today_count = today_sales.count()

    month_start = today.replace(day=1)
    month_sales = Sale.objects.filter(
        sale_date__date__gte=month_start, is_held=False
    ).prefetch_related('items')
    month_total = sum(sale.total_amount for sale in month_sales)

    low_stock = Product.objects.select_related('stock', 'joint').filter(
        is_active=True,
        stock__quantity__lte=settings.LOW_STOCK_THRESHOLD
    )

    expiring_soon = Product.objects.select_related('stock', 'joint').filter(
        is_active=True,
        stock__expiry_date__isnull=False,
        stock__expiry_date__lte=timezone.now().date() + timezone.timedelta(days=30)
    )

    recent_sales = Sale.objects.select_related('joint', 'sold_by').prefetch_related('items').filter(
        is_held=False
    ).order_by('-created_at')[:10]

    joint_stats = []
    for joint in Joint.objects.all():
        joint_today_sales = [s for s in today_sales if s.joint_id == joint.pk]
        joint_today_total = sum(sale.total_amount for sale in joint_today_sales)
        joint_stats.append({
            'joint': joint,
            'count': len(joint_today_sales),
            'total': joint_today_total,
        })

    context = {
        'today_total': today_total,
        'today_count': today_count,
        'month_total': month_total,
        'month_count': month_sales.count(),
        'low_stock': low_stock,
        'low_stock_count': low_stock.count(),
        'expiring_soon': expiring_soon,
        'recent_sales': recent_sales,
        'joint_stats': joint_stats,
    }
    return render(request, 'dashboard.html', context)


@login_required
def pos(request):
    joints = Joint.objects.all()
    held_sales = Sale.objects.filter(
        is_held=True, sold_by=request.user
    ).prefetch_related('items__product').order_by('-held_at')

    default_joint = None
    if request.user.primary_joint:
        default_joint = request.user.primary_joint

    return render(request, 'pos/pos.html', {
        'joints': joints,
        'held_sales': held_sales,
        'default_joint': default_joint,
    })


@login_required
def pos_scan(request):
    barcode = request.GET.get('barcode', '').strip()
    joint_id = request.GET.get('joint_id', '').strip()

    if not barcode or not joint_id:
        return JsonResponse({'found': False, 'message': 'Barcode and joint required'})

    product = Product.objects.select_related('stock', 'category', 'brand').filter(
        Q(barcode=barcode) | Q(code=barcode),
        joint_id=joint_id,
        is_active=True
    ).first()

    if not product:
        return JsonResponse({'found': False, 'message': f'No product for barcode: {barcode}'})

    return JsonResponse({
        'found': True,
        'product': _product_to_dict(product),
    })


@login_required
def pos_search(request):
    q = request.GET.get('q', '').strip()
    joint_id = request.GET.get('joint_id', '').strip()
    filter_type = request.GET.get('filter', 'all')
    category_id = request.GET.get('category_id', '').strip()

    if not joint_id:
        return JsonResponse({'products': []})

    products = Product.objects.select_related(
        'stock', 'category', 'brand'
    ).filter(joint_id=joint_id, is_active=True)

    if q:
        products = products.filter(
            Q(name__icontains=q) |
            Q(code__icontains=q) |
            Q(barcode__icontains=q) |
            Q(brand__name__icontains=q) |
            Q(category__name__icontains=q)
        )

    if category_id:
        products = products.filter(category_id=category_id)

    if filter_type == 'clearance':
        products = products.filter(is_clearance=True)
    elif filter_type == 'sale':
        products = products.filter(sale_price__isnull=False)
    elif filter_type == 'low_stock':
        products = products.filter(stock__quantity__lte=settings.LOW_STOCK_THRESHOLD)
    elif filter_type == 'in_stock':
        products = products.filter(stock__quantity__gt=0)

    data = [_product_to_dict(p) for p in products[:60]]
    return JsonResponse({'products': data})


@login_required
def pos_categories(request):
    joint_id = request.GET.get('joint_id', '').strip()
    if not joint_id:
        return JsonResponse({'categories': []})
    from inventory.models import Category
    cats = Category.objects.filter(joint_id=joint_id).values('id', 'name', 'icon', 'color')
    return JsonResponse({'categories': list(cats)})

@login_required
@require_POST
def pos_update_cart(request):
    body     = json.loads(request.body)
    joint_id = body.get('joint_id')
    raw_items = body.get('items', [])

    if not raw_items:
        return JsonResponse({
            'items': [],
            'subtotal': '0.00',
            'cart_discount': '0.00',
            'cart_discount_label': '',
            'total': '0.00',
            'free_accessory_warnings': [],
        })

    pids     = [i['product_id'] for i in raw_items]
    products = {p.pk: p for p in Product.objects.filter(pk__in=pids)}

    cart_items = []
    for item in raw_items:
        pid = item['product_id']
        p   = products.get(pid)
        if p:
            cart_items.append({
                'product_id':  pid,
                'product_obj': p,
                'qty':         int(item['qty']),
                'unit_price':  Decimal(str(item['unit_price'])),
                'is_free_gift': False,
                'promo_label': '',
            })

    from promotions.engine import apply_promotions
    result = apply_promotions(cart_items, joint_id=joint_id)

    trigger_pids = [
        i['product_id']
        for i in result['items']
        if not i.get('is_free_gift')
    ]

    # Load all active accessory rules for these triggers in one query.
    accessory_rules = (
        ProductFreeAccessory.objects
        .select_related('accessory_product__stock')
        .filter(trigger_product_id__in=trigger_pids, is_active=True)
    )

    trigger_qty_map = {i['product_id']: i['qty'] for i in result['items'] if not i.get('is_free_gift')}
    accessory_map   = {}   # accessory_product_id → dict
    for rule in accessory_rules:
        aid = rule.accessory_product_id
        trigger_qty = trigger_qty_map.get(rule.trigger_product_id, 1)
        needed_qty  = rule.quantity * trigger_qty
        if aid in accessory_map:
            accessory_map[aid]['qty'] += needed_qty
        else:
            accessory_map[aid] = {
                'product':    rule.accessory_product,
                'qty':        needed_qty,
                'label':      rule.get_label(),
                'rule_id':    rule.pk,
            }

    # Build warning list for out-of-stock accessories.
    free_accessory_warnings = []
    for aid, acc in accessory_map.items():
        available = acc['product'].current_stock
        if available == 0:
            free_accessory_warnings.append(
                f"⚠ Free accessory '{acc['product'].name}' is out of stock — "
                f"it will NOT be included in this sale."
            )
        elif available < acc['qty']:
            free_accessory_warnings.append(
                f"⚠ Only {available} unit(s) of free accessory "
                f"'{acc['product'].name}' in stock (needed {acc['qty']}) — "
                f"sale will proceed with {available} unit(s)."
            )

    # Add free accessories to the items list (skip fully OOS ones).
    for aid, acc in accessory_map.items():
        available = acc['product'].current_stock
        actual_qty = min(acc['qty'], available)
        if actual_qty <= 0:
            continue
        result['items'].append({
            'product_id':   aid,
            'product_obj':  acc['product'],
            'qty':          actual_qty,
            'unit_price':   Decimal('0'),
            'is_free_gift': True,
            'promo_label':  acc['label'],
        })

    # ── Totals ───────────────────────────────────────────────────────────────
    subtotal = sum(
        i['unit_price'] * i['qty']
        for i in result['items']
        if not i.get('is_free_gift')
    )
    total = max(Decimal('0'), subtotal - result['cart_discount'])

    return JsonResponse({
        'items': [{
            'product_id':   i['product_id'],
            'name':         i['product_obj'].name,
            'qty':          i['qty'],
            'unit_price':   str(i['unit_price']),
            'line_total':   '0.00' if i.get('is_free_gift') else str(
                (i['unit_price'] * i['qty']).quantize(Decimal('0.01'))
            ),
            'is_free_gift': i.get('is_free_gift', False),
            'promo_label':  i.get('promo_label', ''),
        } for i in result['items']],
        'subtotal':               str(subtotal.quantize(Decimal('0.01'))),
        'cart_discount':          str(result['cart_discount'].quantize(Decimal('0.01'))),
        'cart_discount_label':    result['cart_discount_label'],
        'total':                  str(total.quantize(Decimal('0.01'))),
        'free_accessory_warnings': free_accessory_warnings,   # ← NEW field
    })


@login_required
@require_POST
def pos_complete(request):
    body                = json.loads(request.body)
    joint_id            = body.get('joint_id')
    items_data          = body.get('items', [])
    payment_method      = body.get('payment_method', 'cash')
    customer_name       = body.get('customer_name', '')
    customer_phone      = body.get('customer_phone', '')
    cart_discount       = Decimal(str(body.get('cart_discount', '0')))
    cart_discount_label = body.get('cart_discount_label', '')

    if not joint_id or not items_data:
        return JsonResponse({'success': False, 'error': 'Joint and items are required.'})

    # ── Stock validation for PAID items only ─────────────────────────────────
    pids     = [i['product_id'] for i in items_data if not i.get('is_free_gift')]
    products = {
        p.pk: p
        for p in Product.objects.select_related('stock').filter(pk__in=pids)
    }

    for item in items_data:
        if item.get('is_free_gift'):
            continue
        p = products.get(item['product_id'])
        if not p:
            return JsonResponse({'success': False, 'error': f"Product {item['product_id']} not found."})
        if p.current_stock < item['qty']:
            return JsonResponse({
                'success': False,
                'error': f"Insufficient stock for '{p.name}'. Available: {p.current_stock}."
            })

    # ── Free accessory stock check (warn-only, clamp quantity) ───────────────
    free_items   = [i for i in items_data if i.get('is_free_gift')]
    free_pids    = [i['product_id'] for i in free_items]
    free_products = {
        p.pk: p
        for p in Product.objects.select_related('stock').filter(pk__in=free_pids)
    }

    # Clamp free quantities to available stock; collect warnings.
    sale_warnings = []
    clamped_free  = []
    for item in free_items:
        p         = free_products.get(item['product_id'])
        if not p:
            continue
        available = p.current_stock
        needed    = int(item['qty'])
        actual    = min(needed, available)
        if available == 0:
            sale_warnings.append(
                f"Free accessory '{p.name}' was out of stock and not included."
            )
            continue   # skip entirely
        if actual < needed:
            sale_warnings.append(
                f"Only {actual} of {needed} free '{p.name}' included (limited stock)."
            )
        clamped_free.append({**item, 'qty': actual, '_product': p})

    with transaction.atomic():
        sale = Sale.objects.create(
            joint_id        = joint_id,
            sold_by         = request.user,
            sale_type       = 'pos',
            payment_method  = payment_method,
            customer_name   = customer_name,
            customer_phone  = customer_phone,
            discount_amount = cart_discount,
            discount_type   = 'fixed' if cart_discount else '',
            discount_label  = cart_discount_label,
        )

        snapshot = []

        # Paid items
        for item in items_data:
            if item.get('is_free_gift'):
                continue
            p          = products[item['product_id']]
            qty        = int(item['qty'])
            unit_price = Decimal(str(item['unit_price']))

            SaleItem.objects.create(
                sale            = sale,
                product         = p,
                quantity        = qty,
                unit_price      = unit_price,
                is_free_gift    = False,
                promotion_label = item.get('promo_label', ''),
            )
            p.stock.deduct(qty)
            snapshot.append({
                'product_id':   p.pk,
                'product_name': p.name,
                'quantity':     qty,
                'unit_price':   str(unit_price),
                'is_free_gift': False,
            })

        # Free accessory items (clamped to available stock)
        for item in clamped_free:
            p   = item['_product']
            qty = item['qty']

            SaleItem.objects.create(
                sale            = sale,
                product         = p,
                quantity        = qty,
                unit_price      = Decimal('0'),
                is_free_gift    = True,
                promotion_label = item.get('promo_label', ''),
            )
            p.stock.deduct(qty)
            snapshot.append({
                'product_id':   p.pk,
                'product_name': p.name,
                'quantity':     qty,
                'unit_price':   '0.00',
                'is_free_gift': True,
            })

        SaleAuditLog.objects.create(
            sale         = sale,
            action       = 'created',
            performed_by = request.user,
            details={
                'source':            'pos',
                'total':             str(sale.total_amount),
                'payment_method':    payment_method,
                'items':             snapshot,
                'accessory_warnings': sale_warnings,
            }
        )

        if payment_method in ('ecocash', 'mixed'):
            from ecocash.services import create_ecocash_payment
            create_ecocash_payment(sale)

    return JsonResponse({
        'success':                 True,
        'receipt_url':             f'/sales/{sale.pk}/receipt/thermal/',
        'receipt_number':          sale.receipt_number,
        'sale_id':                 sale.pk,
        'free_accessory_warnings': sale_warnings,   # surfaced to POS UI
    })


@login_required
@require_POST
def pos_hold(request):
    body = json.loads(request.body)
    joint_id = body.get('joint_id')
    items_data = body.get('items', [])
    customer_name = body.get('customer_name', '')

    if not joint_id or not items_data:
        return JsonResponse({'success': False, 'error': 'Nothing to hold.'})

    pids = [i['product_id'] for i in items_data]
    products = {p.pk: p for p in Product.objects.filter(pk__in=pids)}

    with transaction.atomic():
        sale = Sale.objects.create(
            joint_id=joint_id,
            sold_by=request.user,
            sale_type='pos',
            is_held=True,
            held_at=timezone.now(),
            customer_name=customer_name,
        )
        for item in items_data:
            p = products.get(item['product_id'])
            if p:
                SaleItem.objects.create(
                    sale=sale,
                    product=p,
                    quantity=int(item['qty']),
                    unit_price=Decimal(str(item['unit_price'])),
                    is_free_gift=item.get('is_free_gift', False),
                    promotion_label=item.get('promo_label', ''),
                )

    return JsonResponse({'success': True, 'held_id': sale.pk})


@login_required
def pos_recall(request, pk):
    sale = get_object_or_404(
        Sale.objects.prefetch_related('items__product'),
        pk=pk, is_held=True, sold_by=request.user
    )
    items = [{
        'product_id': item.product_id,
        'name': item.product.name,
        'qty': item.quantity,
        'unit_price': str(item.unit_price),
        'is_free_gift': item.is_free_gift,
        'promo_label': item.promotion_label,
        'stock': item.product.current_stock,
        'image_url': item.product.image.url if item.product.image else '',
        'promotion_label_badge': item.product.promotion_label or '',
    } for item in sale.items.all()]

    sale.delete()

    return JsonResponse({'success': True, 'items': items, 'customer_name': sale.customer_name})


@login_required
def make_sale(request):
    joints = Joint.objects.all()

    if request.method == 'POST':
        sale_form = SaleForm(request.POST)

        if sale_form.is_valid():
            items_data = []
            errors = []
            try:
                item_count = int(request.POST.get('item_count', 0))
            except (ValueError, TypeError):
                item_count = 0

            if item_count == 0:
                i = 0
                while f'product_{i}' in request.POST:
                    i += 1
                item_count = i

            for i in range(item_count):
                product_id = request.POST.get(f'product_{i}', '').strip()
                quantity_str = request.POST.get(f'quantity_{i}', '').strip()
                unit_price_str = request.POST.get(f'unit_price_{i}', '').strip()

                if product_id and quantity_str and unit_price_str:
                    try:
                        product = Product.objects.select_related('stock').get(pk=product_id)
                        qty = int(quantity_str)
                        price = float(unit_price_str)
                        if qty < 1:
                            errors.append(f"Quantity for '{product.name}' must be at least 1.")
                        elif product.current_stock < qty:
                            errors.append(
                                f"Not enough stock for '{product.name}'. "
                                f"Available: {product.current_stock}, Requested: {qty}"
                            )
                        else:
                            items_data.append({'product': product, 'quantity': qty, 'unit_price': price})
                    except Product.DoesNotExist:
                        errors.append(f"Product ID {product_id} not found.")
                    except (ValueError, TypeError):
                        errors.append("Invalid quantity or price value.")

            if errors:
                for err in errors:
                    messages.error(request, err)
                return render(request, 'make_sale.html', {'sale_form': sale_form, 'joints': joints})

            if not items_data:
                messages.error(request, "Please add at least one product to the sale.")
                return render(request, 'make_sale.html', {'sale_form': sale_form, 'joints': joints})

            with transaction.atomic():
                sale = sale_form.save(commit=False)
                sale.sold_by = request.user
                sale.sale_type = 'system'
                sale.save()

                snapshot = []
                for item_data in items_data:
                    SaleItem.objects.create(
                        sale=sale,
                        product=item_data['product'],
                        quantity=item_data['quantity'],
                        unit_price=item_data['unit_price'],
                    )
                    item_data['product'].stock.deduct(item_data['quantity'])
                    snapshot.append({
                        'product_id': item_data['product'].pk,
                        'product_name': item_data['product'].name,
                        'quantity': item_data['quantity'],
                        'unit_price': str(item_data['unit_price']),
                    })

                SaleAuditLog.objects.create(
                    sale=sale,
                    action='created',
                    performed_by=request.user,
                    details={
                        'items': snapshot,
                        'total': str(sale.total_amount),
                        'payment_method': sale.payment_method,
                        'joint': sale.joint.name,
                    }
                )

                if sale.payment_method in ['ecocash', 'mixed']:
                    from ecocash.services import create_ecocash_payment
                    create_ecocash_payment(sale)

            messages.success(request, f"Sale recorded! Receipt: {sale.receipt_number}")
            return redirect('sales:sale_receipt_thermal', pk=sale.pk)
    else:
        sale_form = SaleForm()

    return render(request, 'make_sale.html', {'sale_form': sale_form, 'joints': joints})


@login_required
def manual_sale(request):
    if request.method == 'POST':
        form = ManualSaleForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                sale = form.save(commit=False)
                sale.sold_by = request.user
                sale.sale_type = 'manual'
                sale.save()

                i = 0
                while f'product_{i}' in request.POST:
                    product_id = request.POST.get(f'product_{i}')
                    quantity = request.POST.get(f'quantity_{i}')
                    unit_price = request.POST.get(f'unit_price_{i}')
                    if product_id and quantity and unit_price:
                        try:
                            product = Product.objects.select_related('stock').get(pk=product_id)
                            qty = int(quantity)
                            price = float(unit_price)
                            SaleItem.objects.create(
                                sale=sale, product=product, quantity=qty, unit_price=price
                            )
                            product.stock.deduct(qty)
                        except Product.DoesNotExist:
                            messages.warning(request, f"Product ID {product_id} not found.")
                        except ValueError:
                            messages.warning(request, "Invalid quantity or price.")
                    i += 1

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

                if sale.payment_method in ['ecocash', 'mixed']:
                    from ecocash.services import create_ecocash_payment
                    create_ecocash_payment(sale)

            messages.success(request, f"Manual sale recorded! Receipt: {sale.receipt_number}")
            return redirect('sales:sale_receipt_thermal', pk=sale.pk)
    else:
        form = ManualSaleForm()

    joints = Joint.objects.all()
    return render(request, 'manual_sale.html', {'form': form, 'joints': joints})


@login_required
def sale_receipt(request, pk):
    sale = get_object_or_404(
        Sale.objects.select_related('joint', 'sold_by').prefetch_related('items__product'),
        pk=pk
    )
    return render(request, 'receipt.html', {'sale': sale})


@login_required
def sale_receipt_thermal(request, pk):
    sale = get_object_or_404(
        Sale.objects.select_related('joint', 'sold_by').prefetch_related('items__product'),
        pk=pk
    )
    store_info = getattr(settings, 'STORE_INFO', {}).get(sale.joint.name, {})
    return render(request, 'receipt_thermal.html', {'sale': sale, 'store_info': store_info})


@login_required
def sale_list(request):
    sales = Sale.objects.select_related('joint', 'sold_by').prefetch_related('items').filter(
        is_held=False
    ).order_by('-sale_date')

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

    sales_list = list(sales)
    return render(request, 'sale_list.html', {
        'sales': sales_list,
        'filter_form': form,
        'total': sum(sale.total_amount for sale in sales_list),
    })


@login_required
def sale_detail(request, pk):
    sale = get_object_or_404(
        Sale.objects.select_related('joint', 'sold_by').prefetch_related('items__product'),
        pk=pk
    )
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
    if not request.user.is_manager_role:
        messages.error(request, "You don't have permission to view reports.")
        return redirect('sales:dashboard')

    today = timezone.now().date()
    month_start = today.replace(day=1)

    joints = Joint.objects.all()
    joint_reports = []
    for joint in joints:
        month_joint_sales = Sale.objects.filter(
            joint=joint, sale_date__date__gte=month_start, is_held=False
        ).prefetch_related('items')
        joint_reports.append({
            'joint': joint,
            'count': month_joint_sales.count(),
            'total': sum(sale.total_amount for sale in month_joint_sales),
        })

    payment_breakdown = {}
    for method, label in Sale.PAYMENT_CHOICES:
        count = Sale.objects.filter(
            sale_date__date__gte=month_start,
            payment_method=method,
            is_held=False
        ).count()
        payment_breakdown[label] = count

    top_products = SaleItem.objects.filter(
        sale__sale_date__date__gte=month_start,
        sale__is_held=False,
        is_free_gift=False
    ).values('product__name', 'product__joint__display_name').annotate(
        total_qty=Sum('quantity')
    ).order_by('-total_qty')[:10]

    from users.models import User
    staff_performance = []
    for user in User.objects.filter(is_active=True):
        user_sales = Sale.objects.filter(
            sold_by=user, sale_date__date__gte=month_start, is_held=False
        ).prefetch_related('items')
        if user_sales.exists():
            staff_performance.append({
                'user': user,
                'count': user_sales.count(),
                'total': sum(sale.total_amount for sale in user_sales),
            })
    staff_performance.sort(key=lambda x: x['total'], reverse=True)

    from promotions.models import Promotion
    promo_performance = []
    for promo in Promotion.objects.filter(is_active=True):
        promo_sales = Sale.objects.filter(
            promotion_applied=promo,
            sale_date__date__gte=month_start
        ).prefetch_related('items')
        if promo_sales.exists():
            promo_performance.append({
                'promo': promo,
                'count': promo_sales.count(),
                'total': sum(s.total_amount for s in promo_sales),
            })

    return render(request, 'reports.html', {
        'joint_reports': joint_reports,
        'payment_breakdown': payment_breakdown,
        'top_products': top_products,
        'staff_performance': staff_performance,
        'promo_performance': promo_performance,
        'month': today.strftime('%B %Y'),
        'month_count': Sale.objects.filter(
            sale_date__date__gte=month_start, is_held=False
        ).count(),
    })


def _product_to_dict(product):
    return {
        'id': product.pk,
        'name': product.name,
        'code': product.code or '',
        'barcode': product.barcode or '',
        'price': str(product.effective_price),
        'original_price': str(product.price),
        'stock': product.current_stock,
        'promotion_label': product.promotion_label or '',
        'is_clearance': product.is_clearance,
        'category': product.category.name if product.category else '',
        'category_id': product.category_id or '',
        'brand': product.brand.name if product.brand else '',
        'image_url': product.image.url if product.image else '',
    }
