from decimal import Decimal
from django.db import models, transaction
from django.conf import settings
from django.utils import timezone


class PurchaseOrder(models.Model):
    STATUS_DRAFT     = 'draft'
    STATUS_ORDERED   = 'ordered'
    STATUS_PARTIAL   = 'partial'
    STATUS_RECEIVED  = 'received'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_DRAFT,     'Draft'),
        (STATUS_ORDERED,   'Ordered'),
        (STATUS_PARTIAL,   'Partially Received'),
        (STATUS_RECEIVED,  'Fully Received'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    supplier          = models.ForeignKey('inventory.Supplier', on_delete=models.PROTECT, related_name='purchase_orders')
    joint             = models.ForeignKey('inventory.Joint', on_delete=models.PROTECT, related_name='purchase_orders')
    order_number      = models.CharField(max_length=50, unique=True, blank=True)
    order_date        = models.DateField(default=timezone.localdate)
    expected_delivery = models.DateField(null=True, blank=True)
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    notes             = models.TextField(blank=True)
    created_by        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='purchase_orders_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name        = 'Purchase Order'
        verbose_name_plural = 'Purchase Orders'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['joint', 'status']),
        ]

    def __str__(self):
        return f"{self.order_number} — {self.supplier.name} → {self.joint.display_name}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self._generate_order_number()
        super().save(*args, **kwargs)

    def _generate_order_number(self):
        last = PurchaseOrder.objects.filter(
            order_number__startswith='PO-'
        ).order_by('-pk').first()
        num = 1
        if last and last.order_number:
            try:
                num = int(last.order_number.split('-')[1]) + 1
            except (IndexError, ValueError):
                pass
        return f"PO-{str(num).zfill(5)}"

    @property
    def total_cost(self):
        return sum(item.total_cost for item in self.items.all())

    @property
    def total_received_cost(self):
        return sum(item.received_cost for item in self.items.all())

    @property
    def is_fully_received(self):
        return all(item.is_fully_received for item in self.items.all())

    @property
    def is_partially_received(self):
        return any(item.quantity_received > 0 for item in self.items.all())

    def mark_ordered(self):
        if self.status != self.STATUS_DRAFT:
            raise ValueError("Only draft orders can be marked as ordered.")
        self.status = self.STATUS_ORDERED
        self.save()

    def refresh_status(self):
        """Recalculate status based on received quantities. Called after each GRN."""
        if self.is_fully_received:
            self.status = self.STATUS_RECEIVED
        elif self.is_partially_received:
            self.status = self.STATUS_PARTIAL
        self.save(update_fields=['status', 'updated_at'])

    def cancel(self, user):
        if self.status in (self.STATUS_RECEIVED,):
            raise ValueError("Cannot cancel a fully received order.")
        self.status = self.STATUS_CANCELLED
        self.save()


class PurchaseOrderItem(models.Model):
    purchase_order   = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    product          = models.ForeignKey('inventory.Product', on_delete=models.PROTECT)
    quantity_ordered = models.PositiveIntegerField()
    unit_cost        = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_received = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'PO Line Item'

    def __str__(self):
        return f"{self.quantity_ordered}× {self.product.name} @ ${self.unit_cost}"

    @property
    def total_cost(self):
        return self.quantity_ordered * self.unit_cost

    @property
    def received_cost(self):
        return self.quantity_received * self.unit_cost

    @property
    def pending_quantity(self):
        return max(0, self.quantity_ordered - self.quantity_received)

    @property
    def is_fully_received(self):
        return self.quantity_received >= self.quantity_ordered


class GoodsReceivedNote(models.Model):
    purchase_order     = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name='grns')
    grn_number         = models.CharField(max_length=50, unique=True, blank=True)
    received_by        = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='grns_received'
    )
    received_date      = models.DateField(default=timezone.localdate)
    supplier_reference = models.CharField(max_length=100, blank=True, help_text="Supplier invoice / delivery note #")
    notes              = models.TextField(blank=True)
    created_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name        = 'Goods Received Note'
        verbose_name_plural = 'Goods Received Notes'

    def __str__(self):
        return f"{self.grn_number} — {self.purchase_order.order_number}"

    def save(self, *args, **kwargs):
        if not self.grn_number:
            self.grn_number = self._generate_grn_number()
        super().save(*args, **kwargs)

    def _generate_grn_number(self):
        last = GoodsReceivedNote.objects.filter(
            grn_number__startswith='GRN-'
        ).order_by('-pk').first()
        num = 1
        if last and last.grn_number:
            try:
                num = int(last.grn_number.split('-')[1]) + 1
            except (IndexError, ValueError):
                pass
        return f"GRN-{str(num).zfill(5)}"

    @property
    def total_cost(self):
        return sum(item.line_cost for item in self.items.all())

    def apply_to_stock(self):
        """
        Update stock levels and PO received quantities.
        Called inside an atomic block after the GRN is saved.
        """
        with transaction.atomic():
            for grn_item in self.items.select_related(
                'po_item__product__stock', 'po_item__purchase_order'
            ).all():
                # Add to inventory
                stock = grn_item.po_item.product.stock
                stock.add(grn_item.quantity_received)

                # Update PO line received qty
                po_item = grn_item.po_item
                po_item.quantity_received = min(
                    po_item.quantity_ordered,
                    po_item.quantity_received + grn_item.quantity_received,
                )
                po_item.save(update_fields=['quantity_received'])

            # Recalculate PO status
            self.purchase_order.refresh_status()


class GRNItem(models.Model):
    grn               = models.ForeignKey(GoodsReceivedNote, on_delete=models.CASCADE, related_name='items')
    po_item           = models.ForeignKey(PurchaseOrderItem, on_delete=models.PROTECT, related_name='grn_items')
    quantity_received = models.PositiveIntegerField()
    unit_cost         = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        verbose_name = 'GRN Line Item'

    def __str__(self):
        return f"{self.quantity_received}× {self.po_item.product.name}"

    @property
    def line_cost(self):
        return self.quantity_received * self.unit_cost