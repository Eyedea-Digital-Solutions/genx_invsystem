from decimal import Decimal
from django.db import models, transaction
from django.conf import settings
from django.utils import timezone


class Return(models.Model):
    REFUND_CASH         = 'cash'
    REFUND_STORE_CREDIT = 'store_credit'
    REFUND_REVERSAL     = 'reversal'

    REFUND_TYPE_CHOICES = [
        (REFUND_CASH,         'Cash Refund'),
        (REFUND_STORE_CREDIT, 'Store Credit (Loyalty Points)'),
        (REFUND_REVERSAL,     'Payment Reversal'),
    ]

    STATUS_PENDING   = 'pending'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING,   'Pending'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    original_sale = models.ForeignKey(
        'sales.Sale', on_delete=models.PROTECT, related_name='returns'
    )
    return_date  = models.DateTimeField(default=timezone.now)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='returns_processed'
    )
    refund_type         = models.CharField(max_length=20, choices=REFUND_TYPE_CHOICES)
    reason              = models.CharField(max_length=200)
    notes               = models.TextField(blank=True)
    status              = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    total_refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    created_at          = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name        = 'Return'
        verbose_name_plural = 'Returns & Refunds'

    def __str__(self):
        return f"Return #{self.pk} for {self.original_sale.receipt_number}"

    @property
    def return_number(self):
        return f"RET-{str(self.pk).zfill(4)}"

    def process(self, restock=True):
        """
        Mark return as completed.
        - Restocks items (if restock=True and item.restock=True)
        - Awards store credit as loyalty points (if refund_type = store_credit)
        - Creates an audit log entry
        """
        with transaction.atomic():
            if self.status != self.STATUS_PENDING:
                raise ValueError("Only pending returns can be processed.")

            total = Decimal('0')
            for item in self.items.select_related('original_item__product__stock').all():
                if item.original_item.product and item.restock:
                    item.original_item.product.stock.add(item.quantity_returned)
                total += item.total_refund

            self.total_refund_amount = total
            self.status = self.STATUS_COMPLETED
            self.save()

            # Award loyalty points for store credit refunds
            if self.refund_type == self.REFUND_STORE_CREDIT:
                customer = self.original_sale.customer
                if customer:
                    points = int(total)   # 1 point per $1 refund
                    customer.add_loyalty_points(
                        points,
                        reason=f'Store credit for return #{self.pk}',
                        performed_by=self.processed_by,
                    )

            ReturnAuditLog.objects.create(
                return_record=self,
                action='processed',
                performed_by=self.processed_by,
                details={
                    'total_refund':  str(total),
                    'refund_type':   self.refund_type,
                    'items_count':   self.items.count(),
                }
            )

    def cancel(self, user, reason=''):
        if self.status != self.STATUS_PENDING:
            raise ValueError("Only pending returns can be cancelled.")
        self.status = self.STATUS_CANCELLED
        self.save()
        ReturnAuditLog.objects.create(
            return_record=self,
            action='cancelled',
            performed_by=user,
            details={'reason': reason},
        )


class ReturnItem(models.Model):
    return_record     = models.ForeignKey(Return, on_delete=models.CASCADE, related_name='items')
    original_item     = models.ForeignKey(
        'sales.SaleItem', on_delete=models.PROTECT, related_name='return_items'
    )
    quantity_returned = models.PositiveIntegerField()
    unit_refund_amount = models.DecimalField(max_digits=10, decimal_places=2)
    restock           = models.BooleanField(default=True, help_text='Add returned stock back to inventory')

    class Meta:
        verbose_name        = 'Return Item'
        verbose_name_plural = 'Return Items'

    def __str__(self):
        name = self.original_item.product.name if self.original_item.product else '(deleted)'
        return f"{self.quantity_returned}× {name}"

    @property
    def total_refund(self):
        return self.quantity_returned * self.unit_refund_amount

    @property
    def max_returnable(self):
        """How many of this item can still be returned (original qty minus prior returns)."""
        already_returned = (
            ReturnItem.objects
            .filter(
                original_item=self.original_item,
                return_record__status=Return.STATUS_COMPLETED,
            )
            .exclude(pk=self.pk)
            .aggregate(t=models.Sum('quantity_returned'))['t'] or 0
        )
        return self.original_item.quantity - already_returned


class ReturnAuditLog(models.Model):
    return_record = models.ForeignKey(Return, on_delete=models.CASCADE, related_name='audit_logs')
    action        = models.CharField(max_length=50)
    performed_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    details   = models.JSONField(default=dict)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.return_record} — {self.action}"