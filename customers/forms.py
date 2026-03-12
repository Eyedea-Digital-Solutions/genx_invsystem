from django import forms
from .models import Customer


class CustomerForm(forms.ModelForm):
    class Meta:
        model  = Customer
        fields = ['name', 'phone', 'email', 'address', 'customer_type', 'notes', 'is_active']
        widgets = {
            'name':          forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full name'}),
            'phone':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+263 7xx xxx xxx'}),
            'email':         forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'address':       forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'customer_type': forms.Select(attrs={'class': 'form-select'}),
            'notes':         forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'is_active':     forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CustomerSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name or phone…',
            'autofocus': True,
        })
    )
    customer_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All Types')] + Customer.TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'style': 'width:140px;'}),
    )


class LoyaltyAdjustForm(forms.Form):
    points = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        help_text='Use a negative number to deduct points.',
    )
    reason = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Reason for adjustment…'}),
    )

    def clean_reason(self):
        r = self.cleaned_data.get('reason', '').strip()
        if not r:
            raise forms.ValidationError('Please provide a reason.')
        return r