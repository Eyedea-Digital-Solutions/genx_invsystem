from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.decorators import method_decorator
from .forms import LoginForm, UserCreateForm, UserUpdateForm
from .models import User


def login_view(request):
    """Handles user login."""
    if request.user.is_authenticated:
        return redirect('sales:dashboard')

    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        messages.success(request, f"Welcome back, {user.first_name or user.username}!")
        return redirect('sales:dashboard')

    return render(request, 'login.html', {'form': form})


@login_required
def logout_view(request):
    """Logs the user out."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('users:login')


@login_required
def user_list(request):
    """Shows all users. Admin only."""
    if not request.user.is_admin_role:
        messages.error(request, "You don't have permission to view this page.")
        return redirect('sales:dashboard')

    users = User.objects.select_related('primary_joint').all()
    return render(request, 'user_list.html', {'users': users})


@login_required
def user_create(request):
    """Create a new user. Admin only."""
    if not request.user.is_admin_role:
        messages.error(request, "You don't have permission to do this.")
        return redirect('sales:dashboard')

    form = UserCreateForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        messages.success(request, f"User '{user.username}' created successfully!")
        return redirect('users:user_list')

    return render(request, 'user_form.html', {'form': form, 'title': 'Create User'})


@login_required
def user_edit(request, pk):
    """Edit an existing user. Admin only."""
    if not request.user.is_admin_role:
        messages.error(request, "You don't have permission to do this.")
        return redirect('sales:dashboard')

    user = get_object_or_404(User, pk=pk)
    form = UserUpdateForm(request.POST or None, instance=user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f"User '{user.username}' updated successfully!")
        return redirect('users:user_list')

    return render(request, 'user_form.html', {'form': form, 'title': 'Edit User', 'edit_user': user})
