"""
expenses/forms.py
"""
from django import forms
from .models import Expense, ExpenseCategory


class ExpenseForm(forms.ModelForm):
    class Meta:
        model  = Expense
        fields = ['joint', 'category', 'description', 'amount',
                  'payment_method', 'reference', 'expense_date', 'notes']
        widgets = {
            'joint':          forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'category':       forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'description':    forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'e.g. Electricity bill'}),
            'amount':         forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.01', 'min': '0.01'}),
            'payment_method': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'reference':      forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Receipt / invoice number (optional)'}),
            'expense_date':   forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'}),
            'notes':          forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 2, 'placeholder': 'Optional notes…'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = ExpenseCategory.objects.filter(is_active=True)
        self.fields['notes'].required    = False
        self.fields['reference'].required = False


class ExpenseFilterForm(forms.Form):
    joint = forms.ChoiceField(required=False, widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'style': 'width:160px;'}))
    category = forms.ChoiceField(required=False, widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'style': 'width:160px;'}))
    payment_method = forms.ChoiceField(required=False, widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'style': 'width:130px;'}))
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date', 'style': 'width:140px;'}))
    date_to   = forms.DateField(required=False, widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date', 'style': 'width:140px;'}))

    def __init__(self, joints, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['joint'].choices = [('', 'All Joints')] + [(j.pk, j.display_name) for j in joints]
        self.fields['category'].choices = [('', 'All Categories')] + list(
            ExpenseCategory.objects.filter(is_active=True).values_list('pk', 'name')
        )
        self.fields['payment_method'].choices = [('', 'All Methods')] + list(Expense.PAYMENT_METHODS)


class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model  = ExpenseCategory
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name':        forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'description': forms.Textarea(attrs={'class': 'form-control form-control-sm', 'rows': 2}),
            'is_active':   forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }