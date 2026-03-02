from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.inventory_dashboard, name='inventory_dashboard'),
    path('products/', views.product_list, name='product_list'),
    path('products/add/', views.product_create, name='product_create'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pk>/stock-adjust/', views.stock_adjust, name='stock_adjust'),
    path('stock-takes/', views.stock_take_list, name='stock_take_list'),
    path('stock-takes/new/', views.stock_take_create, name='stock_take_create'),
    path('stock-takes/<int:pk>/', views.stock_take_detail, name='stock_take_detail'),
    path('transfers/new/', views.transfer_create, name='transfer_create'),
    # AJAX endpoint
    path('api/products/', views.get_products_by_joint, name='get_products_by_joint'),
]
