from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

from inventory_system.admin_site import genx_admin_site  # ← custom site

urlpatterns = [
    path("admin/", genx_admin_site.urls),
    path("", RedirectView.as_view(pattern_name="sales:pos"), name="home"),
    path("users/",      include("users.urls",      namespace="users")),
    path("inventory/",  include("inventory.urls",  namespace="inventory")),
    path("sales/",      include("sales.urls",      namespace="sales")),
    path("ecocash/",    include("ecocash.urls",    namespace="ecocash")),
    path("promotions/", include("promotions.urls", namespace="promotions")),
    path('expenses/', include('expenses.urls')),
] + static(settings.MEDIA_URL,  document_root=settings.MEDIA_ROOT) \
  + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
