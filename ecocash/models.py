from django.db import models
from django.utils import timezone


class EcoCashTransaction(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_CONFIRMED, 'Confirmed'),
        (STATUS_FAILED, 'Failed'),
    ]

    sale = models.OneToOneField(
        'sales.Sale',
        on_delete=models.PROTECT,
        related_name='ecocash_transaction',
    )
    phone_number = models.CharField(max_length=20, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='ecocash_confirmations',
    )

    def confirm(self, user):
        self.status = self.STATUS_CONFIRMED
        self.confirmed_at = timezone.now()
        self.confirmed_by = user
        self.save()

    def mark_failed(self, notes=''):
        self.status = self.STATUS_FAILED
        if notes:
            self.notes = notes
        self.save()

    def __str__(self):
        return f"EcoCash {self.reference or 'pending'} – ${self.amount} ({self.status})"

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'EcoCash Transaction'
