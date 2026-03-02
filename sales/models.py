from django.db import models
from django.conf import settings
from django.utils import timezone
from inventory.models import Product, Joint


class Sale(models.Model):
    """
    Records a sale made at one of the joints.

    IMPORTANT: Sales are IMMUTABLE. Once saved, they cannot be deleted or modified.
    This enforces data integrity and provides a proper audit trail.

    Two types of sales:
    1. System sale: Made directly in the system (stock auto-deducted)
    2. Manual sale: Uploaded photo of a manual receipt (for cases where sale was made manually)
    """

    PAYMENT_CHOICES = [
        ('cash', 'Cash'),
        ('ecocash', 'EcoCash'),
        ('card', 'Card'),
        ('mixed', 'Mixed (Cash + EcoCash)'),
    ]

    SALE_TYPE_CHOICES = [
        ('system', 'System Sale'),
        ('manual', 'Manual Sale (Receipt Upload)'),
    ]

    # Which joint made this sale
    joint = models.ForeignKey(Joint, on_delete=models.PROTECT, related_name='sales')

    # Who made the sale (cannot be null — we always track this)
    sold_by = models.ForeignKey(
        'users.User',
        on_delete=models.PROTECT,
        related_name='sales_made',
        help_text="The staff member who processed this sale."
    )

    # When the sale happened
    sale_date = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    # Payment details
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default='cash')
    sale_type = models.CharField(max_length=20, choices=SALE_TYPE_CHOICES, default='system')

    # For manual sales: photo of the manual receipt
    manual_receipt_image = models.ImageField(
        upload_to='manual_receipts/%Y/%m/',
        null=True,
        blank=True,
        help_text="Photo of the manual receipt (for manual sales only)."
    )

    # Optional customer name
    customer_name = models.CharField(max_length=200, blank=True, help_text="Optional customer name.")

    # Notes
    notes = models.TextField(blank=True)

    # Receipt number (auto-generated)
    receipt_number = models.CharField(max_length=50, unique=True, blank=True)

    @property
    def total_amount(self):
        """Calculate total from all sale items."""
        return sum(item.line_total for item in self.items.all())

    def generate_receipt_number(self):
        """
        Generate a unique receipt number for this sale.
        Format: GNX-0001, EYE-0001, ARM-0001
        Orders by pk (creation order) to avoid string-sort issues.
        """
        prefix_map = {
            'eyedentity': 'EYE',
            'genx': 'GNX',
            'armor_sole': 'ARM',
        }
        prefix = prefix_map.get(self.joint.name, 'SAL')
        # Order by pk desc (not receipt_number string, which sorts incorrectly)
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


class SaleItem(models.Model):
    """
    A single line item within a sale.
    For example: 1x Ray-Ban Aviators @ $45.00
    Each Sale can have multiple SaleItems.
    """

    sale = models.ForeignKey(Sale, on_delete=models.PROTECT, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='sale_items')

    # We store the price AT TIME OF SALE in case price changes later
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price per unit at time of sale (snapshot, in case price changes later)."
    )

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.quantity}x {self.product.name} @ ${self.unit_price}"

    class Meta:
        pass


class SaleAuditLog(models.Model):
    """
    Immutable audit log for all sales.
    Every sale creation is logged here automatically.
    This record can never be deleted.
    """

    sale = models.OneToOneField(Sale, on_delete=models.PROTECT, related_name='audit_log')
    action = models.CharField(max_length=50, default='created')
    performed_by = models.ForeignKey('users.User', on_delete=models.PROTECT)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict, help_text="JSON snapshot of the sale at creation time.")

    def __str__(self):
        return f"Audit: {self.sale.receipt_number} by {self.performed_by.username}"

    class Meta:
        ordering = ['-timestamp']
