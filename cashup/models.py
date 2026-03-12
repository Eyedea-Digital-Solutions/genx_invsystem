from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.conf import settings


class CashUp(models.Model):
    STATUS_OPEN = 'open'
    STATUS_SUBMITTED = 'submitted'
    STATUS_APPROVED = 'approved'
    STATUS_DISPUTED = 'disputed'

    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_DISPUTED, 'Disputed'),
    ]

    SHIFT_MORNING = 'morning'
    SHIFT_AFTERNOON = 'afternoon'
    SHIFT_FULL = 'full'

    SHIFT_CHOICES = [
        (SHIFT_MORNING, 'Morning'),
        (SHIFT_AFTERNOON, 'Afternoon'),
        (SHIFT_FULL, 'Full Day'),
    ]

    joint = models.ForeignKey('inventory.Joint', on_delete=models.PROTECT, related_name='cash_ups')
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='cash_ups_submitted',
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cash_ups_approved',
    )
    shift = models.CharField(max_length=20, choices=SHIFT_CHOICES, default=SHIFT_FULL)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)

    shift_date = models.DateField(default=timezone.localdate)
    opened_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    opening_float = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))

    expected_cash = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    expected_ecocash = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    expected_card = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    expected_mixed_cash = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    expected_mixed_ecocash = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))

    actual_cash = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    actual_ecocash = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    actual_card = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))

    cash_denomination_100 = models.PositiveIntegerField(default=0)
    cash_denomination_50 = models.PositiveIntegerField(default=0)
    cash_denomination_20 = models.PositiveIntegerField(default=0)
    cash_denomination_10 = models.PositiveIntegerField(default=0)
    cash_denomination_5 = models.PositiveIntegerField(default=0)
    cash_denomination_2 = models.PositiveIntegerField(default=0)
    cash_denomination_1 = models.PositiveIntegerField(default=0)
    cash_denomination_cents = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0'))

    expenses_cash = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    expenses_ecocash = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))

    notes = models.TextField(blank=True)
    manager_notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-shift_date', '-opened_at']
        unique_together = [['joint', 'cashier', 'shift_date', 'shift']]
        verbose_name = 'Cash-Up'
        verbose_name_plural = 'Cash-Ups'

    def __str__(self):
        return f"{self.joint.display_name} — {self.cashier} — {self.shift_date} ({self.get_shift_display()})"

    @property
    def denomination_total(self):
        return (
            Decimal(self.cash_denomination_100) * 100 +
            Decimal(self.cash_denomination_50) * 50 +
            Decimal(self.cash_denomination_20) * 20 +
            Decimal(self.cash_denomination_10) * 10 +
            Decimal(self.cash_denomination_5) * 5 +
            Decimal(self.cash_denomination_2) * 2 +
            Decimal(self.cash_denomination_1) * 1 +
            Decimal(self.cash_denomination_cents)
        )

    @property
    def expected_cash_total(self):
        return self.expected_cash + self.expected_mixed_cash

    @property
    def expected_ecocash_total(self):
        return self.expected_ecocash + self.expected_mixed_ecocash

    @property
    def cash_variance(self):
        net_expected = self.expected_cash_total - self.opening_float - self.expenses_cash
        return self.actual_cash - net_expected

    @property
    def ecocash_variance(self):
        net_expected = self.expected_ecocash_total - self.expenses_ecocash
        return self.actual_ecocash - net_expected

    @property
    def card_variance(self):
        return self.actual_card - self.expected_card

    @property
    def total_variance(self):
        return self.cash_variance + self.ecocash_variance + self.card_variance

    @property
    def total_expected(self):
        return self.expected_cash_total + self.expected_ecocash_total + self.expected_card

    @property
    def total_actual(self):
        return self.actual_cash + self.actual_ecocash + self.actual_card

    @property
    def is_balanced(self):
        return abs(self.total_variance) < Decimal('0.05')

    def compute_expected_from_sales(self):
        from sales.models import Sale
        from django.db.models import Sum

        sales_qs = Sale.objects.filter(
            joint=self.joint,
            sold_by=self.cashier,
            sale_date__date=self.shift_date,
            is_held=False,
        )

        def agg(method):
            return sales_qs.filter(payment_method=method).aggregate(
                t=Sum('discount_amount')
            )

        cash_total = Decimal('0')
        for sale in sales_qs.filter(payment_method='cash').prefetch_related('items'):
            cash_total += sale.total_amount

        ecocash_total = Decimal('0')
        for sale in sales_qs.filter(payment_method='ecocash').prefetch_related('items'):
            ecocash_total += sale.total_amount

        card_total = Decimal('0')
        for sale in sales_qs.filter(payment_method='card').prefetch_related('items'):
            card_total += sale.total_amount

        mixed_cash_total = Decimal('0')
        mixed_ecocash_total = Decimal('0')
        for sale in sales_qs.filter(payment_method='mixed').prefetch_related('items'):
            total = sale.total_amount
            cash_part = getattr(sale, 'cash_amount', None)
            if cash_part is not None:
                mixed_cash_total += Decimal(str(cash_part))
                mixed_ecocash_total += max(Decimal('0'), total - Decimal(str(cash_part)))
            else:
                mixed_cash_total += total

        self.expected_cash = cash_total
        self.expected_ecocash = ecocash_total
        self.expected_card = card_total
        self.expected_mixed_cash = mixed_cash_total
        self.expected_mixed_ecocash = mixed_ecocash_total

        from expense.models import Expense
        exp = Expense.objects.filter(
            joint=self.joint,
            expense_date=self.shift_date,
            recorded_by=self.cashier,
        )
        self.expenses_cash = exp.filter(payment_method='cash').aggregate(
            t=Sum('amount')
        )['t'] or Decimal('0')
        self.expenses_ecocash = exp.filter(payment_method='ecocash').aggregate(
            t=Sum('amount')
        )['t'] or Decimal('0')

    def submit(self, user):
        self.status = self.STATUS_SUBMITTED
        self.submitted_at = timezone.now()
        self.save()
        CashUpAuditLog.objects.create(
            cash_up=self,
            action='submitted',
            performed_by=user,
            details={
                'total_actual': str(self.total_actual),
                'total_variance': str(self.total_variance),
            }
        )

    def approve(self, user, notes=''):
        self.status = self.STATUS_APPROVED
        self.approved_by = user
        self.approved_at = timezone.now()
        if notes:
            self.manager_notes = notes
        self.save()
        CashUpAuditLog.objects.create(
            cash_up=self,
            action='approved',
            performed_by=user,
            details={'manager_notes': notes}
        )

    def dispute(self, user, notes=''):
        self.status = self.STATUS_DISPUTED
        if notes:
            self.manager_notes = notes
        self.save()
        CashUpAuditLog.objects.create(
            cash_up=self,
            action='disputed',
            performed_by=user,
            details={'manager_notes': notes}
        )


class CashUpAuditLog(models.Model):
    cash_up = models.ForeignKey(CashUp, on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=50)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.cash_up} — {self.action}"