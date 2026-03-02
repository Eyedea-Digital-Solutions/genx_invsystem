from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model extending Django's AbstractUser.
    We add a 'role' field to distinguish between admin, manager, and staff.
    This controls what each person can see and do in the system.
    """

    ROLE_CHOICES = [
        ('admin', 'Admin'),       # Full access - can manage everything
        ('manager', 'Manager'),   # Can view reports, manage stock
        ('staff', 'Staff'),       # Can only make sales
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='staff',
        help_text="Determines what this user can access in the system."
    )

    # Which joint (shop) this user primarily works at
    # Null means they can work across all joints (e.g., admin)
    primary_joint = models.ForeignKey(
        'inventory.Joint',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='staff_members',
        help_text="The shop this user primarily works at."
    )

    phone = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    @property
    def is_admin_role(self):
        return self.role == 'admin'

    @property
    def is_manager_role(self):
        return self.role in ['admin', 'manager']
