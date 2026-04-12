from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from .models import Employee
from .forms import EmployeeForm


class EmployeeListView(LoginRequiredMixin, ListView):
    model = Employee
    template_name = 'employees/employee_list.html'
    context_object_name = 'employees'
    paginate_by = 50

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(first_name__icontains=q) | qs.filter(last_name__icontains=q) | qs.filter(email__icontains=q)
        return qs


class EmployeeDetailView(LoginRequiredMixin, DetailView):
    model = Employee
    template_name = 'employees/employee_detail.html'
    context_object_name = 'employee'


class EmployeeCreateView(LoginRequiredMixin, CreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = 'components/form.html'
    success_url = reverse_lazy('employees:list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Add Employee'
        ctx['back_url'] = '/employees/'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Employee added successfully.')
        return super().form_valid(form)


class EmployeeUpdateView(LoginRequiredMixin, UpdateView):
    model = Employee
    form_class = EmployeeForm
    template_name = 'components/form.html'
    success_url = reverse_lazy('employees:list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = f'Edit {self.object.get_full_name()}'
        ctx['back_url'] = '/employees/'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Employee updated successfully.')
        return super().form_valid(form)
