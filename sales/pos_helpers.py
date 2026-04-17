"""
sales/pos_helpers.py
Helper to annotate products with has_free_accessories and free_accessories_json
so the template doesn't need to call .filter().exists() which causes a 500.

Usage in your POS view:
    from sales.pos_helpers import annotate_pos_products
    products = annotate_pos_products(products_queryset)
"""
import json


def annotate_pos_products(products):
    """
    Takes a queryset or list of products and adds:
      - product.has_free_accessories  (bool)
      - product.free_accessories_json (JSON string for the template)

    Handles missing FreeAccessory model gracefully.
    """
    result = list(products)

    # Try to get free accessories
    try:
        from promotions.models import FreeAccessory  # adjust import path as needed
        # Build a mapping of product_id → list of accessories
        acc_map = {}
        for acc in FreeAccessory.objects.filter(is_active=True).select_related('accessory_product'):
            pid = str(acc.product_id)
            if pid not in acc_map:
                acc_map[pid] = []
            acc_map[pid].append({
                'accessory_id': acc.accessory_product_id,
                'accessory_name': acc.accessory_product.name,
                'quantity': acc.quantity,
                'label': getattr(acc, 'label', None) or f'Free {acc.accessory_product.name}',
            })
    except Exception:
        acc_map = {}

    for product in result:
        pid = str(product.id)
        accs = acc_map.get(pid, [])
        product.has_free_accessories = bool(accs)
        product.free_accessories_json = json.dumps(accs)

    return result


def get_pos_context(request):
    """
    Returns safe context dict for the POS view.
    Call this from your existing pos view and merge with its context.
    """
    from django.conf import settings
    return {
        'tax_rate': getattr(settings, 'POS_TAX_RATE', 0),
    }