from decimal import Decimal
from django.db import models as django_models
from .models import Promotion


def apply_promotions(cart_items, joint_id=None):
    result_items = [dict(item) for item in cart_items]
    product_ids = {item['product_id'] for item in result_items}
    cart_discount = Decimal('0')
    cart_discount_label = ''

    q_filter = django_models.Q(joint_id=joint_id) | django_models.Q(joint__isnull=True)
    active_promos = (
        Promotion.objects
        .filter(is_active=True)
        .filter(q_filter)
        .select_related('spend_threshold', 'free_gift', 'bundle')
        .prefetch_related('bundle__products')
    )
    active_promos = [p for p in active_promos if p.is_currently_active]

    subtotal = sum(
        item['unit_price'] * item['qty']
        for item in result_items
        if not item.get('is_free_gift')
    )

    for promo in active_promos:

        if promo.promo_type in ('free_gift', 'buy_n_get_n') and hasattr(promo, 'free_gift'):
            fg = promo.free_gift

            trigger_in_cart = next(
                (i for i in result_items
                 if i['product_id'] == fg.trigger_product_id
                 and not i.get('is_free_gift')),
                None
            )

            if not trigger_in_cart:
                continue

            qty_in_cart = trigger_in_cart['qty']

            if promo.promo_type == 'free_gift':
                if qty_in_cart < fg.trigger_quantity:
                    continue
                free_qty = fg.gift_quantity
            else:
                free_qty = (qty_in_cart // fg.trigger_quantity) * fg.gift_quantity
                if free_qty == 0:
                    continue

            gift_pid = fg.gift_product_id or fg.trigger_product_id
            gift_product = fg.gift_product or fg.trigger_product

            existing_gift = next(
                (i for i in result_items
                 if i['product_id'] == gift_pid and i.get('is_free_gift')),
                None
            )
            if existing_gift:
                existing_gift['qty'] = free_qty
            else:
                result_items.append({
                    'product_id': gift_pid,
                    'product_obj': gift_product,
                    'qty': free_qty,
                    'unit_price': gift_product.effective_price,
                    'is_free_gift': True,
                    'promo_label': promo.name,
                })

        elif promo.promo_type == 'spend_threshold' and hasattr(promo, 'spend_threshold'):
            st = promo.spend_threshold
            if subtotal >= st.min_cart_value:
                if st.discount_type == 'fixed':
                    disc = st.discount_value
                else:
                    disc = (subtotal * st.discount_value / Decimal('100')).quantize(Decimal('0.01'))
                if disc > cart_discount:
                    cart_discount = disc
                    cart_discount_label = promo.name

        elif promo.promo_type == 'bundle' and hasattr(promo, 'bundle'):
            bundle = promo.bundle
            bundle_pids = set(bundle.products.values_list('id', flat=True))
            if bundle_pids.issubset(product_ids):
                normal_total = sum(
                    i['unit_price'] * i['qty']
                    for i in result_items
                    if i['product_id'] in bundle_pids and not i.get('is_free_gift')
                )
                bundle_savings = normal_total - bundle.bundle_price
                if bundle_savings > cart_discount:
                    cart_discount = bundle_savings
                    cart_discount_label = promo.name
                    for item in result_items:
                        if item['product_id'] in bundle_pids:
                            item['promo_label'] = promo.name

    return {
        'items': result_items,
        'cart_discount': cart_discount,
        'cart_discount_label': cart_discount_label,
    }
