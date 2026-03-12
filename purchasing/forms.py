from django import forms
from django.forms import inlineformset_factory
from .models import PurchaseOrder, PurchaseOrderItem, GoodsReceivedNote, GRNItem


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model  = PurchaseOrder
        fields = ['supplier', 'joint', 'order_date', 'expected_delivery', 'notes']
        widgets = {
            'supplier':          forms.Select(attrs={'class': 'form-select'}),
            'joint':             forms.Select(attrs={'class': 'form-select'}),
            'order_date':        forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'expected_delivery': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes':             forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class PurchaseOrderItemForm(forms.ModelForm):
    class Meta:
        model  = PurchaseOrderItem
        fields = ['product', 'quantity_ordered', 'unit_cost']
        widgets = {
            'product':          forms.Select(attrs={'class': 'form-select po-product-select'}),
            'quantity_ordered':  forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'unit_cost':         forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }


# Inline formset for PO items (used in the create/edit view)
POItemFormSet = inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderItem,
    form=PurchaseOrderItemForm,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class GoodsReceivedNoteForm(forms.ModelForm):
    class Meta:
        model  = GoodsReceivedNote
        fields = ['received_date', 'supplier_reference', 'notes']
        widgets = {
            'received_date':      forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'supplier_reference': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Supplier invoice / delivery note #'}),
            'notes':              forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class GRNItemForm(forms.ModelForm):
    class Meta:
        model  = GRNItem
        fields = ['po_item', 'quantity_received', 'unit_cost']
        widgets = {
            'po_item':           forms.HiddenInput(),
            'quantity_received': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'unit_cost':         forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }


# Inline formset for GRN items
GRNItemFormSet = inlineformset_factory(
    GoodsReceivedNote,
    GRNItem,
    form=GRNItemForm,
    extra=0,
    can_delete=False,
)


class POFilterForm(forms.Form):
    from inventory.models import Supplier, Joint
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.all(),
        required=False,
        empty_label='All Suppliers',
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'style': 'width:180px;'}),
    )
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Statuses')] + PurchaseOrder.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm', 'style': 'width:160px;'}),
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date', 'style': 'width:140px;'}),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date', 'style': 'width:140px;'}),
    )