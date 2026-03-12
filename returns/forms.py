from django import forms
from .models import Return


class ReturnSearchForm(forms.Form):
    receipt_number = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class':       'form-control form-control-lg',
            'placeholder': 'Enter receipt number (e.g. GNX-0042)…',
            'autofocus':   True,
        })
    )


class ReturnReasonForm(forms.Form):
    """Step 2 of the return wizard — choose refund type and reason."""
    refund_type = forms.ChoiceField(
        choices=Return.REFUND_TYPE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
    )
    reason = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class':       'form-control',
            'placeholder': 'e.g. Defective item, wrong size, customer changed mind…',
        }),
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
    )

    def clean_reason(self):
        r = self.cleaned_data.get('reason', '').strip()
        if not r:
            raise forms.ValidationError('Please state the reason for the return.')
        return r


class ReturnItemForm(forms.Form):
    """
    Dynamically generated in the view for each returnable SaleItem.
    Bound to the sale_item pk via field name prefix.
    """
    quantity = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': '0'}),
    )
    restock = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )