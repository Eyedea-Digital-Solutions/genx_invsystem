from django.contrib import admin
from .models import EcoCashTransaction


@admin.register(EcoCashTransaction)
class EcoCashTransactionAdmin(admin.ModelAdmin):
    list_display = ['sale', 'amount', 'reference', 'status', 'created_at', 'confirmed_by']
    list_filter = ['status']
    search_fields = ['reference', 'sale__receipt_number']
    readonly_fields = ['created_at', 'confirmed_at']
