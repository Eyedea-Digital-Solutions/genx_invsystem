from django import forms
from .models import Sale, SaleItem
from inventory.models import Joint, Product


class SaleForm(forms.ModelForm):
    """Main form to record a sale."""
    class Meta:
        model = Sale
        fields = ['joint', 'payment_method', 'customer_name', 'notes']
        widgets = {
            'joint': forms.Select(attrs={'class': 'form-select', 'id': 'joint-select'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'customer_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional customer name'
            }),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ManualSaleForm(forms.ModelForm):
    """Form to record a manual sale by uploading a receipt photo."""
    class Meta:
        model = Sale
        fields = ['joint', 'payment_method', 'customer_name', 'manual_receipt_image', 'notes', 'sale_date']
        widgets = {
            'joint': forms.Select(attrs={'class': 'form-select'}),
            'payment_method': forms.Select(attrs={'class': 'form-select'}),
            'customer_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Customer name (optional)'
            }),
            'manual_receipt_image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'sale_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }

    def clean_manual_receipt_image(self):
        image = self.cleaned_data.get('manual_receipt_image')
        if not image:
            raise forms.ValidationError("Please upload a photo of the manual receipt.")
        return image


class SaleItemForm(forms.ModelForm):
    """Form for individual product lines in a sale."""
    class Meta:
        model = SaleItem
        fields = ['product', 'quantity', 'unit_price']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select product-select'}),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': 'Qty'
            }),
            'unit_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': 'Price'
            }),
        }


# Django formsets allow multiple SaleItems per sale
SaleItemFormSet = forms.inlineformset_factory(
    Sale,
    SaleItem,
    form=SaleItemForm,
    extra=3,        # Start with 3 empty rows
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class SaleFilterForm(forms.Form):
    """Form to filter sales in the list view."""
    joint = forms.ModelChoiceField(
        queryset=Joint.objects.all(),
        required=False,
        empty_label='All Joints',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    payment_method = forms.ChoiceField(
        choices=[('', 'All Methods')] + Sale.PAYMENT_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    sold_by = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Staff name...'})
    )
