from django.db import models
from django.utils import timezone
from django.db.models import Q


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

class CategoryTierFreeRule(models.Model):
    name        = models.CharField(max_length=120,
                                   help_text='Internal label, e.g. "Glasses tier 1 (<$12)"')
    category    = models.ForeignKey(
        'inventory.Category', on_delete=models.CASCADE,
        related_name='tier_free_rules',
        help_text='Products in this category trigger the rule',
    )
    joint       = models.ForeignKey(
        'inventory.Joint', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='tier_free_rules',
        help_text='Leave blank to apply to ALL branches',
    )
    min_price   = models.DecimalField(max_digits=10, decimal_places=2)
    max_price   = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Leave blank for no upper limit (i.e. $X and above)',
    )
    label       = models.CharField(
        max_length=120, blank=True,
        help_text='Label shown on cart / receipt, e.g. "Free pouch & wipe"',
    )
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['category', 'min_price']
        verbose_name = 'Category tier free rule'

    def __str__(self):
        joint_tag = f' [{self.joint}]' if self.joint else ' [all branches]'
        upper = f'–${self.max_price}' if self.max_price is not None else '+'
        return f'{self.name}  ${self.min_price}{upper}{joint_tag}'

    def matches_price(self, unit_price):
        """Return True if unit_price falls within this tier."""
        from decimal import Decimal
        price = Decimal(str(unit_price))
        if price < self.min_price:
            return False
        if self.max_price is not None and price >= self.max_price:
            return False
        return True

    def applies_to_joint(self, joint_id):
        """Return True if this rule covers the given joint."""
        return self.joint_id is None or str(self.joint_id) == str(joint_id)


class CategoryTierFreeItem(models.Model):
    rule     = models.ForeignKey(
        CategoryTierFreeRule, on_delete=models.CASCADE, related_name='free_items',
    )
    product  = models.ForeignKey(
        'inventory.Product', on_delete=models.CASCADE,
        related_name='given_free_by_tier',
    )
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.quantity}× {self.product.name} (rule: {self.rule.name})'

class Bundle(models.Model):
    name        = models.CharField(max_length=200)
    sku         = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    price       = models.DecimalField(max_digits=10, decimal_places=2)
    joints      = models.ManyToManyField(
        'inventory.Joint', blank=True,
        related_name='bundles',
        help_text='Select branches. Leave empty to make available in ALL branches.',
    )
    is_active   = models.BooleanField(default=True)
    image       = models.ImageField(upload_to='bundles/', null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} (${self.price})'

    def is_available_in(self, joint_id):
        """True if this bundle is available in the given joint."""
        if not self.joints.exists():
            return True  # cross-branch
        return self.joints.filter(pk=joint_id).exists()

    def effective_stock(self, joint_id):
        """
        Min sellable-unit stock across all components in the given joint.
        Returns 0 if any component is unavailable.
        """
        from inventory.models import Product
        min_units = None
        for item in self.items.select_related('product__stock').all():
            try:
                p = Product.objects.select_related('stock').get(
                    pk=item.product_id, joint_id=joint_id,
                )
            except Product.DoesNotExist:
                return 0
            units = p.current_stock // item.quantity
            if min_units is None or units < min_units:
                min_units = units
        return min_units or 0


class BundleItem(models.Model):
    bundle   = models.ForeignKey(Bundle, on_delete=models.CASCADE, related_name='items')
    product  = models.ForeignKey(
        'inventory.Product', on_delete=models.CASCADE, related_name='in_bundles',
    )
    quantity = models.PositiveIntegerField(default=1)
    is_free  = models.BooleanField(
        default=False,
        help_text='If True, this item is shown at $0 on the receipt (price absorbed into bundle)',
    )

    class Meta:
        ordering = ['is_free', 'id']   # paid items first

    def __str__(self):
        tag = ' [free]' if self.is_free else ''
        return f'{self.quantity}× {self.product.name}{tag}'