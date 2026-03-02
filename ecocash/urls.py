from django.urls import path
from . import views

app_name = 'ecocash'

urlpatterns = [
    path('pending/', views.pending_payments, name='pending_payments'),
    path('confirm/<int:pk>/', views.confirm_payment_view, name='confirm_payment'),
    path('transactions/', views.transaction_list, name='transaction_list'),
]
