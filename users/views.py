from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import User
from .forms import LoginForm, UserCreateForm, UserEditForm, PasswordChangeForm


def user_login(request):
    if request.user.is_authenticated:
        return redirect('sales:pos')

    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        next_url = request.GET.get('next', 'sales:pos')
        return redirect(next_url)

    return render(request, 'registration/login.html', {'form': form})


def user_logout(request):
    logout(request)
    return redirect('users:login')


@login_required
def user_list(request):
    if not request.user.is_admin_role:
        messages.error(request, "Admins only.")
        return redirect('sales:dashboard')
    users = User.objects.select_related('primary_joint').all()
    return render(request, 'user_list.html', {'users': users})


@login_required
def user_create(request):
    if not request.user.is_admin_role:
        messages.error(request, "Admins only.")
        return redirect('sales:dashboard')

    form = UserCreateForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        messages.success(request, f"User '{user.username}' created.")
        return redirect('users:user_list')

    return render(request, 'user_form.html', {'form': form, 'title': 'Add User'})


@login_required
def user_edit(request, pk):
    if not request.user.is_admin_role:
        messages.error(request, "Admins only.")
        return redirect('sales:dashboard')

    user = get_object_or_404(User, pk=pk)
    form = UserEditForm(request.POST or None, instance=user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f"User '{user.username}' updated.")
        return redirect('users:user_list')

    return render(request, 'user_form.html', {'form': form, 'title': 'Edit User', 'edit_user': user})


@login_required
def user_set_password(request, pk):
    if not request.user.is_admin_role:
        messages.error(request, "Admins only.")
        return redirect('sales:dashboard')

    target_user = get_object_or_404(User, pk=pk)
    form = PasswordChangeForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        target_user.set_password(form.cleaned_data['new_password1'])
        target_user.save()
        messages.success(request, f"Password updated for '{target_user.username}'.")
        return redirect('users:user_list')

    return render(request, 'user_password.html', {'form': form, 'target_user': target_user})


@login_required
def profile(request):
    form = PasswordChangeForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        request.user.set_password(form.cleaned_data['new_password1'])
        request.user.save()
        update_session_auth_hash(request, request.user)
        messages.success(request, "Password changed successfully.")
        return redirect('users:profile')

    return render(request, 'profile.html', {'form': form})
