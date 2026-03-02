from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    # Root URL redirects to the sales dashboard
    path('', RedirectView.as_view(pattern_name='sales:dashboard'), name='home'),
    path('users/', include('users.urls', namespace='users')),
    path('inventory/', include('inventory.urls', namespace='inventory')),
    path('sales/', include('sales.urls', namespace='sales')),
    path('ecocash/', include('ecocash.urls', namespace='ecocash')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
  + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
