from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CASHIER = 'cashier'
    ROLE_MANAGER = 'manager'
    ROLE_ADMIN = 'admin'

    ROLE_CHOICES = [
        (ROLE_CASHIER, 'Cashier'),
        (ROLE_MANAGER, 'Manager'),
        (ROLE_ADMIN, 'Admin'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_CASHIER)
    primary_joint = models.ForeignKey(
        'inventory.Joint',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='primary_staff',
    )
    phone = models.CharField(max_length=20, blank=True)

    @property
    def is_cashier_role(self):
        return self.role == self.ROLE_CASHIER

    @property
    def is_manager_role(self):
        return self.role in (self.ROLE_MANAGER, self.ROLE_ADMIN) or self.is_superuser

    @property
    def is_admin_role(self):
        return self.role == self.ROLE_ADMIN or self.is_superuser

    def get_role_display_label(self):
        return dict(self.ROLE_CHOICES).get(self.role, self.role)

    def __str__(self):
        full = self.get_full_name()
        return full if full else self.username

    class Meta:
        ordering = ['first_name', 'last_name']
