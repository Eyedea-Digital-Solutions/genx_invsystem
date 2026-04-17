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


# ── Helper: auto-create or fetch customer from name+phone ────────────────────

def _get_or_create_customer(customer_id, customer_name, customer_phone, performed_by=None):
    """
    Returns a Customer instance (or None).
    Priority:
      1. Explicit customer_id
      2. Lookup by phone
      3. Auto-create if name + phone provided
    """
    from customers.models import Customer as CustomerModel

    if customer_id:
        try:
            return CustomerModel.objects.get(pk=customer_id, is_active=True)
        except CustomerModel.DoesNotExist:
            pass

    if customer_phone:
        existing = CustomerModel.objects.filter(phone=customer_phone, is_active=True).first()
        if existing:
            return existing

    # Auto-create when we have at least a name or phone
    if customer_name or customer_phone:
        customer = CustomerModel.objects.create(
            name=customer_name or customer_phone,
            phone=customer_phone or '',
            customer_type=CustomerModel.TYPE_REGULAR,
            is_active=True,
        )
        return customer

    return None

@login_required
def dashboard(request):
    """
    Main sales dashboard — /dashboard/
    Gracefully handles missing models/data.
    """
    today = timezone.now().date()
    month_start = today.replace(day=1)
 
    context = {
        'today_total':    Decimal('0'),
        'today_count':    0,
        'month_total':    Decimal('0'),
        'month_count':    0,
        'low_stock_count': 0,
        'low_stock':      [],
        'expiring_soon':  [],
        'recent_sales':   [],
        'joint_stats':    [],
    }
 
    # Today's sales
    try:
        from django.db.models import Sum
        from sales.models import Sale, SaleItem
 
        today_qs = Sale.objects.filter(sale_date__date=today, is_held=False)
        context['today_count'] = today_qs.count()
 
        today_total = (
            SaleItem.objects
            .filter(sale__sale_date__date=today, sale__is_held=False)
            .aggregate(t=Sum('line_total'))['t']
        )
        if today_total is None:
            today_total = today_qs.aggregate(t=Sum('total_amount'))['t']
        context['today_total'] = today_total or Decimal('0')
 
        # Month
        month_qs = Sale.objects.filter(sale_date__date__gte=month_start, is_held=False)
        context['month_count'] = month_qs.count()
        month_total = (
            SaleItem.objects
            .filter(sale__sale_date__date__gte=month_start, sale__is_held=False)
            .aggregate(t=Sum('line_total'))['t']
        )
        if month_total is None:
            month_total = month_qs.aggregate(t=Sum('total_amount'))['t']
        context['month_total'] = month_total or Decimal('0')
 
        # Recent sales
        context['recent_sales'] = (
            Sale.objects
            .filter(is_held=False)
            .select_related('customer', 'sold_by', 'joint')
            .order_by('-sale_date')[:10]
        )
 
        # Joint breakdown today
        from django.db.models import Count
        from inventory.models import Joint
 
        joint_stats = []
        for joint in Joint.objects.filter(is_active=True):
            jqs = today_qs.filter(joint=joint)
            jrev = jqs.aggregate(t=Sum('total_amount'))['t'] or Decimal('0')
            joint_stats.append({
                'joint': joint,
                'count': jqs.count(),
                'total': jrev,
            })
        context['joint_stats'] = joint_stats
 
    except Exception:
        pass
 
    # Low stock
    try:
        from django.conf import settings as django_settings
        from inventory.models import Product
 
        threshold = getattr(django_settings, 'LOW_STOCK_THRESHOLD', 3)
        low = list(
            Product.objects
            .filter(is_active=True)
            .select_related('stock')
            .filter(stock__quantity__lte=threshold)
            .order_by('stock__quantity')[:20]
        )
        context['low_stock'] = low
        context['low_stock_count'] = len(low)
    except Exception:
        pass
 
    # Expiring soon
    try:
        from django.conf import settings as django_settings
        from inventory.models import Product
 
        warn_days = getattr(django_settings, 'EXPIRY_WARNING_DAYS', 30)
        expiry_cutoff = timezone.now().date() + timezone.timedelta(days=warn_days)
        context['expiring_soon'] = list(
            Product.objects
            .filter(is_active=True, stock__expiry_date__lte=expiry_cutoff)
            .select_related('stock')
            .order_by('stock__expiry_date')[:20]
        )
    except Exception:
        pass
 
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
    barcode  = request.GET.get('barcode', '').strip()
    joint_id = request.GET.get('joint_id', '').strip()

    if not barcode or not joint_id:
        return JsonResponse({'found': False, 'message': 'Barcode and joint required'})

    product = Product.objects.select_related('stock', 'category', 'brand').filter(
        Q(barcode=barcode) | Q(code=barcode),
        joint_id=joint_id,
        is_active=True
    ).first()

    if product:
        return JsonResponse({'found': True, 'product': _product_to_dict(product)})

    # Try matching a bundle SKU
    from promotions.models import Bundle
    bundle = Bundle.objects.prefetch_related('items__product__stock', 'joints').filter(
        sku=barcode, is_active=True
    ).first()
    if bundle and bundle.is_available_in(joint_id):
        return JsonResponse({'found': True, 'bundle': _bundle_to_dict(bundle, joint_id)})

    return JsonResponse({'found': False, 'message': f'No product for barcode: {barcode}'})


@login_required
def pos_search(request):
    q            = request.GET.get('q', '').strip()
    joint_id     = request.GET.get('joint_id', '').strip()
    filter_type  = request.GET.get('filter', 'all')
    category_id  = request.GET.get('category_id', '').strip()

    if not joint_id:
        return JsonResponse({'products': [], 'bundles': []})

    try:
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
            products = products.filter(stock__isnull=False, stock__quantity__lte=settings.LOW_STOCK_THRESHOLD)
        elif filter_type == 'in_stock':
            products = products.filter(stock__isnull=False, stock__quantity__gt=0)

        # Bundles (cross-branch aware) — only on 'all' filter with no category restriction
        bundles_data = []
        if filter_type == 'all' and not category_id:
            from promotions.models import Bundle
            bqs = Bundle.objects.prefetch_related('items__product__stock', 'joints').filter(is_active=True)
            if q:
                bqs = bqs.filter(Q(name__icontains=q) | Q(sku__icontains=q))
            for bundle in bqs[:20]:
                if bundle.is_available_in(joint_id):
                    bundles_data.append(_bundle_to_dict(bundle, joint_id))

        data = [_product_to_dict(p) for p in products[:60]]
        return JsonResponse({'products': data, 'bundles': bundles_data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


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
            'items': [], 'subtotal': '0.00',
            'cart_discount': '0.00', 'cart_discount_label': '',
            'total': '0.00', 'free_accessory_warnings': [],
        })

    # Separate regular products from bundles and custom items
    raw_products = [i for i in raw_items if not i.get('bundle_id') and not i.get('is_free_gift') and not i.get('is_custom')]
    raw_bundles  = [i for i in raw_items if i.get('bundle_id')]
    raw_customs  = [i for i in raw_items if i.get('is_custom')]

    pids     = [i['product_id'] for i in raw_products]
    products = {p.pk: p for p in Product.objects.filter(pk__in=pids)}

    cart_items = []
    for item in raw_products:
        pid = item['product_id']
        p   = products.get(pid)
        if p:
            cart_items.append({
                'product_id':   pid,
                'product_obj':  p,
                'qty':          int(item['qty']),
                'unit_price':   Decimal(str(item['unit_price'])),
                'is_free_gift': False,
                'promo_label':  '',
            })

    from promotions.engine import apply_promotions
    result = apply_promotions(cart_items, joint_id=joint_id)

    # ── ProductFreeAccessory (trigger-product rules) ─────────────────────────
    trigger_pids = [
        i['product_id']
        for i in result['items']
        if not i.get('is_free_gift')
    ]
    accessory_rules = (
        ProductFreeAccessory.objects
        .select_related('accessory_product__stock')
        .filter(trigger_product_id__in=trigger_pids, is_active=True)
    )
    trigger_qty_map = {
        i['product_id']: i['qty']
        for i in result['items']
        if not i.get('is_free_gift')
    }
    accessory_map = {}
    for rule in accessory_rules:
        aid         = rule.accessory_product_id
        trigger_qty = trigger_qty_map.get(rule.trigger_product_id, 1)
        needed_qty  = rule.quantity * trigger_qty
        if aid in accessory_map:
            accessory_map[aid]['qty'] += needed_qty
        else:
            accessory_map[aid] = {
                'product': rule.accessory_product,
                'qty':     needed_qty,
                'label':   rule.get_label(),
                'rule_id': rule.pk,
            }

    # ── CategoryTierFreeRule (price-tier-based free accessories) ────────────
    from promotions.models import CategoryTierFreeRule
    active_tier_rules = (
        CategoryTierFreeRule.objects
        .filter(is_active=True)
        .prefetch_related('free_items__product__stock', 'category')
    )

    for item in result['items']:
        if item.get('is_free_gift'):
            continue
        p          = item['product_obj']
        unit_price = item['unit_price']
        qty        = item['qty']
        if not p.category_id:
            continue
        for rule in active_tier_rules:
            if rule.category_id != p.category_id:
                continue
            if not rule.applies_to_joint(joint_id):
                continue
            if not rule.matches_price(unit_price):
                continue
            for free_item in rule.free_items.all():
                aid    = free_item.product_id
                needed = free_item.quantity * qty
                if aid in accessory_map:
                    accessory_map[aid]['qty'] += needed
                else:
                    accessory_map[aid] = {
                        'product': free_item.product,
                        'qty':     needed,
                        'label':   rule.label or rule.name,
                        'rule_id': None,
                    }

    # ── Stock-clamp free accessories, build warnings ─────────────────────────
    free_accessory_warnings = []
    for aid, acc in accessory_map.items():
        available = acc['product'].current_stock
        if available == 0:
            free_accessory_warnings.append(
                f"⚠ Free '{acc['product'].name}' is out of stock and won't be included."
            )
        elif available < acc['qty']:
            free_accessory_warnings.append(
                f"⚠ Only {available} unit(s) of free '{acc['product'].name}' in stock "
                f"(needed {acc['qty']}) — {available} will be included."
            )

    for aid, acc in accessory_map.items():
        available  = acc['product'].current_stock
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

    # ── Bundles (pass-through at bundle price) ───────────────────────────────
    from promotions.models import Bundle
    bundle_ids    = [i['bundle_id'] for i in raw_bundles]
    bundles_by_id = {
        b.pk: b
        for b in Bundle.objects.prefetch_related('items__product__stock', 'joints').filter(
            pk__in=bundle_ids, is_active=True
        )
    }
    bundle_response_items = []
    for raw in raw_bundles:
        bid    = raw['bundle_id']
        bundle = bundles_by_id.get(bid)
        if not bundle:
            continue
        qty   = int(raw.get('qty', 1))
        stock = bundle.effective_stock(joint_id)
        bundle_response_items.append({
            'bundle_id':    bid,
            'name':         bundle.name,
            'qty':          qty,
            'unit_price':   str(bundle.price),
            'line_total':   str((bundle.price * qty).quantize(Decimal('0.01'))),
            'is_free_gift': False,
            'promo_label':  'Bundle',
            'stock':        stock,
        })

    # ── Custom items (pass-through unchanged) ────────────────────────────────
    custom_response_items = []
    for raw in raw_customs:
        price     = Decimal(str(raw.get('unit_price', '0')))
        qty       = int(raw.get('qty', 1))
        is_free   = price == Decimal('0')
        line_tot  = Decimal('0') if is_free else (price * qty).quantize(Decimal('0.01'))
        custom_response_items.append({
            'is_custom':    True,
            'custom_id':    raw.get('custom_id'),
            'name':         raw.get('name', 'Custom Item'),
            'qty':          qty,
            'unit_price':   str(price),
            'line_total':   str(line_tot),
            'is_free_gift': is_free,
            'promo_label':  raw.get('promo_label', ''),
            'item_note':    raw.get('item_note', ''),
        })

    # ── Totals ───────────────────────────────────────────────────────────────
    product_subtotal = sum(
        i['unit_price'] * i['qty']
        for i in result['items']
        if not i.get('is_free_gift')
    )
    bundle_subtotal = Decimal('0')
    for raw in raw_bundles:
        bid = raw['bundle_id']
        b   = bundles_by_id.get(bid)
        if b:
            bundle_subtotal += b.price * int(raw.get('qty', 1))

    custom_subtotal = Decimal('0')
    for raw in raw_customs:
        price = Decimal(str(raw.get('unit_price', '0')))
        if price > 0:
            custom_subtotal += price * int(raw.get('qty', 1))

    subtotal = product_subtotal + bundle_subtotal + custom_subtotal
    total    = max(Decimal('0'), subtotal - result['cart_discount'])

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
            'item_note':    i.get('item_note', ''),
        } for i in result['items']] + bundle_response_items + custom_response_items,
        'subtotal':               str(subtotal.quantize(Decimal('0.01'))),
        'cart_discount':          str(result['cart_discount'].quantize(Decimal('0.01'))),
        'cart_discount_label':    result['cart_discount_label'],
        'total':                  str(total.quantize(Decimal('0.01'))),
        'free_accessory_warnings': free_accessory_warnings,
    })


@login_required
@require_POST
def pos_complete(request):
    body                = json.loads(request.body)
    joint_id            = body.get('joint_id')
    items_data          = body.get('items', [])
    payment_method      = body.get('payment_method', 'cash')
    customer_id         = body.get('customer_id')
    customer_name       = body.get('customer_name', '').strip()
    customer_phone      = body.get('customer_phone', '').strip()
    cart_discount       = Decimal(str(body.get('cart_discount', '0')))
    cart_discount_label = body.get('cart_discount_label', '')

    if not joint_id or not items_data:
        return JsonResponse({'success': False, 'error': 'Joint and items are required.'})

    # Normalize items: if a client marked an item as 'is_custom' but also
    # provided a `product_id`, treat it as a regular product so stock will
    # be deducted. Some POS flows add linked products via the Custom Item
    # modal and may send them as custom — normalize here to keep server
    # authoritative about stock changes.
    for itm in items_data:
        try:
            if itm.get('product_id') and itm.get('is_custom'):
                itm['is_custom'] = False
        except Exception:
            pass

    # ── Separate item types ───────────────────────────────────────────────────
    regular_items = [i for i in items_data if not i.get('bundle_id') and not i.get('is_free_gift') and not i.get('is_custom')]
    free_items    = [i for i in items_data if i.get('is_free_gift') and not i.get('bundle_id') and not i.get('is_custom')]
    bundle_items  = [i for i in items_data if i.get('bundle_id')]
    custom_items  = [i for i in items_data if i.get('is_custom')]

    # ── Stock validation — regular paid items ─────────────────────────────────
    pids     = [i['product_id'] for i in regular_items]
    products = {
        p.pk: p
        for p in Product.objects.select_related('stock').filter(pk__in=pids)
    }
    for item in regular_items:
        p = products.get(item['product_id'])
        if not p:
            return JsonResponse({'success': False, 'error': f"Product {item['product_id']} not found."})
        if p.current_stock < item['qty']:
            return JsonResponse({'success': False, 'error': f"Insufficient stock for '{p.name}'. Available: {p.current_stock}."})

    # ── Stock validation — free accessories ───────────────────────────────────
    free_pids     = [i['product_id'] for i in free_items]
    free_products = {
        p.pk: p
        for p in Product.objects.select_related('stock').filter(pk__in=free_pids)
    }
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
            sale_warnings.append(f"Free '{p.name}' was out of stock and not included.")
            continue
        if actual < needed:
            sale_warnings.append(f"Only {actual} of {needed} free '{p.name}' included (limited stock).")
        clamped_free.append({**item, 'qty': actual, '_product': p})

    # ── Stock validation — bundles ────────────────────────────────────────────
    from promotions.models import Bundle, CategoryTierFreeRule
    bundle_ids    = [i['bundle_id'] for i in bundle_items]
    bundles_by_id = {
        b.pk: b
        for b in Bundle.objects.prefetch_related('items__product__stock', 'joints').filter(
            pk__in=bundle_ids, is_active=True
        )
    }
    for bi in bundle_items:
        bundle     = bundles_by_id.get(bi['bundle_id'])
        bundle_qty = int(bi.get('qty', 1))
        if not bundle:
            return JsonResponse({'success': False, 'error': f"Bundle {bi['bundle_id']} not found."})
        if not bundle.is_available_in(joint_id):
            return JsonResponse({'success': False, 'error': f"Bundle '{bundle.name}' not available in this branch."})
        for comp in bundle.items.all():
            needed = comp.quantity * bundle_qty
            if comp.product.current_stock < needed:
                return JsonResponse({'success': False, 'error': f"Insufficient stock for '{comp.product.name}' in bundle '{bundle.name}'."})

    # ── Re-derive tier-rule free accessories (server-side truth) ─────────────
    active_tier_rules = (
        CategoryTierFreeRule.objects
        .filter(is_active=True)
        .prefetch_related('free_items__product__stock', 'category')
    )
    tier_free_map = {}
    for item in regular_items:
        p          = products.get(item['product_id'])
        if not p or not p.category_id:
            continue
        unit_price = Decimal(str(item['unit_price']))
        qty        = int(item['qty'])
        for rule in active_tier_rules:
            if rule.category_id != p.category_id:
                continue
            if not rule.applies_to_joint(joint_id):
                continue
            if not rule.matches_price(unit_price):
                continue
            for fi in rule.free_items.all():
                aid    = fi.product_id
                needed = fi.quantity * qty
                if aid in tier_free_map:
                    tier_free_map[aid]['qty'] += needed
                else:
                    tier_free_map[aid] = {
                        'product': fi.product,
                        'qty':     needed,
                        'label':   rule.label or rule.name,
                    }

    # Merge tier free into clamped_free (skip if already covered by passed free_items)
    existing_free_pids = {i['product_id'] for i in clamped_free}
    for aid, tf in tier_free_map.items():
        if aid in existing_free_pids:
            continue
        available = tf['product'].current_stock
        actual    = min(tf['qty'], available)
        if actual <= 0:
            sale_warnings.append(f"Free '{tf['product'].name}' (tier) was out of stock and not included.")
            continue
        if actual < tf['qty']:
            sale_warnings.append(f"Only {actual} of {tf['qty']} free '{tf['product'].name}' included.")
        clamped_free.append({
            'product_id':   aid,
            'qty':          actual,
            'promo_label':  tf['label'],
            'is_free_gift': True,
            '_product':     tf['product'],
        })

    # ── Create sale ───────────────────────────────────────────────────────────
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

        # Regular paid items
        for item in regular_items:
            p          = products[item['product_id']]
            qty        = int(item['qty'])
            unit_price = Decimal(str(item['unit_price']))
            SaleItem.objects.create(
                sale=sale, product=p, quantity=qty,
                unit_price=unit_price, is_free_gift=False,
                promotion_label=item.get('promo_label', ''),
                item_note=item.get('item_note', ''),
            )
            p.stock.deduct(qty)
            snapshot.append({'product_id': p.pk, 'product_name': p.name, 'quantity': qty,
                              'unit_price': str(unit_price), 'is_free_gift': False})

        # Free accessories (per-product rules + tier rules)
        for item in clamped_free:
            p   = item['_product']
            qty = item['qty']
            SaleItem.objects.create(
                sale=sale, product=p, quantity=qty,
                unit_price=Decimal('0'), is_free_gift=True,
                promotion_label=item.get('promo_label', ''),
                item_note=item.get('item_note', ''),
            )
            p.stock.deduct(qty)
            snapshot.append({'product_id': p.pk, 'product_name': p.name, 'quantity': qty,
                              'unit_price': '0.00', 'is_free_gift': True})

        # Custom items (no stock deduction — these are ad-hoc services/items)
        for item in custom_items:
            price    = Decimal(str(item.get('unit_price', '0')))
            qty      = int(item.get('qty', 1))
            is_free  = price == Decimal('0')
            SaleItem.objects.create(
                sale=sale,
                product=None,
                custom_item_name=item.get('name', 'Custom Item'),
                quantity=qty,
                unit_price=price,
                is_free_gift=is_free,
                promotion_label=item.get('promo_label', ''),
                item_note=item.get('item_note', ''),
            )
            snapshot.append({
                'custom_item_name': item.get('name', 'Custom Item'),
                'quantity':         qty,
                'unit_price':       str(price),
                'is_free_gift':     is_free,
                'item_note':        item.get('item_note', ''),
            })

        # Bundles — expand to individual SaleItems
        for bi in bundle_items:
            bundle      = bundles_by_id[bi['bundle_id']]
            bundle_qty  = int(bi.get('qty', 1))
            bundle_price_total = bundle.price * bundle_qty

            non_free = [c for c in bundle.items.all() if not c.is_free]
            free_comp = [c for c in bundle.items.all() if c.is_free]

            total_nonfree_units = sum(c.quantity for c in non_free) * bundle_qty
            price_per_unit = (
                bundle_price_total / total_nonfree_units
                if total_nonfree_units else Decimal('0')
            )

            for comp in non_free:
                qty = comp.quantity * bundle_qty
                SaleItem.objects.create(
                    sale=sale, product=comp.product, quantity=qty,
                    unit_price=price_per_unit, is_free_gift=False,
                    promotion_label=f'Bundle: {bundle.name}',
                )
                comp.product.stock.deduct(qty)
                snapshot.append({'product_id': comp.product_id, 'product_name': comp.product.name,
                                  'quantity': qty, 'unit_price': str(price_per_unit),
                                  'is_free_gift': False, 'bundle': bundle.name})

            for comp in free_comp:
                qty = comp.quantity * bundle_qty
                SaleItem.objects.create(
                    sale=sale, product=comp.product, quantity=qty,
                    unit_price=Decimal('0'), is_free_gift=True,
                    promotion_label=f'Bundle: {bundle.name}',
                )
                comp.product.stock.deduct(qty)
                snapshot.append({'product_id': comp.product_id, 'product_name': comp.product.name,
                                  'quantity': qty, 'unit_price': '0.00',
                                  'is_free_gift': True, 'bundle': bundle.name})

        # ── Link Customer & award loyalty points ──────────────────────────────
        loyalty_points_earned = 0
        linked_customer = _get_or_create_customer(
            customer_id, customer_name, customer_phone, performed_by=request.user
        )

        if linked_customer:
            sale.customer       = linked_customer
            sale.customer_name  = sale.customer_name or linked_customer.name
            sale.customer_phone = sale.customer_phone or linked_customer.phone
            sale.save(update_fields=['customer', 'customer_name', 'customer_phone'])

            loyalty_points_earned = int(sale.total_amount)
            if loyalty_points_earned > 0:
                linked_customer.add_loyalty_points(
                    points       = loyalty_points_earned,
                    reason       = f'POS purchase — {sale.receipt_number}',
                    sale         = sale,
                    performed_by = request.user,
                )

        SaleAuditLog.objects.create(
            sale=sale, action='created', performed_by=request.user,
            details={
                'source':                'pos',
                'total':                 str(sale.total_amount),
                'payment_method':        payment_method,
                'items':                 snapshot,
                'accessory_warnings':    sale_warnings,
                'customer_id':           linked_customer.pk if linked_customer else None,
                'loyalty_points_earned': loyalty_points_earned,
                'bundles':               [bi['bundle_id'] for bi in bundle_items],
                'custom_items_count':    len(custom_items),
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
        'free_accessory_warnings': sale_warnings,
        'loyalty_points_earned':   loyalty_points_earned,
        'customer_name':           linked_customer.name if linked_customer else '',
        'customer_created':        bool(linked_customer and not customer_id),
    })


@login_required
@require_POST
def pos_hold(request):
    body          = json.loads(request.body)
    joint_id      = body.get('joint_id')
    items_data    = body.get('items', [])
    customer_name = body.get('customer_name', '')

    if not joint_id or not items_data:
        return JsonResponse({'success': False, 'error': 'Nothing to hold.'})

    pids     = [i['product_id'] for i in items_data if not i.get('bundle_id') and not i.get('is_custom')]
    products = {p.pk: p for p in Product.objects.filter(pk__in=pids)}

    with transaction.atomic():
        sale = Sale.objects.create(
            joint_id=joint_id, sold_by=request.user, sale_type='pos',
            is_held=True, held_at=timezone.now(), customer_name=customer_name,
        )
        for item in items_data:
            if item.get('bundle_id'):
                # Encode bundle into promotion_label for recall
                from promotions.models import Bundle
                try:
                    bundle = Bundle.objects.prefetch_related('items').get(pk=item['bundle_id'])
                    first_comp = bundle.items.filter(is_free=False).first()
                    if first_comp:
                        SaleItem.objects.create(
                            sale=sale, product=first_comp.product,
                            quantity=int(item.get('qty', 1)),
                            unit_price=Decimal(str(item['unit_price'])),
                            is_free_gift=False,
                            promotion_label=f'__bundle__{bundle.pk}__{bundle.name}',
                        )
                except Exception:
                    pass
            elif item.get('is_custom'):
                # Encode custom item for recall
                price = Decimal(str(item.get('unit_price', '0')))
                SaleItem.objects.create(
                    sale=sale,
                    product=None,
                    custom_item_name=item.get('name', 'Custom Item'),
                    quantity=int(item.get('qty', 1)),
                    unit_price=price,
                    is_free_gift=price == Decimal('0'),
                    promotion_label=f'__custom__{item.get("custom_id", "")}',
                    item_note=item.get('item_note', ''),
                )
            else:
                p = products.get(item['product_id'])
                if p:
                    SaleItem.objects.create(
                        sale=sale, product=p,
                        quantity=int(item['qty']),
                        unit_price=Decimal(str(item['unit_price'])),
                        is_free_gift=item.get('is_free_gift', False),
                        promotion_label=item.get('promo_label', ''),
                        item_note=item.get('item_note', ''),
                    )

    return JsonResponse({'success': True, 'held_id': sale.pk})


@login_required
def pos_recall(request, pk):
    sale = get_object_or_404(
        Sale.objects.prefetch_related('items__product'),
        pk=pk, is_held=True, sold_by=request.user
    )
    items = []
    for item in sale.items.all():
        label = item.promotion_label or ''
        if label.startswith('__bundle__'):
            parts = label.split('__', 3)
            items.append({
                'type':        'bundle',
                'bundle_id':   int(parts[2]),
                'name':        parts[3] if len(parts) > 3 else 'Bundle',
                'qty':         item.quantity,
                'unit_price':  str(item.unit_price),
                'is_free_gift': False,
                'promo_label':  'Bundle',
                'image_url':    '',
                'stock':        99,
            })
        elif label.startswith('__custom__') or item.custom_item_name:
            items.append({
                'is_custom':   True,
                'custom_id':   f'recalled_{item.pk}',
                'name':        item.custom_item_name or 'Custom Item',
                'qty':         item.quantity,
                'unit_price':  str(item.unit_price),
                'is_free_gift': item.is_free_gift,
                'promo_label':  '',
                'item_note':    item.item_note or '',
            })
        else:
            items.append({
                'product_id':   item.product_id,
                'name':         item.product.name if item.product else '(deleted)',
                'qty':          item.quantity,
                'unit_price':   str(item.unit_price),
                'is_free_gift': item.is_free_gift,
                'promo_label':  label,
                'item_note':    item.item_note or '',
                'stock':        item.product.current_stock if item.product else 0,
                'image_url':    item.product.image.url if item.product and item.product.image else '',
                'promotion_label_badge': item.product.promotion_label if item.product else '',
            })

    sale.delete()
    return JsonResponse({'success': True, 'items': items, 'customer_name': sale.customer_name})


@login_required
def make_sale(request):
    joints = Joint.objects.all()

    if request.method == 'POST':
        sale_form = SaleForm(request.POST)
        if sale_form.is_valid():
            items_data = []
            errors     = []
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
                product_id     = request.POST.get(f'product_{i}', '').strip()
                quantity_str   = request.POST.get(f'quantity_{i}', '').strip()
                unit_price_str = request.POST.get(f'unit_price_{i}', '').strip()
                if product_id and quantity_str and unit_price_str:
                    try:
                        product = Product.objects.select_related('stock').get(pk=product_id)
                        qty     = int(quantity_str)
                        price   = float(unit_price_str)
                        if qty < 1:
                            errors.append(f"Quantity for '{product.name}' must be at least 1.")
                        elif product.current_stock < qty:
                            errors.append(f"Not enough stock for '{product.name}'. Available: {product.current_stock}, Requested: {qty}")
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
                sale           = sale_form.save(commit=False)
                sale.sold_by   = request.user
                sale.sale_type = 'system'
                sale.save()
                snapshot = []
                for item_data in items_data:
                    SaleItem.objects.create(
                        sale=sale, product=item_data['product'],
                        quantity=item_data['quantity'], unit_price=item_data['unit_price'],
                    )
                    item_data['product'].stock.deduct(item_data['quantity'])
                    snapshot.append({'product_id': item_data['product'].pk, 'product_name': item_data['product'].name,
                                     'quantity': item_data['quantity'], 'unit_price': str(item_data['unit_price'])})

                # Auto-create/link customer
                c_name  = getattr(sale, 'customer_name', '').strip()
                c_phone = getattr(sale, 'customer_phone', '').strip()
                linked_customer = _get_or_create_customer(None, c_name, c_phone, performed_by=request.user)
                if linked_customer and not sale.customer:
                    sale.customer = linked_customer
                    sale.save(update_fields=['customer'])

                SaleAuditLog.objects.create(
                    sale=sale, action='created', performed_by=request.user,
                    details={'items': snapshot, 'total': str(sale.total_amount),
                             'payment_method': sale.payment_method, 'joint': sale.joint.name}
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
                sale           = form.save(commit=False)
                sale.sold_by   = request.user
                sale.sale_type = 'manual'
                sale.save()
                i = 0
                while f'product_{i}' in request.POST:
                    product_id = request.POST.get(f'product_{i}')
                    quantity   = request.POST.get(f'quantity_{i}')
                    unit_price = request.POST.get(f'unit_price_{i}')
                    if product_id and quantity and unit_price:
                        try:
                            product = Product.objects.select_related('stock').get(pk=product_id)
                            SaleItem.objects.create(
                                sale=sale, product=product,
                                quantity=int(quantity), unit_price=float(unit_price),
                            )
                            product.stock.deduct(int(quantity))
                        except Product.DoesNotExist:
                            messages.warning(request, f"Product ID {product_id} not found.")
                        except ValueError:
                            messages.warning(request, "Invalid quantity or price.")
                    i += 1

                # Auto-create/link customer
                c_name  = getattr(sale, 'customer_name', '').strip()
                c_phone = getattr(sale, 'customer_phone', '').strip()
                linked_customer = _get_or_create_customer(None, c_name, c_phone, performed_by=request.user)
                if linked_customer and not sale.customer:
                    sale.customer = linked_customer
                    sale.save(update_fields=['customer'])

                SaleAuditLog.objects.create(
                    sale=sale, action='manual_sale_recorded', performed_by=request.user,
                    details={'receipt_image': sale.manual_receipt_image.name if sale.manual_receipt_image else None,
                             'notes': sale.notes, 'joint': sale.joint.name}
                )
                if sale.payment_method in ['ecocash', 'mixed']:
                    from ecocash.services import create_ecocash_payment
                    create_ecocash_payment(sale)
            messages.success(request, f"Manual sale recorded! Receipt: {sale.receipt_number}")
            return redirect('sales:sale_receipt_thermal', pk=sale.pk)
    else:
        form = ManualSaleForm()
    return render(request, 'manual_sale.html', {'form': form, 'joints': Joint.objects.all()})


@login_required
def sale_receipt(request, pk):
    sale = get_object_or_404(
        Sale.objects.select_related('joint', 'sold_by').prefetch_related('items__product'), pk=pk
    )
    return render(request, 'receipt.html', {'sale': sale})


@login_required
def sale_receipt_thermal(request, pk):
    sale = get_object_or_404(
        Sale.objects.select_related('joint', 'sold_by').prefetch_related('items__product'), pk=pk
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
        Sale.objects.select_related('joint', 'sold_by').prefetch_related('items__product'), pk=pk
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

    today       = timezone.now().date()
    month_start = today.replace(day=1)

    joint_reports = []
    for joint in Joint.objects.all():
        month_joint_sales = Sale.objects.filter(
            joint=joint, sale_date__date__gte=month_start, is_held=False
        ).prefetch_related('items')
        joint_reports.append({
            'joint': joint, 'count': month_joint_sales.count(),
            'total': sum(sale.total_amount for sale in month_joint_sales),
        })

    payment_breakdown = {}
    for method, label in Sale.PAYMENT_CHOICES:
        payment_breakdown[label] = Sale.objects.filter(
            sale_date__date__gte=month_start, payment_method=method, is_held=False
        ).count()

    top_products = SaleItem.objects.filter(
        sale__sale_date__date__gte=month_start, sale__is_held=False, is_free_gift=False
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
            staff_performance.append({'user': user, 'count': user_sales.count(),
                                      'total': sum(sale.total_amount for sale in user_sales)})
    staff_performance.sort(key=lambda x: x['total'], reverse=True)

    from promotions.models import Promotion
    promo_performance = []
    for promo in Promotion.objects.filter(is_active=True):
        promo_sales = Sale.objects.filter(
            promotion_applied=promo, sale_date__date__gte=month_start
        ).prefetch_related('items')
        if promo_sales.exists():
            promo_performance.append({'promo': promo, 'count': promo_sales.count(),
                                      'total': sum(s.total_amount for s in promo_sales)})

    return render(request, 'reports.html', {
        'joint_reports': joint_reports, 'payment_breakdown': payment_breakdown,
        'top_products': top_products, 'staff_performance': staff_performance,
        'promo_performance': promo_performance,
        'month': today.strftime('%B %Y'),
        'month_count': Sale.objects.filter(sale_date__date__gte=month_start, is_held=False).count(),
    })


def _product_to_dict(product):
    return {
        'id':              product.pk,
        'name':            product.name,
        'code':            product.code or '',
        'barcode':         product.barcode or '',
        'price':           str(product.effective_price),
        'original_price':  str(product.price),
        'stock':           product.current_stock,
        'promotion_label': product.promotion_label or '',
        'is_clearance':    product.is_clearance,
        'category':        product.category.name if product.category else '',
        'category_id':     product.category_id or '',
        'brand':           product.brand.name if product.brand else '',
        'image_url':       product.image.url if product.image else '',
    }


def _bundle_to_dict(bundle, joint_id):
    return {
        'id':          bundle.pk,
        'bundle_id':   bundle.pk,
        'name':        bundle.name,
        'sku':         bundle.sku,
        'description': bundle.description,
        'price':       str(bundle.price),
        'stock':       bundle.effective_stock(joint_id),
        'image_url':   bundle.image.url if bundle.image else '',
        'is_bundle':   True,
        'components':  [
            {'name': c.product.name, 'quantity': c.quantity, 'is_free': c.is_free}
            for c in bundle.items.select_related('product').all()
        ],
    }