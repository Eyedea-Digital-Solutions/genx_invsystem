from django.db import models
from django.conf import settings
from django.utils import timezone


class Joint(models.Model):
    """
    A 'Joint' is one of the three shops: Eyedentity, GenX, or Armor Sole.
    Everything in the system belongs to a joint.
    """

    JOINT_CHOICES = [
        ('eyedentity', 'Eyedentity'),
        ('genx', 'GenX'),
        ('armor_sole', 'Armor Sole'),
    ]

    name = models.CharField(
        max_length=50,
        choices=JOINT_CHOICES,
        unique=True,
        help_text="The name/identifier of this shop."
    )
    display_name = models.CharField(max_length=100, help_text="Full display name, e.g. 'Eyedentity - Zee Eyewear'")
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    uses_product_codes = models.BooleanField(
        default=False,
        help_text="Eyedentity and Armor Sole use product codes; GenX does not."
    )

    def __str__(self):
        return self.display_name

    class Meta:
        ordering = ['name']


class Product(models.Model):
    """
    A product sold at one of the joints.
    Eyedentity and Armor Sole use product codes; GenX uses just names.
    """

    joint = models.ForeignKey(Joint, on_delete=models.CASCADE, related_name='products')
    code = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Product code (required for Eyedentity and Armor Sole)."
    )
    name = models.CharField(max_length=200, help_text="Product name or description.")
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Selling price in USD."
    )
    is_active = models.BooleanField(default=True, help_text="Uncheck to hide from sales without deleting.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.code:
            return f"[{self.code}] {self.name}"
        return self.name

    @property
    def current_stock(self):
        """Returns the current stock quantity for this product."""
        try:
            return self.stock.quantity
        except Stock.DoesNotExist:
            return 0

    @property
    def is_low_stock(self):
        """Returns True if stock is at or below the low stock threshold."""
        return self.current_stock <= settings.LOW_STOCK_THRESHOLD

    class Meta:
        ordering = ['joint', 'name']
        unique_together = [['joint', 'code']]  # Codes must be unique per joint


class Stock(models.Model):
    """
    Tracks stock levels for each product.
    One Stock record per Product (OneToOne relationship).
    Stock is automatically deducted when a sale is made.
    """

    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='stock')
    quantity = models.IntegerField(default=0, help_text="Current quantity in stock.")
    last_stock_take = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date and time of the last monthly stock take."
    )
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} - Qty: {self.quantity}"

    def deduct(self, qty):
        """
        Deducts stock when a sale is made.
        This is called automatically — do NOT call manually from outside.
        """
        if self.quantity < qty:
            raise ValueError(f"Insufficient stock. Available: {self.quantity}, Requested: {qty}")
        self.quantity -= qty
        self.save()

    def add(self, qty):
        """Adds stock (used during stock take or when receiving new stock)."""
        self.quantity += qty
        self.save()

    class Meta:
        verbose_name = 'Stock Level'


class StockTake(models.Model):
    """
    Records monthly stock takes.
    When a stock take is done, we log who did it, when, and what the count was.
    Stock takes CANNOT be undone once saved.
    """

    joint = models.ForeignKey(Joint, on_delete=models.CASCADE, related_name='stock_takes')
    conducted_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='stock_takes_conducted'
    )
    conducted_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Stock Take - {self.joint.display_name} - {self.conducted_at.strftime('%B %Y')}"

    class Meta:
        ordering = ['-conducted_at']


class StockTakeItem(models.Model):
    """
    Individual product counts within a stock take.
    Records what the actual count was vs what the system said.
    """

    stock_take = models.ForeignKey(StockTake, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    system_count = models.IntegerField(help_text="What the system showed before the stock take.")
    actual_count = models.IntegerField(help_text="The physical count during the stock take.")

    @property
    def variance(self):
        """Difference between system count and actual count."""
        return self.actual_count - self.system_count

    def __str__(self):
        return f"{self.product.name}: System={self.system_count}, Actual={self.actual_count}"


class StockTransfer(models.Model):
    """
    Records stock transfers between joints (shops).
    For example, moving 5 pairs of shoes from Armor Sole to GenX.
    """

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
    ]

    from_joint = models.ForeignKey(Joint, on_delete=models.CASCADE, related_name='transfers_out')
    to_joint = models.ForeignKey(Joint, on_delete=models.CASCADE, related_name='transfers_in')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    transferred_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, related_name='stock_transfers')
    transferred_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Transfer: {self.product.name} x{self.quantity} ({self.from_joint} → {self.to_joint})"

    class Meta:
        ordering = ['-transferred_at']
