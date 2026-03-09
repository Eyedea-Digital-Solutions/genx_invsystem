from django import forms
from .models import Sale


class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ['joint', 'payment_method', 'customer_name', 'notes']
        widgets = {
            'joint': forms.Select(attrs={'class': 'form-select'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'customer_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Customer name (optional)'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Notes (optional)'}),
        }


class ManualSaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ['joint', 'payment_method', 'customer_name', 'manual_receipt_image', 'notes']
        widgets = {
            'joint': forms.Select(attrs={'class': 'form-select'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'customer_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Customer name (optional)'}),
            'manual_receipt_image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class SaleFilterForm(forms.Form):
    from inventory.models import Joint
    joint = forms.ModelChoiceField(
        queryset=Joint.objects.all(),
        required=False,
        empty_label='All Joints',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    payment_method = forms.ChoiceField(
        choices=[('', 'All Methods')] + Sale.PAYMENT_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'})
    )
    sold_by = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Staff name'})
    )
