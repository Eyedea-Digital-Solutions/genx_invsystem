"""
EcoCash Payment Services

Since you're using an Econet number (not a merchant API account),
this module handles the payment flow without API integration.

Payment Flow:
1. Sale is created
2. System generates a payment reference (e.g., GNX-0001-PAY)
3. Staff tells customer: "Please send $XX.XX to 0777XXXXXX and quote GNX-0001-PAY"
4. Customer pays and gets an EcoCash confirmation SMS
5. Staff confirms payment by entering the EcoCash transaction code from customer's SMS
6. System records the confirmed EcoCash transaction
"""

from django.conf import settings
from django.utils import timezone
from .models import EcoCashTransaction


def create_ecocash_payment(sale):
    """
    Creates an EcoCash payment record for a sale.
    Returns the EcoCashTransaction object.
    
    Call this when a customer wants to pay via EcoCash.
    """
    econet_number = settings.ECOCASH_ECONET_NUMBER

    # Create the pending transaction record
    ecocash_tx = EcoCashTransaction.objects.create(
        sale=sale,
        econet_number=econet_number,
        amount=sale.total_amount,
        status='pending',
    )

    return ecocash_tx


def get_payment_instruction(ecocash_tx):
    """
    Returns the payment instruction text to show on screen
    or print for the customer.
    """
    return {
        'number': ecocash_tx.econet_number,
        'amount': ecocash_tx.amount,
        'reference': ecocash_tx.sale.receipt_number,
        'message': (
            f"Please send ${ecocash_tx.amount} to {ecocash_tx.econet_number} "
            f"and quote reference: {ecocash_tx.sale.receipt_number}"
        )
    }


def confirm_payment(ecocash_tx, transaction_reference, confirmed_by_user):
    """
    Confirms an EcoCash payment after the customer provides 
    their EcoCash transaction reference from their SMS.
    
    Args:
        ecocash_tx: The EcoCashTransaction to confirm
        transaction_reference: The reference number from the customer's SMS
        confirmed_by_user: The User who confirmed the payment
    
    Returns:
        True if successful, False otherwise
    """
    if ecocash_tx.status == 'confirmed':
        return False  # Already confirmed

    ecocash_tx.transaction_reference = transaction_reference
    ecocash_tx.status = 'confirmed'
    ecocash_tx.confirmed_at = timezone.now()
    ecocash_tx.confirmed_by = confirmed_by_user
    ecocash_tx.save()
    return True


def get_pending_payments():
    """Returns all unconfirmed EcoCash payments (for reconciliation)."""
    return EcoCashTransaction.objects.filter(status='pending').select_related('sale', 'sale__joint')