from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone


class Customer(models.Model):
    TYPE_REGULAR   = 'regular'
    TYPE_WHOLESALE = 'wholesale'
    TYPE_VIP       = 'vip'
    TYPE_STAFF     = 'staff'

    TYPE_CHOICES = [
        (TYPE_REGULAR,   'Regular'),
        (TYPE_WHOLESALE, 'Wholesale'),
        (TYPE_VIP,       'VIP'),
        (TYPE_STAFF,     'Staff'),
    ]

    name          = models.CharField(max_length=200)
    phone         = models.CharField(max_length=30, blank=True, db_index=True)
    email         = models.EmailField(blank=True)
    address       = models.TextField(blank=True)
    customer_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_REGULAR)
    loyalty_points = models.IntegerField(default=0)
    notes         = models.TextField(blank=True)
    is_active     = models.BooleanField(default=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        indexes  = [
            models.Index(fields=['phone']),
            models.Index(fields=['customer_type']),
        ]

    def __str__(self):
        return f"{self.name} ({self.phone})" if self.phone else self.name

    # ── aggregated purchase stats ──────────────────────────────────────────
    @property
    def total_spend(self):
        # `Sale.total_amount` is a Python property (computed), not a DB field,
        # so we can't aggregate it via the ORM. Compute in Python instead.
        total = Decimal('0')
        for s in self.sales.filter(is_held=False):
            try:
                total += Decimal(s.total_amount)
            except Exception:
                # fallback: skip malformed entries
                continue
        return total

    @property
    def purchase_count(self):
        return self.sales.filter(is_held=False).count()

    @property
    def last_purchase(self):
        return self.sales.filter(is_held=False).order_by('-sale_date').first()

    # ── loyalty helpers ────────────────────────────────────────────────────
    def add_loyalty_points(self, points, reason='', sale=None, performed_by=None):
        """Earn points (e.g. $1 spent = 1 point). Creates a transaction log."""
        self.loyalty_points += points
        self.save(update_fields=['loyalty_points', 'updated_at'])
        LoyaltyTransaction.objects.create(
            customer=self,
            transaction_type=LoyaltyTransaction.TYPE_EARN,
            points=points,
            balance_after=self.loyalty_points,
            reason=reason or f'Purchase',
            sale=sale,
            performed_by=performed_by,
        )

    def redeem_loyalty_points(self, points, reason='', performed_by=None):
        """Redeem points. Raises ValueError if insufficient balance."""
        if self.loyalty_points < points:
            raise ValueError(f"Insufficient points. Balance: {self.loyalty_points}")
        self.loyalty_points -= points
        self.save(update_fields=['loyalty_points', 'updated_at'])
        LoyaltyTransaction.objects.create(
            customer=self,
            transaction_type=LoyaltyTransaction.TYPE_REDEEM,
            points=-points,
            balance_after=self.loyalty_points,
            reason=reason or 'Points redeemed',
            performed_by=performed_by,
        )

    def adjust_loyalty_points(self, points, reason, performed_by=None):
        """Manual positive or negative adjustment by a manager."""
        self.loyalty_points = max(0, self.loyalty_points + points)
        self.save(update_fields=['loyalty_points', 'updated_at'])
        LoyaltyTransaction.objects.create(
            customer=self,
            transaction_type=LoyaltyTransaction.TYPE_ADJUST,
            points=points,
            balance_after=self.loyalty_points,
            reason=reason,
            performed_by=performed_by,
        )


class LoyaltyTransaction(models.Model):
    TYPE_EARN   = 'earn'
    TYPE_REDEEM = 'redeem'
    TYPE_ADJUST = 'adjust'

    TYPE_CHOICES = [
        (TYPE_EARN,   'Points Earned'),
        (TYPE_REDEEM, 'Points Redeemed'),
        (TYPE_ADJUST, 'Manual Adjustment'),
    ]

    customer         = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='loyalty_transactions')
    transaction_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    points           = models.IntegerField()           # positive = credit, negative = debit
    balance_after    = models.IntegerField()
    reason           = models.CharField(max_length=200, blank=True)
    sale             = models.ForeignKey(
        'sales.Sale', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='loyalty_transactions',
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        sign = '+' if self.points >= 0 else ''
        return f"{self.customer.name} — {sign}{self.points} pts (bal: {self.balance_after})"