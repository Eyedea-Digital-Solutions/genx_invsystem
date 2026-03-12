from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from inventory_system.admin_site import genx_admin_site
from .models import Return, ReturnItem, ReturnAuditLog


class ReturnItemInline(admin.TabularInline):
    model          = ReturnItem
    extra          = 0
    readonly_fields = ['original_item', 'quantity_returned', 'unit_refund_amount', 'total_refund_disp', 'restock']
    can_delete     = False
    fields         = ['original_item', 'quantity_returned', 'unit_refund_amount', 'total_refund_disp', 'restock']

    @admin.display(description='Line Refund')
    def total_refund_disp(self, obj):
        return format_html('<strong>${:.2f}</strong>', obj.total_refund)

    def has_add_permission(self, request, obj=None):
        return False


class ReturnAuditLogInline(admin.TabularInline):
    model          = ReturnAuditLog
    extra          = 0
    readonly_fields = ['action', 'performed_by', 'timestamp', 'details']
    can_delete     = False

    def has_add_permission(self, request, obj=None):
        return False


class ReturnAdmin(admin.ModelAdmin):
    list_display  = ['return_number', 'original_sale_link', 'return_date_fmt',
                     'refund_type_badge', 'status_badge', 'total_refund_amount', 'processed_by']
    list_filter   = ['status', 'refund_type', 'original_sale__joint']
    search_fields = ['original_sale__receipt_number', 'reason', 'processed_by__username']
    readonly_fields = ['return_number', 'total_refund_amount', 'created_at']
    ordering      = ['-created_at']
    inlines       = [ReturnItemInline, ReturnAuditLogInline]

    @admin.display(description='Return #')
    def return_number(self, obj):
        return obj.return_number

    @admin.display(description='Original Sale')
    def original_sale_link(self, obj):
        url = reverse('genx_admin:sales_sale_change', args=[obj.original_sale_id])
        return format_html('<a href="{}" style="font-weight:600;">{}</a>', url, obj.original_sale.receipt_number)

    @admin.display(description='Date')
    def return_date_fmt(self, obj):
        return obj.return_date.strftime('%d %b %Y %H:%M')

    @admin.display(description='Refund Type')
    def refund_type_badge(self, obj):
        cfg = {
            'cash':         ('#d1fae5', '#065f46', '💵 Cash'),
            'store_credit': ('#dbeafe', '#1e40af', '⭐ Store Credit'),
            'reversal':     ('#ede9fe', '#5b21b6', '↩ Reversal'),
        }
        bg, fg, label = cfg.get(obj.refund_type, ('#f3f4f6', '#374151', obj.refund_type))
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;border-radius:4px;font-size:10px;font-weight:700;">{}</span>',
            bg, fg, label
        )

    @admin.display(description='Status')
    def status_badge(self, obj):
        cfg = {
            Return.STATUS_PENDING:   ('#fef3c7', '#92400e', '⏳ Pending'),
            Return.STATUS_COMPLETED: ('#d1fae5', '#065f46', '✓ Completed'),
            Return.STATUS_CANCELLED: ('#fee2e2', '#7f1d1d', '✗ Cancelled'),
        }
        bg, fg, label = cfg.get(obj.status, ('#f3f4f6', '#374151', obj.status))
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;border-radius:4px;font-size:10px;font-weight:700;">{}</span>',
            bg, fg, label
        )


genx_admin_site.register(Return, ReturnAdmin)