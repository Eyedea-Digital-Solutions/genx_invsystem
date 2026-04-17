"""
sales/context_processors.py
Injects live admin stats into every template context.
Mirrors the logic in GenXAdminSite._get_stats() but for the main site.
"""
from decimal import Decimal


def admin_stats(request):
    """
    Returns a dict of live stats used in the sidebar / topbar.
    Each stat is fetched independently — a single failure never crashes a page.
    """
    if not request.user.is_authenticated:
        return {}

    from django.utils import timezone
    today = timezone.now().date()
    month_start = today.replace(day=1)

    stats = {
        'today_total':     Decimal('0'),
        'today_count':     0,
        'month_total':     Decimal('0'),
        'month_count':     0,
        'pending_ecocash': 0,
        'low_stock_count': 0,
        'held_count':      0,
        'active_promos':   0,
    }

    # Today's sales
    try:
        from django.db.models import Sum
        from sales.models import Sale, SaleItem

        today_qs = Sale.objects.filter(sale_date__date=today, is_held=False)
        stats['today_count'] = today_qs.count()

        today_total = (
            SaleItem.objects
            .filter(sale__sale_date__date=today, sale__is_held=False)
            .aggregate(t=Sum('line_total'))['t']
        )
        if today_total is None:
            today_total = today_qs.aggregate(t=Sum('total_amount'))['t']
        stats['today_total'] = today_total or Decimal('0')
    except Exception:
        pass

    # Month's sales
    try:
        from django.db.models import Sum
        from sales.models import Sale, SaleItem

        month_qs = Sale.objects.filter(
            sale_date__date__gte=month_start, is_held=False
        )
        stats['month_count'] = month_qs.count()

        month_total = (
            SaleItem.objects
            .filter(sale__sale_date__date__gte=month_start, sale__is_held=False)
            .aggregate(t=Sum('line_total'))['t']
        )
        if month_total is None:
            month_total = month_qs.aggregate(t=Sum('total_amount'))['t']
        stats['month_total'] = month_total or Decimal('0')
    except Exception:
        pass

    # Pending EcoCash
    try:
        from ecocash.models import EcoCashTransaction
        stats['pending_ecocash'] = EcoCashTransaction.objects.filter(
            status=EcoCashTransaction.STATUS_PENDING
        ).count()
    except Exception:
        pass

    # Low stock
    try:
        from django.conf import settings as django_settings
        from inventory.models import Stock

        threshold = getattr(django_settings, 'LOW_STOCK_THRESHOLD', 3)
        stats['low_stock_count'] = (
            Stock.objects
            .filter(product__is_active=True, quantity__lte=threshold)
            .count()
        )
    except Exception:
        pass

    # Held sales
    try:
        from sales.models import Sale
        stats['held_count'] = Sale.objects.filter(is_held=True).count()
    except Exception:
        pass

    # Active promotions — pure DB query, no Python-side is_currently_active
    try:
        from promotions.models import Promotion
        from django.db.models import Q

        now = timezone.now()
        today_date = now.date()

        stats['active_promos'] = Promotion.objects.filter(
            is_active=True,
        ).filter(
            Q(start_date__isnull=True) | Q(start_date__lte=today_date)
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=today_date)
        ).count()
    except Exception:
        pass

    return stats