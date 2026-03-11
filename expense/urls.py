"""
expense/urls.py
"""
from django.urls import path
from . import views

app_name = 'expense'

urlpatterns = [
    path('',                          views.expense_list,    name='expense_list'),
    path('new/',                      views.expense_create,  name='expense_create'),
    path('<int:pk>/edit/',            views.expense_edit,    name='expense_edit'),
    path('<int:pk>/delete/',          views.expense_delete,  name='expense_delete'),
    path('categories/',               views.category_list,   name='category_list'),
    path('categories/new/',           views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_edit,   name='category_edit'),
]