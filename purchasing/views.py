from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone

from .models import PurchaseOrder, PurchaseOrderItem, GoodsReceivedNote, GRNItem
from .forms import (
    PurchaseOrderForm, POItemFormSet,
    GoodsReceivedNoteForm, GRNItemForm, POFilterForm,
)
from inventory.models import Product


def _manager_required(request):
    if not request.user.is_manager_role:
        messages.error(request, 'Managers and above only.')
        return True
    return False


# ── PURCHASE ORDER LIST ──────────────────────────────────────────────────────

@login_required
def po_list(request):
    if _manager_required(request):
        return redirect('sales:dashboard')

    qs   = PurchaseOrder.objects.select_related('supplier', 'joint', 'created_by').order_by('-created_at')
    form = POFilterForm(request.GET or None)

    if form.is_valid():
        cd = form.cleaned_data
        if cd.get('supplier'):
            qs = qs.filter(supplier=cd['supplier'])
        if cd.get('status'):
            qs = qs.filter(status=cd['status'])
        if cd.get('date_from'):
            qs = qs.filter(order_date__gte=cd['date_from'])
        if cd.get('date_to'):
            qs = qs.filter(order_date__lte=cd['date_to'])

    # Annotate total cost per PO
    pos_with_totals = []
    for po in qs:
        po._total = po.total_cost
        pos_with_totals.append(po)

    return render(request, 'purchasing/po_list.html', {
        'purchase_orders': pos_with_totals,
        'filter_form': form,
    })


# ── CREATE PO ────────────────────────────────────────────────────────────────

@login_required
def po_create(request):
    if _manager_required(request):
        return redirect('purchasing:po_list')

    po_form   = PurchaseOrderForm(request.POST or None)
    item_formset = POItemFormSet(request.POST or None)

    if request.method == 'POST' and po_form.is_valid() and item_formset.is_valid():
        # Check at least one non-deleted item exists
        valid_items = [f for f in item_formset if f.cleaned_data and not f.cleaned_data.get('DELETE')]
        if not valid_items:
            messages.error(request, 'Please add at least one product to the purchase order.')
        else:
            with transaction.atomic():
                po = po_form.save(commit=False)
                po.created_by = request.user
                po.save()
                item_formset.instance = po
                item_formset.save()

            messages.success(request, f"Purchase Order {po.order_number} created.")
            return redirect('purchasing:po_detail', pk=po.pk)

    return render(request, 'purchasing/po_form.html', {
        'po_form': po_form,
        'item_formset': item_formset,
        'title': 'New Purchase Order',
    })


# ── PO DETAIL ────────────────────────────────────────────────────────────────

@login_required
def po_detail(request, pk):
    if _manager_required(request):
        return redirect('purchasing:po_list')

    po = get_object_or_404(
        PurchaseOrder.objects.select_related('supplier', 'joint', 'created_by')
        .prefetch_related('items__product', 'grns__items__po_item__product', 'grns__received_by'),
        pk=pk,
    )
    return render(request, 'purchasing/po_detail.html', {'po': po})


# ── MARK AS ORDERED ──────────────────────────────────────────────────────────

@login_required
def po_mark_ordered(request, pk):
    if _manager_required(request):
        return redirect('purchasing:po_list')

    po = get_object_or_404(PurchaseOrder, pk=pk)
    try:
        po.mark_ordered()
        messages.success(request, f"{po.order_number} marked as ordered.")
    except ValueError as e:
        messages.error(request, str(e))
    return redirect('purchasing:po_detail', pk=pk)


# ── CANCEL PO ────────────────────────────────────────────────────────────────

@login_required
def po_cancel(request, pk):
    if _manager_required(request):
        return redirect('purchasing:po_list')

    po = get_object_or_404(PurchaseOrder, pk=pk)
    if request.method == 'POST':
        try:
            po.cancel(request.user)
            messages.warning(request, f"{po.order_number} cancelled.")
        except ValueError as e:
            messages.error(request, str(e))
    return redirect('purchasing:po_detail', pk=pk)


# ── CREATE GRN (receive goods) ───────────────────────────────────────────────

@login_required
def grn_create(request, po_pk):
    if _manager_required(request):
        return redirect('purchasing:po_list')

    po = get_object_or_404(
        PurchaseOrder.objects.prefetch_related('items__product__stock'),
        pk=po_pk,
        status__in=[PurchaseOrder.STATUS_ORDERED, PurchaseOrder.STATUS_PARTIAL],
    )

    grn_form = GoodsReceivedNoteForm(
        request.POST or None,
        initial={'received_date': timezone.localdate()},
    )

    # Build a form for each pending PO line
    pending_items = [item for item in po.items.all() if item.pending_quantity > 0]

    if request.method == 'POST' and grn_form.is_valid():
        # Collect received quantities from POST
        received_data = []
        for po_item in pending_items:
            field_name = f'qty_{po_item.pk}'
            try:
                qty = int(request.POST.get(field_name, 0))
            except (ValueError, TypeError):
                qty = 0
            if qty < 0:
                qty = 0
            if qty > po_item.pending_quantity:
                messages.error(
                    request,
                    f"Cannot receive {qty}× '{po_item.product.name}'. "
                    f"Max pending: {po_item.pending_quantity}."
                )
                return render(request, 'purchasing/grn_form.html', {
                    'po': po, 'grn_form': grn_form, 'pending_items': pending_items,
                })
            if qty > 0:
                received_data.append({'po_item': po_item, 'qty': qty})

        if not received_data:
            messages.error(request, 'Please enter at least one received quantity.')
        else:
            with transaction.atomic():
                grn = grn_form.save(commit=False)
                grn.purchase_order = po
                grn.received_by    = request.user
                grn.save()

                for entry in received_data:
                    GRNItem.objects.create(
                        grn               = grn,
                        po_item           = entry['po_item'],
                        quantity_received = entry['qty'],
                        unit_cost         = entry['po_item'].unit_cost,
                    )

                grn.apply_to_stock()

            messages.success(
                request,
                f"GRN {grn.grn_number} recorded. "
                f"{len(received_data)} product(s) added to inventory."
            )
            return redirect('purchasing:grn_detail', pk=grn.pk)

    return render(request, 'purchasing/grn_form.html', {
        'po': po, 'grn_form': grn_form, 'pending_items': pending_items,
    })


# ── GRN DETAIL ───────────────────────────────────────────────────────────────

@login_required
def grn_detail(request, pk):
    if _manager_required(request):
        return redirect('purchasing:po_list')

    grn = get_object_or_404(
        GoodsReceivedNote.objects.select_related(
            'purchase_order__supplier', 'purchase_order__joint', 'received_by'
        ).prefetch_related('items__po_item__product'),
        pk=pk,
    )
    return render(request, 'purchasing/grn_detail.html', {'grn': grn})


# ── API: products for a joint (used in PO form JS) ───────────────────────────

@login_required
def api_products_for_joint(request):
    joint_id = request.GET.get('joint_id', '')
    if not joint_id:
        return JsonResponse({'products': []})
    products = Product.objects.filter(
        joint_id=joint_id, is_active=True
    ).values('id', 'name', 'code', 'price')
    return JsonResponse({'products': list(products)})