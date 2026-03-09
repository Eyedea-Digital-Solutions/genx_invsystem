from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import EcoCashTransaction
from .services import get_econet_number, get_merchant_name


@login_required
def pending_payments(request):
    transactions = EcoCashTransaction.objects.select_related(
        'sale__joint', 'sale__sold_by'
    ).filter(status=EcoCashTransaction.STATUS_PENDING).order_by('-created_at')
    return render(request, 'ecocash/pending_payments.html', {
        'transactions': transactions,
        'econet_number': get_econet_number(),
        'merchant_name': get_merchant_name(),
    })


@login_required
def transaction_list(request):
    transactions = EcoCashTransaction.objects.select_related(
        'sale__joint', 'sale__sold_by', 'confirmed_by'
    ).all().order_by('-created_at')

    if not request.user.is_manager_role:
        transactions = transactions.filter(sale__sold_by=request.user)

    return render(request, 'ecocash/transaction_list.html', {
        'transactions': transactions,
    })


@login_required
def confirm_payment(request, pk):
    tx = get_object_or_404(EcoCashTransaction, pk=pk, status=EcoCashTransaction.STATUS_PENDING)
    reference = request.POST.get('reference', '').strip()

    if not reference:
        messages.error(request, "Enter the EcoCash reference number.")
        return redirect('ecocash:pending_payments')

    tx.reference = reference
    tx.confirm(request.user)
    messages.success(request, f"Payment for {tx.sale.receipt_number} confirmed. Ref: {reference}")
    return redirect('ecocash:pending_payments')


@login_required
def fail_payment(request, pk):
    tx = get_object_or_404(EcoCashTransaction, pk=pk, status=EcoCashTransaction.STATUS_PENDING)
    notes = request.POST.get('notes', '').strip()
    tx.mark_failed(notes=notes or 'Marked failed manually.')
    messages.warning(request, f"Payment for {tx.sale.receipt_number} marked as failed.")
    return redirect('ecocash:pending_payments')
