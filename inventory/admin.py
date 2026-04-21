import datetime

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.urls import reverse

from inventory_system.admin_site import genx_admin_site
from .models import Joint, Product, Stock, StockTake, StockTakeItem, StockTransfer, Category, Brand, Supplier, ProductFreeAccessory


# ─── JOINT ──────────────────────────────────────────────────────────────────
class JointAdmin(admin.ModelAdmin):
    list_display    = ['display_name', 'name', 'phone', 'address_short', 'uses_product_codes',
                       'active_product_count', 'total_stock_value']
    list_filter     = ['uses_product_codes']
    search_fields   = ['display_name', 'name', 'phone']
    readonly_fields = ['active_product_count', 'total_stock_value']

    fieldsets = (
        (None, {'fields': ('name', 'display_name', 'phone', 'address', 'uses_product_codes')}),
    )

    @admin.display(description='Address')
    def address_short(self, obj):
        return (obj.address[:40] + '…') if len(obj.address) > 40 else obj.address or '—'

    @admin.display(description='Active Products')
    def active_product_count(self, obj):
        count = obj.products.filter(is_active=True).count()
        url   = reverse('genx_admin:inventory_product_changelist') + f'?joint__id__exact={obj.pk}&is_active__exact=1'
        return format_html('<a href="{}">{}</a>', url, count)

    @admin.display(description='Stock Value')
    def total_stock_value(self, obj):
        total = (
            Product.objects
            .filter(joint=obj, is_active=True)
            .select_related('stock')
            .annotate(val=ExpressionWrapper(F('price') * F('stock__quantity'), output_field=DecimalField()))
            .aggregate(t=Sum('val'))['t']
        ) or 0
        return format_html('<strong>${:.2f}</strong>', total)


genx_admin_site.register(Joint, JointAdmin)


# ─── BRAND ──────────────────────────────────────────────────────────────────
class BrandAdmin(admin.ModelAdmin):
    list_display  = ['name', 'product_count']
    search_fields = ['name']

    @admin.display(description='Products')
    def product_count(self, obj):
        count = obj.product_set.count()
        url   = reverse('genx_admin:inventory_product_changelist') + f'?brand__id__exact={obj.pk}'
        return format_html('<a href="{}">{}</a>', url, count)


genx_admin_site.register(Brand, BrandAdmin)


# ─── SUPPLIER ────────────────────────────────────────────────────────────────
class SupplierAdmin(admin.ModelAdmin):
    list_display  = ['name', 'contact_person', 'phone', 'email', 'stock_items']
    search_fields = ['name', 'contact_person', 'phone', 'email']

    fieldsets = (
        (None, {'fields': ('name', 'contact_person')}),
        ('Contact', {'fields': ('phone', 'email', 'address')}),
    )

    @admin.display(description='Stock Items')
    def stock_items(self, obj):
        return obj.stock_set.count()


genx_admin_site.register(Supplier, SupplierAdmin)


# ─── CATEGORY ────────────────────────────────────────────────────────────────
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ['name', 'joint', 'icon', 'color_swatch', 'sort_order', 'product_count']
    list_filter   = ['joint']
    search_fields = ['name']
    list_editable = ['sort_order']
    ordering      = ['joint', 'sort_order', 'name']

    @admin.display(description='Colour')
    def color_swatch(self, obj):
        if obj.color:
            return format_html(
                '<span style="display:inline-flex;align-items:center;gap:5px;">'
                '<span style="width:16px;height:16px;background:{};border-radius:3px;border:1px solid #e5e7eb;"></span>'
                '<code style="font-size:10px;">{}</code></span>',
                obj.color, obj.color
            )
        return '—'

    @admin.display(description='Products')
    def product_count(self, obj):
        count = obj.products.count()
        url   = reverse('genx_admin:inventory_product_changelist') + f'?category__id__exact={obj.pk}'
        return format_html('<a href="{}">{}</a>', url, count)


genx_admin_site.register(Category, CategoryAdmin)


# ─── STOCK INLINE ────────────────────────────────────────────────────────────
class StockInline(admin.StackedInline):
    model         = Stock
    extra         = 0
    can_delete    = False
    fields        = ['quantity', 'min_quantity', 'reorder_level', 'supplier', 'batch_number', 'expiry_date']
    verbose_name  = 'Stock Level'

    def has_add_permission(self, request, obj=None):
        return False


# ─── FREE ACCESSORY INLINE ───────────────────────────────────────────────────
# Must be defined BEFORE ProductAdmin which references it in `inlines`
class ProductFreeAccessoryInline(admin.TabularInline):
    """
    Shown inside ProductAdmin so managers can attach free accessories
    directly on the product edit page.
    """
    model               = ProductFreeAccessory
    extra               = 1
    fk_name             = 'trigger_product'
    fields              = ['accessory_product', 'quantity', 'label', 'is_active']
    verbose_name        = 'Free Accessory'
    verbose_name_plural = 'Free Accessories (auto-added to cart)'

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Limit accessory choices to the same joint as the trigger product."""
        if db_field.name == 'accessory_product' and hasattr(request, '_product_joint'):
            kwargs['queryset'] = Product.objects.filter(
                joint=request._product_joint, is_active=True
            ).order_by('name')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


# ─── PRODUCT ─────────────────────────────────────────────────────────────────
class ProductAdmin(admin.ModelAdmin):
    list_display   = ['name', 'code', 'barcode_display', 'joint', 'category', 'brand',
                       'price_display', 'effective_price_display', 'stock_display',
                       'promo_flags', 'is_clearance', 'is_active']
    list_filter    = ['joint', 'is_active', 'is_clearance', 'category', 'brand']
    search_fields  = ['name', 'code', 'barcode']
    list_editable  = ['is_clearance', 'is_active']
    list_per_page  = 50
    ordering       = ['joint', 'name']
    inlines        = [StockInline, ProductFreeAccessoryInline]
    readonly_fields = ['effective_price', 'promotion_label', 'current_stock',
                       'created_at', 'updated_at', 'image_preview']

    fieldsets = (
        ('Basic Info', {
            'fields': ('joint', 'code', 'barcode', 'name', 'category', 'brand', 'is_active')
        }),
        ('Pricing', {
            'fields': ('price', 'effective_price')
        }),
        ('Sale / Promotion', {
            'fields': ('sale_price', 'sale_start', 'sale_end',
                       'is_clearance', 'clearance_price', 'promotion_label'),
            'classes': ('collapse',),
        }),
        ('Image', {
            'fields': ('image', 'image_preview'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Barcode')
    def barcode_display(self, obj):
        return obj.barcode or '—'

    @admin.display(description='Price', ordering='price')
    def price_display(self, obj):
        return format_html('${}', obj.price)

    @admin.display(description='Eff. Price')
    def effective_price_display(self, obj):
        ep = obj.effective_price
        if ep != obj.price:
            return format_html(
                '<span style="color:#16a34a;font-weight:700;">${}</span> '
                '<span style="text-decoration:line-through;color:#9ca3af;font-size:10px;">${}</span>',
                ep, obj.price
            )
        return format_html('${}', ep)

    @admin.display(description='Stock', ordering='stock__quantity')
    def stock_display(self, obj):
        qty = obj.current_stock
        if qty == 0:
            return format_html('<span style="background:#fee2e2;color:#dc2626;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700;">OUT</span>')
        if obj.is_low_stock:
            return format_html('<span style="background:#fef3c7;color:#d97706;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700;">{} ⚠</span>', qty)
        return format_html('<span style="color:#16a34a;font-weight:600;">{}</span>', qty)

    @admin.display(description='Flags')
    def promo_flags(self, obj):
        badges = []
        if obj.is_clearance:
            badges.append('<span style="background:#5b21b6;color:#fff;padding:1px 6px;border-radius:3px;font-size:10px;font-weight:700;">CLR</span>')
        if obj.promotion_label == 'SALE':
            badges.append('<span style="background:#d97706;color:#fff;padding:1px 6px;border-radius:3px;font-size:10px;font-weight:700;">SALE</span>')
        return format_html(' '.join(badges)) if badges else '—'

    @admin.display(description='Image Preview')
    def image_preview(self, obj):
        if obj.image_url:
            return format_html(
                '<img src="{}" style="max-height:130px;max-width:220px;border-radius:7px;border:1px solid #e5e7eb;" />',
                obj.image_url
            )
        return '—'

    actions = ['mark_clearance', 'unmark_clearance', 'deactivate_products', 'activate_products']

    @admin.action(description='✓ Mark selected as clearance')
    def mark_clearance(self, request, queryset):
        n = queryset.update(is_clearance=True)
        self.message_user(request, f'{n} product(s) marked as clearance.')

    @admin.action(description='✗ Remove clearance flag')
    def unmark_clearance(self, request, queryset):
        n = queryset.update(is_clearance=False)
        self.message_user(request, f'{n} product(s) updated.')

    @admin.action(description='⏸ Deactivate selected products')
    def deactivate_products(self, request, queryset):
        n = queryset.update(is_active=False)
        self.message_user(request, f'{n} product(s) deactivated.')

    @admin.action(description='▶ Activate selected products')
    def activate_products(self, request, queryset):
        n = queryset.update(is_active=True)
        self.message_user(request, f'{n} product(s) activated.')


genx_admin_site.register(Product, ProductAdmin)


# ─── STOCK ───────────────────────────────────────────────────────────────────
class StockAdmin(admin.ModelAdmin):
    list_display   = ['product_link', 'joint_display', 'quantity', 'min_quantity',
                       'reorder_level', 'supplier', 'batch_number', 'expiry_display', 'last_updated']
    list_filter    = ['product__joint', 'supplier']
    search_fields  = ['product__name', 'product__code', 'batch_number']
    list_editable  = ['quantity', 'min_quantity', 'reorder_level']
    ordering       = ['product__joint', 'product__name']
    list_per_page  = 60
    readonly_fields = ['last_updated', 'last_stock_take']

    fieldsets = (
        ('Product', {'fields': ('product',)}),
        ('Levels', {'fields': ('quantity', 'min_quantity', 'reorder_level')}),
        ('Details', {'fields': ('supplier', 'batch_number', 'expiry_date', 'last_stock_take', 'last_updated')}),
    )

    @admin.display(description='Product', ordering='product__name')
    def product_link(self, obj):
        url = reverse('genx_admin:inventory_product_change', args=[obj.product_id])
        return format_html('<a href="{}" style="font-weight:600;">{}</a>', url, obj.product.name)

    @admin.display(description='Joint', ordering='product__joint__display_name')
    def joint_display(self, obj):
        return obj.product.joint.display_name

    @admin.display(description='Expiry')
    def expiry_display(self, obj):
        if not obj.expiry_date:
            return '—'
        today = datetime.date.today()
        days  = (obj.expiry_date - today).days
        if days < 0:
            return format_html('<span style="background:#fee2e2;color:#dc2626;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:700;">EXPIRED</span>')
        if days <= 7:
            return format_html('<span style="background:#fee2e2;color:#dc2626;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:700;">{} days left ⚠</span>', days)
        if days <= 30:
            return format_html('<span style="background:#fef3c7;color:#d97706;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:700;">{} days left</span>', days)
        return format_html('<span style="color:#16a34a;font-size:12px;">{}</span>', obj.expiry_date)

    actions = ['zero_stock']

    @admin.action(description='⚠ Zero out stock (set quantity to 0)')
    def zero_stock(self, request, queryset):
        n = queryset.update(quantity=0)
        self.message_user(request, f'{n} stock record(s) zeroed.', level='warning')


genx_admin_site.register(Stock, StockAdmin)


# ─── STOCK TAKE ───────────────────────────────────────────────────────────────
class StockTakeItemInline(admin.TabularInline):
    model           = StockTakeItem
    extra           = 0
    readonly_fields = ['product', 'system_count', 'actual_count', 'variance_col']
    can_delete      = False
    fields          = ['product', 'system_count', 'actual_count', 'variance_col']

    @admin.display(description='Variance')
    def variance_col(self, obj):
        v = obj.variance
        if v > 0:
            return format_html('<span style="color:#16a34a;font-weight:700;">+{}</span>', v)
        if v < 0:
            return format_html('<span style="color:#dc2626;font-weight:700;">{}</span>', v)
        return format_html('<span style="color:#9ca3af;">0</span>')


class StockTakeAdmin(admin.ModelAdmin):
    list_display    = ['joint', 'conducted_by', 'conducted_at_fmt', 'item_count', 'restocked_count', 'notes_short']
    list_filter     = ['joint', 'conducted_by']
    search_fields   = ['joint__display_name', 'conducted_by__username', 'notes']
    readonly_fields = ['conducted_at']
    inlines         = [StockTakeItemInline]

    @admin.display(description='Conducted At', ordering='conducted_at')
    def conducted_at_fmt(self, obj):
        return obj.conducted_at.strftime('%d %b %Y %H:%M')

    @admin.display(description='Total Items')
    def item_count(self, obj):
        return obj.items.count()

    @admin.display(description='Items Added')
    def restocked_count(self, obj):
        changed = obj.items.filter(actual_count__gt=0).count()
        return format_html('<span style="color:#16a34a;font-weight:600;">{}</span>', changed) if changed else '0'

    @admin.display(description='Notes')
    def notes_short(self, obj):
        if obj.notes:
            return (obj.notes[:50] + '…') if len(obj.notes) > 50 else obj.notes
        return '—'


genx_admin_site.register(StockTake, StockTakeAdmin)


# ─── STOCK TRANSFER ───────────────────────────────────────────────────────────
class StockTransferAdmin(admin.ModelAdmin):
    list_display    = ['product', 'from_joint', 'arrow', 'to_joint', 'quantity',
                       'transferred_by', 'transferred_at_fmt', 'status_badge']
    list_filter     = ['status', 'from_joint', 'to_joint']
    search_fields   = ['product__name', 'transferred_by__username', 'notes']
    readonly_fields = ['transferred_at']

    @admin.display(description='')
    def arrow(self, obj):
        return format_html('<span style="color:#9ca3af;">→</span>')

    @admin.display(description='Transferred At', ordering='transferred_at')
    def transferred_at_fmt(self, obj):
        return obj.transferred_at.strftime('%d %b %Y %H:%M')

    @admin.display(description='Status')
    def status_badge(self, obj):
        if obj.status == 'completed':
            return format_html('<span style="background:#d1fae5;color:#065f46;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;">✓ Completed</span>')
        return format_html('<span style="background:#fef3c7;color:#92400e;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;">⏳ Pending</span>')

    actions = ['mark_completed']

    @admin.action(description='✓ Mark selected transfers as completed')
    def mark_completed(self, request, queryset):
        n = queryset.filter(status='pending').update(status='completed')
        self.message_user(request, f'{n} transfer(s) marked as completed.')


genx_admin_site.register(StockTransfer, StockTransferAdmin)


# ─── FREE ACCESSORY (standalone) ─────────────────────────────────────────────
class ProductFreeAccessoryAdmin(admin.ModelAdmin):
    """
    Standalone admin for browsing/editing all free accessory bundles.
    """
    list_display  = ['trigger_product', 'joint_display', 'arrow', 'accessory_product',
                     'quantity', 'label', 'accessory_stock', 'is_active']
    list_filter   = ['is_active', 'trigger_product__joint']
    search_fields = ['trigger_product__name', 'accessory_product__name', 'label']
    list_editable = ['quantity', 'is_active']
    ordering      = ['trigger_product__joint__name', 'trigger_product__name']

    fieldsets = (
        (None, {
            'fields': ('trigger_product', 'accessory_product', 'quantity', 'label', 'is_active'),
            'description': (
                'When the <strong>Trigger Product</strong> is added to the POS cart, '
                '<strong>Quantity</strong> units of the <strong>Accessory Product</strong> '
                'are automatically added for free and deducted from stock on sale.'
            ),
        }),
    )

    @admin.display(description='Joint', ordering='trigger_product__joint__display_name')
    def joint_display(self, obj):
        return obj.trigger_product.joint.display_name

    @admin.display(description='')
    def arrow(self, obj):
        return format_html('<span style="color:#9ca3af;font-weight:700;">→ FREE</span>')

    @admin.display(description='Accessory Stock')
    def accessory_stock(self, obj):
        qty = obj.accessory_product.current_stock
        if qty == 0:
            return format_html(
                '<span style="background:#fee2e2;color:#dc2626;padding:2px 7px;'
                'border-radius:4px;font-size:10px;font-weight:700;">OUT OF STOCK</span>'
            )
        if qty <= obj.accessory_product.stock.min_quantity:
            return format_html(
                '<span style="background:#fef3c7;color:#d97706;padding:2px 7px;'
                'border-radius:4px;font-size:10px;font-weight:700;">{} ⚠ LOW</span>', qty
            )
        return format_html('<span style="color:#16a34a;font-weight:600;">{}</span>', qty)


genx_admin_site.register(ProductFreeAccessory, ProductFreeAccessoryAdmin)
