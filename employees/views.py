"""
employees/views.py
──────────────────
Section 5 — Employee Management Module

Views:
  staff_dashboard      /employees/
  staff_directory      /employees/staff/
  employee_create      /employees/staff/add/
  employee_detail      /employees/<pk>/
  employee_edit        /employees/<pk>/edit/
  schedule_view        /employees/schedule/
  shift_create         /employees/schedule/shift/add/
  shift_edit           /employees/schedule/shift/<pk>/edit/
  attendance_view      /employees/attendance/
  clock_in             /employees/attendance/clock-in/
  clock_out            /employees/attendance/<pk>/clock-out/
  leave_list           /employees/leave/
  leave_create         /employees/leave/apply/
  leave_review         /employees/leave/<pk>/review/      [manager]
  performance_list     /employees/performance/
  performance_create   /employees/performance/add/
  performance_detail   /employees/performance/<pk>/
  performance_share    /employees/performance/<pk>/share/ [manager]
  export_staff_csv     /employees/export/
"""
import csv
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum, Count, F
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import EmployeeProfile, Shift, Attendance, LeaveRequest, PerformanceReview, Commission
from .forms import (
    EmployeeProfileForm, ShiftForm, AttendanceClockInForm,
    LeaveRequestForm, LeaveReviewForm, PerformanceReviewForm, EmployeeFilterForm,
)


# ── permission helpers ────────────────────────────────────────────────────────

def _require_manager(request):
    if not request.user.is_manager_role:
        messages.error(request, "Managers and above only.")
        return True
    return False


# ═════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def staff_dashboard(request):
    today      = timezone.localdate()
    month_start = today.replace(day=1)

    # Today's schedule across all joints
    todays_shifts = (
        Shift.objects
        .filter(date=today)
        .select_related("employee", "joint")
        .order_by("joint__name", "start_time")
    )

    # Attendance summary for today
    today_attendance = Attendance.objects.filter(clock_in__date=today)
    present_count = today_attendance.filter(clock_out__isnull=True).count()
    late_count    = today_attendance.filter(is_late=True).count()

    # Pending leave requests (managers see all, employees see own)
    pending_leaves = LeaveRequest.objects.filter(status=LeaveRequest.STATUS_PENDING)
    if not request.user.is_manager_role:
        pending_leaves = pending_leaves.filter(employee=request.user)
    pending_leaves = pending_leaves.select_related("employee").order_by("-created_at")[:10]

    # Performance leaderboard (top sellers this month via sales)
    from sales.models import Sale, SaleItem
    from users.models import User

    leaderboard = []
    for user in User.objects.filter(is_active=True):
        user_sales = Sale.objects.filter(
            sold_by=user, sale_date__date__gte=month_start, is_held=False
        )
        cnt = user_sales.count()
        if cnt == 0:
            continue
        items = SaleItem.objects.filter(sale__in=user_sales, is_free_gift=False)
        rev = items.aggregate(
            t=Sum(F("quantity") * F("unit_price"))
        )["t"] or Decimal("0")
        leaderboard.append({"user": user, "count": cnt, "revenue": rev})
    leaderboard.sort(key=lambda x: x["revenue"], reverse=True)
    leaderboard = leaderboard[:5]

    # Active employee count
    active_emp_count = EmployeeProfile.objects.filter(date_terminated__isnull=True).count()

    # Upcoming leaves (approved, next 14 days)
    upcoming_leaves = (
        LeaveRequest.objects
        .filter(
            status=LeaveRequest.STATUS_APPROVED,
            start_date__gte=today,
            start_date__lte=today + timedelta(days=14),
        )
        .select_related("employee")
        .order_by("start_date")
    )

    return render(request, "employees/dashboard.html", {
        "todays_shifts":    todays_shifts,
        "present_count":    present_count,
        "late_count":       late_count,
        "pending_leaves":   pending_leaves,
        "leaderboard":      leaderboard,
        "active_emp_count": active_emp_count,
        "upcoming_leaves":  upcoming_leaves,
        "today":            today,
        "month":            today.strftime("%B %Y"),
    })


# ═════════════════════════════════════════════════════════════════════════════
# STAFF DIRECTORY
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def staff_directory(request):
    from users.models import User

    filter_form = EmployeeFilterForm(request.GET or None)
    profiles    = EmployeeProfile.objects.select_related(
        "user", "user__primary_joint"
    ).filter(date_terminated__isnull=True)

    if filter_form.is_valid():
        cd = filter_form.cleaned_data
        if cd.get("q"):
            q = cd["q"]
            profiles = profiles.filter(
                Q(user__first_name__icontains=q)
                | Q(user__last_name__icontains=q)
                | Q(user__username__icontains=q)
                | Q(employee_id__icontains=q)
            )
        if cd.get("department"):
            profiles = profiles.filter(department=cd["department"])
        if cd.get("employment_type"):
            profiles = profiles.filter(employment_type=cd["employment_type"])
        if cd.get("joint"):
            profiles = profiles.filter(user__primary_joint=cd["joint"])

    return render(request, "employees/staff_directory.html", {
        "profiles":     profiles.order_by("user__first_name"),
        "filter_form":  filter_form,
        "total_count":  profiles.count(),
    })


# ═════════════════════════════════════════════════════════════════════════════
# EMPLOYEE CREATE / EDIT / DETAIL
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def employee_create(request):
    if _require_manager(request):
        return redirect("employees:staff_directory")

    from users.models import User
    from users.forms import UserCreateForm

    user_form    = UserCreateForm(request.POST or None)
    profile_form = EmployeeProfileForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and user_form.is_valid() and profile_form.is_valid():
        with transaction.atomic():
            user    = user_form.save()
            profile = profile_form.save(commit=False)
            profile.user = user
            profile.save()
        messages.success(request, f"Employee {profile.employee_id} — {user.get_full_name()} created.")
        return redirect("employees:employee_detail", pk=profile.pk)

    return render(request, "employees/employee_form.html", {
        "user_form":    user_form,
        "profile_form": profile_form,
        "title":        "Add Employee",
    })


@login_required
def employee_edit(request, pk):
    if _require_manager(request):
        return redirect("employees:staff_directory")

    profile = get_object_or_404(EmployeeProfile, pk=pk)
    form    = EmployeeProfileForm(
        request.POST or None, request.FILES or None, instance=profile
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Profile updated for {profile.full_name}.")
        return redirect("employees:employee_detail", pk=pk)

    return render(request, "employees/employee_form.html", {
        "profile_form": form,
        "profile":      profile,
        "title":        f"Edit — {profile.full_name}",
    })


@login_required
def employee_detail(request, pk):
    profile = get_object_or_404(
        EmployeeProfile.objects.select_related("user", "user__primary_joint"), pk=pk
    )

    # Only managers or the employee themselves can view
    if not request.user.is_manager_role and request.user != profile.user:
        messages.error(request, "Access denied.")
        return redirect("employees:staff_directory")

    today       = timezone.localdate()
    month_start = today.replace(day=1)

    # Sales performance
    from sales.models import Sale, SaleItem
    all_sales = Sale.objects.filter(sold_by=profile.user, is_held=False)
    month_sales = all_sales.filter(sale_date__date__gte=month_start)

    total_revenue = sum(s.total_amount for s in all_sales)
    month_revenue = sum(s.total_amount for s in month_sales)
    avg_order     = total_revenue / all_sales.count() if all_sales.exists() else Decimal("0")

    # Attendance this month
    monthly_attendance = Attendance.objects.filter(
        employee=profile.user, clock_in__date__gte=month_start
    ).select_related("shift", "joint")

    # Leave history
    leaves = LeaveRequest.objects.filter(
        employee=profile.user
    ).order_by("-created_at")[:10]

    # Shared performance reviews
    reviews = PerformanceReview.objects.filter(employee=profile.user)
    if not request.user.is_manager_role:
        reviews = reviews.filter(is_shared=True)
    reviews = reviews.select_related("reviewer").order_by("-review_period_end")[:5]

    # Commission this month
    commissions = Commission.objects.filter(
        employee=profile.user, period=month_start
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

    # 12-month revenue for sparkline
    twelve_months = []
    for i in range(11, -1, -1):
        ref_date  = today.replace(day=1) - timedelta(days=30 * i)
        ms        = ref_date.replace(day=1)
        import calendar
        _, ld     = calendar.monthrange(ms.year, ms.month)
        me        = ms.replace(day=ld)
        rev       = sum(
            s.total_amount for s in all_sales.filter(
                sale_date__date__gte=ms, sale_date__date__lte=me
            )
        )
        twelve_months.append({"month": ms.strftime("%b %y"), "revenue": float(rev)})

    return render(request, "employees/employee_detail.html", {
        "profile":            profile,
        "total_revenue":      total_revenue,
        "month_revenue":      month_revenue,
        "avg_order":          avg_order,
        "all_sales_count":    all_sales.count(),
        "month_sales_count":  month_sales.count(),
        "monthly_attendance": monthly_attendance,
        "leaves":             leaves,
        "reviews":            reviews,
        "commissions":        commissions,
        "twelve_months":      twelve_months,
        "days_employed":      profile.days_employed,
    })


# ═════════════════════════════════════════════════════════════════════════════
# SCHEDULE
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def schedule_view(request):
    # Default: show current week
    today      = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    week_end   = week_start + timedelta(days=6)

    # Allow ?week_offset=N navigation
    offset = int(request.GET.get("offset", 0))
    week_start = week_start + timedelta(weeks=offset)
    week_end   = week_start + timedelta(days=6)

    week_days = [week_start + timedelta(days=i) for i in range(7)]

    from users.models import User
    joint_id = request.GET.get("joint", "")

    employees = User.objects.filter(is_active=True).order_by("first_name")
    if joint_id:
        employees = employees.filter(primary_joint_id=joint_id)

    shifts = (
        Shift.objects
        .filter(date__gte=week_start, date__lte=week_end)
        .select_related("employee", "joint", "confirmed_by")
    )
    if joint_id:
        shifts = shifts.filter(joint_id=joint_id)

    # Build lookup: {(employee_id, date): shift}
    shift_map = {}
    for s in shifts:
        shift_map[(s.employee_id, s.date)] = s

    from inventory.models import Joint
    return render(request, "employees/schedule.html", {
        "week_days":  week_days,
        "employees":  employees,
        "shift_map":  shift_map,
        "offset":     offset,
        "joints":     Joint.objects.all(),
        "joint_id":   joint_id,
        "week_start": week_start,
        "week_end":   week_end,
        "today":      today,
    })


@login_required
def shift_create(request):
    if _require_manager(request):
        return redirect("employees:schedule")

    form = ShiftForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Shift created.")
        return redirect("employees:schedule")

    return render(request, "employees/shift_form.html", {
        "form": form, "title": "Add Shift"
    })


@login_required
def shift_edit(request, pk):
    if _require_manager(request):
        return redirect("employees:schedule")

    shift = get_object_or_404(Shift, pk=pk)
    form  = ShiftForm(request.POST or None, instance=shift)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Shift updated.")
        return redirect("employees:schedule")

    return render(request, "employees/shift_form.html", {
        "form": form, "shift": shift, "title": "Edit Shift"
    })


@login_required
def shift_delete(request, pk):
    if _require_manager(request):
        return redirect("employees:schedule")
    shift = get_object_or_404(Shift, pk=pk)
    if request.method == "POST":
        shift.delete()
        messages.success(request, "Shift removed.")
    return redirect("employees:schedule")


@login_required
def shift_confirm(request, pk):
    if _require_manager(request):
        return redirect("employees:schedule")
    shift = get_object_or_404(Shift, pk=pk)
    shift.is_confirmed = True
    shift.confirmed_by = request.user
    shift.save(update_fields=["is_confirmed", "confirmed_by"])
    messages.success(request, f"Shift for {shift.employee.get_full_name()} confirmed.")
    return redirect("employees:schedule")


# ═════════════════════════════════════════════════════════════════════════════
# ATTENDANCE
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def attendance_view(request):
    today    = timezone.localdate()
    date_str = request.GET.get("date", str(today))
    try:
        view_date = date.fromisoformat(date_str)
    except ValueError:
        view_date = today

    records = (
        Attendance.objects
        .filter(clock_in__date=view_date)
        .select_related("employee", "joint", "shift")
        .order_by("clock_in")
    )
    if not request.user.is_manager_role:
        records = records.filter(employee=request.user)

    # Timesheet summary (current month)
    month_start = today.replace(day=1)
    my_hours = (
        Attendance.objects
        .filter(employee=request.user, clock_in__date__gte=month_start, total_hours__isnull=False)
        .aggregate(t=Sum("total_hours"))["t"] or Decimal("0")
    )

    # Currently clocked in (no clock_out)
    active_sessions = Attendance.objects.filter(
        employee=request.user, clock_out__isnull=True
    ).first()

    return render(request, "employees/attendance.html", {
        "records":         records,
        "view_date":       view_date,
        "today":           today,
        "my_hours":        my_hours,
        "active_session":  active_sessions,
    })


@login_required
def clock_in(request):
    # Prevent double clock-in
    active = Attendance.objects.filter(
        employee=request.user, clock_out__isnull=True
    ).first()
    if active:
        messages.warning(request, "You are already clocked in. Please clock out first.")
        return redirect("employees:attendance")

    form = AttendanceClockInForm(request.POST or None, initial={
        "employee": request.user,
        "joint":    request.user.primary_joint,
    })
    if request.method == "POST" and form.is_valid():
        record = form.save(commit=False)
        record.employee    = request.user
        record.clock_in    = timezone.now()
        record.recorded_by = request.user
        record.save()
        record.compute_lateness()
        messages.success(request, f"Clocked in at {record.clock_in.strftime('%H:%M')}.")
        return redirect("employees:attendance")

    return render(request, "employees/clock_in.html", {"form": form})


@login_required
def clock_out(request, pk):
    record = get_object_or_404(
        Attendance, pk=pk, employee=request.user, clock_out__isnull=True
    )
    if request.method == "POST":
        record.clock_out_now(actor=request.user)
        messages.success(
            request,
            f"Clocked out at {record.clock_out.strftime('%H:%M')}. "
            f"Total: {record.total_hours}h",
        )
    return redirect("employees:attendance")


# ═════════════════════════════════════════════════════════════════════════════
# LEAVE
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def leave_list(request):
    today = timezone.localdate()

    if request.user.is_manager_role:
        qs = LeaveRequest.objects.all()
    else:
        qs = LeaveRequest.objects.filter(employee=request.user)

    qs = qs.select_related("employee", "reviewed_by").order_by("-created_at")

    # Separate views
    pending  = qs.filter(status=LeaveRequest.STATUS_PENDING)
    approved = qs.filter(status=LeaveRequest.STATUS_APPROVED)
    rejected = qs.filter(status=LeaveRequest.STATUS_REJECTED)

    # Leave calendar (upcoming 3 months)
    upcoming = (
        LeaveRequest.objects
        .filter(
            status=LeaveRequest.STATUS_APPROVED,
            start_date__gte=today,
        )
        .select_related("employee")
        .order_by("start_date")[:20]
    )

    return render(request, "employees/leave_list.html", {
        "pending":  pending,
        "approved": approved,
        "rejected": rejected,
        "upcoming": upcoming,
    })


@login_required
def leave_create(request):
    form = LeaveRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        leave = form.save(commit=False)
        leave.employee = request.user
        leave.save()
        messages.success(
            request,
            f"Leave request submitted for {leave.days_requested} day(s) — awaiting approval.",
        )
        return redirect("employees:leave_list")

    return render(request, "employees/leave_form.html", {
        "form": form, "title": "Apply for Leave"
    })


@login_required
def leave_review(request, pk):
    if _require_manager(request):
        return redirect("employees:leave_list")

    leave = get_object_or_404(
        LeaveRequest.objects.select_related("employee"),
        pk=pk, status=LeaveRequest.STATUS_PENDING
    )
    form = LeaveReviewForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        action = form.cleaned_data["action"]
        if action == "approve":
            leave.approve(request.user)
            messages.success(request, f"Leave approved for {leave.employee.get_full_name()}.")
        else:
            leave.reject(request.user)
            messages.warning(request, f"Leave rejected for {leave.employee.get_full_name()}.")
        return redirect("employees:leave_list")

    return render(request, "employees/leave_review.html", {
        "leave": leave, "form": form
    })


# ═════════════════════════════════════════════════════════════════════════════
# PERFORMANCE REVIEWS
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def performance_list(request):
    if request.user.is_manager_role:
        reviews = PerformanceReview.objects.all()
    else:
        reviews = PerformanceReview.objects.filter(
            employee=request.user, is_shared=True
        )

    reviews = reviews.select_related("employee", "reviewer").order_by("-review_period_end")

    return render(request, "employees/performance_list.html", {"reviews": reviews})


@login_required
def performance_create(request):
    if _require_manager(request):
        return redirect("employees:performance_list")

    form = PerformanceReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        review = form.save(commit=False)
        review.reviewer = request.user
        review.save()
        messages.success(
            request,
            f"Review created for {review.employee.get_full_name()} — "
            f"overall score {review.overall_score}/5.",
        )
        return redirect("employees:performance_detail", pk=review.pk)

    return render(request, "employees/performance_form.html", {
        "form": form, "title": "New Performance Review"
    })


@login_required
def performance_detail(request, pk):
    review = get_object_or_404(
        PerformanceReview.objects.select_related("employee", "reviewer"), pk=pk
    )
    # Access control: only manager or employee (when shared)
    if not request.user.is_manager_role:
        if request.user != review.employee or not review.is_shared:
            messages.error(request, "Access denied.")
            return redirect("employees:performance_list")

    return render(request, "employees/performance_detail.html", {"review": review})


@login_required
def performance_share(request, pk):
    if _require_manager(request):
        return redirect("employees:performance_list")

    review = get_object_or_404(PerformanceReview, pk=pk)
    review.share()
    messages.success(
        request,
        f"Review shared with {review.employee.get_full_name()}. "
        "They can now view it.",
    )
    return redirect("employees:performance_detail", pk=pk)


# ═════════════════════════════════════════════════════════════════════════════
# EXPORT
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def export_staff_csv(request):
    if _require_manager(request):
        return redirect("employees:staff_directory")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="staff_directory.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "Employee ID", "First Name", "Last Name", "Username", "Email", "Phone",
        "Role", "Primary Joint", "Department", "Employment Type",
        "Date Hired", "Date Terminated", "Commission %",
    ])

    for profile in EmployeeProfile.objects.select_related(
        "user", "user__primary_joint"
    ).order_by("employee_id"):
        u = profile.user
        writer.writerow([
            profile.employee_id,
            u.first_name, u.last_name, u.username, u.email,
            getattr(u, "phone", ""),
            u.get_role_display(),
            u.primary_joint.display_name if u.primary_joint else "",
            profile.get_department_display(),
            profile.get_employment_type_display(),
            profile.date_hired,
            profile.date_terminated or "",
            profile.commission_rate_percent,
        ])

    return response


# ═════════════════════════════════════════════════════════════════════════════
# API: quick employee lookup (for schedule AJAX)
# ═════════════════════════════════════════════════════════════════════════════

@login_required
def api_employee_list(request):
    from users.models import User
    users = User.objects.filter(is_active=True).select_related("primary_joint")
    data = [{
        "id":    u.pk,
        "name":  u.get_full_name() or u.username,
        "joint": u.primary_joint.display_name if u.primary_joint else "",
        "role":  u.get_role_display(),
    } for u in users]
    return JsonResponse({"employees": data})