from django.urls import path
from . import views

app_name = 'purchasing'

urlpatterns = [
    path('',                        views.po_list,            name='po_list'),
    path('new/',                    views.po_create,          name='po_create'),
    path('<int:pk>/',               views.po_detail,          name='po_detail'),
    path('<int:pk>/order/',         views.po_mark_ordered,    name='po_mark_ordered'),
    path('<int:pk>/cancel/',        views.po_cancel,          name='po_cancel'),
    path('<int:po_pk>/receive/',    views.grn_create,         name='grn_create'),
    path('grn/<int:pk>/',           views.grn_detail,         name='grn_detail'),
    path('api/products/',           views.api_products_for_joint, name='api_products'),
]