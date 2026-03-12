from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.utils import timezone

from .models import Customer, LoyaltyTransaction
from .forms import CustomerForm, CustomerSearchForm, LoyaltyAdjustForm


# ── LIST ────────────────────────────────────────────────────────────────────

@login_required
def customer_list(request):
    form = CustomerSearchForm(request.GET or None)
    qs   = Customer.objects.filter(is_active=True)

    if form.is_valid():
        q    = form.cleaned_data.get('q', '')
        ctype = form.cleaned_data.get('customer_type', '')
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q))
        if ctype:
            qs = qs.filter(customer_type=ctype)

    return render(request, 'customers/customer_list.html', {
        'customers': qs.order_by('name'),
        'form': form,
        'total_customers': qs.count(),
    })


# ── CREATE ───────────────────────────────────────────────────────────────────

@login_required
def customer_create(request):
    form = CustomerForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        customer = form.save()
        messages.success(request, f"Customer '{customer.name}' added.")
        return redirect('customers:customer_detail', pk=customer.pk)
    return render(request, 'customers/customer_form.html', {'form': form, 'title': 'Add Customer'})


# ── EDIT ─────────────────────────────────────────────────────────────────────

@login_required
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    form     = CustomerForm(request.POST or None, instance=customer)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f"Customer '{customer.name}' updated.")
        return redirect('customers:customer_detail', pk=customer.pk)
    return render(request, 'customers/customer_form.html', {
        'form': form, 'title': 'Edit Customer', 'customer': customer
    })


# ── DETAIL + PURCHASE HISTORY ────────────────────────────────────────────────

@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    sales = customer.sales.filter(is_held=False).prefetch_related('items__product').order_by('-sale_date')

    # Summary stats
    total_spend   = sum(s.total_amount for s in sales)
    today         = timezone.localdate()
    month_start   = today.replace(day=1)
    month_spend   = sum(
        s.total_amount for s in sales
        if s.sale_date.date() >= month_start
    )

    loyalty_log = customer.loyalty_transactions.select_related('sale', 'performed_by')[:30]

    return render(request, 'customers/customer_detail.html', {
        'customer':     customer,
        'sales':        sales,
        'total_spend':  total_spend,
        'month_spend':  month_spend,
        'sale_count':   sales.count(),
        'loyalty_log':  loyalty_log,
    })


# ── LOYALTY ADJUSTMENT (manager only) ────────────────────────────────────────

@login_required
def loyalty_adjust(request, pk):
    if not request.user.is_manager_role:
        messages.error(request, 'Managers and above only.')
        return redirect('customers:customer_detail', pk=pk)

    customer = get_object_or_404(Customer, pk=pk)
    form     = LoyaltyAdjustForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        points = form.cleaned_data['points']
        reason = form.cleaned_data['reason']
        try:
            customer.adjust_loyalty_points(points, reason, performed_by=request.user)
            direction = 'added to' if points >= 0 else 'deducted from'
            messages.success(request, f"{abs(points)} points {direction} {customer.name}. New balance: {customer.loyalty_points}.")
        except ValueError as e:
            messages.error(request, str(e))
        return redirect('customers:customer_detail', pk=pk)

    return render(request, 'customers/loyalty_adjust.html', {
        'form': form, 'customer': customer
    })


# ── POS API: lookup customer by phone ────────────────────────────────────────

@login_required
def customer_lookup_api(request):
    """
    Called by the POS when a cashier types a phone number.
    Returns JSON for fast customer attachment at checkout.
    """
    q = request.GET.get('q', '').strip()
    if not q or len(q) < 3:
        return JsonResponse({'customers': []})

    qs = Customer.objects.filter(
        Q(phone__icontains=q) | Q(name__icontains=q),
        is_active=True
    )[:10]

    data = [{
        'id':              c.pk,
        'name':            c.name,
        'phone':           c.phone,
        'customer_type':   c.get_customer_type_display(),
        'loyalty_points':  c.loyalty_points,
    } for c in qs]

    return JsonResponse({'customers': data})