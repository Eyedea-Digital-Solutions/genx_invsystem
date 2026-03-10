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
        """
        Return a dict of live stats using DB-level aggregation.
        Each stat is fetched independently so a single failure never
        crashes the whole admin panel.
        """
        stats = {
            "today_total":     Decimal("0"),
            "today_count":     0,
            "month_total":     Decimal("0"),
            "month_count":     0,
            "pending_ecocash": 0,
            "low_stock_count": 0,
            "held_count":      0,
            "active_promos":   0,
        }

        today       = timezone.now().date()
        month_start = today.replace(day=1)

        # ── today's sales ──────────────────────────────────────────────
        try:
            from django.db.models import Sum
            from sales.models import Sale, SaleItem

            today_qs = Sale.objects.filter(sale_date__date=today, is_held=False)
            stats["today_count"] = today_qs.count()

            today_total = (
                SaleItem.objects
                .filter(sale__sale_date__date=today, sale__is_held=False)
                .aggregate(t=Sum("line_total"))["t"]
            )
            if today_total is None:
                today_total = today_qs.aggregate(t=Sum("total_amount"))["t"]

            stats["today_total"] = today_total or Decimal("0")
        except Exception:
            pass

        # ── month's sales ──────────────────────────────────────────────
        try:
            from django.db.models import Sum
            from sales.models import Sale, SaleItem

            month_qs = Sale.objects.filter(
                sale_date__date__gte=month_start, is_held=False
            )
            stats["month_count"] = month_qs.count()

            month_total = (
                SaleItem.objects
                .filter(
                    sale__sale_date__date__gte=month_start,
                    sale__is_held=False,
                )
                .aggregate(t=Sum("line_total"))["t"]
            )
            if month_total is None:
                month_total = month_qs.aggregate(t=Sum("total_amount"))["t"]

            stats["month_total"] = month_total or Decimal("0")
        except Exception:
            pass

        # ── pending ecocash ────────────────────────────────────────────
        try:
            from ecocash.models import EcoCashTransaction
            stats["pending_ecocash"] = EcoCashTransaction.objects.filter(
                status=EcoCashTransaction.STATUS_PENDING
            ).count()
        except Exception:
            pass

        # ── low stock ──────────────────────────────────────────────────
        try:
            from django.conf import settings as django_settings
            from inventory.models import Stock

            threshold = getattr(django_settings, "LOW_STOCK_THRESHOLD", 3)
            stats["low_stock_count"] = (
                Stock.objects
                .filter(
                    product__is_active=True,
                    quantity__lte=threshold,
                )
                .count()
            )
        except Exception:
            pass

        # ── held sales ─────────────────────────────────────────────────
        try:
            from sales.models import Sale
            stats["held_count"] = Sale.objects.filter(is_held=True).count()
        except Exception:
            pass

        # ── active promotions — pure DB query, no Python-side filtering ──
        # Avoids the 500 that came from loading all promos and calling
        # the is_currently_active property in Python.
        try:
            from promotions.models import Promotion
            from django.db.models import Q

            now = timezone.now()
            today_date = now.date()

            stats["active_promos"] = Promotion.objects.filter(
                is_active=True,
            ).filter(
                # start_date is null OR start_date <= today
                Q(start_date__isnull=True) | Q(start_date__lte=today_date)
            ).filter(
                # end_date is null OR end_date >= today
                Q(end_date__isnull=True) | Q(end_date__gte=today_date)
            ).count()
        except Exception:
            pass

        return stats


# Singleton — imported everywhere instead of django.contrib.admin.site
genx_admin_site = GenXAdminSite(name="genx_admin")