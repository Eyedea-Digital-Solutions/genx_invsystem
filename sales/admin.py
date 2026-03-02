from django.contrib import admin
from .models import Sale, SaleItem, SaleAuditLog


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'unit_price', 'line_total']
    can_delete = False


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['receipt_number', 'joint', 'sold_by', 'sale_date', 'total_amount', 'payment_method']
    list_filter = ['joint', 'payment_method', 'sale_type', 'sale_date']
    search_fields = ['receipt_number', 'customer_name', 'sold_by__username']
    readonly_fields = ['receipt_number', 'sold_by', 'created_at', 'total_amount']
    inlines = [SaleItemInline]

    def has_delete_permission(self, request, obj=None):
        # Sales CANNOT be deleted — data integrity
        return False

    def has_change_permission(self, request, obj=None):
        # Sales cannot be modified after creation
        return False


@admin.register(SaleAuditLog)
class SaleAuditLogAdmin(admin.ModelAdmin):
    list_display = ['sale', 'action', 'performed_by', 'timestamp']
    readonly_fields = ['sale', 'action', 'performed_by', 'timestamp', 'details']

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False
