from django.urls import path
from . import views
from . import analytics_views

app_name = 'sales'

urlpatterns = [
    path('',                        views.dashboard,             name='dashboard'),
    path('pos/',                    views.pos,                   name='pos'),
    path('pos/scan/',               views.pos_scan,              name='pos_scan'),
    path('pos/search/',             views.pos_search,            name='pos_search'),
    path('pos/categories/',         views.pos_categories,        name='pos_categories'),
    path('pos/update-cart/',        views.pos_update_cart,       name='pos_update_cart'),
    path('pos/complete/',           views.pos_complete,          name='pos_complete'),
    path('pos/hold/',               views.pos_hold,              name='pos_hold'),
    path('pos/recall/<int:pk>/',    views.pos_recall,            name='pos_recall'),
    path('make/',                   views.make_sale,             name='make_sale'),
    path('manual/',                 views.manual_sale,           name='manual_sale'),
    path('list/',                   views.sale_list,             name='sale_list'),
    path('<int:pk>/',               views.sale_detail,           name='sale_detail'),
    path('<int:pk>/receipt/',       views.sale_receipt,          name='sale_receipt'),
    path('<int:pk>/receipt/thermal/', views.sale_receipt_thermal, name='sale_receipt_thermal'),
    path('reports/',                views.reports,               name='reports'),

    path('analytics/',                        analytics_views.analytics_dashboard,          name='analytics_dashboard'),
    path('analytics/api/revenue/',            analytics_views.analytics_api_revenue,        name='analytics_api_revenue'),
    path('analytics/api/top-products/',       analytics_views.analytics_api_top_products,   name='analytics_api_top_products'),
    path('analytics/api/payment-breakdown/',  analytics_views.analytics_api_payment_breakdown, name='analytics_api_payment_breakdown'),
    path('analytics/export/',                 analytics_views.analytics_export_csv,         name='analytics_export_csv'),
]