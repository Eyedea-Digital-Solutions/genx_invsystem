from django.urls import path
from . import views

app_name = 'returns'

urlpatterns = [
    path('',                    views.return_search,  name='return_search'),
    path('list/',               views.return_list,    name='return_list'),
    path('new/<int:sale_pk>/',  views.return_create,  name='return_create'),
    path('<int:pk>/confirm/',   views.return_confirm, name='return_confirm'),
    path('<int:pk>/',           views.return_detail,  name='return_detail'),
]