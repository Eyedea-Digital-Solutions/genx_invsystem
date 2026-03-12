from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from decimal import Decimal

from inventory_system.admin_site import genx_admin_site
from .models import CashUp, CashUpAuditLog


class CashUpAuditLogInline(admin.TabularInline):
    model = CashUpAuditLog
    extra = 0
    readonly_fields = ['action', 'performed_by', 'timestamp', 'details']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class CashUpAdmin(admin.ModelAdmin):
    list_display = [
        'shift_date', 'joint', 'cashier', 'shift_badge', 'status_badge',
        'expected_total_disp', 'actual_total_disp', 'variance_disp', 'approved_by',
    ]
    list_filter = ['status', 'joint', 'shift', 'shift_date']
    search_fields = ['cashier__username', 'cashier__first_name', 'cashier__last_name', 'joint__display_name']
    readonly_fields = [
        'expected_cash', 'expected_ecocash', 'expected_card',
        'expected_mixed_cash', 'expected_mixed_ecocash',
        'expenses_cash', 'expenses_ecocash',
        'submitted_at', 'approved_at', 'created_at', 'updated_at',
        'variance_summary',
    ]
    date_hierarchy = 'shift_date'
    ordering = ['-shift_date', '-opened_at']
    inlines = [CashUpAuditLogInline]

    fieldsets = (
        ('Session', {
            'fields': ('joint', 'cashier', 'shift', 'shift_date', 'status', 'opening_float'),
        }),
        ('Expected (Auto-computed)', {
            'fields': (
                'expected_cash', 'expected_ecocash', 'expected_card',
                'expected_mixed_cash', 'expected_mixed_ecocash',
                'expenses_cash', 'expenses_ecocash',
            ),
            'classes': ('collapse',),
        }),
        ('Denomination Count', {
            'fields': (
                'cash_denomination_100', 'cash_denomination_50', 'cash_denomination_20',
                'cash_denomination_10', 'cash_denomination_5', 'cash_denomination_2',
                'cash_denomination_1', 'cash_denomination_cents',
            ),
        }),
        ('Actuals', {
            'fields': ('actual_cash', 'actual_ecocash', 'actual_card', 'variance_summary'),
        }),
        ('Review', {
            'fields': ('approved_by', 'notes', 'manager_notes'),
        }),
        ('Timestamps', {
            'fields': ('opened_at', 'submitted_at', 'approved_at', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='Shift')
    def shift_badge(self, obj):
        colors = {
            'morning': ('#dbeafe', '#1e40af'),
            'afternoon': ('#fef3c7', '#92400e'),
            'full': ('#d1fae5', '#065f46'),
        }
        bg, fg = colors.get(obj.shift, ('#f3f4f6', '#374151'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 8px;border-radius:4px;font-size:10px;font-weight:700;">{}</span>',
            bg, fg, obj.get_shift_display()
        )

    @admin.display(description='Status')
    def status_badge(self, obj):
        cfg = {
            CashUp.STATUS_OPEN: ('#f3f4f6', '#374151', '● Open'),
            CashUp.STATUS_SUBMITTED: ('#fef3c7', '#92400e', '⏳ Submitted'),
            CashUp.STATUS_APPROVED: ('#d1fae5', '#065f46', '✓ Approved'),
            CashUp.STATUS_DISPUTED: ('#fee2e2', '#7f1d1d', '✗ Disputed'),
        }
        bg, fg, label = cfg.get(obj.status, ('#f3f4f6', '#374151', obj.status))
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;border-radius:5px;font-size:10px;font-weight:700;">{}</span>',
            bg, fg, label
        )

    @admin.display(description='Expected')
    def expected_total_disp(self, obj):
        return format_html('${:.2f}', obj.total_expected)

    @admin.display(description='Actual')
    def actual_total_disp(self, obj):
        return format_html('<strong>${:.2f}</strong>', obj.total_actual)

    @admin.display(description='Variance')
    def variance_disp(self, obj):
        v = obj.total_variance
        color = '#16a34a' if v >= 0 else '#dc2626'
        sign = '+' if v >= 0 else ''
        return format_html(
            '<span style="color:{};font-weight:700;">{}{:.2f}</span>',
            color, sign, v
        )

    @admin.display(description='Variance Summary')
    def variance_summary(self, obj):
        def row(label, variance):
            color = '#16a34a' if variance >= 0 else '#dc2626'
            sign = '+' if variance >= 0 else ''
            return f'<tr><td style="padding:4px 8px;">{label}</td><td style="padding:4px 8px;color:{color};font-weight:700;">{sign}{variance:.2f}</td></tr>'

        html = (
            '<table style="border-collapse:collapse;font-size:12px;">'
            + row('Cash', obj.cash_variance)
            + row('EcoCash', obj.ecocash_variance)
            + row('Card', obj.card_variance)
            + row('TOTAL', obj.total_variance)
            + '</table>'
        )
        return format_html(html)

    actions = ['approve_cashups', 'flag_disputed']

    @admin.action(description='✓ Approve selected cash-ups')
    def approve_cashups(self, request, queryset):
        n = 0
        for cu in queryset.filter(status=CashUp.STATUS_SUBMITTED):
            cu.approve(request.user, notes='Bulk approved via admin')
            n += 1
        self.message_user(request, f'{n} cash-up(s) approved.')

    @admin.action(description='✗ Flag selected as disputed')
    def flag_disputed(self, request, queryset):
        n = queryset.filter(
            status__in=[CashUp.STATUS_SUBMITTED, CashUp.STATUS_APPROVED]
        ).update(status=CashUp.STATUS_DISPUTED)
        self.message_user(request, f'{n} cash-up(s) flagged as disputed.', level='warning')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('joint', 'cashier', 'approved_by')


genx_admin_site.register(CashUp, CashUpAdmin)
genx_admin_site.register(CashUpAuditLog)