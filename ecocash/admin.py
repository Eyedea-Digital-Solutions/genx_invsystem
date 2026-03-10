from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse

from inventory_system.admin_site import genx_admin_site
from .models import EcoCashTransaction


class EcoCashTransactionAdmin(admin.ModelAdmin):
    list_display    = ['id', 'phone_number', 'sale_info', 'amount_disp',
                       'status_badge', 'created_at_fmt', 'confirmed_at_fmt']
    list_filter     = ['status', 'sale__joint']
    search_fields   = ['phone_number', 'sale__receipt_number']
    readonly_fields = ['created_at', 'confirmed_at', 'sale_info']
    ordering        = ['-created_at']
    list_per_page   = 50
    date_hierarchy  = 'created_at'

    fieldsets = (
        ('Transaction', {
            'fields': ('sale', 'phone_number', 'amount', 'status')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'confirmed_at'),
        }),
    )

    @admin.display(description='Sale / Cashier / Joint')
    def sale_info(self, obj):
        if not obj.sale_id:
            return '—'
        url = reverse('genx_admin:sales_sale_change', args=[obj.sale_id])
        return format_html(
            '<a href="{}" style="font-weight:600;">{}</a>'
            '<span style="color:#9ca3af;font-size:10px;"> · {} · {}</span>',
            url,
            obj.sale.receipt_number,
            obj.sale.sold_by.get_full_name() or obj.sale.sold_by.username,
            obj.sale.joint.display_name,
        )

    @admin.display(description='Amount')
    def amount_disp(self, obj):
        return format_html('<strong>${:.2f}</strong>', obj.amount)

    @admin.display(description='Status')
    def status_badge(self, obj):
        cfg = {
            EcoCashTransaction.STATUS_PENDING:   ('#fef3c7', '#92400e', '⏳ Pending'),
            EcoCashTransaction.STATUS_CONFIRMED: ('#d1fae5', '#065f46', '✓ Confirmed'),
            EcoCashTransaction.STATUS_FAILED:    ('#fee2e2', '#7f1d1d', '✗ Failed'),
        }
        bg, fg, label = cfg.get(obj.status, ('#f3f4f6', '#374151', obj.status))
        return format_html(
            '<span style="background:{};color:{};padding:3px 9px;border-radius:5px;'
            'font-size:10px;font-weight:700;">{}</span>',
            bg, fg, label
        )

    @admin.display(description='Created', ordering='created_at')
    def created_at_fmt(self, obj):
        return obj.created_at.strftime('%d %b %Y  %H:%M')

    @admin.display(description='Confirmed At')
    def confirmed_at_fmt(self, obj):
        return obj.confirmed_at.strftime('%d %b %Y  %H:%M') if obj.confirmed_at else '—'

    actions = ['confirm_payments', 'fail_payments']

    @admin.action(description='✓ Confirm selected EcoCash payments')
    def confirm_payments(self, request, queryset):
        confirmed = 0
        errors    = []
        for tx in queryset.filter(status=EcoCashTransaction.STATUS_PENDING):
            try:
                tx.confirm(request.user)
                confirmed += 1
            except Exception as exc:
                errors.append(f'{tx.id}: {exc}')
        if confirmed:
            self.message_user(request, f'{confirmed} payment(s) confirmed.')
        for e in errors:
            self.message_user(request, e, level='error')

    @admin.action(description='✗ Mark selected as failed')
    def fail_payments(self, request, queryset):
        failed = 0
        for tx in queryset.filter(status=EcoCashTransaction.STATUS_PENDING):
            try:
                tx.mark_failed(notes='Manually failed via admin')
                failed += 1
            except Exception:
                pass
        self.message_user(request, f'{failed} payment(s) marked as failed.', level='warning')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('sale__joint', 'sale__sold_by', 'initiated_by')


genx_admin_site.register(EcoCashTransaction, EcoCashTransactionAdmin)