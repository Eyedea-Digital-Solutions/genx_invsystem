"""
expenses/models.py
Add this to your expenses app (or create the app with: python manage.py startapp expenses)
"""
from django.db import models
from django.conf import settings


class ExpenseCategory(models.Model):
    name        = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active   = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Expense Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Expense(models.Model):
    PAYMENT_METHODS = [
        ('cash',    'Cash'),
        ('ecocash', 'EcoCash'),
        ('card',    'Card'),
        ('transfer','Bank Transfer'),
    ]

    joint          = models.ForeignKey('inventory.Joint', on_delete=models.PROTECT, related_name='expenses')
    category       = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='expenses')
    description    = models.CharField(max_length=255)
    amount         = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='cash')
    reference      = models.CharField(max_length=100, blank=True, help_text="Receipt #, invoice #, etc.")
    notes          = models.TextField(blank=True)
    expense_date   = models.DateField()
    recorded_by    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='expenses_recorded')
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-expense_date', '-created_at']

    def __str__(self):
        return f"{self.joint} — {self.description} — ${self.amount}"

    def get_payment_method_display_label(self):
        return dict(self.PAYMENT_METHODS).get(self.payment_method, self.payment_method)