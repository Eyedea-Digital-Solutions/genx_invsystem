"""
sales/urls.py  ── updated for Section 3 analytics upgrade
Drop this file in place of the existing sales/urls.py.
All original routes preserved; new analytics routes appended.
"""
from django.urls import path
from . import views
from . import analytics_views
from .receipt_api import receipt_data_api

app_name = "sales"

urlpatterns = [
    # ── Original POS / Sale routes (unchanged) ─────────────────────────────────
    path("",                        views.dashboard,              name="dashboard"),
    path("pos/",                    views.pos,                    name="pos"),
    path("pos/scan/",               views.pos_scan,               name="pos_scan"),
    path("pos/search/",             views.pos_search,             name="pos_search"),
    path("pos/categories/",         views.pos_categories,         name="pos_categories"),
    path("pos/update-cart/",        views.pos_update_cart,        name="pos_update_cart"),
    path("pos/complete/",           views.pos_complete,           name="pos_complete"),
    path("pos/hold/",               views.pos_hold,               name="pos_hold"),
    path("pos/recall/<int:pk>/",    views.pos_recall,             name="pos_recall"),
    path("make/",                   views.make_sale,              name="make_sale"),
    path("manual/",                 views.manual_sale,            name="manual_sale"),
    path("list/",                   views.sale_list,              name="sale_list"),
    path("<int:pk>/",               views.sale_detail,            name="sale_detail"),
    path("<int:pk>/receipt/",       views.sale_receipt,           name="sale_receipt"),
    path("<int:pk>/receipt/thermal/",   views.sale_receipt_thermal,   name="sale_receipt_thermal"),
    path("<int:pk>/receipt/data/",      receipt_data_api,             name="receipt_data_api"),
    path("reports/",                views.reports,                name="reports"),

    # ── Analytics dashboard ────────────────────────────────────────────────────
    path(
        "analytics/",
        analytics_views.analytics_dashboard,
        name="analytics_dashboard",
    ),

    # ── Chart data JSON endpoints ──────────────────────────────────────────────
    path(
        "analytics/api/revenue/",
        analytics_views.analytics_api_revenue,
        name="analytics_api_revenue",
    ),
    path(
        "analytics/api/top-products/",
        analytics_views.analytics_api_top_products,
        name="analytics_api_top_products",
    ),
    path(
        "analytics/api/payment-breakdown/",
        analytics_views.analytics_api_payment_breakdown,
        name="analytics_api_payment_breakdown",
    ),
    path(
        "analytics/api/hourly/",
        analytics_views.analytics_api_hourly,
        name="analytics_api_hourly",
    ),
    path(
        "analytics/api/staff/",
        analytics_views.analytics_api_staff,
        name="analytics_api_staff",
    ),

    # ── Advanced analytics endpoints ───────────────────────────────────────────
    path(
        "analytics/api/cohort/",
        analytics_views.analytics_api_cohort,
        name="analytics_api_cohort",
    ),
    path(
        "analytics/api/basket/",
        analytics_views.analytics_api_basket,
        name="analytics_api_basket",
    ),
    path(
        "analytics/api/velocity/",
        analytics_views.analytics_api_velocity,
        name="analytics_api_velocity",
    ),

    # ── Live KPI refresh (polled every 60s) ────────────────────────────────────
    path(
        "analytics/api/live/",
        analytics_views.analytics_api_live_kpis,
        name="analytics_api_live",
    ),

    # ── Export ─────────────────────────────────────────────────────────────────
    path(
        "analytics/export/",
        analytics_views.analytics_export_csv,
        name="analytics_export_csv",
    ),
]