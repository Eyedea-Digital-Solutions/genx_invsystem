from django.contrib import admin
from .models import Joint, Product, Stock, StockTake, StockTakeItem, StockTransfer, Category, Brand, Supplier


@admin.register(Joint)
class JointAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'name', 'phone', 'uses_product_codes']


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['name']
    search_fields = ['name']


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact_person', 'phone', 'email']
    search_fields = ['name']


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'joint', 'sort_order']
    list_filter = ['joint']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'barcode', 'joint', 'price', 'effective_price', 'current_stock', 'is_clearance', 'is_active']
    list_filter = ['joint', 'is_active', 'is_clearance', 'category']
    search_fields = ['name', 'code', 'barcode']
    list_editable = ['is_clearance', 'is_active']


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ['product', 'quantity', 'min_quantity', 'reorder_level', 'expiry_date', 'last_updated']
    list_filter = ['product__joint']


class StockTakeItemInline(admin.TabularInline):
    model = StockTakeItem
    extra = 0
    readonly_fields = ['product', 'system_count', 'actual_count']
    can_delete = False


@admin.register(StockTake)
class StockTakeAdmin(admin.ModelAdmin):
    list_display = ['joint', 'conducted_by', 'conducted_at']
    inlines = [StockTakeItemInline]


@admin.register(StockTransfer)
class StockTransferAdmin(admin.ModelAdmin):
    list_display = ['product', 'from_joint', 'to_joint', 'quantity', 'transferred_by', 'status']
