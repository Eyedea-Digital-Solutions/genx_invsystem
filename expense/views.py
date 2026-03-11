"""
expense/views.py
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count
from django.utils import timezone
from decimal import Decimal

from .models import Expense, ExpenseCategory
from .forms import ExpenseForm, ExpenseFilterForm, ExpenseCategoryForm
from inventory.models import Joint


# ─── LIST / DASHBOARD ──────────────────────────────────────────────────────────

@login_required
def expense_list(request):
    joints = Joint.objects.all()
    filter_form = ExpenseFilterForm(joints, request.GET or None)

    qs = Expense.objects.select_related('joint', 'category', 'recorded_by')

    if request.GET:
        data = request.GET
        if data.get('joint'):
            qs = qs.filter(joint_id=data['joint'])
        if data.get('category'):
            qs = qs.filter(category_id=data['category'])
        if data.get('payment_method'):
            qs = qs.filter(payment_method=data['payment_method'])
        if data.get('date_from'):
            qs = qs.filter(expense_date__gte=data['date_from'])
        if data.get('date_to'):
            qs = qs.filter(expense_date__lte=data['date_to'])

    total = qs.aggregate(t=Sum('amount'))['t'] or Decimal('0.00')

    today       = timezone.localdate()
    month_start = today.replace(day=1)

    joint_totals = []
    for joint in joints:
        mt = Expense.objects.filter(
            joint=joint,
            expense_date__gte=month_start,
            expense_date__lte=today,
        ).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')
        joint_totals.append({'joint': joint, 'month_total': mt})

    today_total = Expense.objects.filter(
        expense_date=today
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')

    month_total_all = Expense.objects.filter(
        expense_date__gte=month_start
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')

    return render(request, 'expenses/expense_list.html', {
        'expenses':     qs,
        'filter_form':  filter_form,
        'total':        total,
        'joint_totals': joint_totals,
        'today_total':  today_total,
        'month_total':  month_total_all,
    })


# ─── CREATE ─────────────────────────────────────────────────────────────────────

@login_required
def expense_create(request):
    if request.method == 'POST':
        form = ExpenseForm(request.POST)
        if form.is_valid():
            expense = form.save(commit=False)
            expense.recorded_by = request.user
            expense.save()
            messages.success(request, f'Expense "${expense.amount}" recorded for {expense.joint.display_name}.')
            return redirect('expense:expense_list')
    else:
        initial = {'expense_date': timezone.localdate()}
        if hasattr(request.user, 'primary_joint') and request.user.primary_joint:
            initial['joint'] = request.user.primary_joint.pk
        form = ExpenseForm(initial=initial)

    return render(request, 'expenses/expense_form.html', {
        'form':  form,
        'title': 'Record Expense',
    })


# ─── EDIT ────────────────────────────────────────────────────────────────────────

@login_required
def expense_edit(request, pk):
    expense = get_object_or_404(Expense, pk=pk)
    if not request.user.is_manager_role:
        messages.error(request, 'You do not have permission to edit expenses.')
        return redirect('expense:expense_list')

    if request.method == 'POST':
        form = ExpenseForm(request.POST, instance=expense)
        if form.is_valid():
            form.save()
            messages.success(request, 'Expense updated.')
            return redirect('expense:expense_list')
    else:
        form = ExpenseForm(instance=expense)

    return render(request, 'expenses/expense_form.html', {
        'form':    form,
        'expense': expense,
        'title':   'Edit Expense',
    })


# ─── DELETE ──────────────────────────────────────────────────────────────────────

@login_required
def expense_delete(request, pk):
    if not request.user.is_manager_role:
        messages.error(request, 'You do not have permission to delete expenses.')
        return redirect('expense:expense_list')

    expense = get_object_or_404(Expense, pk=pk)
    if request.method == 'POST':
        expense.delete()
        messages.success(request, 'Expense deleted.')
    return redirect('expense:expense_list')


# ─── CATEGORIES ──────────────────────────────────────────────────────────────────

@login_required
def category_list(request):
    categories = ExpenseCategory.objects.annotate(
        expense_count=Count('expenses')
    ).order_by('name')
    return render(request, 'expenses/category_list.html', {'categories': categories})


@login_required
def category_create(request):
    if not request.user.is_manager_role:
        messages.error(request, 'You do not have permission to manage categories.')
        return redirect('expense:expense_list')
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category created.')
            return redirect('expense:category_list')
    else:
        form = ExpenseCategoryForm()
    return render(request, 'expenses/category_form.html', {'form': form, 'title': 'Add Category'})


@login_required
def category_edit(request, pk):
    if not request.user.is_manager_role:
        messages.error(request, 'You do not have permission to manage categories.')
        return redirect('expense:expense_list')
    cat = get_object_or_404(ExpenseCategory, pk=pk)
    if request.method == 'POST':
        form = ExpenseCategoryForm(request.POST, instance=cat)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated.')
            return redirect('expense:category_list')
    else:
        form = ExpenseCategoryForm(instance=cat)
    return render(request, 'expenses/category_form.html', {
        'form':     form,
        'title':    'Edit Category',
        'category': cat,
    })