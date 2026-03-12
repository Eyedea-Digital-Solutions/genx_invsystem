"""
sales/context_processors.py
Injects live stats into admin pages. Replaces the broken __import__ pattern.
"""
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal


def admin_stats(request):
    """Only runs queries on admin URL requests."""
    if not request.path.startswith('/admin/') and not request.path.startswith('/genx-admin/'):
        return {}

    try:
        from sales.models import Sale
        from inventory.models import Stock
        from ecocash.models import EcoCashTransaction
        from promotions.models import Promotion

        today       = timezone.localdate()
        month_start = today.replace(day=1)

        completed = Sale.objects.filter(is_held=False)

        today_qs    = completed.filter(sale_date__date=today)
        today_total = today_qs.aggregate(t=Sum('total_amount'))['t'] or Decimal('0.00')
        today_count = today_qs.count()

        month_qs    = completed.filter(sale_date__date__gte=month_start)
        month_total = month_qs.aggregate(t=Sum('total_amount'))['t'] or Decimal('0.00')
        month_count = month_qs.count()

        pending_ecocash = EcoCashTransaction.objects.filter(status='pending').count()
        low_stock_count = Stock.objects.filter(
            product__is_active=True,
            quantity__lte=3
        ).count()
        held_count    = Sale.objects.filter(is_held=True).count()
        active_promos = Promotion.objects.filter(is_active=True).count()

        return {
            'today_total':     today_total,
            'today_count':     today_count,
            'month_total':     month_total,
            'month_count':     month_count,
            'pending_ecocash': pending_ecocash,
            'low_stock_count': low_stock_count,
            'held_count':      held_count,
            'active_promos':   active_promos,
        }

    except Exception:
        return {
            'today_total':     Decimal('0.00'),
            'today_count':     0,
            'month_total':     Decimal('0.00'),
            'month_count':     0,
            'pending_ecocash': 0,
            'low_stock_count': 0,
            'held_count':      0,
            'active_promos':   0,
        }