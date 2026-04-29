import csv
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView, DetailView, ListView, TemplateView, UpdateView, View,
)

from .models import Employee
from .forms import EmployeeForm


# ── helpers ───────────────────────────────────────────────────────────────────

def _safe_import(model_path):
    """Return a model class or None if it hasn't been migrated yet."""
    try:
        app, name = model_path.rsplit('.', 1)
        from django.apps import apps
        return apps.get_model(app, name)
    except Exception:
        return None


# ── EXISTING VIEWS (unchanged) ─────────────────────────────────────────────────

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
        ctx['back_url'] = '/employees/list/'
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
        ctx['back_url'] = '/employees/list/'
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Employee updated successfully.')
        return super().form_valid(form)


# ── DASHBOARD ─────────────────────────────────────────────────────────────────

class EmployeeDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'employees/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.now().date()
        month_start = today.replace(day=1)

        ctx['today'] = today
        ctx['month'] = today.strftime('%B %Y')
        ctx['active_emp_count'] = Employee.objects.filter(is_active=True).count()
        ctx['present_count'] = 0
        ctx['late_count'] = 0
        ctx['todays_shifts'] = []
        ctx['pending_leaves'] = []
        ctx['upcoming_leaves'] = []
        ctx['leaderboard'] = []

        # Build leaderboard from sales data
        try:
            from django.db.models import Sum, Count, F
            from django.db.models import FloatField
            from sales.models import Sale, SaleItem
            from users.models import User

            leaderboard = []
            for user in User.objects.filter(is_active=True):
                user_sales = Sale.objects.filter(
                    sold_by=user,
                    sale_date__date__gte=month_start,
                    is_held=False,
                )
                cnt = user_sales.count()
                if cnt == 0:
                    continue
                items = SaleItem.objects.filter(sale__in=user_sales, is_free_gift=False)
                rev = items.aggregate(
                    t=Sum(F('quantity') * F('unit_price'), output_field=FloatField())
                )['t'] or 0
                leaderboard.append({'user': user, 'count': cnt, 'revenue': round(rev, 2)})
            leaderboard.sort(key=lambda x: x['revenue'], reverse=True)
            ctx['leaderboard'] = leaderboard[:10]
        except Exception:
            pass

        # Try to pull attendance / leave if models exist
        try:
            from .hr_models import AttendanceRecord, LeaveRequest, Shift
            ctx['present_count'] = AttendanceRecord.objects.filter(
                clock_in__date=today, clock_out__isnull=True
            ).count() + AttendanceRecord.objects.filter(clock_in__date=today).count()
            ctx['todays_shifts'] = list(
                Shift.objects.filter(date=today).select_related('employee', 'joint')
            )
            ctx['pending_leaves'] = list(
                LeaveRequest.objects.filter(status='pending').select_related('employee')[:10]
            )
            ctx['upcoming_leaves'] = list(
                LeaveRequest.objects.filter(
                    status='approved',
                    start_date__gt=today,
                ).select_related('employee').order_by('start_date')[:5]
            )
        except Exception:
            pass

        return ctx


# ── STAFF DIRECTORY ────────────────────────────────────────────────────────────

class StaffDirectoryView(LoginRequiredMixin, TemplateView):
    template_name = 'employees/staff_directory.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        employees = Employee.objects.filter(is_active=True).order_by('last_name', 'first_name')

        # Simple search
        q = self.request.GET.get('q', '').strip()
        if q:
            employees = employees.filter(
                models.Q(first_name__icontains=q) |
                models.Q(last_name__icontains=q) |
                models.Q(email__icontains=q)
            )

        ctx['profiles'] = employees
        ctx['total_count'] = employees.count()
        ctx['filter_form'] = _StubFilterForm()
        return ctx


class _StubFilterForm:
    """Minimal stand-in so the template can render {{ filter_form.X }} without errors."""
    department = ''
    employment_type = ''
    joint = ''

    def __str__(self):
        return ''


@login_required
def export_staff_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="staff_export.csv"'
    writer = csv.writer(response)
    writer.writerow(['First Name', 'Last Name', 'Email', 'Phone', 'Role', 'Branch', 'Active', 'Date Joined'])
    for emp in Employee.objects.all().order_by('last_name', 'first_name'):
        writer.writerow([
            emp.first_name, emp.last_name, emp.email, emp.phone,
            emp.role, emp.branch,
            'Yes' if emp.is_active else 'No',
            emp.date_joined or '',
        ])
    return response

class EmployeeProfileCreateView(LoginRequiredMixin, CreateView):
    model = Employee
    form_class = EmployeeForm
    template_name = 'employees/employee_form.html'
    success_url = reverse_lazy('employees:staff_directory')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Add Employee'
        ctx['profile'] = None
        ctx['user_form'] = ctx['form']
        ctx['profile_form'] = _NullForm()
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Employee created.')
        return super().form_valid(form)


class EmployeeProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = Employee
    form_class = EmployeeForm
    template_name = 'employees/employee_form.html'
    success_url = reverse_lazy('employees:staff_directory')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = f'Edit {self.object.get_full_name()}'
        ctx['profile'] = self.object
        ctx['profile_form'] = ctx['form']
        return ctx

    def form_valid(self, form):
        messages.success(self.request, 'Employee updated.')
        return super().form_valid(form)


class EmployeeProfileDetailView(LoginRequiredMixin, DetailView):
    model = Employee
    template_name = 'employees/employee_detail.html'
    context_object_name = 'employee'


class _NullForm:
    """Renders nothing — placeholder for optional form sections."""
    def __str__(self):
        return ''
    def __iter__(self):
        return iter([])
    # Make every attribute access return an empty string
    def __getattr__(self, item):
        return ''


# ── SCHEDULE ──────────────────────────────────────────────────────────────────

class ScheduleView(LoginRequiredMixin, TemplateView):
    template_name = 'employees/schedule.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        offset = int(self.request.GET.get('offset', 0))
        joint_id = self.request.GET.get('joint', '')
        today = timezone.now().date()
        week_start = today - timedelta(days=today.weekday()) + timedelta(weeks=offset)
        week_end = week_start + timedelta(days=6)
        week_days = [week_start + timedelta(days=i) for i in range(7)]

        from inventory.models import Joint
        ctx.update({
            'today': today,
            'week_start': week_start,
            'week_end': week_end,
            'week_days': week_days,
            'offset': offset,
            'joint_id': joint_id,
            'joints': Joint.objects.filter(is_active=True),
            'employees': Employee.objects.filter(is_active=True),
            'shift_map': {},
        })

        try:
            from .hr_models import Shift
            shifts = Shift.objects.filter(
                date__gte=week_start, date__lte=week_end
            ).select_related('employee', 'joint')
            if joint_id:
                shifts = shifts.filter(joint_id=joint_id)
            shift_map = {(s.employee_id, s.date): s for s in shifts}
            ctx['shift_map'] = shift_map
        except Exception:
            pass

        return ctx


class ShiftCreateView(LoginRequiredMixin, TemplateView):
    template_name = 'employees/shift_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Add Shift'
        ctx['form'] = _ShiftStubForm(initial={
            'employee': self.request.GET.get('employee', ''),
            'date': self.request.GET.get('date', ''),
        })
        return ctx

    def post(self, request, *args, **kwargs):
        messages.info(request, 'Shift scheduling requires the HR models migration. Coming soon.')
        return redirect('employees:schedule')


class ShiftUpdateView(LoginRequiredMixin, TemplateView):
    template_name = 'employees/shift_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Edit Shift'
        ctx['form'] = _ShiftStubForm()
        return ctx

    def post(self, request, *args, **kwargs):
        messages.info(request, 'Shift update requires the HR models migration. Coming soon.')
        return redirect('employees:schedule')


@login_required
def shift_confirm(request, pk):
    try:
        from .hr_models import Shift
        shift = get_object_or_404(Shift, pk=pk)
        shift.is_confirmed = True
        shift.save(update_fields=['is_confirmed'])
        messages.success(request, 'Shift confirmed.')
    except Exception:
        messages.info(request, 'HR models not yet available.')
    return redirect('employees:schedule')


@login_required
def shift_delete(request, pk):
    try:
        from .hr_models import Shift
        shift = get_object_or_404(Shift, pk=pk)
        shift.delete()
        messages.success(request, 'Shift deleted.')
    except Exception:
        messages.info(request, 'HR models not yet available.')
    return redirect('employees:schedule')


class _ShiftStubForm:
    def __init__(self, initial=None):
        self._initial = initial or {}

    def __getattr__(self, item):
        return ''

    def __iter__(self):
        return iter([])

    @property
    def non_field_errors(self):
        return []

    @property
    def employee(self):
        return ''

    @property
    def joint(self):
        return ''

    @property
    def date(self):
        return ''

    @property
    def start_time(self):
        return ''

    @property
    def end_time(self):
        return ''

    @property
    def notes(self):
        return ''


# ── ATTENDANCE ────────────────────────────────────────────────────────────────

class AttendanceView(LoginRequiredMixin, TemplateView):
    template_name = 'employees/attendance.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = timezone.now().date()
        view_date_str = self.request.GET.get('date', str(today))
        try:
            view_date = date.fromisoformat(view_date_str)
        except ValueError:
            view_date = today

        ctx['today'] = today
        ctx['view_date'] = view_date
        ctx['records'] = []
        ctx['active_session'] = None
        ctx['my_hours'] = 0

        try:
            from .hr_models import AttendanceRecord
            ctx['records'] = list(
                AttendanceRecord.objects.filter(clock_in__date=view_date)
                .select_related('employee', 'joint')
                .order_by('clock_in')
            )
            # Active session for this user's linked employee
            if hasattr(self.request.user, 'employee_profile'):
                emp = self.request.user.employee_profile
                ctx['active_session'] = AttendanceRecord.objects.filter(
                    employee=emp, clock_out__isnull=True
                ).first()
            # Monthly hours
            month_start = today.replace(day=1)
            records_month = AttendanceRecord.objects.filter(
                clock_in__date__gte=month_start,
                clock_in__date__lte=today,
            )
            if hasattr(self.request.user, 'employee_profile'):
                records_month = records_month.filter(employee=self.request.user.employee_profile)
            total_seconds = sum(
                (r.clock_out - r.clock_in).total_seconds()
                for r in records_month
                if r.clock_out
            )
            ctx['my_hours'] = round(total_seconds / 3600, 1)
        except Exception:
            pass

        return ctx


class ClockInView(LoginRequiredMixin, TemplateView):
    template_name = 'employees/clock_in.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form'] = _ClockInStubForm(employees=Employee.objects.filter(is_active=True))
        return ctx

    def post(self, request, *args, **kwargs):
        messages.info(request, 'Clock-in requires the HR models migration. Coming soon.')
        return redirect('employees:attendance')


@login_required
def clock_out(request, pk):
    try:
        from .hr_models import AttendanceRecord
        record = get_object_or_404(AttendanceRecord, pk=pk)
        record.clock_out = timezone.now()
        record.save(update_fields=['clock_out'])
        messages.success(request, 'Clocked out successfully.')
    except Exception:
        messages.info(request, 'HR models not yet available.')
    return redirect('employees:attendance')


class _ClockInStubForm:
    def __init__(self, employees=None):
        self._employees = employees or []

    def __getattr__(self, item):
        return ''

    @property
    def employee(self):
        return ''

    @property
    def joint(self):
        return ''

    @property
    def shift(self):
        return ''

    @property
    def notes(self):
        return ''


# ── LEAVE ─────────────────────────────────────────────────────────────────────

class LeaveListView(LoginRequiredMixin, TemplateView):
    template_name = 'employees/leave_list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['pending'] = []
        ctx['approved'] = []
        ctx['rejected'] = []
        ctx['upcoming'] = []
        today = timezone.now().date()

        try:
            from .hr_models import LeaveRequest
            qs = LeaveRequest.objects.select_related('employee', 'reviewed_by').order_by('-start_date')
            if not self.request.user.is_manager_role:
                if hasattr(self.request.user, 'employee_profile'):
                    qs = qs.filter(employee=self.request.user.employee_profile)
                else:
                    qs = qs.none()
            ctx['pending'] = list(qs.filter(status='pending'))
            ctx['approved'] = list(qs.filter(status='approved'))
            ctx['rejected'] = list(qs.filter(status='rejected'))
            ctx['upcoming'] = list(qs.filter(status='approved', start_date__gt=today).order_by('start_date')[:10])
        except Exception:
            pass

        return ctx


class LeaveCreateView(LoginRequiredMixin, TemplateView):
    template_name = 'employees/leave_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'Apply for Leave'
        ctx['form'] = _LeaveStubForm()
        return ctx

    def post(self, request, *args, **kwargs):
        messages.info(request, 'Leave requests require the HR models migration. Coming soon.')
        return redirect('employees:leave_list')


class LeaveReviewView(LoginRequiredMixin, TemplateView):
    template_name = 'employees/leave_review.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form'] = _LeaveStubForm()
        try:
            from .hr_models import LeaveRequest
            ctx['leave'] = get_object_or_404(LeaveRequest, pk=self.kwargs['pk'])
        except Exception:
            ctx['leave'] = None
        return ctx

    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        try:
            from .hr_models import LeaveRequest
            leave = get_object_or_404(LeaveRequest, pk=kwargs['pk'])
            if action in ('approve', 'reject'):
                leave.status = 'approved' if action == 'approve' else 'rejected'
                leave.reviewed_by = request.user
                leave.reviewed_at = timezone.now()
                leave.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
                messages.success(request, f'Leave request {leave.status}.')
        except Exception:
            messages.info(request, 'HR models not yet available.')
        return redirect('employees:leave_list')


class _LeaveStubForm:
    def __getattr__(self, item):
        return ''

    @property
    def non_field_errors(self):
        return []

    @property
    def leave_type(self):
        return ''

    @property
    def start_date(self):
        return ''

    @property
    def end_date(self):
        return ''

    @property
    def reason(self):
        return ''


# ── PERFORMANCE REVIEWS ────────────────────────────────────────────────────────

class PerformanceListView(LoginRequiredMixin, TemplateView):
    template_name = 'employees/performance_list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['reviews'] = []
        try:
            from .hr_models import PerformanceReview
            ctx['reviews'] = list(
                PerformanceReview.objects.select_related('employee', 'reviewer').order_by('-created_at')
            )
        except Exception:
            pass
        return ctx


class PerformanceCreateView(LoginRequiredMixin, TemplateView):
    template_name = 'employees/performance_form.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = 'New Performance Review'
        ctx['form'] = _PerformanceStubForm()
        return ctx

    def post(self, request, *args, **kwargs):
        messages.info(request, 'Performance reviews require the HR models migration. Coming soon.')
        return redirect('employees:performance_list')


class PerformanceDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'employees/performance_detail.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            from .hr_models import PerformanceReview
            ctx['review'] = get_object_or_404(PerformanceReview, pk=self.kwargs['pk'])
        except Exception:
            ctx['review'] = None
        return ctx


@login_required
def performance_share(request, pk):
    try:
        from .hr_models import PerformanceReview
        review = get_object_or_404(PerformanceReview, pk=pk)
        review.is_shared = True
        review.save(update_fields=['is_shared'])
        messages.success(request, 'Review shared with employee.')
    except Exception:
        messages.info(request, 'HR models not yet available.')
    return redirect('employees:performance_list')


class _PerformanceStubForm:
    def __getattr__(self, item):
        return ''

    @property
    def non_field_errors(self):
        return []

    def __iter__(self):
        return iter([])

    class fields:
        class sales_score:
            choices = [(i, str(i)) for i in range(1, 6)]

        class attendance_score:
            choices = [(i, str(i)) for i in range(1, 6)]

        class attitude_score:
            choices = [(i, str(i)) for i in range(1, 6)]