from django.contrib import admin
from .models import EcoCashTransaction


@admin.register(EcoCashTransaction)
class EcoCashTransactionAdmin(admin.ModelAdmin):
    list_display = ['sale', 'amount', 'econet_number', 'transaction_reference', 'status', 'confirmed_by', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['sale__receipt_number', 'transaction_reference']
    readonly_fields = ['sale', 'econet_number', 'amount', 'created_at']

    def has_delete_permission(self, request, obj=None):
        return False
