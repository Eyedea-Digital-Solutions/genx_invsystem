from django.contrib import admin
from .models import Joint, Product, Stock, StockTake, StockTakeItem, StockTransfer


@admin.register(Joint)
class JointAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'name', 'phone', 'uses_product_codes']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'joint', 'price', 'current_stock', 'is_active']
    list_filter = ['joint', 'is_active']
    search_fields = ['name', 'code']


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ['product', 'quantity', 'last_stock_take', 'last_updated']
    list_filter = ['product__joint']


@admin.register(StockTake)
class StockTakeAdmin(admin.ModelAdmin):
    list_display = ['joint', 'conducted_by', 'conducted_at']
    inlines_pass = True


@admin.register(StockTransfer)
class StockTransferAdmin(admin.ModelAdmin):
    list_display = ['product', 'from_joint', 'to_joint', 'quantity', 'transferred_by', 'status']
