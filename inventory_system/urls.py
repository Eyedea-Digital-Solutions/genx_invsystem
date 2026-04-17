from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.views.generic import RedirectView
from sales.analytics_views import analytics_dashboard
from sales.views import dashboard
from inventory_system.admin_site import genx_admin_site


def manifest_view(request):
    import json, os
    manifest_path = os.path.join(settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else settings.STATIC_ROOT, 'manifest.json')
    try:
        with open(manifest_path) as f:
            data = json.load(f)
        return JsonResponse(data, content_type='application/manifest+json')
    except Exception:
        return JsonResponse({
            "name": "GenX POS",
            "short_name": "GenX",
            "start_url": "/sales/pos/",
            "display": "standalone",
            "background_color": "#080810",
            "theme_color": "#7c3aed",
            "icons": [{"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png"}]
        }, content_type='application/manifest+json')


urlpatterns = [
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
    path('dashboard/', dashboard, name='main_dashboard'),
    path('admin/', genx_admin_site.urls),

    path('inventory/', include('inventory.urls')),
    path('sales/', include('sales.urls')),
    path('cashup/', include('cashup.urls')),
    path('customers/', include('customers.urls')),
    path('employees/', include('employees.urls')),
    path('users/', include('users.urls')),
    path('returns/', include('returns.urls')),
    path('purchasing/', include('purchasing.urls')),
    path('expenses/', include('expense.urls')),
    path('promotions/', include('promotions.urls')),
    path('ecocash/', include('ecocash.urls')),
    path('analytics/dashboard/', analytics_dashboard, name='analytics_dashboard'),
    path('accounts/', include('django.contrib.auth.urls')),

    path('manifest.json', manifest_view, name='manifest'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
