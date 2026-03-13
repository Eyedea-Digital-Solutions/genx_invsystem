from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone

from inventory_system.admin_site import genx_admin_site
from .models import (
    Promotion, SpendThresholdPromo, FreeGiftPromo, BundlePromo,
    CategoryTierFreeRule, CategoryTierFreeItem, Bundle, BundleItem,
)


# ─── SUB-RULE INLINES ────────────────────────────────────────────────────────
class SpendThresholdInline(admin.StackedInline):
    model   = SpendThresholdPromo
    extra   = 0
    fields  = ['minimum_spend', 'discount_type', 'discount_value']


class FreeGiftInline(admin.StackedInline):
    model   = FreeGiftPromo
    extra   = 0
    fields  = ['gift_product', 'quantity']


class BundlePromoInline(admin.StackedInline):
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
    inlines         = [SpendThresholdInline, FreeGiftInline, BundlePromoInline]

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


# ── Category Tier Free Rules ──────────────────────────────────────────────────

class CategoryTierFreeItemInline(admin.TabularInline):
    model      = CategoryTierFreeItem
    extra      = 1
    fields     = ('product', 'quantity')
    # Use raw_id_fields instead of autocomplete_fields — no need to register
    # Product admin with search_fields just to satisfy Django's autocomplete check.
    raw_id_fields = ('product',)


@admin.register(CategoryTierFreeRule)
class CategoryTierFreeRuleAdmin(admin.ModelAdmin):
    list_display  = ('name', 'category', 'joint_display', 'price_range', 'label', 'is_active')
    list_filter   = ('is_active', 'category', 'joint')
    list_editable = ('is_active',)
    inlines       = [CategoryTierFreeItemInline]
    fieldsets = (
        (None, {'fields': ('name', 'is_active', 'label')}),
        ('Trigger', {'fields': ('category', 'joint')}),
        ('Price range', {
            'description': (
                'Rule fires when product unit price ≥ min_price and < max_price. '
                'Leave max_price blank for "and above" tiers.'
            ),
            'fields': ('min_price', 'max_price'),
        }),
    )

    @admin.display(description='Branch')
    def joint_display(self, obj):
        return obj.joint or '— all branches —'

    @admin.display(description='Price range')
    def price_range(self, obj):
        upper = f'–${obj.max_price}' if obj.max_price is not None else '+'
        return f'${obj.min_price}{upper}'


# ── Bundles ───────────────────────────────────────────────────────────────────

class BundleItemInline(admin.TabularInline):
    model         = BundleItem
    extra         = 1
    fields        = ('product', 'quantity', 'is_free')
    raw_id_fields = ('product',)


@admin.register(Bundle)
class BundleAdmin(admin.ModelAdmin):
    list_display      = ('name', 'sku', 'price', 'branch_display', 'is_active', 'created_at')
    list_filter       = ('is_active', 'joints')
    list_editable     = ('is_active',)
    search_fields     = ('name', 'sku')
    filter_horizontal = ('joints',)
    inlines           = [BundleItemInline]
    fieldsets = (
        (None, {'fields': ('name', 'sku', 'description', 'price', 'image', 'is_active')}),
        ('Branch availability', {
            'description': 'Select one or more branches. Leave empty to make available everywhere.',
            'fields': ('joints',),
        }),
    )

    @admin.display(description='Branches')
    def branch_display(self, obj):
        joints = list(obj.joints.all())
        if not joints:
            return '— all branches —'
        return ', '.join(j.display_name for j in joints)


# ─── Register on custom admin site too ───────────────────────────────────────
genx_admin_site.register(Promotion, PromotionAdmin)


class SpendThresholdAdmin(admin.ModelAdmin):
    list_display  = ['promotion', '__str__']
    list_filter   = ['promotion__joint']
    search_fields = ['promotion__name']

genx_admin_site.register(SpendThresholdPromo, SpendThresholdAdmin)


class FreeGiftAdmin(admin.ModelAdmin):
    list_display  = ['promotion', '__str__']
    list_filter   = ['promotion__joint']
    search_fields = ['promotion__name']

genx_admin_site.register(FreeGiftPromo, FreeGiftAdmin)


class BundlePromoAdmin(admin.ModelAdmin):
    list_display  = ['promotion', '__str__']
    list_filter   = ['promotion__joint']
    search_fields = ['promotion__name']

genx_admin_site.register(BundlePromo, BundlePromoAdmin)