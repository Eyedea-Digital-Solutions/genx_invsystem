from django.contrib import admin

from inventory_system.admin_site import genx_admin_site
from .models import Employee


@admin.register(Employee, site=genx_admin_site)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        'get_full_name',
        'role',
        'branch',
        'email',
        'phone',
        'is_active',
        'updated_at',
    )
    list_filter = ('role', 'branch', 'is_active')
    search_fields = ('first_name', 'last_name', 'email', 'phone')
