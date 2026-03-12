from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from inventory_system.admin_site import genx_admin_site
from .models import PurchaseOrder, PurchaseOrderItem, GoodsReceivedNote, GRNItem


class POItemInline(admin.TabularInline):
    model          = PurchaseOrderItem
    extra          = 1
    fields         = ['product', 'quantity_ordered', 'unit_cost', 'quantity_received', 'pending_qty_disp']
    readonly_fields = ['quantity_received', 'pending_qty_disp']

    @admin.display(description='Pending')
    def pending_qty_disp(self, obj):
        pending = obj.pending_quantity
        if pending == 0:
            return format_html('<span style="color:#16a34a;font-weight:700;">✓ Done</span>')
        return format_html('<span style="color:#d97706;font-weight:600;">{}</span>', pending)


class GRNInline(admin.TabularInline):
    model          = GoodsReceivedNote
    extra          = 0
    readonly_fields = ['grn_number', 'received_date', 'received_by', 'total_cost_disp', 'supplier_reference']
    can_delete     = False
    fields         = ['grn_number', 'received_date', 'received_by', 'total_cost_disp', 'supplier_reference']
    show_change_link = True

    @admin.display(description='Value')
    def total_cost_disp(self, obj):
        return format_html('${:.2f}', obj.total_cost)

    def has_add_permission(self, request, obj=None):
        return False


class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display  = ['order_number', 'supplier', 'joint', 'order_date', 'status_badge',
                     'total_cost_disp', 'expected_delivery', 'created_by']
    list_filter   = ['status', 'joint', 'supplier']
    search_fields = ['order_number', 'supplier__name', 'notes']
    readonly_fields = ['order_number', 'created_at', 'updated_at', 'total_cost_disp']
    ordering      = ['-created_at']
    inlines       = [POItemInline, GRNInline]
    date_hierarchy = 'order_date'

    fieldsets = (
        ('Order', {'fields': ('order_number', 'supplier', 'joint', 'order_date', 'expected_delivery', 'status')}),
        ('Notes', {'fields': ('notes',)}),
        ('Meta',  {'fields': ('created_by', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    @admin.display(description='Status')
    def status_badge(self, obj):
        cfg = {
            'draft':     ('#f3f4f6', '#374151', '📝 Draft'),
            'ordered':   ('#dbeafe', '#1e40af', '📦 Ordered'),
            'partial':   ('#fef3c7', '#92400e', '⏳ Partial'),
            'received':  ('#d1fae5', '#065f46', '✓ Received'),
            'cancelled': ('#fee2e2', '#7f1d1d', '✗ Cancelled'),
        }
        bg, fg, label = cfg.get(obj.status, ('#f3f4f6', '#374151', obj.status))
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;border-radius:4px;font-size:10px;font-weight:700;">{}</span>',
            bg, fg, label
        )

    @admin.display(description='Total Cost')
    def total_cost_disp(self, obj):
        return format_html('<strong>${:.2f}</strong>', obj.total_cost)

    actions = ['mark_ordered']

    @admin.action(description='📦 Mark selected as Ordered')
    def mark_ordered(self, request, queryset):
        n, errors = 0, []
        for po in queryset.filter(status=PurchaseOrder.STATUS_DRAFT):
            try:
                po.mark_ordered()
                n += 1
            except ValueError as e:
                errors.append(str(e))
        if n:
            self.message_user(request, f'{n} order(s) marked as ordered.')
        for e in errors:
            self.message_user(request, e, level='error')


genx_admin_site.register(PurchaseOrder, PurchaseOrderAdmin)
genx_admin_site.register(GoodsReceivedNote)