from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST

from .models import CashUp, CashUpAuditLog
from .forms import CashUpOpenForm, CashUpCountForm, ManagerReviewForm, CashUpFilterForm
from inventory.models import Joint
from sales.models import Sale, SaleItem


def _manager_required(request):
    if not request.user.is_manager_role:
        messages.error(request, 'Managers and above only.')
        return True
    return False


@login_required
def cashup_dashboard(request):
    today = timezone.localdate()

    pending_review = CashUp.objects.filter(
        status=CashUp.STATUS_SUBMITTED
    ).select_related('joint', 'cashier').order_by('-submitted_at') if request.user.is_manager_role else CashUp.objects.none()

    my_open = CashUp.objects.filter(
        cashier=request.user,
        status__in=[CashUp.STATUS_OPEN, CashUp.STATUS_SUBMITTED],
    ).select_related('joint').order_by('-shift_date')

    recent = CashUp.objects.select_related(
        'joint', 'cashier', 'approved_by'
    ).order_by('-shift_date', '-opened_at')

    if not request.user.is_manager_role:
        recent = recent.filter(cashier=request.user)

    recent = recent[:20]

    today_stats = {}
    if request.user.is_manager_role:
        for joint in Joint.objects.all():
            approved_today = CashUp.objects.filter(
                joint=joint,
                shift_date=today,
                status=CashUp.STATUS_APPROVED,
            )
            today_stats[joint.pk] = {
                'joint': joint,
                'count': approved_today.count(),
                'total_actual': approved_today.aggregate(
                    t=Sum('actual_cash') + Sum('actual_ecocash') + Sum('actual_card')
                )['t'] or Decimal('0'),
                'disputed': CashUp.objects.filter(
                    joint=joint, shift_date=today, status=CashUp.STATUS_DISPUTED
                ).count(),
            }

    return render(request, 'cashup/dashboard.html', {
        'pending_review': pending_review,
        'my_open': my_open,
        'recent': recent,
        'today_stats': today_stats,
        'today': today,
    })


@login_required
def cashup_open(request):
    initial = {'shift_date': timezone.localdate()}
    if request.user.primary_joint:
        initial['joint'] = request.user.primary_joint

    form = CashUpOpenForm(request.POST or None, initial=initial)

    if request.method == 'POST' and form.is_valid():
        cashup = form.save(commit=False)
        cashup.cashier = request.user
        try:
            cashup.save()
            CashUpAuditLog.objects.create(
                cash_up=cashup,
                action='opened',
                performed_by=request.user,
                details={'opening_float': str(cashup.opening_float)},
            )
            messages.success(request, f'Cash-up opened for {cashup.joint.display_name} — {cashup.get_shift_display()} shift.')
            return redirect('cashup:count', pk=cashup.pk)
        except Exception:
            messages.error(request, 'A cash-up for this shift already exists. Please check your open cash-ups.')

    return render(request, 'cashup/open.html', {'form': form})


@login_required
def cashup_count(request, pk):
    cashup = get_object_or_404(
        CashUp.objects.select_related('joint', 'cashier'),
        pk=pk,
    )

    if cashup.cashier != request.user and not request.user.is_manager_role:
        messages.error(request, 'You can only count your own cash-ups.')
        return redirect('cashup:dashboard')

    if cashup.status not in [CashUp.STATUS_OPEN, CashUp.STATUS_DISPUTED]:
        messages.warning(request, 'This cash-up is already submitted.')
        return redirect('cashup:detail', pk=pk)

    cashup.compute_expected_from_sales()
    cashup.save(update_fields=[
        'expected_cash', 'expected_ecocash', 'expected_card',
        'expected_mixed_cash', 'expected_mixed_ecocash',
        'expenses_cash', 'expenses_ecocash',
    ])

    sales_qs = Sale.objects.filter(
        joint=cashup.joint,
        sold_by=cashup.cashier,
        sale_date__date=cashup.shift_date,
        is_held=False,
    ).prefetch_related('items')

    sales_by_method = {
        'cash': [], 'ecocash': [], 'card': [], 'mixed': [],
    }
    for sale in sales_qs:
        method = sale.payment_method
        if method in sales_by_method:
            sales_by_method[method].append(sale)

    from expense.models import Expense
    expenses = Expense.objects.filter(
        joint=cashup.joint,
        expense_date=cashup.shift_date,
        recorded_by=cashup.cashier,
    ).select_related('category')

    form = CashUpCountForm(request.POST or None, instance=cashup)

    if request.method == 'POST' and form.is_valid():
        cu = form.save(commit=False)
        cu.actual_cash = cu.denomination_total
        cu.save()
        CashUpAuditLog.objects.create(
            cash_up=cu,
            action='count_saved',
            performed_by=request.user,
            details={
                'actual_cash': str(cu.actual_cash),
                'actual_ecocash': str(cu.actual_ecocash),
                'actual_card': str(cu.actual_card),
                'denomination_total': str(cu.denomination_total),
            }
        )
        if 'submit' in request.POST:
            cu.submit(request.user)
            messages.success(request, 'Cash-up submitted for manager review.')
            return redirect('cashup:detail', pk=cu.pk)
        messages.success(request, 'Cash-up saved.')
        return redirect('cashup:count', pk=cu.pk)

    return render(request, 'cashup/count.html', {
        'cashup': cashup,
        'form': form,
        'sales_by_method': sales_by_method,
        'expenses': expenses,
        'denominations': [
            ('$100', 'cash_denomination_100', 100),
            ('$50', 'cash_denomination_50', 50),
            ('$20', 'cash_denomination_20', 20),
            ('$10', 'cash_denomination_10', 10),
            ('$5', 'cash_denomination_5', 5),
            ('$2', 'cash_denomination_2', 2),
            ('$1', 'cash_denomination_1', 1),
        ],
    })


@login_required
def cashup_detail(request, pk):
    cashup = get_object_or_404(
        CashUp.objects.select_related('joint', 'cashier', 'approved_by'),
        pk=pk,
    )

    if cashup.cashier != request.user and not request.user.is_manager_role:
        messages.error(request, 'Access denied.')
        return redirect('cashup:dashboard')

    review_form = None
    if request.user.is_manager_role and cashup.status == CashUp.STATUS_SUBMITTED:
        review_form = ManagerReviewForm(request.POST or None)
        if request.method == 'POST' and review_form.is_valid():
            action = review_form.cleaned_data['action']
            notes = review_form.cleaned_data.get('manager_notes', '')
            if action == 'approve':
                cashup.approve(request.user, notes)
                messages.success(request, f'Cash-up approved for {cashup.cashier}.')
            else:
                cashup.dispute(request.user, notes)
                messages.warning(request, f'Cash-up disputed. {cashup.cashier} will need to recount.')
            return redirect('cashup:detail', pk=pk)

    audit_logs = cashup.audit_logs.select_related('performed_by').order_by('timestamp')

    sales_qs = Sale.objects.filter(
        joint=cashup.joint,
        sold_by=cashup.cashier,
        sale_date__date=cashup.shift_date,
        is_held=False,
    ).prefetch_related('items').order_by('sale_date')

    from expense.models import Expense
    expenses = Expense.objects.filter(
        joint=cashup.joint,
        expense_date=cashup.shift_date,
        recorded_by=cashup.cashier,
    ).select_related('category')

    return render(request, 'cashup/detail.html', {
        'cashup': cashup,
        'review_form': review_form,
        'audit_logs': audit_logs,
        'sales': sales_qs,
        'expenses': expenses,
    })


@login_required
def cashup_list(request):
    if _manager_required(request):
        return redirect('cashup:dashboard')

    qs = CashUp.objects.select_related('joint', 'cashier', 'approved_by').order_by('-shift_date', '-opened_at')
    filter_form = CashUpFilterForm(request.GET or None)

    if filter_form.is_valid():
        cd = filter_form.cleaned_data
        if cd.get('joint'):
            qs = qs.filter(joint=cd['joint'])
        if cd.get('status'):
            qs = qs.filter(status=cd['status'])
        if cd.get('date_from'):
            qs = qs.filter(shift_date__gte=cd['date_from'])
        if cd.get('date_to'):
            qs = qs.filter(shift_date__lte=cd['date_to'])
        if cd.get('cashier'):
            qs = qs.filter(
                Q(cashier__first_name__icontains=cd['cashier']) |
                Q(cashier__last_name__icontains=cd['cashier']) |
                Q(cashier__username__icontains=cd['cashier'])
            )

    totals = qs.aggregate(
        total_cash=Sum('actual_cash'),
        total_ecocash=Sum('actual_ecocash'),
        total_card=Sum('actual_card'),
        count=Count('id'),
    )

    return render(request, 'cashup/list.html', {
        'cash_ups': qs,
        'filter_form': filter_form,
        'totals': totals,
    })


@login_required
def cashup_report(request):
    if _manager_required(request):
        return redirect('cashup:dashboard')

    today = timezone.localdate()
    month_start = today.replace(day=1)

    date_from = request.GET.get('date_from', str(month_start))
    date_to = request.GET.get('date_to', str(today))
    joint_id = request.GET.get('joint')

    qs = CashUp.objects.filter(
        status=CashUp.STATUS_APPROVED,
        shift_date__gte=date_from,
        shift_date__lte=date_to,
    ).select_related('joint', 'cashier')

    if joint_id:
        qs = qs.filter(joint_id=joint_id)

    per_cashier = {}
    for cu in qs:
        uid = cu.cashier_id
        if uid not in per_cashier:
            per_cashier[uid] = {
                'cashier': cu.cashier,
                'count': 0,
                'total_cash': Decimal('0'),
                'total_ecocash': Decimal('0'),
                'total_card': Decimal('0'),
                'total_variance': Decimal('0'),
                'disputed_count': 0,
            }
        per_cashier[uid]['count'] += 1
        per_cashier[uid]['total_cash'] += cu.actual_cash
        per_cashier[uid]['total_ecocash'] += cu.actual_ecocash
        per_cashier[uid]['total_card'] += cu.actual_card
        per_cashier[uid]['total_variance'] += cu.total_variance

    disputed_qs = CashUp.objects.filter(
        status=CashUp.STATUS_DISPUTED,
        shift_date__gte=date_from,
        shift_date__lte=date_to,
    ).select_related('joint', 'cashier')

    if joint_id:
        disputed_qs = disputed_qs.filter(joint_id=joint_id)

    grand = qs.aggregate(
        total_cash=Sum('actual_cash'),
        total_ecocash=Sum('actual_ecocash'),
        total_card=Sum('actual_card'),
        count=Count('id'),
    )

    return render(request, 'cashup/report.html', {
        'cash_ups': qs.order_by('-shift_date'),
        'per_cashier': list(per_cashier.values()),
        'disputed': disputed_qs,
        'grand': grand,
        'date_from': date_from,
        'date_to': date_to,
        'joints': Joint.objects.all(),
        'selected_joint': joint_id,
    })


@login_required
def cashup_api_live(request, pk):
    cashup = get_object_or_404(CashUp, pk=pk)
    if cashup.cashier != request.user and not request.user.is_manager_role:
        return JsonResponse({'error': 'forbidden'}, status=403)

    d100 = int(request.GET.get('d100', 0) or 0)
    d50 = int(request.GET.get('d50', 0) or 0)
    d20 = int(request.GET.get('d20', 0) or 0)
    d10 = int(request.GET.get('d10', 0) or 0)
    d5 = int(request.GET.get('d5', 0) or 0)
    d2 = int(request.GET.get('d2', 0) or 0)
    d1 = int(request.GET.get('d1', 0) or 0)
    cents = Decimal(str(request.GET.get('cents', '0') or '0'))

    denom_total = (
        Decimal(d100) * 100 + Decimal(d50) * 50 + Decimal(d20) * 20 +
        Decimal(d10) * 10 + Decimal(d5) * 5 + Decimal(d2) * 2 +
        Decimal(d1) * 1 + cents
    )
    actual_ecocash = Decimal(str(request.GET.get('actual_ecocash', '0') or '0'))
    actual_card = Decimal(str(request.GET.get('actual_card', '0') or '0'))

    net_cash_expected = cashup.expected_cash_total - cashup.opening_float - cashup.expenses_cash
    cash_variance = denom_total - net_cash_expected
    eco_variance = actual_ecocash - (cashup.expected_ecocash_total - cashup.expenses_ecocash)
    card_variance = actual_card - cashup.expected_card
    total_variance = cash_variance + eco_variance + card_variance

    def fmt(v):
        return str(v.quantize(Decimal('0.01')))

    return JsonResponse({
        'denom_total': fmt(denom_total),
        'cash_variance': fmt(cash_variance),
        'eco_variance': fmt(eco_variance),
        'card_variance': fmt(card_variance),
        'total_variance': fmt(total_variance),
        'expected_cash_net': fmt(net_cash_expected),
        'is_balanced': abs(total_variance) < Decimal('0.05'),
    })