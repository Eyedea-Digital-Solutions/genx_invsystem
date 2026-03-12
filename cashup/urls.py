from django.urls import path
from . import views

app_name = 'cashup'

urlpatterns = [
    path('', views.cashup_dashboard, name='dashboard'),
    path('open/', views.cashup_open, name='open'),
    path('<int:pk>/count/', views.cashup_count, name='count'),
    path('<int:pk>/', views.cashup_detail, name='detail'),
    path('list/', views.cashup_list, name='list'),
    path('report/', views.cashup_report, name='report'),
    path('<int:pk>/api/live/', views.cashup_api_live, name='api_live'),
]