from django.db import models
from django.conf import settings


class Employee(models.Model):
    ROLE_CHOICES = [
        ('cashier', 'Cashier'),
        ('manager', 'Manager'),
        ('supervisor', 'Supervisor'),
        ('stock_controller', 'Stock Controller'),
        ('accountant', 'Accountant'),
        ('admin', 'Admin'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='employee_profile'
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default='cashier')
    branch = models.CharField(max_length=100, blank=True)
    date_joined = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def username(self):
        return self.user.username if self.user else self.email

    @property
    def is_staff(self):
        return self.user.is_staff if self.user else False
