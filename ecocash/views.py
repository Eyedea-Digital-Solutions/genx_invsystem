from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django import forms
from .models import EcoCashTransaction
from .services import confirm_payment, get_pending_payments
from sales.models import Sale


class ConfirmPaymentForm(forms.Form):
    transaction_reference = forms.CharField(
        label='EcoCash Transaction Reference',
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g. MMMXXXXXXX (from customer SMS)',
        })
    )


@login_required
def pending_payments(request):
    """
    Lists all EcoCash payments waiting for confirmation.
    Staff should use this to reconcile payments.
    """
    pending = get_pending_payments()
    return render(request, 'pending_payments.html', {'pending_payments': pending})


@login_required
def confirm_payment_view(request, pk):
    """
    Confirms an EcoCash payment after staff verifies the customer's transaction reference.
    """
    ecocash_tx = get_object_or_404(EcoCashTransaction, pk=pk)

    if ecocash_tx.status == 'confirmed':
        messages.info(request, "This payment has already been confirmed.")
        return redirect('ecocash:pending_payments')

    form = ConfirmPaymentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        ref = form.cleaned_data['transaction_reference']
        success = confirm_payment(ecocash_tx, ref, request.user)
        if success:
            messages.success(request, f"EcoCash payment confirmed! Ref: {ref}")
            return redirect('sales:sale_detail', pk=ecocash_tx.sale.pk)

    return render(request, 'confirm_payment.html', {
        'ecocash_tx': ecocash_tx,
        'form': form,
    })


@login_required
def transaction_list(request):
    """View all EcoCash transactions."""
    transactions = EcoCashTransaction.objects.select_related('sale', 'sale__joint', 'confirmed_by').order_by('-created_at')
    return render(request, 'transaction_list.html', {'transactions': transactions})
