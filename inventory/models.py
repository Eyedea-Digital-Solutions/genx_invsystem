from django.db import models
from django.conf import settings
from django.utils import timezone


class Joint(models.Model):
    JOINT_CHOICES = [
        ('eyedentity', 'Eyedentity'),
        ('genx', 'GenX'),
        ('armor_sole', 'Armor Sole'),
    ]

    name = models.CharField(max_length=50, choices=JOINT_CHOICES, unique=True)
    display_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    uses_product_codes = models.BooleanField(default=False)

    def __str__(self):
        return self.display_name

    class Meta:
        ordering = ['name']


class Supplier(models.Model):
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Category(models.Model):
    joint = models.ForeignKey(Joint, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=20, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.joint.display_name} › {self.name}"

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'Categories'


class Product(models.Model):
    joint = models.ForeignKey(Joint, on_delete=models.CASCADE, related_name='products')
    code = models.CharField(max_length=50, blank=True, null=True)
    name = models.CharField(max_length=200)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    barcode = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True)
    image = models.ImageField(upload_to='products/', null=True, blank=True)

    sale_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    sale_start = models.DateField(null=True, blank=True)
    sale_end = models.DateField(null=True, blank=True)

    is_clearance = models.BooleanField(default=False)
    clearance_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        if self.code:
            return f"[{self.code}] {self.name}"
        return self.name

    @property
    def effective_price(self):
        today = timezone.now().date()
        if self.is_clearance and self.clearance_price:
            return self.clearance_price
        if self.sale_price:
            in_date = True
            if self.sale_start and today < self.sale_start:
                in_date = False
            if self.sale_end and today > self.sale_end:
                in_date = False
            if in_date:
                return self.sale_price
        return self.price

    @property
    def promotion_label(self):
        today = timezone.now().date()
        if self.is_clearance:
            return 'CLEARANCE'
        if self.sale_price:
            in_date = True
            if self.sale_start and today < self.sale_start:
                in_date = False
            if self.sale_end and today > self.sale_end:
                in_date = False
            if in_date:
                return 'SALE'
        return None

    @property
    def current_stock(self):
        try:
            return self.stock.quantity
        except Stock.DoesNotExist:
            return 0

    @property
    def is_low_stock(self):
        try:
            threshold = self.stock.min_quantity
        except Stock.DoesNotExist:
            threshold = getattr(settings, 'LOW_STOCK_THRESHOLD', 3)
        return self.current_stock <= threshold

    class Meta:
        ordering = ['joint', 'name']
        unique_together = [['joint', 'code']]
        indexes = [
            models.Index(fields=['barcode']),
            models.Index(fields=['joint', 'is_active']),
            models.Index(fields=['is_clearance']),
            models.Index(fields=['joint', 'is_active', 'is_clearance']),
        ]


class Stock(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='stock')
    quantity = models.IntegerField(default=0)
    min_quantity = models.IntegerField(default=3)
    reorder_level = models.IntegerField(default=10)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    batch_number = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    last_stock_take = models.DateTimeField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.name} - Qty: {self.quantity}"

    @property
    def is_expiring_soon(self):
        from datetime import date, timedelta
        if not self.expiry_date:
            return False
        return self.expiry_date <= date.today() + timedelta(days=30)

    def deduct(self, qty):
        if self.quantity < qty:
            raise ValueError(f"Insufficient stock. Available: {self.quantity}, Requested: {qty}")
        self.quantity -= qty
        self.save()

    def add(self, qty):
        self.quantity += qty
        self.save()

    class Meta:
        verbose_name = 'Stock Level'


class StockTake(models.Model):
    joint = models.ForeignKey(Joint, on_delete=models.CASCADE, related_name='stock_takes')
    conducted_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL, null=True, related_name='stock_takes_conducted'
    )
    conducted_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Stock Take - {self.joint.display_name} - {self.conducted_at.strftime('%B %Y')}"

    class Meta:
        ordering = ['-conducted_at']


class StockTakeItem(models.Model):
    stock_take = models.ForeignKey(StockTake, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    system_count = models.IntegerField()
    actual_count = models.IntegerField()

    @property
    def variance(self):
        return self.actual_count - self.system_count

    def __str__(self):
        return f"{self.product.name}: System={self.system_count}, Actual={self.actual_count}"


class StockTransfer(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
    ]

    from_joint = models.ForeignKey(Joint, on_delete=models.CASCADE, related_name='transfers_out')
    to_joint = models.ForeignKey(Joint, on_delete=models.CASCADE, related_name='transfers_in')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    transferred_by = models.ForeignKey(
        'users.User', on_delete=models.SET_NULL, null=True, related_name='stock_transfers'
    )
    transferred_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Transfer: {self.product.name} x{self.quantity} ({self.from_joint} → {self.to_joint})"

    class Meta:
        ordering = ['-transferred_at']

class ProductFreeAccessory(models.Model):
   
    trigger_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='free_accessories',
        help_text='When this product is added to cart, the accessory is auto-added for free',
    )
    accessory_product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='given_as_free_with',
        help_text='The product given for free (must belong to same joint)',
    )
    quantity = models.PositiveIntegerField(
        default=1,
        help_text='How many free units come with each unit of the trigger product',
    )
    label = models.CharField(
        max_length=200, blank=True,
        help_text='Receipt label, e.g. "Free case with purchase". Defaults to accessory name.',
    )
    is_active = models.BooleanField(default=True)

    def get_label(self):
        return self.label or f"Free {self.accessory_product.name}"

    def __str__(self):
        return (
            f"{self.trigger_product.name} → FREE {self.accessory_product.name} "
            f"×{self.quantity} [{self.trigger_product.joint.display_name}]"
        )

    class Meta:
        verbose_name = 'Free Accessory Bundle'
        verbose_name_plural = 'Free Accessory Bundles'
        ordering = ['trigger_product__name']
        constraints = [
            models.UniqueConstraint(
                fields=['trigger_product', 'accessory_product'],
                name='unique_trigger_accessory_pair',
            )
        ]