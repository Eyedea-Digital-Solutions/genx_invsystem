"""
employees/urls.py
"""
from django.urls import path
from . import views

app_name = "employees"

urlpatterns = [
    # ── Dashboard ────────────────────────────────────────────────────────────
    path("",                                views.staff_dashboard,      name="dashboard"),

    # ── Staff directory ──────────────────────────────────────────────────────
    path("staff/",                          views.staff_directory,      name="staff_directory"),
    path("staff/add/",                      views.employee_create,      name="employee_create"),
    path("staff/export/",                   views.export_staff_csv,     name="export_staff_csv"),
    path("staff/<int:pk>/",                 views.employee_detail,      name="employee_detail"),
    path("staff/<int:pk>/edit/",            views.employee_edit,        name="employee_edit"),

    # ── Schedule ─────────────────────────────────────────────────────────────
    path("schedule/",                       views.schedule_view,        name="schedule"),
    path("schedule/shift/add/",             views.shift_create,         name="shift_create"),
    path("schedule/shift/<int:pk>/edit/",   views.shift_edit,           name="shift_edit"),
    path("schedule/shift/<int:pk>/delete/", views.shift_delete,         name="shift_delete"),
    path("schedule/shift/<int:pk>/confirm/",views.shift_confirm,        name="shift_confirm"),

    # ── Attendance ───────────────────────────────────────────────────────────
    path("attendance/",                     views.attendance_view,      name="attendance"),
    path("attendance/clock-in/",            views.clock_in,             name="clock_in"),
    path("attendance/<int:pk>/clock-out/",  views.clock_out,            name="clock_out"),

    # ── Leave ────────────────────────────────────────────────────────────────
    path("leave/",                          views.leave_list,           name="leave_list"),
    path("leave/apply/",                    views.leave_create,         name="leave_create"),
    path("leave/<int:pk>/review/",          views.leave_review,         name="leave_review"),

    # ── Performance reviews ──────────────────────────────────────────────────
    path("performance/",                    views.performance_list,     name="performance_list"),
    path("performance/add/",               views.performance_create,   name="performance_create"),
    path("performance/<int:pk>/",           views.performance_detail,   name="performance_detail"),
    path("performance/<int:pk>/share/",     views.performance_share,    name="performance_share"),

    # ── API ──────────────────────────────────────────────────────────────────
    path("api/employees/",                  views.api_employee_list,    name="api_employee_list"),
]