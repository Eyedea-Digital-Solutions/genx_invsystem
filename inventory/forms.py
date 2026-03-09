from django import forms
from .models import Product, Stock, StockTake, StockTakeItem, StockTransfer, Joint, Category, Brand, Supplier


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'joint', 'code', 'barcode', 'name', 'price',
            'sale_price', 'sale_start', 'sale_end',
            'is_clearance', 'clearance_price',
            'category', 'brand', 'image', 'is_active'
        ]
        widgets = {
            'joint': forms.Select(attrs={'class': 'form-select'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. EYE-001'}),
            'barcode': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'EAN-13 / Code-128'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Product name'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'sale_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'sale_start': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'sale_end': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_clearance': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'clearance_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'brand': forms.Select(attrs={'class': 'form-select'}),
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        joint = cleaned_data.get('joint')
        code = cleaned_data.get('code')
        if joint and joint.uses_product_codes and not code:
            self.add_error('code', 'This joint requires a product code.')
        return cleaned_data


class StockAdjustForm(forms.Form):
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


class StockDetailForm(forms.ModelForm):
    class Meta:
        model = Stock
        fields = ['min_quantity', 'reorder_level', 'supplier', 'batch_number', 'expiry_date']
        widgets = {
            'min_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'reorder_level': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'batch_number': forms.TextInput(attrs={'class': 'form-control'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class StockTakeForm(forms.ModelForm):
    class Meta:
        model = StockTake
        fields = ['joint', 'notes']
        widgets = {
            'joint': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class StockTransferForm(forms.ModelForm):
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

        if product and from_joint and product.joint != from_joint:
            raise forms.ValidationError(
                f"'{product.name}' belongs to {product.joint.display_name}, "
                f"not {from_joint.display_name}."
            )

        if product and quantity:
            if product.current_stock < quantity:
                raise forms.ValidationError(
                    f"Not enough stock. Available: {product.current_stock}, Requested: {quantity}"
                )
        return cleaned_data


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['joint', 'name', 'icon', 'color', 'sort_order']
        widgets = {
            'joint': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'icon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'bi-tag'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'sort_order': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'contact_person', 'phone', 'email', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
