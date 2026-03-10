"""
users/admin.py
──────────────
Extended UserAdmin for GenX POS — adds role badge, sales summary,
and bulk role/status actions.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone

from inventory_system.admin_site import genx_admin_site
from .models import User


class UserAdmin(BaseUserAdmin):
    list_display    = ['username', 'full_name', 'role_badge', 'primary_joint',
                       'is_active', 'sales_count', 'last_login_display']
    list_filter     = ['role', 'primary_joint', 'is_active', 'is_staff']
    search_fields   = ['username', 'first_name', 'last_name', 'email', 'phone']
    ordering        = ['username']
    list_per_page   = 40
    readonly_fields = ['last_login', 'date_joined', 'sales_summary', 'sales_count']

    # ── fieldsets (extend base) ──────────────────────────────────────
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email', 'phone')}),
        ('GenX POS Role', {'fields': ('role', 'primary_joint')}),
        ('Sales Summary', {'fields': ('sales_summary',)}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',),
        }),
        ('Dates', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',),
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2'),
        }),
        ('GenX POS', {
            'fields': ('first_name', 'last_name', 'email', 'phone', 'role', 'primary_joint'),
        }),
    )

    # ── display methods ──────────────────────────────────────────────
    @admin.display(description='Name', ordering='first_name')
    def full_name(self, obj):
        return obj.get_full_name() or '—'

    @admin.display(description='Role')
    def role_badge(self, obj):
        cfg = {
            'cashier': ('#f3f4f6', '#374151'),
            'manager': ('#dbeafe', '#1e40af'),
            'admin':   ('#fee2e2', '#7f1d1d'),
        }
        bg, fg = cfg.get(obj.role, ('#f3f4f6', '#6b7280'))
        return format_html(
            '<span style="background:{};color:{};padding:2px 9px;border-radius:4px;'
            'font-size:10px;font-weight:800;text-transform:uppercase;">{}</span>',
            bg, fg, obj.role
        )

    @admin.display(description='Last Login')
    def last_login_display(self, obj):
        if not obj.last_login:
            return format_html('<span style="color:#9ca3af;font-size:11px;">Never</span>')
        return obj.last_login.strftime('%d %b %Y %H:%M')

    @admin.display(description='Sales')
    def sales_count(self, obj):
        try:
            from sales.models import Sale
            count = Sale.objects.filter(sold_by=obj, is_held=False).count()
            url   = reverse('genx_admin:sales_sale_changelist') + f'?sold_by__id__exact={obj.pk}'
            return format_html('<a href="{}" style="font-weight:600;">{}</a>', url, count)
        except Exception:
            return '—'

    @admin.display(description='Sales Summary')
    def sales_summary(self, obj):
        try:
            from sales.models import Sale
            from django.db.models import Sum
            today      = timezone.now().date()
            this_month = today.replace(day=1)

            all_sales = Sale.objects.filter(sold_by=obj, is_held=False)
            month_sales = all_sales.filter(sale_date__date__gte=this_month)

            all_total   = sum(s.total_amount for s in all_sales)
            month_total = sum(s.total_amount for s in month_sales)

            return format_html(
                '<div style="display:flex;gap:16px;">'
                '<div><div style="font-size:10px;color:#9ca3af;text-transform:uppercase;letter-spacing:.4px;">This Month</div>'
                '<div style="font-size:18px;font-weight:800;color:#2563eb;">${:.2f}</div>'
                '<div style="font-size:11px;color:#6b7280;">{} sales</div></div>'
                '<div><div style="font-size:10px;color:#9ca3af;text-transform:uppercase;letter-spacing:.4px;">All Time</div>'
                '<div style="font-size:18px;font-weight:800;">${:.2f}</div>'
                '<div style="font-size:11px;color:#6b7280;">{} sales</div></div>'
                '</div>',
                month_total, month_sales.count(),
                all_total,   all_sales.count(),
            )
        except Exception:
            return '—'

    # ── bulk actions ─────────────────────────────────────────────────
    actions = ['activate_users', 'deactivate_users', 'set_role_cashier', 'set_role_manager']

    @admin.action(description='✓ Activate selected users')
    def activate_users(self, request, queryset):
        n = queryset.update(is_active=True)
        self.message_user(request, f'{n} user(s) activated.')

    @admin.action(description='⏸ Deactivate selected users')
    def deactivate_users(self, request, queryset):
        n = queryset.exclude(pk=request.user.pk).update(is_active=False)
        self.message_user(request, f'{n} user(s) deactivated.')

    @admin.action(description='Set role → Cashier')
    def set_role_cashier(self, request, queryset):
        n = queryset.update(role='cashier')
        self.message_user(request, f'{n} user(s) set to Cashier.')

    @admin.action(description='Set role → Manager')
    def set_role_manager(self, request, queryset):
        n = queryset.update(role='manager')
        self.message_user(request, f'{n} user(s) set to Manager.')


genx_admin_site.register(User, UserAdmin)
