from django.urls import path
from . import views

app_name = 'sales'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('make/', views.make_sale, name='make_sale'),
    path('manual/', views.manual_sale, name='manual_sale'),
    path('list/', views.sale_list, name='sale_list'),
    path('<int:pk>/', views.sale_detail, name='sale_detail'),
    path('<int:pk>/receipt/', views.sale_receipt, name='sale_receipt'),
    path('reports/', views.reports, name='reports'),
]
