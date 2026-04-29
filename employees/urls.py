from django.urls import path
from . import views

app_name = 'employees'

urlpatterns = [
    # ── Dashboard (the sidebar link hits this) ──────────────────────
    path('', views.EmployeeDashboardView.as_view(), name='dashboard'),

    # ── Basic CRUD (existing) ────────────────────────────────────────
    path('list/', views.EmployeeListView.as_view(), name='list'),
    path('add/', views.EmployeeCreateView.as_view(), name='add'),
    path('<int:pk>/', views.EmployeeDetailView.as_view(), name='detail'),
    path('<int:pk>/edit/', views.EmployeeUpdateView.as_view(), name='edit'),

    # ── Staff directory ──────────────────────────────────────────────
    path('directory/', views.StaffDirectoryView.as_view(), name='staff_directory'),
    path('directory/export/', views.export_staff_csv, name='export_staff_csv'),
    path('employee/create/', views.EmployeeProfileCreateView.as_view(), name='employee_create'),
    path('employee/<int:pk>/edit/', views.EmployeeProfileUpdateView.as_view(), name='employee_edit'),
    path('employee/<int:pk>/', views.EmployeeProfileDetailView.as_view(), name='employee_detail'),

    # ── Schedule ─────────────────────────────────────────────────────
    path('schedule/', views.ScheduleView.as_view(), name='schedule'),
    path('shifts/create/', views.ShiftCreateView.as_view(), name='shift_create'),
    path('shifts/<int:pk>/edit/', views.ShiftUpdateView.as_view(), name='shift_edit'),
    path('shifts/<int:pk>/confirm/', views.shift_confirm, name='shift_confirm'),
    path('shifts/<int:pk>/delete/', views.shift_delete, name='shift_delete'),

    # ── Attendance ───────────────────────────────────────────────────
    path('attendance/', views.AttendanceView.as_view(), name='attendance'),
    path('attendance/clock-in/', views.ClockInView.as_view(), name='clock_in'),
    path('attendance/<int:pk>/clock-out/', views.clock_out, name='clock_out'),

    # ── Leave ────────────────────────────────────────────────────────
    path('leave/', views.LeaveListView.as_view(), name='leave_list'),
    path('leave/apply/', views.LeaveCreateView.as_view(), name='leave_create'),
    path('leave/<int:pk>/review/', views.LeaveReviewView.as_view(), name='leave_review'),

    # ── Performance reviews ──────────────────────────────────────────
    path('performance/', views.PerformanceListView.as_view(), name='performance_list'),
    path('performance/create/', views.PerformanceCreateView.as_view(), name='performance_create'),
    path('performance/<int:pk>/', views.PerformanceDetailView.as_view(), name='performance_detail'),
    path('performance/<int:pk>/share/', views.performance_share, name='performance_share'),
]