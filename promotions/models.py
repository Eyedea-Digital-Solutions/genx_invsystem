from django.db import models
from django.utils import timezone


class Promotion(models.Model):
    TYPE_CHOICES = [
        ('spend_threshold', 'Spend Threshold Discount'),
        ('free_gift', 'Free Gift with Purchase'),
        ('buy_n_get_n', 'Buy N Get N Free'),
        ('bundle', 'Bundle Discount'),
    ]

    name = models.CharField(max_length=200)
    promo_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    is_active = models.BooleanField(default=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    joint = models.ForeignKey(
        'inventory.Joint', on_delete=models.CASCADE, null=True, blank=True
    )
    created_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL, null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_currently_active(self):
        today = timezone.now().date()
        if not self.is_active:
            return False
        if self.start_date and today < self.start_date:
            return False
        if self.end_date and today > self.end_date:
            return False
        return True

    @property
    def status_label(self):
        today = timezone.now().date()
        if not self.is_active:
            return 'inactive'
        if self.start_date and today < self.start_date:
            return 'upcoming'
        if self.end_date and today > self.end_date:
            return 'expired'
        return 'active'

    def __str__(self):
        return f"{self.name} ({self.get_promo_type_display()})"

    class Meta:
        ordering = ['-created_at']


class SpendThresholdPromo(models.Model):
    promotion = models.OneToOneField(
        Promotion, on_delete=models.CASCADE, related_name='spend_threshold'
    )
    min_cart_value = models.DecimalField(max_digits=10, decimal_places=2)
    discount_type = models.CharField(
        max_length=10,
        choices=[('fixed', 'Fixed $'), ('percent', 'Percentage %')]
    )
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Spend ${self.min_cart_value} → {self.discount_type} {self.discount_value} off"


class FreeGiftPromo(models.Model):
    promotion = models.OneToOneField(
        Promotion, on_delete=models.CASCADE, related_name='free_gift'
    )
    trigger_product = models.ForeignKey(
        'inventory.Product', on_delete=models.CASCADE, related_name='triggers_free_gift'
    )
    trigger_quantity = models.PositiveIntegerField(default=1)
    gift_product = models.ForeignKey(
        'inventory.Product', on_delete=models.CASCADE,
        related_name='given_as_free_gift', null=True, blank=True
    )
    gift_quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        gift = self.gift_product.name if self.gift_product else "itself"
        return f"Buy {self.trigger_quantity}× {self.trigger_product.name} → {self.gift_quantity}× {gift} FREE"


class BundlePromo(models.Model):
    promotion = models.OneToOneField(
        Promotion, on_delete=models.CASCADE, related_name='bundle'
    )
    bundle_price = models.DecimalField(max_digits=10, decimal_places=2)
    products = models.ManyToManyField('inventory.Product', related_name='bundle_promos')

    def __str__(self):
        names = ', '.join(p.name for p in self.products.all())
        return f"Bundle: {names} = ${self.bundle_price}"
