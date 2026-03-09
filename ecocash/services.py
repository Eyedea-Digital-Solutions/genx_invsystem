from django.conf import settings
from .models import EcoCashTransaction


def create_ecocash_payment(sale):
    if hasattr(sale, 'ecocash_transaction'):
        return sale.ecocash_transaction

    amount = sale.total_amount
    if sale.payment_method == 'mixed':
        cash_amount = getattr(sale, 'cash_amount', None)
        if cash_amount:
            from decimal import Decimal
            amount = max(Decimal('0'), amount - Decimal(str(cash_amount)))

    tx = EcoCashTransaction.objects.create(
        sale=sale,
        amount=amount,
        phone_number='',
        reference='',
        status=EcoCashTransaction.STATUS_PENDING,
    )
    return tx


def get_econet_number():
    return getattr(settings, 'ECOCASH_ECONET_NUMBER', '')


def get_merchant_name():
    return getattr(settings, 'ECOCASH_MERCHANT_NAME', '')
