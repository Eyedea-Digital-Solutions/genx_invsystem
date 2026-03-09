from django.urls import path
from . import views

app_name = 'promotions'

urlpatterns = [
    path('', views.promo_dashboard, name='dashboard'),
    path('create/', views.promo_create, name='create'),
    path('<int:pk>/toggle/', views.promo_toggle, name='toggle'),
    path('<int:pk>/', views.promo_detail, name='detail'),
]
