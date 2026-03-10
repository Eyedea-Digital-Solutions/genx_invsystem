"""
inventory_system/admin_site.py
──────────────────────────────
Custom AdminSite that injects live dashboard stats into every admin page
context so templates can display them in the sidebar and on the index page.
"""
from decimal import Decimal

from django.contrib.admin import AdminSite
from django.utils import timezone


class GenXAdminSite(AdminSite):
    site_header  = "GenX POS — Admin"
    site_title   = "GenX POS"
    index_title  = "System Administration"
    enable_nav_sidebar = True

    # ── live stats injected into every admin page ──────────────────────
    def each_context(self, request):
        ctx = super().each_context(request)
        if request.user.is_authenticated:
            ctx.update(self._get_stats())
        return ctx

    @staticmethod
    def _get_stats():
        """Return a dict of live stats, safely — never crash the admin."""
        stats = {
            "today_total":      Decimal("0"),
            "today_count":      0,
            "month_total":      Decimal("0"),
            "month_count":      0,
            "pending_ecocash":  0,
            "low_stock_count":  0,
            "held_count":       0,
            "active_promos":    0,
        }
        try:
            from django.conf import settings as django_settings
            from sales.models import Sale
            from ecocash.models import EcoCashTransaction
            from inventory.models import Product
            from promotions.models import Promotion

            today       = timezone.now().date()
            month_start = today.replace(day=1)
            threshold   = getattr(django_settings, "LOW_STOCK_THRESHOLD", 3)

            today_sales = Sale.objects.filter(
                sale_date__date=today, is_held=False
            ).prefetch_related("items")
            stats["today_count"] = today_sales.count()
            stats["today_total"] = sum(s.total_amount for s in today_sales)

            month_sales = Sale.objects.filter(
                sale_date__date__gte=month_start, is_held=False
            ).prefetch_related("items")
            stats["month_count"] = month_sales.count()
            stats["month_total"] = sum(s.total_amount for s in month_sales)

            stats["pending_ecocash"] = EcoCashTransaction.objects.filter(
                status=EcoCashTransaction.STATUS_PENDING
            ).count()

            stats["low_stock_count"] = Product.objects.filter(
                is_active=True, stock__quantity__lte=threshold
            ).count()

            stats["held_count"] = Sale.objects.filter(is_held=True).count()

            stats["active_promos"] = sum(
                1 for p in Promotion.objects.filter(is_active=True)
                if p.is_currently_active
            )
        except Exception:
            pass
        return stats


# Singleton — imported everywhere instead of django.contrib.admin.site
genx_admin_site = GenXAdminSite(name="genx_admin")
