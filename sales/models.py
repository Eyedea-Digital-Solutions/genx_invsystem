from django.db import models
from django.conf import settings
from django.utils import timezone
from inventory.models import Product, Joint


class Sale(models.Model):
    PAYMENT_CHOICES = [
        ('cash', 'Cash'),
        ('ecocash', 'EcoCash'),
        ('card', 'Card'),
        ('mixed', 'Mixed (Cash + EcoCash)'),
    ]

    SALE_TYPE_CHOICES = [
        ('system', 'System Sale'),
        ('manual', 'Manual Sale (Receipt Upload)'),
        ('pos', 'POS Sale'),
    ]

    joint = models.ForeignKey(Joint, on_delete=models.PROTECT, related_name='sales')
    sold_by = models.ForeignKey(
        'users.User', on_delete=models.PROTECT, related_name='sales_made'
    )
    sale_date = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='cash')
    sale_type = models.CharField(max_length=20, choices=SALE_TYPE_CHOICES, default='system')
    manual_receipt_image = models.ImageField(
        upload_to='manual_receipts/%Y/%m/', null=True, blank=True
    )
    customer_name = models.CharField(max_length=200, blank=True)
    customer_phone = models.CharField(max_length=30, blank=True)   # ← NEW
    notes = models.TextField(blank=True)
    receipt_number = models.CharField(max_length=50, unique=True, blank=True)

    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_type = models.CharField(
        max_length=20,
        choices=[('fixed', 'Fixed $'), ('percent', 'Percentage %')],
        blank=True
    )
    discount_label = models.CharField(max_length=200, blank=True)
    promotion_applied = models.ForeignKey(
        'promotions.Promotion', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='sales'
    )

    is_held = models.BooleanField(default=False)
    held_at = models.DateTimeField(null=True, blank=True)

    @property
    def subtotal(self):
        return sum(item.line_total for item in self.items.all())

    @property
    def total_amount(self):
        sub = self.subtotal
        if self.discount_type == 'percent':
            from decimal import Decimal
            return (sub * (1 - self.discount_amount / 100)).quantize(Decimal('0.01'))
        return max(0, sub - self.discount_amount)

    def generate_receipt_number(self):
        prefix_map = {
            'eyedentity': 'EYE',
            'genx': 'GNX',
            'armor_sole': 'ARM',
        }
        prefix = prefix_map.get(self.joint.name, 'SAL')
        last_sale = Sale.objects.filter(
            joint=self.joint,
            receipt_number__startswith=prefix
        ).order_by('-pk').first()

        if last_sale and last_sale.receipt_number:
            try:
                last_num = int(last_sale.receipt_number.split('-')[1])
                new_num = last_num + 1
            except (IndexError, ValueError):
                new_num = 1
        else:
            new_num = 1

        return f"{prefix}-{str(new_num).zfill(4)}"

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = self.generate_receipt_number()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Receipt {self.receipt_number} - {self.joint.display_name} - {self.sale_date.strftime('%d/%m/%Y')}"

    class Meta:
        ordering = ['-sale_date']
        indexes = [
            models.Index(fields=['joint', 'sale_date']),
            models.Index(fields=['sold_by', 'sale_date']),
            models.Index(fields=['is_held']),
        ]


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='sale_items')
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_free_gift = models.BooleanField(default=False)
    promotion_label = models.CharField(max_length=200, blank=True)

    @property
    def line_total(self):
        if self.is_free_gift:
            return 0
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.quantity}x {self.product.name} @ ${self.unit_price}"


class SaleAuditLog(models.Model):
    sale = models.OneToOneField(Sale, on_delete=models.PROTECT, related_name='audit_log')
    action = models.CharField(max_length=50, default='created')
    performed_by = models.ForeignKey('users.User', on_delete=models.PROTECT)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict)

    def __str__(self):
        return f"Audit: {self.sale.receipt_number} by {self.performed_by.username}"

    class Meta:
        ordering = ['-timestamp']