from django.db import models


class EcoCashTransaction(models.Model):
    """
    Records an EcoCash payment associated with a sale.
    
    Since you're using an Econet number (not a merchant API), the flow is:
    1. Customer pays to your EcoCash number
    2. You (or system) record the transaction reference number
    3. This record links the payment to a sale for reconciliation
    
    The system generates a payment reference that the customer quotes when paying.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending - Awaiting Payment'),
        ('confirmed', 'Confirmed'),
        ('failed', 'Failed'),
    ]

    sale = models.OneToOneField('sales.Sale', on_delete=models.PROTECT, related_name='ecocash_transaction')

    # Your EcoCash number (the Econet number customers pay to)
    econet_number = models.CharField(
        max_length=20,
        help_text="Your EcoCash number that the customer paid to."
    )

    # Amount that should be paid
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    # Transaction reference from EcoCash (provided by customer after payment)
    transaction_reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="EcoCash transaction reference number (e.g. from customer's SMS receipt)."
    )

    # Payment status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # When the payment was confirmed
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ecocash_confirmations'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"EcoCash: {self.sale.receipt_number} - ${self.amount} ({self.get_status_display()})"

    class Meta:
        ordering = ['-created_at']