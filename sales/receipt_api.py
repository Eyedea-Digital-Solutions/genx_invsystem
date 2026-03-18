from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.conf import settings

from .models import Sale


@login_required
def receipt_data_api(request, pk):
    """
    Returns all receipt data as JSON for the WebUSB thermal printer.
    Called by thermal_printer.js → GenXPrinter.printFromUrl(url)
    """
    sale = get_object_or_404(
        Sale.objects
            .select_related('joint', 'sold_by', 'customer')
            .prefetch_related('items__product'),
        pk=pk,
    )

    # Permission guard
    if sale.sold_by != request.user and not request.user.is_manager_role:
        return JsonResponse({'error': 'forbidden'}, status=403)

    store_info = getattr(settings, 'STORE_INFO', {}).get(sale.joint.name, {})

    cashier = ''
    if sale.sold_by:
        cashier = sale.sold_by.get_full_name() or sale.sold_by.username

    items = []
    for item in sale.items.all():
        if item.product:
            name = item.product.name
        elif getattr(item, 'custom_item_name', None):
            name = item.custom_item_name
        else:
            name = '(item)'

        items.append({
            'name':            name,
            'qty':             item.quantity,
            'unit_price':      str(item.unit_price),
            'line_total':      '{:.2f}'.format(item.line_total),
            'is_free_gift':    item.is_free_gift,
            'promotion_label': item.promotion_label or '',
        })

    # Pull loyalty points earned from the sale's audit log
    loyalty_points = None
    try:
        log = sale.audit_logs.filter(action='created').order_by('-timestamp').first()
        if log:
            loyalty_points = log.details.get('loyalty_points_earned') or None
    except Exception:
        pass

    discount = None
    if sale.discount_amount and float(sale.discount_amount) > 0:
        discount = '{:.2f}'.format(sale.discount_amount)

    return JsonResponse({
        'store_name':     store_info.get('legal_name', sale.joint.display_name),
        'store_address':  store_info.get('address', ''),
        'store_phone':    store_info.get('phone', ''),
        'store_tin':      store_info.get('tin', ''),
        'joint':          sale.joint.display_name,
        'receipt_number': sale.receipt_number,
        'date':           sale.sale_date.strftime('%d %b %Y  %H:%M'),
        'cashier':        cashier,
        'payment_method': sale.get_payment_method_display(),
        'customer_name':  (sale.customer.name if sale.customer
                           else sale.customer_name or None),
        'items':          items,
        'subtotal':       '{:.2f}'.format(sale.subtotal),
        'discount':       discount,
        'discount_label': sale.discount_label or None,
        'total':          '{:.2f}'.format(sale.total_amount),
        'tagline':        store_info.get('tagline', 'Thank you for your purchase!'),
        'loyalty_points': loyalty_points,
    })