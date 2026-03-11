from django.contrib import admin
from .models import Expense, ExpenseCategory


@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'description')
    list_editable = ('is_active',)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display  = ('expense_date', 'joint', 'category', 'description', 'amount', 'payment_method', 'recorded_by')
    list_filter   = ('joint', 'category', 'payment_method', 'expense_date')
    search_fields = ('description', 'reference', 'notes')
    date_hierarchy = 'expense_date'
    readonly_fields = ('created_at', 'updated_at', 'recorded_by')

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.recorded_by = request.user
        super().save_model(request, obj, form, change)