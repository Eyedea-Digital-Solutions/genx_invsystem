from django.urls import path
from . import views

app_name = 'ecocash'

urlpatterns = [
    path('', views.pending_payments, name='pending_payments'),
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('<int:pk>/confirm/', views.confirm_payment, name='confirm_payment'),
    path('<int:pk>/fail/', views.fail_payment, name='fail_payment'),
]
