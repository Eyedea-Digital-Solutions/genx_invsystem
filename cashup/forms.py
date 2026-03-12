from decimal import Decimal
from django import forms
from .models import CashUp


class CashUpOpenForm(forms.ModelForm):
    class Meta:
        model = CashUp
        fields = ['joint', 'shift', 'shift_date', 'opening_float']
        widgets = {
            'joint': forms.Select(attrs={'class': 'form-select'}),
            'shift': forms.Select(attrs={'class': 'form-select'}),
            'shift_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'opening_float': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00'
            }),
        }


class CashUpCountForm(forms.ModelForm):
    class Meta:
        model = CashUp
        fields = [
            'cash_denomination_100', 'cash_denomination_50', 'cash_denomination_20',
            'cash_denomination_10', 'cash_denomination_5', 'cash_denomination_2',
            'cash_denomination_1', 'cash_denomination_cents',
            'actual_ecocash', 'actual_card', 'notes',
        ]
        widgets = {
            'cash_denomination_100': forms.NumberInput(attrs={'class': 'form-control denom-input', 'min': '0', 'placeholder': '0'}),
            'cash_denomination_50': forms.NumberInput(attrs={'class': 'form-control denom-input', 'min': '0', 'placeholder': '0'}),
            'cash_denomination_20': forms.NumberInput(attrs={'class': 'form-control denom-input', 'min': '0', 'placeholder': '0'}),
            'cash_denomination_10': forms.NumberInput(attrs={'class': 'form-control denom-input', 'min': '0', 'placeholder': '0'}),
            'cash_denomination_5': forms.NumberInput(attrs={'class': 'form-control denom-input', 'min': '0', 'placeholder': '0'}),
            'cash_denomination_2': forms.NumberInput(attrs={'class': 'form-control denom-input', 'min': '0', 'placeholder': '0'}),
            'cash_denomination_1': forms.NumberInput(attrs={'class': 'form-control denom-input', 'min': '0', 'placeholder': '0'}),
            'cash_denomination_cents': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'actual_ecocash': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'actual_card': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Any notes about this cash-up…'}),
        }

    def clean(self):
        cd = super().clean()
        denom_total = (
            Decimal(cd.get('cash_denomination_100', 0)) * 100 +
            Decimal(cd.get('cash_denomination_50', 0)) * 50 +
            Decimal(cd.get('cash_denomination_20', 0)) * 20 +
            Decimal(cd.get('cash_denomination_10', 0)) * 10 +
            Decimal(cd.get('cash_denomination_5', 0)) * 5 +
            Decimal(cd.get('cash_denomination_2', 0)) * 2 +
            Decimal(cd.get('cash_denomination_1', 0)) * 1 +
            Decimal(cd.get('cash_denomination_cents', 0))
        )
        self._denom_total = denom_total
        return cd


class ManagerReviewForm(forms.Form):
    action = forms.ChoiceField(
        choices=[('approve', 'Approve'), ('dispute', 'Dispute')],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
    )
    manager_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Manager notes…'}),
    )

    def clean(self):
        cd = super().clean()
        if cd.get('action') == 'dispute' and not cd.get('manager_notes', '').strip():
            raise forms.ValidationError('Please provide notes when disputing a cash-up.')
        return cd


class CashUpFilterForm(forms.Form):
    from inventory.models import Joint
    joint = forms.ModelChoiceField(
        queryset=Joint.objects.all(),
        required=False,
        empty_label='All Joints',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'style': 'width:150px;'}),
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Statuses')] + CashUp.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'style': 'width:140px;'}),
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date', 'style': 'width:140px;'}),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date', 'style': 'width:140px;'}),
    )
    cashier = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Cashier name', 'style': 'width:140px;'}),
    )