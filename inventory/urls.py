from django.urls import path
from . import views

app_name = 'inventory'

from inventory.views_v4 import (
    inventory_dashboard,
    stock_take_wizard,
    stock_take_list,
    api_products_for_count,
    api_stock_take_submit,
    api_stock_adjust,
    api_bulk_action,
    export_csv,
    bulk_import,
)

urlpatterns = [
    path('', inventory_dashboard, name='inventory_dashboard'),
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.product_create, name='product_create'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pk>/stock-adjust/', views.stock_adjust, name='stock_adjust'),
    path('low-stock/', views.low_stock_report, name='low_stock_report'),
    path('stock-takes/', stock_take_list, name='stock_take_list'),
    path('stock-takes/new/', stock_take_wizard, name='stock_take_create'),
    path('stock-take/', stock_take_list),
    path('stock-take/new/', stock_take_wizard, name='stock_take_wizard'),
    path('stock-takes/<int:pk>/', views.stock_take_detail, name='stock_take_detail'),
    path('transfers/new/', views.transfer_create, name='transfer_create'),
    path('categories/', views.category_list, name='category_list'),
    path('categories/add/', views.category_create, name='category_create'),
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/add/', views.supplier_create, name='supplier_create'),
    path('api/products/', views.get_products_by_joint, name='get_products_by_joint'),

    path('export/',              export_csv,                name='export_csv'),
    path('import/',              bulk_import,               name='bulk_import'),
    path('api/products-for-count/', api_products_for_count, name='api_products_for_count'),
    path('api/stock-take/submit/',  api_stock_take_submit,  name='api_stock_take_submit'),
    path('api/stock-adjust/',       api_stock_adjust,       name='api_stock_adjust'),
    path('api/bulk-action/',        api_bulk_action,        name='api_bulk_action'),
]
