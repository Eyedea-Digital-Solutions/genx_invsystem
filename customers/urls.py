from django.urls import path
from . import views

app_name = 'customers'

urlpatterns = [
    path('',                          views.customer_list,       name='customer_list'),
    path('add/',                      views.customer_create,     name='customer_create'),
    path('<int:pk>/',                 views.customer_detail,     name='customer_detail'),
    path('<int:pk>/edit/',            views.customer_edit,       name='customer_edit'),
    path('<int:pk>/loyalty/adjust/',  views.loyalty_adjust,      name='loyalty_adjust'),
    path('api/lookup/',               views.customer_lookup_api, name='lookup_api'),
]