"""
employees/admin.py
"""
from django.contrib import admin
from django.utils.html import format_html

from inventory_system.admin_site import genx_admin_site
from .models import EmployeeProfile, Shift, Attendance, LeaveRequest, PerformanceReview, Commission


class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display  = ["employee_id", "full_name_display", "department_badge",
                     "employment_type", "date_hired", "is_active_badge", "commission_rate_percent"]
    list_filter   = ["department", "employment_type"]
    search_fields = ["employee_id", "user__first_name", "user__last_name", "user__username"]
    readonly_fields = ["employee_id"]

    @admin.display(description="Name")
    def full_name_display(self, obj):
        return obj.full_name

    @admin.display(description="Department")
    def department_badge(self, obj):
        colors = {
            "sales":      ("#dbeafe", "#1e40af"),
            "management": ("#ede9fe", "#5b21b6"),
            "operations": ("#dcfce7", "#166534"),
            "admin":      ("#fef3c7", "#92400e"),
        }
        bg, fg = colors.get(obj.department, ("#f3f4f6", "#374151"))
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;border-radius:4px;'
            'font-size:10px;font-weight:700;text-transform:uppercase;">{}</span>',
            bg, fg, obj.get_department_display()
        )

    @admin.display(description="Active")
    def is_active_badge(self, obj):
        if obj.is_active_employee:
            return format_html('<span style="color:#16a34a;font-weight:700;">✓ Active</span>')
        return format_html('<span style="color:#9ca3af;">Terminated</span>')


class ShiftAdmin(admin.ModelAdmin):
    list_display = ["employee", "joint", "date", "start_time", "end_time", "is_confirmed"]
    list_filter  = ["joint", "is_confirmed", "date"]
    date_hierarchy = "date"

    actions = ["confirm_shifts"]

    @admin.action(description="✓ Confirm selected shifts")
    def confirm_shifts(self, request, queryset):
        n = queryset.update(is_confirmed=True, confirmed_by=request.user)
        self.message_user(request, f"{n} shift(s) confirmed.")


class AttendanceAdmin(admin.ModelAdmin):
    list_display  = ["employee", "joint", "clock_in", "clock_out", "total_hours", "is_late"]
    list_filter   = ["joint", "is_late"]
    date_hierarchy = "clock_in"
    search_fields = ["employee__first_name", "employee__last_name"]


class LeaveRequestAdmin(admin.ModelAdmin):
    list_display  = ["employee", "leave_type", "start_date", "end_date",
                     "days_requested", "status_badge", "reviewed_by"]
    list_filter   = ["status", "leave_type"]
    search_fields = ["employee__first_name", "employee__last_name"]

    @admin.display(description="Status")
    def status_badge(self, obj):
        cfg = {
            "pending":  ("#fef3c7", "#92400e", "⏳ Pending"),
            "approved": ("#dcfce7", "#166534", "✓ Approved"),
            "rejected": ("#fee2e2", "#7f1d1d", "✗ Rejected"),
        }
        bg, fg, lbl = cfg.get(obj.status, ("#f3f4f6", "#374151", obj.status))
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;border-radius:4px;'
            'font-size:10px;font-weight:700;">{}</span>', bg, fg, lbl
        )

    actions = ["approve_leaves", "reject_leaves"]

    @admin.action(description="✓ Approve selected leave requests")
    def approve_leaves(self, request, queryset):
        n = 0
        for leave in queryset.filter(status=LeaveRequest.STATUS_PENDING):
            leave.approve(request.user); n += 1
        self.message_user(request, f"{n} leave request(s) approved.")

    @admin.action(description="✗ Reject selected leave requests")
    def reject_leaves(self, request, queryset):
        n = 0
        for leave in queryset.filter(status=LeaveRequest.STATUS_PENDING):
            leave.reject(request.user); n += 1
        self.message_user(request, f"{n} leave request(s) rejected.", level="warning")


class PerformanceReviewAdmin(admin.ModelAdmin):
    list_display  = ["employee", "reviewer", "review_period_start",
                     "review_period_end", "overall_score", "score_label", "is_shared"]
    list_filter   = ["is_shared"]
    search_fields = ["employee__first_name", "employee__last_name"]

    actions = ["share_reviews"]

    @admin.action(description="Share selected reviews with employees")
    def share_reviews(self, request, queryset):
        n = queryset.update(is_shared=True)
        self.message_user(request, f"{n} review(s) shared.")


class CommissionAdmin(admin.ModelAdmin):
    list_display = ["employee", "period", "rate_percent", "amount", "is_paid", "paid_at"]
    list_filter  = ["is_paid", "period"]
    search_fields = ["employee__first_name", "employee__last_name"]


genx_admin_site.register(EmployeeProfile, EmployeeProfileAdmin)
genx_admin_site.register(Shift, ShiftAdmin)
genx_admin_site.register(Attendance, AttendanceAdmin)
genx_admin_site.register(LeaveRequest, LeaveRequestAdmin)
genx_admin_site.register(PerformanceReview, PerformanceReviewAdmin)
genx_admin_site.register(Commission, CommissionAdmin)
