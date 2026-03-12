from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse

from .models import Return, ReturnItem, ReturnAuditLog
from .forms import ReturnSearchForm, ReturnReasonForm
from sales.models import Sale, SaleItem


def _manager_required(request):
    if not request.user.is_manager_role:
        messages.error(request, 'Managers and above only.')
        return True
    return False


# ── STEP 1: Search by receipt number ────────────────────────────────────────

@login_required
def return_search(request):
    form  = ReturnSearchForm(request.POST or None)
    sale  = None
    error = None

    if request.method == 'POST' and form.is_valid():
        receipt_number = form.cleaned_data['receipt_number'].strip().upper()
        try:
            sale = Sale.objects.prefetch_related(
                'items__product', 'items__return_items'
            ).get(receipt_number__iexact=receipt_number, is_held=False)
        except Sale.DoesNotExist:
            error = f"No sale found with receipt number '{receipt_number}'."

    return render(request, 'returns/return_search.html', {
        'form': form, 'sale': sale, 'error': error,
    })


# ── STEP 2 + 3: Select items, reason, confirm ────────────────────────────────

@login_required
def return_create(request, sale_pk):
    if _manager_required(request):
        return redirect('returns:return_search')

    sale = get_object_or_404(
        Sale.objects.prefetch_related('items__product__stock', 'items__return_items'),
        pk=sale_pk, is_held=False,
    )

    # Build returnable items: original qty minus already-returned qty
    returnable = []
    for item in sale.items.all():
        if item.is_free_gift or not item.product:
            continue
        already_returned = (
            ReturnItem.objects.filter(
                original_item=item,
                return_record__status=Return.STATUS_COMPLETED,
            ).aggregate(t=__import__('django').db.models.Sum('quantity_returned'))['t'] or 0
        )
        max_qty = item.quantity - already_returned
        if max_qty > 0:
            returnable.append({'item': item, 'max_qty': max_qty})

    if not returnable:
        messages.warning(request, 'All items on this receipt have already been returned.')
        return redirect('returns:return_search')

    reason_form = ReturnReasonForm(request.POST or None)

    if request.method == 'POST' and reason_form.is_valid():
        # Parse item quantities from POST
        items_to_return = []
        for entry in returnable:
            item   = entry['item']
            field  = f'qty_{item.pk}'
            restock_field = f'restock_{item.pk}'
            try:
                qty = int(request.POST.get(field, 0))
            except (TypeError, ValueError):
                qty = 0
            restock = request.POST.get(restock_field) == 'on'
            if qty < 0:
                qty = 0
            if qty > entry['max_qty']:
                messages.error(request, f"Cannot return {qty} × '{item.product.name}'. Maximum: {entry['max_qty']}.")
                return render(request, 'returns/return_create.html', {
                    'sale': sale, 'returnable': returnable, 'reason_form': reason_form,
                })
            if qty > 0:
                items_to_return.append({'item': item, 'qty': qty, 'restock': restock})

        if not items_to_return:
            messages.error(request, 'Please enter a quantity of at least 1 item to return.')
            return render(request, 'returns/return_create.html', {
                'sale': sale, 'returnable': returnable, 'reason_form': reason_form,
            })

        with transaction.atomic():
            ret = Return.objects.create(
                original_sale = sale,
                processed_by  = request.user,
                refund_type   = reason_form.cleaned_data['refund_type'],
                reason        = reason_form.cleaned_data['reason'],
                notes         = reason_form.cleaned_data.get('notes', ''),
                status        = Return.STATUS_PENDING,
            )
            for entry in items_to_return:
                ReturnItem.objects.create(
                    return_record      = ret,
                    original_item      = entry['item'],
                    quantity_returned  = entry['qty'],
                    unit_refund_amount = entry['item'].unit_price,
                    restock            = entry['restock'],
                )
            ReturnAuditLog.objects.create(
                return_record=ret,
                action='created',
                performed_by=request.user,
                details={
                    'items': [
                        {'product': e['item'].product.name, 'qty': e['qty']}
                        for e in items_to_return
                    ]
                },
            )

        return redirect('returns:return_confirm', pk=ret.pk)

    return render(request, 'returns/return_create.html', {
        'sale': sale, 'returnable': returnable, 'reason_form': reason_form,
    })


# ── STEP 4: Confirm & finalise ───────────────────────────────────────────────

@login_required
def return_confirm(request, pk):
    if _manager_required(request):
        return redirect('returns:return_list')

    ret = get_object_or_404(
        Return.objects.select_related(
            'original_sale__joint', 'processed_by'
        ).prefetch_related('items__original_item__product'),
        pk=pk, status=Return.STATUS_PENDING,
    )

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'confirm':
            try:
                ret.process()
                messages.success(
                    request,
                    f"Return {ret.return_number} processed. "
                    f"Refund: ${ret.total_refund_amount:.2f} ({ret.get_refund_type_display()})."
                )
                return redirect('returns:return_detail', pk=ret.pk)
            except ValueError as e:
                messages.error(request, str(e))
        elif action == 'cancel':
            ret.cancel(request.user, reason='Cancelled at confirmation step.')
            messages.warning(request, f"Return {ret.return_number} cancelled.")
            return redirect('returns:return_search')

    # Pre-calculate totals for display
    total = sum(i.total_refund for i in ret.items.all())
    return render(request, 'returns/return_confirm.html', {'ret': ret, 'total': total})


# ── DETAIL ───────────────────────────────────────────────────────────────────

@login_required
def return_detail(request, pk):
    ret = get_object_or_404(
        Return.objects.select_related(
            'original_sale__joint', 'processed_by'
        ).prefetch_related(
            'items__original_item__product', 'audit_logs__performed_by'
        ),
        pk=pk,
    )
    return render(request, 'returns/return_detail.html', {'ret': ret})


# ── LIST ─────────────────────────────────────────────────────────────────────

@login_required
def return_list(request):
    if _manager_required(request):
        return redirect('returns:return_search')

    qs = Return.objects.select_related(
        'original_sale__joint', 'processed_by'
    ).order_by('-created_at')

    # Simple filters
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)

    date_from = request.GET.get('date_from', '')
    date_to   = request.GET.get('date_to', '')
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    return render(request, 'returns/return_list.html', {
        'returns':    qs,
        'status':     status,
        'date_from':  date_from,
        'date_to':    date_to,
        'status_choices': Return.STATUS_CHOICES,
    })