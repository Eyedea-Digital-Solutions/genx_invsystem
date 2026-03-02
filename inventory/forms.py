from django import forms
from .models import Product, Stock, StockTake, StockTakeItem, StockTransfer, Joint


class ProductForm(forms.ModelForm):
    """Form to add or edit a product."""
    class Meta:
        model = Product
        fields = ['joint', 'code', 'name', 'price', 'is_active']
        widgets = {
            'joint': forms.Select(attrs={'class': 'form-select'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. EYE-001'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Product name'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        joint = cleaned_data.get('joint')
        code = cleaned_data.get('code')
        # If joint uses product codes, code is required
        if joint and joint.uses_product_codes and not code:
            self.add_error('code', 'This joint requires a product code.')
        return cleaned_data


class StockAdjustForm(forms.Form):
    """Form to manually adjust stock levels (for receiving new stock)."""
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
        label='Quantity to Add'
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        label='Notes (optional)'
    )


class StockTakeForm(forms.ModelForm):
    """Form to start a stock take."""
    class Meta:
        model = StockTake
        fields = ['joint', 'notes']
        widgets = {
            'joint': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class StockTransferForm(forms.ModelForm):
    """Form to transfer stock between joints."""
    class Meta:
        model = StockTransfer
        fields = ['from_joint', 'to_joint', 'product', 'quantity', 'notes']
        widgets = {
            'from_joint': forms.Select(attrs={'class': 'form-select'}),
            'to_joint': forms.Select(attrs={'class': 'form-select'}),
            'product': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def clean(self):
        cleaned_data = super().clean()
        from_joint = cleaned_data.get('from_joint')
        to_joint = cleaned_data.get('to_joint')
        product = cleaned_data.get('product')
        quantity = cleaned_data.get('quantity')

        if from_joint and to_joint and from_joint == to_joint:
            raise forms.ValidationError("From and To joints must be different.")

        if product and quantity:
            if product.current_stock < quantity:
                raise forms.ValidationError(
                    f"Not enough stock. Available: {product.current_stock}, Requested: {quantity}"
                )
        return cleaned_data
