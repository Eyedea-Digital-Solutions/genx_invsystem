from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['username', 'get_full_name', 'role', 'primary_joint', 'is_active']
    list_filter = ['role', 'primary_joint', 'is_active']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('GenX POS', {'fields': ('role', 'primary_joint', 'phone')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('GenX POS', {'fields': ('role', 'primary_joint', 'phone')}),
    )
