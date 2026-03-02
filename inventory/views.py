from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.conf import settings
from django.http import JsonResponse

from .models import Joint, Product, Stock, StockTake, StockTakeItem, StockTransfer
from .forms import ProductForm, StockAdjustForm, StockTakeForm, StockTransferForm


@login_required
def inventory_dashboard(request):
    """
    Shows an overview of all stock across all joints.
    Highlights low stock items.
    """
    joints = Joint.objects.prefetch_related('products__stock').all()

    low_stock_items = Product.objects.select_related('stock', 'joint').filter(
        is_active=True,
        stock__quantity__lte=settings.LOW_STOCK_THRESHOLD
    )

    context = {
        'joints': joints,
        'low_stock_items': low_stock_items,
        'low_stock_threshold': settings.LOW_STOCK_THRESHOLD,
    }
    return render(request, 'stock_overview.html', context)


@login_required
def product_list(request):
    """Lists all products. Can be filtered by joint."""
    joint_id = request.GET.get('joint')
    products = Product.objects.select_related('joint', 'stock').filter(is_active=True)

    if joint_id:
        products = products.filter(joint_id=joint_id)

    joints = Joint.objects.all()
    context = {
        'products': products,
        'joints': joints,
        'selected_joint': joint_id,
    }
    return render(request, 'product_list.html', context)


@login_required
def product_create(request):
    """Add a new product to the inventory."""
    if not request.user.is_manager_role:
        messages.error(request, "Only managers and admins can add products.")
        return redirect('inventory:product_list')

    form = ProductForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            product = form.save()
            Stock.objects.create(product=product, quantity=0)
        messages.success(request, f"Product '{product.name}' added successfully!")
        return redirect('inventory:product_list')

    return render(request, 'product_form.html', {'form': form, 'title': 'Add Product'})


@login_required
def product_edit(request, pk):
    """Edit an existing product."""
    if not request.user.is_manager_role:
        messages.error(request, "Only managers and admins can edit products.")
        return redirect('inventory:product_list')

    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f"Product '{product.name}' updated!")
        return redirect('inventory:product_list')

    return render(request, 'product_form.html', {'form': form, 'title': 'Edit Product', 'product': product})


@login_required
def stock_adjust(request, pk):
    """
    Add stock to a product (e.g. when new stock arrives).
    This is NOT a stock take — just adding units to the current count.
    """
    if not request.user.is_manager_role:
        messages.error(request, "Only managers and admins can adjust stock.")
        return redirect('inventory:product_list')

    product = get_object_or_404(Product, pk=pk)
    form = StockAdjustForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        qty = form.cleaned_data['quantity']
        product.stock.add(qty)
        messages.success(request, f"Added {qty} units to '{product.name}'. New total: {product.stock.quantity}")
        return redirect('inventory:product_list')

    return render(request, 'stock_adjust.html', {'form': form, 'product': product})


@login_required
def stock_take_list(request):
    """List all stock takes."""
    stock_takes = StockTake.objects.select_related('joint', 'conducted_by').order_by('-conducted_at')
    return render(request, 'stock_take_list.html', {'stock_takes': stock_takes})


@login_required
def stock_take_create(request):
    """
    Start a new stock take for a joint.
    """
    if not request.user.is_manager_role:
        messages.error(request, "Only managers and admins can conduct stock takes.")
        return redirect('inventory:stock_take_list')

    if request.method == 'POST':
        form = StockTakeForm(request.POST)
        if form.is_valid():
            joint = form.cleaned_data['joint']
            products = Product.objects.select_related('stock').filter(joint=joint, is_active=True)

            with transaction.atomic():
                stock_take = form.save(commit=False)
                stock_take.conducted_by = request.user
                stock_take.save()

                for product in products:
                    actual_key = f'actual_{product.pk}'
                    actual_count = int(request.POST.get(actual_key, 0))
                    system_count = product.current_stock

                    StockTakeItem.objects.create(
                        stock_take=stock_take,
                        product=product,
                        system_count=system_count,
                        actual_count=actual_count
                    )

                    product.stock.quantity = actual_count
                    product.stock.save()

            messages.success(request, f"Stock take for {joint.display_name} completed successfully!")
            return redirect('inventory:stock_take_list')
    else:
        joint_id = request.GET.get('joint')
        initial = {'joint': joint_id} if joint_id else {}
        form = StockTakeForm(initial=initial)

    joint_id = request.GET.get('joint')
    products = []
    if joint_id:
        products = Product.objects.select_related('stock').filter(joint_id=joint_id, is_active=True)

    return render(request, 'stock_take_form.html', {
        'form': form,
        'products': products,
    })


@login_required
def stock_take_detail(request, pk):
    """View the details of a completed stock take."""
    stock_take = get_object_or_404(StockTake.objects.select_related('joint', 'conducted_by'), pk=pk)
    items = stock_take.items.select_related('product').all()
    return render(request, 'stock_take_detail.html', {'stock_take': stock_take, 'items': items})


@login_required
def transfer_create(request):
    """Transfer stock from one joint to another."""
    if not request.user.is_manager_role:
        messages.error(request, "Only managers and admins can transfer stock.")
        return redirect('inventory:inventory_dashboard')

    form = StockTransferForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        source_product = form.cleaned_data['product']
        to_joint = form.cleaned_data['to_joint']
        quantity = form.cleaned_data['quantity']

        # ✅ FIX: Find the matching product at the destination joint so we can
        # add the transferred quantity there. Previously stock was only deducted
        # from the source — it simply disappeared.
        dest_product = None
        if source_product.code:
            dest_product = Product.objects.filter(
                joint=to_joint, code=source_product.code
            ).select_related('stock').first()
        if not dest_product:
            dest_product = Product.objects.filter(
                joint=to_joint, name=source_product.name
            ).select_related('stock').first()

        if not dest_product:
            messages.error(
                request,
                f"No matching product for '{source_product.name}' found at "
                f"{to_joint.display_name}. Add the product there first, then retry the transfer."
            )
            return render(request, 'transfer_form.html', {'form': form})

        with transaction.atomic():
            transfer = form.save(commit=False)
            transfer.transferred_by = request.user
            transfer.status = 'completed'
            transfer.save()

            # Deduct from source joint
            source_product.stock.deduct(quantity)
            # ✅ FIX: Add to destination joint (was completely missing before)
            dest_product.stock.add(quantity)

        messages.success(
            request,
            f"Transferred {quantity}× {source_product.name} "
            f"from {transfer.from_joint.display_name} to {to_joint.display_name}."
        )
        return redirect('inventory:inventory_dashboard')

    return render(request, 'transfer_form.html', {'form': form})


@login_required
def get_products_by_joint(request):
    """AJAX endpoint: returns products for a selected joint (used in sale form)."""
    joint_id = request.GET.get('joint_id')
    if joint_id:
        products = Product.objects.select_related('stock').filter(
            joint_id=joint_id,
            is_active=True,
            stock__quantity__gt=0
        ).values('id', 'name', 'code', 'price', 'stock__quantity')
        return JsonResponse({'products': list(products)})
    return JsonResponse({'products': []})