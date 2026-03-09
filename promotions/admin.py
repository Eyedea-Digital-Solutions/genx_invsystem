from django.contrib import admin
from .models import Promotion, SpendThresholdPromo, FreeGiftPromo, BundlePromo


class SpendThresholdInline(admin.StackedInline):
    model = SpendThresholdPromo
    extra = 0


class FreeGiftInline(admin.StackedInline):
    model = FreeGiftPromo
    extra = 0


class BundleInline(admin.StackedInline):
    model = BundlePromo
    extra = 0


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ['name', 'promo_type', 'joint', 'is_active', 'start_date', 'end_date', 'status_label']
    list_filter = ['promo_type', 'is_active', 'joint']
    search_fields = ['name']
    inlines = [SpendThresholdInline, FreeGiftInline, BundleInline]
