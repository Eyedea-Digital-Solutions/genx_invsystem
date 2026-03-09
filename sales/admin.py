from django.contrib import admin
from .models import Sale, SaleItem, SaleAuditLog


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ['line_total']


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ['receipt_number', 'joint', 'sold_by', 'sale_date', 'payment_method', 'total_amount', 'is_held']
    list_filter = ['joint', 'payment_method', 'sale_type', 'is_held']
    search_fields = ['receipt_number', 'customer_name', 'sold_by__username']
    readonly_fields = ['receipt_number', 'created_at', 'total_amount', 'subtotal']
    inlines = [SaleItemInline]


@admin.register(SaleAuditLog)
class SaleAuditLogAdmin(admin.ModelAdmin):
    list_display = ['sale', 'action', 'performed_by', 'timestamp']
    readonly_fields = ['sale', 'action', 'performed_by', 'timestamp', 'details']
