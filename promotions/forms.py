from django import forms
from .models import Promotion, SpendThresholdPromo, FreeGiftPromo, BundlePromo
from inventory.models import Product, Joint


class PromotionBaseForm(forms.ModelForm):
    class Meta:
        model = Promotion
        fields = ['name', 'promo_type', 'joint', 'start_date', 'end_date', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'promo_type': forms.Select(attrs={'class': 'form-select'}),
            'joint': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class SpendThresholdForm(forms.ModelForm):
    class Meta:
        model = SpendThresholdPromo
        fields = ['min_cart_value', 'discount_type', 'discount_value']
        widgets = {
            'min_cart_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'discount_type': forms.Select(attrs={'class': 'form-select'}),
            'discount_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }


class FreeGiftForm(forms.ModelForm):
    class Meta:
        model = FreeGiftPromo
        fields = ['trigger_product', 'trigger_quantity', 'gift_product', 'gift_quantity']
        widgets = {
            'trigger_product': forms.Select(attrs={'class': 'form-select'}),
            'trigger_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'gift_product': forms.Select(attrs={'class': 'form-select'}),
            'gift_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
        }


class BundleForm(forms.ModelForm):
    class Meta:
        model = BundlePromo
        fields = ['products', 'bundle_price']
        widgets = {
            'products': forms.SelectMultiple(attrs={'class': 'form-select', 'size': '8'}),
            'bundle_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
