import csv
import io
import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Sum, F, Q, ExpressionWrapper, DecimalField
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.utils import timezone

from inventory.models import (
    Product, Stock, Joint, Category, Brand,
    StockTake, StockTakeItem, StockMovement, StockAlert,
)


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _manager_required(request):
    if not request.user.is_manager_role:
        messages.error(request, 'Managers and above only.')
        return True
    return False


def _json_error(msg, status=400):
    return JsonResponse({'ok': False, 'error': msg}, status=status)


# ─── INVENTORY DASHBOARD ─────────────────────────────────────────────────────

@login_required
def inventory_dashboard(request):
    qs = Product.objects.select_related(
        'stock', 'joint', 'category', 'brand'
    ).filter(is_active=True)

    # --- Filters ---
    joint_id  = request.GET.get('joint', '')
    cat_id    = request.GET.get('category', '')
    brand_id  = request.GET.get('brand', '')
    q         = request.GET.get('q', '').strip()
    stock_f   = request.GET.get('stock', '')
    sort      = request.GET.get('sort', 'name')

    if joint_id:
        qs = qs.filter(joint_id=joint_id)
    if cat_id:
        qs = qs.filter(category_id=cat_id)
    if brand_id:
        qs = qs.filter(brand_id=brand_id)
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(barcode__icontains=q))
    if stock_f == 'out':
        qs = qs.filter(stock__quantity=0)
    elif stock_f == 'low':
        qs = qs.filter(stock__quantity__gt=0, stock__quantity__lte=F('stock__min_quantity'))
    elif stock_f == 'ok':
        qs = qs.filter(stock__quantity__gt=F('stock__min_quantity'))

    # Sort
    sort_map = {
        'name':  'name',
        'stock': 'stock__quantity',
        'price': '-price',
        'value': '-stock__quantity',  # approximation without annotation
    }
    qs = qs.order_by(sort_map.get(sort, 'name'))

    # KPIs (un-filtered for global counts)
    total_products  = Product.objects.filter(is_active=True).count()
    active_products = total_products
    low_stock_count = Stock.objects.filter(
        quantity__gt=0, quantity__lte=F('min_quantity'), product__is_active=True
    ).count()
    out_of_stock = Stock.objects.filter(quantity=0, product__is_active=True).count()
    total_value = Stock.objects.filter(product__is_active=True).aggregate(
        v=Sum(ExpressionWrapper(F('quantity') * F('product__price'), output_field=DecimalField()))
    )['v'] or Decimal('0')

    # Pending transfers
    try:
        from inventory.models import StockTransfer
        pending_transfers = StockTransfer.objects.filter(status='pending').count()
    except Exception:
        pending_transfers = 0

    # Build page items with line value
    items = []
    for p in qs:
        stock = getattr(p, 'stock', None)
        qty   = stock.quantity if stock else 0
        items.append({
            'product':    p,
            'stock':      stock,
            'line_value': qty * p.price,
        })

    paginator  = Paginator(items, 40)
    page_obj   = paginator.get_page(request.GET.get('page', 1))
    joint_obj  = Joint.objects.filter(pk=joint_id).first() if joint_id else None

    return render(request, 'inventory/inventory_dashboard.html', {
        'page_obj':         page_obj,
        'joints':           Joint.objects.all(),
        'categories':       Category.objects.order_by('name'),
        'brands':           Brand.objects.order_by('name'),
        'total_products':   total_products,
        'active_products':  active_products,
        'low_stock_count':  low_stock_count,
        'out_of_stock':     out_of_stock,
        'total_value':      total_value,
        'pending_transfers':pending_transfers,
        'sort':             sort,
        'joint':            joint_obj,
        'request':          request,
    })


# ─── STOCK TAKE WIZARD ───────────────────────────────────────────────────────

@login_required
def stock_take_wizard(request):
    if _manager_required(request):
        return redirect('inventory:inventory_dashboard')
    return render(request, 'inventory/stock_take_wizard.html', {
        'joints':     Joint.objects.all(),
        'categories': Category.objects.order_by('name'),
    })


@login_required
def stock_take_list(request):
    """List of completed/in-progress stock takes."""
    takes = StockTake.objects.select_related('joint', 'conducted_by').order_by('-created_at')
    if not request.user.is_admin_role:
        if hasattr(request.user, 'primary_joint') and request.user.primary_joint:
            takes = takes.filter(joint=request.user.primary_joint)
    return render(request, 'inventory/stock_take_list.html', {'takes': takes})


# ─── JSON APIs ────────────────────────────────────────────────────────────────

@login_required
def api_products_for_count(request):
    """Returns all active products for a joint (+ optional category) with system qty."""
    joint_id = request.GET.get('joint', '')
    cat_id   = request.GET.get('category', '')
    if not joint_id:
        return _json_error('joint_id required')

    qs = Product.objects.select_related('stock', 'category').filter(
        is_active=True, joint_id=joint_id
    )
    if cat_id:
        qs = qs.filter(category_id=cat_id)
    qs = qs.order_by('category__name', 'name')

    products = []
    for p in qs:
        stock = getattr(p, 'stock', None)
        products.append({
            'id':         p.pk,
            'name':       p.name,
            'sku':        p.code or '',
            'price':      str(p.price),
            'system_qty': stock.quantity if stock else 0,
        })
    return JsonResponse({'products': products})


@login_required
@require_POST
def api_stock_take_submit(request):
    """Apply a stock take — create StockTake + StockTakeItem records + adjust stock."""
    if not request.user.is_manager_role:
        return _json_error('forbidden', 403)
    try:
        data     = json.loads(request.body)
        joint_id = data['joint_id']
        notes    = data.get('notes', '')
        counts   = data.get('counts', [])  # [{product_id, counted_qty}]
    except (KeyError, json.JSONDecodeError):
        return _json_error('Invalid payload')

    joint = get_object_or_404(Joint, pk=joint_id)

    with transaction.atomic():
        take = StockTake.objects.create(
            joint        = joint,
            conducted_by = request.user,
            notes        = notes,
            status       = 'completed',
            completed_at = timezone.now(),
        )
        for entry in counts:
            pid        = entry['product_id']
            counted_qty = int(entry['counted_qty'])
            try:
                product = Product.objects.get(pk=pid, joint=joint)
                stock   = Stock.objects.select_for_update().get(product=product)
            except (Product.DoesNotExist, Stock.DoesNotExist):
                continue

            system_qty  = stock.quantity
            variance    = counted_qty - system_qty

            StockTakeItem.objects.create(
                stock_take    = take,
                product       = product,
                system_qty    = system_qty,
                counted_qty   = counted_qty,
                variance      = variance,
            )

            if variance != 0:
                stock.quantity = counted_qty
                stock.save(update_fields=['quantity'])

                # Log movement
                StockMovement.objects.create(
                    product    = product,
                    joint      = joint,
                    qty_before = system_qty,
                    qty_after  = counted_qty,
                    delta      = variance,
                    reason     = 'stock_take',
                    reference  = f'ST-{take.pk}',
                    performed_by = request.user,
                )

    return JsonResponse({'ok': True, 'stock_take_id': take.pk})


@login_required
@require_POST
def api_stock_adjust(request):
    """Quick inline stock adjustment (±1 or custom)."""
    if not request.user.is_manager_role:
        return _json_error('forbidden', 403)
    try:
        data       = json.loads(request.body)
        product_id = data['product_id']
        delta      = int(data['delta'])
        reason     = data.get('reason', 'recount')
        note       = data.get('note', '')
    except (KeyError, ValueError, json.JSONDecodeError):
        return _json_error('Invalid payload')

    try:
        with transaction.atomic():
            product = Product.objects.get(pk=product_id)
            stock   = Stock.objects.select_for_update().get(product=product)
            old_qty = stock.quantity
            new_qty = max(0, old_qty + delta)
            stock.quantity = new_qty
            stock.save(update_fields=['quantity'])

            StockMovement.objects.create(
                product      = product,
                joint        = product.joint,
                qty_before   = old_qty,
                qty_after    = new_qty,
                delta        = delta,
                reason       = reason,
                reference    = note[:100] if note else '',
                performed_by = request.user,
            )
    except (Product.DoesNotExist, Stock.DoesNotExist):
        return _json_error('Product not found', 404)

    return JsonResponse({
        'ok':      True,
        'new_qty': new_qty,
        'min_qty': stock.min_quantity,
    })


@login_required
@require_POST
def api_bulk_action(request):
    """Bulk operations on multiple products."""
    if not request.user.is_manager_role:
        return _json_error('forbidden', 403)
    try:
        data        = json.loads(request.body)
        action      = data['action']
        product_ids = [int(x) for x in data.get('product_ids', [])]
    except (KeyError, ValueError, json.JSONDecodeError):
        return _json_error('Invalid payload')

    if not product_ids:
        return _json_error('No products selected')

    products = Product.objects.filter(pk__in=product_ids)

    with transaction.atomic():
        if action == 'price_adjust':
            adj_type = data.get('adj_type', 'pct_inc')
            adj_val  = Decimal(str(data.get('adj_val', 0)))
            for p in products:
                if adj_type == 'pct_inc':
                    p.price = p.price * (1 + adj_val / 100)
                elif adj_type == 'pct_dec':
                    p.price = p.price * (1 - adj_val / 100)
                elif adj_type == 'fixed_inc':
                    p.price = p.price + adj_val
                elif adj_type == 'fixed_dec':
                    p.price = max(Decimal('0'), p.price - adj_val)
                p.price = p.price.quantize(Decimal('0.01'))
                p.save(update_fields=['price'])
            msg = f'Price updated for {len(product_ids)} products'

        elif action == 'restock':
            qty = int(data.get('qty', 0))
            if qty <= 0:
                return _json_error('Quantity must be > 0')
            for p in products:
                stock = Stock.objects.select_for_update().get_or_create(product=p)[0]
                old = stock.quantity
                stock.quantity += qty
                stock.save(update_fields=['quantity'])
                StockMovement.objects.create(
                    product=p, joint=p.joint,
                    qty_before=old, qty_after=stock.quantity, delta=qty,
                    reason='bulk_restock', performed_by=request.user,
                )
            msg = f'Added {qty} units to {len(product_ids)} products'

        elif action == 'transfer':
            dest_joint_id = data.get('dest_joint')
            dest_joint    = get_object_or_404(Joint, pk=dest_joint_id)
            for p in products:
                p.joint = dest_joint
                p.save(update_fields=['joint'])
            msg = f'Transferred {len(product_ids)} products to {dest_joint.display_name}'

        elif action == 'deactivate':
            products.update(is_active=False)
            msg = f'Deactivated {len(product_ids)} products'

        else:
            return _json_error(f'Unknown action: {action}')

    return JsonResponse({'ok': True, 'message': msg})


# ─── CSV EXPORT ───────────────────────────────────────────────────────────────

@login_required
def export_csv(request):
    if _manager_required(request):
        return redirect('inventory:inventory_dashboard')

    joint_id  = request.GET.get('joint', '')
    response  = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="genx-inventory.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Product', 'Code', 'Barcode', 'Joint', 'Category', 'Brand',
        'Price', 'Sale Price', 'Stock Qty', 'Min Qty', 'Stock Value',
        'Active', 'Is Clearance',
    ])

    qs = Product.objects.select_related(
        'stock', 'joint', 'category', 'brand'
    ).filter(is_active=True).order_by('joint__name', 'name')
    if joint_id:
        qs = qs.filter(joint_id=joint_id)

    for p in qs:
        stock = getattr(p, 'stock', None)
        qty   = stock.quantity if stock else 0
        writer.writerow([
            p.name, p.code or '', p.barcode or '',
            p.joint.display_name,
            p.category.name if p.category else '',
            p.brand.name if p.brand else '',
            f'{p.price:.2f}',
            f'{p.sale_price:.2f}' if p.sale_price else '',
            qty,
            stock.min_quantity if stock else 0,
            f'{qty * p.price:.2f}',
            'Yes' if p.is_active else 'No',
            'Yes' if p.is_clearance else 'No',
        ])
    return response


# ─── BULK IMPORT ─────────────────────────────────────────────────────────────

@login_required
def bulk_import(request):
    if _manager_required(request):
        return redirect('inventory:inventory_dashboard')

    if request.method == 'POST':
        f        = request.FILES.get('csv_file')
        joint_id = request.POST.get('joint')
        if not f or not joint_id:
            messages.error(request, 'CSV file and joint are required.')
            return redirect('inventory:bulk_import')

        joint    = get_object_or_404(Joint, pk=joint_id)
        created  = 0
        updated  = 0
        errors   = []

        try:
            text    = f.read().decode('utf-8')
            reader  = csv.DictReader(io.StringIO(text))
            required = {'name', 'price'}
            if not required.issubset(set(reader.fieldnames or [])):
                messages.error(request, 'CSV must have at least "name" and "price" columns.')
                return redirect('inventory:bulk_import')

            with transaction.atomic():
                for i, row in enumerate(reader, 2):
                    name  = row.get('name', '').strip()
                    price = row.get('price', '0').replace('$','').strip()
                    if not name:
                        errors.append(f'Row {i}: Missing name')
                        continue
                    try:
                        price = Decimal(price)
                    except Exception:
                        errors.append(f'Row {i}: Invalid price "{row.get("price")}"')
                        continue

                    # Category
                    cat = None
                    if row.get('category'):
                        cat, _ = Category.objects.get_or_create(name=row['category'].strip())

                    # Brand
                    brand = None
                    if row.get('brand'):
                        brand, _ = Brand.objects.get_or_create(name=row['brand'].strip())

                    # Upsert by code or name+joint
                    code   = row.get('code', '').strip() or None
                    lookup = Q(joint=joint, name=name) if not code else Q(joint=joint, code=code)

                    p, is_new = Product.objects.get_or_create(
                        **({'joint': joint, 'code': code} if code else {'joint': joint, 'name': name}),
                        defaults={
                            'name':     name,
                            'price':    price,
                            'category': cat,
                            'brand':    brand,
                            'barcode':  row.get('barcode', '').strip() or None,
                        }
                    )
                    if not is_new:
                        p.price    = price
                        p.category = cat or p.category
                        p.brand    = brand or p.brand
                        p.save(update_fields=['price','category','brand'])
                        updated += 1
                    else:
                        created += 1

                    # Stock
                    qty     = int(row.get('stock_qty', 0) or 0)
                    min_qty = int(row.get('min_qty', 0) or 0)
                    Stock.objects.update_or_create(
                        product=p, defaults={'quantity': qty, 'min_quantity': min_qty}
                    )

        except Exception as e:
            messages.error(request, f'Import failed: {e}')
            return redirect('inventory:bulk_import')

        msg = f'Import complete: {created} created, {updated} updated.'
        if errors:
            msg += f' {len(errors)} row error(s): ' + '; '.join(errors[:3])
        messages.success(request, msg)
        return redirect('inventory:inventory_dashboard')

    return render(request, 'inventory/bulk_import.html', {
        'joints':      Joint.objects.all(),
        'csv_columns': ['name*', 'price*', 'code', 'barcode', 'category', 'brand', 'stock_qty', 'min_qty'],
    })