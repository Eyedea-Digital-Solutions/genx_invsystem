"""
sales/admin.py  — fixed version
Changes vs original:
  - AuditLogInline: performed_by shown safely (can now be null/SET_NULL)
  - SaleAuditLogAdmin: performed_by null-safe display
  - has_delete_permission restored to default (True) so deletion works
"""
import json

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from decimal import Decimal

from inventory_system.admin_site import genx_admin_site
from .models import Sale, SaleItem, SaleAuditLog


# ─── SALE ITEM INLINE ────────────────────────────────────────────────────────
class SaleItemInline(admin.TabularInline):
    model           = SaleItem
    extra           = 0
    readonly_fields = ['product', 'quantity', 'unit_price', 'line_total_display',
                       'is_free_gift', 'promotion_label']
    fields          = ['product', 'quantity', 'unit_price', 'line_total_display',
                       'is_free_gift', 'promotion_label']
    can_delete      = False
    show_change_link = True

    @admin.display(description='Line Total')
    def line_total_display(self, obj):
        if obj.is_free_gift:
            return format_html('<span style="color:#16a34a;font-weight:700;">FREE</span>')
        return format_html('<strong>${:.2f}</strong>', obj.line_total)

    def has_add_permission(self, request, obj=None):
        return False


# ─── AUDIT LOG INLINE ────────────────────────────────────────────────────────
class AuditLogInline(admin.StackedInline):
    model           = SaleAuditLog
    extra           = 0
    readonly_fields = ['action', 'performed_by_display', 'timestamp', 'details_pretty']
    fields          = ['action', 'performed_by_display', 'timestamp', 'details_pretty']
    can_delete      = False
    verbose_name    = 'Audit Log Entry'

    @admin.display(description='Performed By')
    def performed_by_display(self, obj):
        if obj.performed_by:
            return obj.performed_by.get_full_name() or obj.performed_by.username
        return '—'

    @admin.display(description='Details')
    def details_pretty(self, obj):
        try:
            fmt = json.dumps(obj.details, indent=2)
            return format_html(
                '<pre style="font-size:11px;max-height:200px;overflow:auto;'
                'background:#f9fafb;padding:8px;border-radius:6px;border:1px solid #e5e7eb;">{}</pre>',
                fmt
            )
        except Exception:
            return str(obj.details)

    def has_add_permission(self, request, obj=None):
        return False


# ─── SALE ─────────────────────────────────────────────────────────────────────
class SaleAdmin(admin.ModelAdmin):
    list_display    = ['receipt_number', 'joint', 'sold_by', 'sale_date_fmt',
                       'payment_badge', 'type_badge', 'item_count',
                       'subtotal_disp', 'discount_disp', 'total_disp', 'held_badge']
    list_filter     = ['joint', 'payment_method', 'sale_type', 'is_held', 'sale_date']
    search_fields   = ['receipt_number', 'customer_name', 'customer_phone',
                       'sold_by__username', 'sold_by__first_name', 'sold_by__last_name']
    readonly_fields = ['receipt_number', 'created_at', 'subtotal', 'total_amount',
                       'sale_date', 'held_at']
    list_per_page   = 40
    date_hierarchy  = 'sale_date'
    ordering        = ['-sale_date']
    inlines         = [SaleItemInline, AuditLogInline]
    show_full_result_count = True

    fieldsets = (
        ('Sale', {
            'fields': ('receipt_number', 'joint', 'sold_by',
                       'sale_date', 'created_at',
                       'payment_method', 'sale_type')
        }),
        ('Hold Status', {
            'fields': ('is_held', 'held_at'),
            'classes': ('collapse',),
        }),
        ('Customer', {
            'fields': ('customer_name', 'customer_phone', 'notes'),
        }),
        ('Pricing & Promotions', {
            'fields': ('discount_amount', 'discount_type', 'discount_label',
                       'promotion_applied', 'subtotal', 'total_amount'),
        }),
        ('Manual Receipt Image', {
            'fields': ('manual_receipt_image',),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Date', ordering='sale_date')
    def sale_date_fmt(self, obj):
        return obj.sale_date.strftime('%d %b %Y  %H:%M')

    @admin.display(description='Payment')
    def payment_badge(self, obj):
        colors = {'cash': '#16a34a', 'ecocash': '#059669', 'card': '#2563eb', 'mixed': '#7c3aed'}
        c = colors.get(obj.payment_method, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;">{}</span>',
            c, obj.get_payment_method_display()
        )

    @admin.display(description='Type')
    def type_badge(self, obj):
        labels = {'pos': 'POS', 'system': 'Classic', 'manual': 'Manual'}
        return labels.get(obj.sale_type, obj.sale_type)

    @admin.display(description='Items')
    def item_count(self, obj):
        return obj.items.count()

    @admin.display(description='Subtotal')
    def subtotal_disp(self, obj):
        return format_html('${:.2f}', obj.subtotal)

    @admin.display(description='Discount')
    def discount_disp(self, obj):
        if obj.discount_amount:
            return format_html('<span style="color:#16a34a;font-weight:600;">-${}</span>', obj.discount_amount)
        return '—'

    @admin.display(description='Total', ordering='id')
    def total_disp(self, obj):
        return format_html('<strong>${:.2f}</strong>', obj.total_amount)

    @admin.display(description='Held')
    def held_badge(self, obj):
        if obj.is_held:
            return format_html(
                '<span style="background:#fef3c7;color:#d97706;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700;">⏸ Held</span>'
            )
        return ''

    actions = ['release_holds', 'list_receipts']

    @admin.action(description='▶ Release selected held transactions')
    def release_holds(self, request, queryset):
        n = queryset.filter(is_held=True).update(is_held=False, held_at=None)
        self.message_user(request, f'{n} transaction(s) released from hold.')

    @admin.action(description='📋 Copy receipt numbers to messages')
    def list_receipts(self, request, queryset):
        nums = ', '.join(queryset.values_list('receipt_number', flat=True))
        self.message_user(request, f'Receipts: {nums}')

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .select_related('joint', 'sold_by')
            .prefetch_related('items')
        )


genx_admin_site.register(Sale, SaleAdmin)


# ─── SALE ITEM ────────────────────────────────────────────────────────────────
class SaleItemAdmin(admin.ModelAdmin):
    list_display   = ['sale_link', 'product', 'joint_disp', 'quantity',
                      'unit_price', 'line_total_disp', 'is_free_gift', 'promo_label_disp']
    list_filter    = ['is_free_gift', 'sale__joint', 'sale__payment_method']
    search_fields  = ['sale__receipt_number', 'product__name', 'product__code', 'promotion_label']
    readonly_fields = ['line_total']
    list_per_page  = 60

    @admin.display(description='Receipt', ordering='sale__receipt_number')
    def sale_link(self, obj):
        url = reverse('genx_admin:sales_sale_change', args=[obj.sale_id])
        return format_html('<a href="{}" style="font-weight:600;">{}</a>', url, obj.sale.receipt_number)

    @admin.display(description='Joint')
    def joint_disp(self, obj):
        return obj.sale.joint.display_name

    @admin.display(description='Total')
    def line_total_disp(self, obj):
        if obj.is_free_gift:
            return format_html('<span style="background:#d1fae5;color:#065f46;padding:1px 6px;border-radius:3px;font-size:10px;font-weight:700;">FREE</span>')
        return format_html('<strong>${:.2f}</strong>', obj.line_total)

    @admin.display(description='Promo')
    def promo_label_disp(self, obj):
        if obj.promotion_label:
            return format_html('<span style="color:#d97706;font-size:11px;">{}</span>', obj.promotion_label)
        return '—'


genx_admin_site.register(SaleItem, SaleItemAdmin)


# ─── AUDIT LOG ────────────────────────────────────────────────────────────────
class SaleAuditLogAdmin(admin.ModelAdmin):
    list_display    = ['sale_link', 'action_badge', 'performed_by_display', 'timestamp_fmt']
    list_filter     = ['action']
    search_fields   = ['sale__receipt_number', 'performed_by__username']
    readonly_fields = ['sale', 'action', 'performed_by', 'timestamp', 'details_pretty']

    # Audit logs should not be manually deleted via admin
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    @admin.display(description='Sale')
    def sale_link(self, obj):
        url = reverse('genx_admin:sales_sale_change', args=[obj.sale_id])
        return format_html('<a href="{}">{}</a>', url, obj.sale.receipt_number)

    @admin.display(description='Performed By')
    def performed_by_display(self, obj):
        if obj.performed_by:
            return obj.performed_by.get_full_name() or obj.performed_by.username
        return '—'

    @admin.display(description='Action')
    def action_badge(self, obj):
        colors = {'created': '#2563eb', 'manual_sale_recorded': '#7c3aed'}
        c = colors.get(obj.action, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:1px 7px;border-radius:4px;font-size:10px;font-weight:700;">{}</span>',
            c, obj.action.upper()
        )

    @admin.display(description='Timestamp', ordering='timestamp')
    def timestamp_fmt(self, obj):
        return obj.timestamp.strftime('%d %b %Y %H:%M')

    @admin.display(description='Details')
    def details_pretty(self, obj):
        try:
            fmt = json.dumps(obj.details, indent=2)
            return format_html(
                '<pre style="font-size:11px;background:#f9fafb;padding:10px;border-radius:6px;border:1px solid #e5e7eb;">{}</pre>',
                fmt
            )
        except Exception:
            return str(obj.details)

    def has_add_permission(self, request):
        return False


genx_admin_site.register(SaleAuditLog, SaleAuditLogAdmin)