from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import Promotion, SpendThresholdPromo, FreeGiftPromo, BundlePromo
from .forms import PromotionBaseForm, SpendThresholdForm, FreeGiftForm, BundleForm
from inventory.models import Product


def manager_required(view_func):
    from functools import wraps
    from django.shortcuts import redirect
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('users:login')
        if not request.user.is_manager_role:
            messages.error(request, "Managers and above only.")
            return redirect('sales:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def admin_required(view_func):
    from functools import wraps
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('users:login')
        if not request.user.is_admin_role:
            messages.error(request, "Admins only.")
            return redirect('sales:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@manager_required
def promo_dashboard(request):
    today = timezone.now().date()
    all_promos = Promotion.objects.select_related('joint').all()

    active = [p for p in all_promos if p.status_label == 'active']
    upcoming = [p for p in all_promos if p.status_label == 'upcoming']
    expired = [p for p in all_promos if p.status_label == 'expired']
    inactive = [p for p in all_promos if p.status_label == 'inactive']

    clearance_products = Product.objects.select_related('joint', 'stock').filter(
        is_clearance=True, is_active=True
    )

    return render(request, 'promotions/dashboard.html', {
        'active': active,
        'upcoming': upcoming,
        'expired': expired,
        'inactive': inactive,
        'clearance_products': clearance_products,
    })


@login_required
@admin_required
def promo_create(request):
    base_form = PromotionBaseForm(request.POST or None)
    spend_form = SpendThresholdForm(request.POST or None, prefix='spend')
    gift_form = FreeGiftForm(request.POST or None, prefix='gift')
    bundle_form = BundleForm(request.POST or None, prefix='bundle')

    if request.method == 'POST' and base_form.is_valid():
        promo = base_form.save(commit=False)
        promo.created_by = request.user
        promo_type = promo.promo_type

        if promo_type == 'spend_threshold' and spend_form.is_valid():
            promo.save()
            sp = spend_form.save(commit=False)
            sp.promotion = promo
            sp.save()
            messages.success(request, f"Spend threshold promotion '{promo.name}' created.")
            return redirect('promotions:dashboard')

        elif promo_type in ('free_gift', 'buy_n_get_n') and gift_form.is_valid():
            promo.save()
            gp = gift_form.save(commit=False)
            gp.promotion = promo
            gp.save()
            messages.success(request, f"Free gift promotion '{promo.name}' created.")
            return redirect('promotions:dashboard')

        elif promo_type == 'bundle' and bundle_form.is_valid():
            promo.save()
            bp = bundle_form.save(commit=False)
            bp.promotion = promo
            bp.save()
            bundle_form.save_m2m()
            messages.success(request, f"Bundle promotion '{promo.name}' created.")
            return redirect('promotions:dashboard')
        else:
            messages.error(request, "Please fill in all required fields for this promotion type.")

    return render(request, 'promotions/promo_form.html', {
        'base_form': base_form,
        'spend_form': spend_form,
        'gift_form': gift_form,
        'bundle_form': bundle_form,
        'title': 'Create Promotion',
    })


@login_required
@manager_required
def promo_toggle(request, pk):
    promo = get_object_or_404(Promotion, pk=pk)
    promo.is_active = not promo.is_active
    promo.save()
    state = "activated" if promo.is_active else "deactivated"
    messages.success(request, f"Promotion '{promo.name}' {state}.")
    return redirect('promotions:dashboard')


@login_required
@manager_required
def promo_detail(request, pk):
    promo = get_object_or_404(Promotion, pk=pk)
    detail = None
    if promo.promo_type == 'spend_threshold' and hasattr(promo, 'spend_threshold'):
        detail = promo.spend_threshold
    elif promo.promo_type in ('free_gift', 'buy_n_get_n') and hasattr(promo, 'free_gift'):
        detail = promo.free_gift
    elif promo.promo_type == 'bundle' and hasattr(promo, 'bundle'):
        detail = promo.bundle
    return render(request, 'promotions/promo_detail.html', {'promo': promo, 'detail': detail})
