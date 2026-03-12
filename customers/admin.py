from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from inventory_system.admin_site import genx_admin_site
from .models import Customer, LoyaltyTransaction


class LoyaltyTransactionInline(admin.TabularInline):
    model          = LoyaltyTransaction
    extra          = 0
    readonly_fields = ['transaction_type', 'points', 'balance_after', 'reason', 'sale', 'performed_by', 'created_at']
    can_delete     = False
    fields         = ['created_at', 'transaction_type', 'points', 'balance_after', 'reason', 'sale']
    ordering       = ['-created_at']
    max_num        = 20

    def has_add_permission(self, request, obj=None):
        return False


class CustomerAdmin(admin.ModelAdmin):
    list_display  = ['name', 'phone', 'email', 'type_badge', 'loyalty_points_disp',
                     'purchase_count_disp', 'total_spend_disp', 'is_active']
    list_filter   = ['customer_type', 'is_active']
    search_fields = ['name', 'phone', 'email']
    list_editable = ['is_active']
    ordering      = ['name']
    inlines       = [LoyaltyTransactionInline]
    readonly_fields = ['created_at', 'updated_at', 'purchase_count_disp', 'total_spend_disp']

    fieldsets = (
        ('Profile', {'fields': ('name', 'phone', 'email', 'address', 'customer_type', 'is_active')}),
        ('Loyalty', {'fields': ('loyalty_points',)}),
        ('Notes',   {'fields': ('notes',)}),
        ('Meta',    {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    @admin.display(description='Type')
    def type_badge(self, obj):
        cfg = {
            'regular':   ('#f3f4f6', '#374151'),
            'wholesale': ('#dbeafe', '#1e40af'),
            'vip':       ('#fef3c7', '#92400e'),
            'staff':     ('#d1fae5', '#065f46'),
        }
        bg, fg = cfg.get(obj.customer_type, ('#f3f4f6', '#374151'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;border-radius:4px;'
            'font-size:10px;font-weight:700;text-transform:uppercase;">{}</span>',
            bg, fg, obj.get_customer_type_display()
        )

    @admin.display(description='Points')
    def loyalty_points_disp(self, obj):
        color = '#d97706' if obj.loyalty_points > 0 else '#9ca3af'
        return format_html('<span style="color:{};font-weight:700;">⭐ {}</span>', color, obj.loyalty_points)

    @admin.display(description='Purchases')
    def purchase_count_disp(self, obj):
        count = obj.purchase_count
        if count == 0:
            return '—'
        url = reverse('genx_admin:sales_sale_changelist') + f'?customer__id__exact={obj.pk}'
        return format_html('<a href="{}">{} sales</a>', url, count)

    @admin.display(description='Total Spend')
    def total_spend_disp(self, obj):
        spend = obj.total_spend
        if spend == 0:
            return '—'
        return format_html('<strong>${:.2f}</strong>', spend)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('sales', 'loyalty_transactions')


genx_admin_site.register(Customer, CustomerAdmin)
genx_admin_site.register(LoyaltyTransaction)