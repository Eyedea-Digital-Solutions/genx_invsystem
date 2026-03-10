"""
promotions/admin.py
────────────────────
Promotion model admin with type/status badges, sub-rule inlines, and bulk actions.
"""
from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from inventory_system.admin_site import genx_admin_site
from .models import Promotion, SpendThresholdPromo, FreeGiftPromo, BundlePromo


# ─── SUB-RULE INLINES ────────────────────────────────────────────────────────
class SpendThresholdInline(admin.StackedInline):
    model   = SpendThresholdPromo
    extra   = 0
    fields  = ['minimum_spend', 'discount_type', 'discount_value']


class FreeGiftInline(admin.StackedInline):
    model   = FreeGiftPromo
    extra   = 0
    fields  = ['gift_product', 'quantity']


class BundleInline(admin.StackedInline):
    model   = BundlePromo
    extra   = 0
    fields  = ['required_products', 'bundle_price', 'discount_percent']


# ─── PROMOTION ───────────────────────────────────────────────────────────────
class PromotionAdmin(admin.ModelAdmin):
    list_display    = ['name', 'joint', 'promo_type_badge', 'status_badge',
                       'start_date', 'end_date', 'sales_count', 'is_active']
    list_filter     = ['joint', 'promo_type', 'is_active']
    search_fields   = ['name', 'description']
    list_editable   = ['is_active']
    ordering        = ['-start_date']
    inlines         = [SpendThresholdInline, FreeGiftInline, BundleInline]

    fieldsets = (
        ('Details', {'fields': ('joint', 'name', 'description', 'promo_type', 'is_active')}),
        ('Schedule', {'fields': ('start_date', 'end_date')}),
    )

    @admin.display(description='Type')
    def promo_type_badge(self, obj):
        colors = {
            'spend_threshold': ('#dbeafe', '#1e40af'),
            'free_gift':       ('#d1fae5', '#065f46'),
            'bundle':          ('#ede9fe', '#5b21b6'),
        }
        bg, fg = colors.get(obj.promo_type, ('#f3f4f6', '#374151'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;border-radius:4px;font-size:10px;font-weight:700;">{}</span>',
            bg, fg, obj.get_promo_type_display()
        )

    @admin.display(description='Status')
    def status_badge(self, obj):
        now = timezone.now()
        if not obj.is_active:
            cfg = ('#f3f4f6', '#6b7280', 'Inactive')
        elif obj.start_date and obj.start_date > now:
            cfg = ('#fef3c7', '#92400e', '⏳ Upcoming')
        elif obj.end_date and obj.end_date < now:
            cfg = ('#fee2e2', '#7f1d1d', 'Expired')
        else:
            cfg = ('#d1fae5', '#065f46', '✓ Active')
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;border-radius:4px;font-size:10px;font-weight:700;">{}</span>',
            *cfg
        )

    @admin.display(description='Sales Used')
    def sales_count(self, obj):
        try:
            return obj.sales.count()
        except Exception:
            return '—'

    actions = ['activate_promos', 'deactivate_promos']

    @admin.action(description='✓ Activate selected promotions')
    def activate_promos(self, request, queryset):
        n = queryset.update(is_active=True)
        self.message_user(request, f'{n} promotion(s) activated.')

    @admin.action(description='✗ Deactivate selected promotions')
    def deactivate_promos(self, request, queryset):
        n = queryset.update(is_active=False)
        self.message_user(request, f'{n} promotion(s) deactivated.')


genx_admin_site.register(Promotion, PromotionAdmin)


# ─── SUB-RULE STANDALONE ADMINS ──────────────────────────────────────────────
class SpendThresholdAdmin(admin.ModelAdmin):
    list_display = ['promotion', 'minimum_spend', 'discount_type', 'discount_value']
    list_filter  = ['discount_type', 'promotion__joint']
    search_fields = ['promotion__name']

genx_admin_site.register(SpendThresholdPromo, SpendThresholdAdmin)


class FreeGiftAdmin(admin.ModelAdmin):
    list_display  = ['promotion', 'gift_product', 'quantity']
    list_filter   = ['promotion__joint']
    search_fields = ['promotion__name', 'gift_product__name']

genx_admin_site.register(FreeGiftPromo, FreeGiftAdmin)


class BundleAdmin(admin.ModelAdmin):
    list_display  = ['promotion', 'bundle_price', 'discount_percent']
    list_filter   = ['promotion__joint']
    search_fields = ['promotion__name']

genx_admin_site.register(BundlePromo, BundleAdmin)
