from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.conf import settings
from django.http import JsonResponse

from .models import Joint, Product, Stock, StockTake, StockTakeItem, StockTransfer, Category, Supplier
from .forms import ProductForm, StockAdjustForm, StockTakeForm, StockTransferForm, CategoryForm, SupplierForm, StockDetailForm


@login_required
def inventory_dashboard(request):
    joints = Joint.objects.prefetch_related('products__stock').all()

    low_stock_items = Product.objects.select_related('stock', 'joint').filter(
        is_active=True,
        stock__quantity__lte=settings.LOW_STOCK_THRESHOLD
    )

    from django.utils import timezone
    import datetime
    expiry_threshold = timezone.now().date() + datetime.timedelta(days=30)
    expiring_items = Product.objects.select_related('stock', 'joint').filter(
        is_active=True,
        stock__expiry_date__isnull=False,
        stock__expiry_date__lte=expiry_threshold,
    )

    clearance_items = Product.objects.select_related('joint').filter(
        is_active=True, is_clearance=True
    )

    context = {
        'joints': joints,
        'low_stock_items': low_stock_items,
        'expiring_items': expiring_items,
        'clearance_items': clearance_items,
        'low_stock_threshold': settings.LOW_STOCK_THRESHOLD,
    }
    return render(request, 'stock_overview.html', context)


@login_required
def product_list(request):
    joint_id = request.GET.get('joint')
    search = request.GET.get('q', '').strip()
    filter_type = request.GET.get('filter', 'all')

    products = Product.objects.select_related('joint', 'stock', 'category', 'brand').filter(is_active=True)

    if joint_id:
        products = products.filter(joint_id=joint_id)
    if search:
        from django.db.models import Q
        products = products.filter(
            Q(name__icontains=search) | Q(code__icontains=search) | Q(barcode__icontains=search)
        )
    if filter_type == 'clearance':
        products = products.filter(is_clearance=True)
    elif filter_type == 'sale':
        products = products.filter(sale_price__isnull=False)
    elif filter_type == 'low_stock':
        products = products.filter(stock__quantity__lte=settings.LOW_STOCK_THRESHOLD)

    joints = Joint.objects.all()
    context = {
        'products': products,
        'joints': joints,
        'selected_joint': joint_id,
        'search': search,
        'filter_type': filter_type,
    }
    return render(request, 'product_list.html', context)


@login_required
def product_create(request):
    if not request.user.is_manager_role:
        messages.error(request, "Only managers and admins can add products.")
        return redirect('inventory:product_list')

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                product = form.save()
                Stock.objects.create(product=product, quantity=0)
            messages.success(request, f"Product '{product.name}' added successfully!")
            return redirect('inventory:product_list')
    else:
        form = ProductForm()

    return render(request, 'product_form.html', {'form': form, 'title': 'Add Product'})


@login_required
def product_edit(request, pk):
    if not request.user.is_manager_role:
        messages.error(request, "Only managers and admins can edit products.")
        return redirect('inventory:product_list')

    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f"Product '{product.name}' updated!")
            return redirect('inventory:product_list')
    else:
        form = ProductForm(instance=product)

    return render(request, 'product_form.html', {'form': form, 'title': 'Edit Product', 'product': product})


@login_required
def stock_adjust(request, pk):
    if not request.user.is_manager_role:
        messages.error(request, "Only managers and admins can adjust stock.")
        return redirect('inventory:product_list')

    product = get_object_or_404(Product, pk=pk)
    form = StockAdjustForm(request.POST or None)
    stock_form = StockDetailForm(request.POST or None, instance=product.stock if hasattr(product, 'stock') else None)

    if request.method == 'POST' and form.is_valid():
        qty = form.cleaned_data['quantity']
        product.stock.add(qty)
        if stock_form.is_valid():
            stock_form.save()
        messages.success(request, f"Added {qty} units to '{product.name}'. New total: {product.stock.quantity}")
        return redirect('inventory:product_list')

    return render(request, 'stock_adjust.html', {
        'form': form, 'stock_form': stock_form, 'product': product
    })


@login_required
def stock_take_list(request):
    stock_takes = StockTake.objects.select_related('joint', 'conducted_by').order_by('-conducted_at')
    return render(request, 'stock_take_list.html', {'stock_takes': stock_takes})


@login_required
def stock_take_create(request):
    if not request.user.is_manager_role:
        messages.error(request, "Only managers and admins can conduct stock takes.")
        return redirect('inventory:stock_take_list')

    if request.method == 'POST':
        form = StockTakeForm(request.POST)
        if form.is_valid():
            joint    = form.cleaned_data['joint']
            products = Product.objects.select_related('stock').filter(
                joint=joint, is_active=True
            )

            with transaction.atomic():
                stock_take              = form.save(commit=False)
                stock_take.conducted_by = request.user
                stock_take.save()

                items_added = 0
                for product in products:
                    add_qty      = max(0, int(request.POST.get(f'add_{product.pk}', 0) or 0))
                    system_count = product.current_stock
                    new_count    = system_count + add_qty

                    StockTakeItem.objects.create(
                        stock_take   = stock_take,
                        product      = product,
                        system_count = system_count,
                        actual_count = new_count,
                    )

                    if add_qty > 0:
                        product.stock.quantity = new_count
                        product.stock.save()
                        items_added += 1

            messages.success(
                request,
                f"Stock take for {joint.display_name} completed — "
                f"{items_added} product{'s' if items_added != 1 else ''} restocked."
            )
            return redirect('inventory:stock_take_list')

    else:
        form = StockTakeForm()

    joint_id = request.GET.get('joint', '')
    products = []
    if joint_id:
        products = Product.objects.select_related('stock').filter(
            joint_id=joint_id, is_active=True
        ).order_by('name')
        form.initial['joint'] = joint_id

    return render(request, 'stock_take_form.html', {
        'form':     form,
        'products': products,
    })


@login_required
def stock_take_detail(request, pk):
    stock_take = get_object_or_404(
        StockTake.objects.select_related('joint', 'conducted_by'), pk=pk
    )
    items = stock_take.items.select_related('product').all()
    return render(request, 'stock_take_detail.html', {'stock_take': stock_take, 'items': items})


@login_required
def transfer_create(request):
    if not request.user.is_manager_role:
        messages.error(request, "Only managers and admins can transfer stock.")
        return redirect('inventory:inventory_dashboard')

    form = StockTransferForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        source_product = form.cleaned_data['product']
        to_joint = form.cleaned_data['to_joint']
        quantity = form.cleaned_data['quantity']

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
                f"{to_joint.display_name}. Add the product there first."
            )
            return render(request, 'transfer_form.html', {'form': form})

        with transaction.atomic():
            transfer = form.save(commit=False)
            transfer.transferred_by = request.user
            transfer.status = 'completed'
            transfer.save()
            source_product.stock.deduct(quantity)
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
    joint_id = request.GET.get('joint_id')
    if joint_id:
        products = Product.objects.select_related('stock').filter(
            joint_id=joint_id, is_active=True
        ).values('id', 'name', 'code', 'price', 'stock__quantity', 'barcode', 'is_clearance', 'image')

        result = []
        for p in products:
            image_url = None
            if p['image']:
                image_url = request.build_absolute_uri(settings.MEDIA_URL + p['image'])
            p['image_url'] = image_url
            del p['image']
            result.append(p)

        return JsonResponse({'products': result})
    return JsonResponse({'products': []})


@login_required
def category_list(request):
    if not request.user.is_manager_role:
        messages.error(request, "Managers and above only.")
        return redirect('inventory:inventory_dashboard')
    categories = Category.objects.select_related('joint').all()
    return render(request, 'category_list.html', {'categories': categories})


@login_required
def category_create(request):
    if not request.user.is_manager_role:
        messages.error(request, "Managers and above only.")
        return redirect('inventory:inventory_dashboard')
    form = CategoryForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Category created.")
        return redirect('inventory:category_list')
    return render(request, 'category_form.html', {'form': form, 'title': 'Add Category'})


@login_required
def supplier_list(request):
    if not request.user.is_manager_role:
        messages.error(request, "Managers and above only.")
        return redirect('inventory:inventory_dashboard')
    suppliers = Supplier.objects.all()
    return render(request, 'supplier_list.html', {'suppliers': suppliers})


@login_required
def supplier_create(request):
    if not request.user.is_manager_role:
        messages.error(request, "Managers and above only.")
        return redirect('inventory:inventory_dashboard')
    form = SupplierForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Supplier created.")
        return redirect('inventory:supplier_list')
    return render(request, 'supplier_form.html', {'form': form, 'title': 'Add Supplier'})