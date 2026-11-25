from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.users.decorators import editor_required, viewer_required, lender_or_above
from django.db.models import Q, Sum, F
from django.http import HttpResponse
import barcode
import qrcode
import base64
from io import BytesIO
import csv
from datetime import datetime
from .models import Item, Category, ItemImage, LabelTemplate
from .forms import ItemForm, ItemImageForm, CategoryForm
import pandas as pd
from reportlab.lib.units import mm
from reportlab.lib import colors


@login_required
def category_list(request):
    """List all categories with hierarchy"""
    categories = Category.objects.all()
    return render(request, 'items/category_list.html', {
        'categories': categories
    })


@login_required
@editor_required
def category_create(request):
    """Create a new category"""
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category created successfully.')
            return redirect('items:category_list')
    else:
        form = CategoryForm()
    
    return render(request, 'items/category_form.html', {
        'form': form,
        'action': 'Create Category'
    })


@login_required
@editor_required
def category_update(request, pk):
    """Update an existing category"""
    category = get_object_or_404(Category, pk=pk)
    
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated successfully.')
            return redirect('items:category_list')
    else:
        form = CategoryForm(instance=category)
    
    return render(request, 'items/category_form.html', {
        'form': form,
        'category': category,
        'action': 'Update Category'
    })


@login_required
@editor_required
def category_delete(request, pk):
    """Delete a category"""
    category = get_object_or_404(Category, pk=pk)
    
    if request.method == 'POST':
        # Check if category has items
        if category.item_set.exists():
            messages.error(request, 'Cannot delete category that has items. Please reassign items first.')
            return redirect('items:category_list')
        
        category.delete()
        messages.success(request, 'Category deleted successfully.')
        return redirect('items:category_list')
    
    return render(request, 'items/category_confirm_delete.html', {'category': category})


@login_required
def label_template_list(request):
    """List all label templates"""
    templates = LabelTemplate.objects.filter(created_by=request.user)
    return render(request, 'items/label_template_list.html', {'templates': templates})


@login_required
def label_template_create(request):
    """Create a new label template"""
    if request.method == 'POST':
        form = CategoryForm(request.POST)  # Will create LabelTemplateForm
        # For now, create manually
        template = LabelTemplate.objects.create(
            name=request.POST.get('name'),
            label_size=request.POST.get('label_size', '50x30'),
            width_mm=int(request.POST.get('width_mm', 50)),
            height_mm=int(request.POST.get('height_mm', 30)),
            include_name=request.POST.get('include_name') == 'on',
            include_barcode=request.POST.get('include_barcode') == 'on',
            include_qr_code=request.POST.get('include_qr_code') == 'on',
            include_location=request.POST.get('include_location') == 'on',
            include_description=request.POST.get('include_description') == 'on',
            font_size=int(request.POST.get('font_size', 12)),
            created_by=request.user
        )
        messages.success(request, 'Label template created successfully.')
        return redirect('items:label_template_list')
    
    return render(request, 'items/label_template_form.html', {'action': 'Create'})


@login_required
def label_template_update(request, pk):
    """Update a label template"""
    template = get_object_or_404(LabelTemplate, pk=pk, created_by=request.user)
    
    if request.method == 'POST':
        template.name = request.POST.get('name')
        template.label_size = request.POST.get('label_size', '50x30')
        template.width_mm = int(request.POST.get('width_mm', 50))
        template.height_mm = int(request.POST.get('height_mm', 30))
        template.include_name = request.POST.get('include_name') == 'on'
        template.include_barcode = request.POST.get('include_barcode') == 'on'
        template.include_qr_code = request.POST.get('include_qr_code') == 'on'
        template.include_location = request.POST.get('include_location') == 'on'
        template.include_description = request.POST.get('include_description') == 'on'
        template.font_size = int(request.POST.get('font_size', 12))
        template.save()
        messages.success(request, 'Label template updated successfully.')
        return redirect('items:label_template_list')
    
    return render(request, 'items/label_template_form.html', {'template': template, 'action': 'Update'})


@login_required
def label_template_delete(request, pk):
    """Delete a label template"""
    template = get_object_or_404(LabelTemplate, pk=pk, created_by=request.user)
    
    if request.method == 'POST':
        template.delete()
        messages.success(request, 'Label template deleted successfully.')
        return redirect('items:label_template_list')
    
    return render(request, 'items/label_template_confirm_delete.html', {'template': template})


@login_required
@editor_required
def import_items(request):
    """Import items from CSV or Excel file"""
    if request.method == 'POST':
        file = request.FILES.get('file')
        if not file:
            messages.error(request, 'Please select a file to import.')
            return redirect('items:item_list')
        
        try:
            # Read file based on extension
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            elif file.name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file)
            else:
                messages.error(request, 'Unsupported file format. Please use CSV or Excel.')
                return redirect('items:item_list')
            
            # Process the data
            imported_count = 0
            errors = []
            
            for index, row in df.iterrows():
                try:
                    # Get or create category
                    category_name = row.get('category', 'Other')
                    category, _ = Category.objects.get_or_create(name=category_name)
                    
                    # Get or create location
                    location_name = row.get('location')
                    location = None
                    if location_name and pd.notna(location_name):
                        from apps.locations.models import Location
                        location, _ = Location.objects.get_or_create(name=location_name)
                    
                    # Create item
                    item = Item.objects.create(
                        name=row.get('name', ''),
                        description=row.get('description', ''),
                        quantity=int(row.get('quantity', 1)) if pd.notna(row.get('quantity')) else 1,
                        min_quantity=int(row.get('min_quantity', 1)) if pd.notna(row.get('min_quantity')) else 1,
                        location=location,
                        serial_number=row.get('serial_number') if pd.notna(row.get('serial_number')) else None,
                        brand=row.get('brand') if pd.notna(row.get('brand')) else None,
                        model=row.get('model') if pd.notna(row.get('model')) else None,
                        condition=row.get('condition', 'good') if pd.notna(row.get('condition')) else 'good',
                        created_by=request.user
                    )
                    
                    # Add category
                    item.categories.add(category)
                    
                    imported_count += 1
                    
                except Exception as e:
                    errors.append(f"Row {index + 1}: {str(e)}")
            
            if errors:
                messages.warning(request, f'Imported {imported_count} items with {len(errors)} errors. Check your data format.')
            else:
                messages.success(request, f'Successfully imported {imported_count} items.')
            
            return redirect('items:item_list')
            
        except Exception as e:
            messages.error(request, f'Error processing file: {str(e)}')
            return redirect('items:item_list')
    
    return render(request, 'items/import_items.html')


@login_required
@viewer_required
def item_list(request):
    """Display all items with search and filter functionality"""
    from django.core.paginator import Paginator
    from django.db.models import Exists, OuterRef
    from apps.lending.models import Lending
    
    # Subquery: does this item have an active (unreturned) lending?
    active_lending = Lending.objects.filter(
        item=OuterRef('pk'), returned_date__isnull=True
    )
    
    # Optimize query with select_related, prefetch_related, and a single
    # EXISTS annotation so templates don't trigger N+1 lending queries
    items = Item.objects.select_related('location', 'created_by').prefetch_related(
        'categories', 
        'images'
    ).annotate(has_active_lending=Exists(active_lending))
    
    # If user is Lender role, only show items available for lending
    if request.user.profile.is_lender():
        items = items.filter(available_for_lending=True)
    
    # Global inventory stats (unaffected by search/filters)
    total_items = items.count()
    total_value = items.aggregate(Sum('current_value'))['current_value__sum'] or 0
    borrowed_count = items.filter(has_active_lending=True).count()
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        items = items.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(serial_number__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(model__icontains=search_query) |
            Q(barcode__icontains=search_query)
        )
    
    # Filters
    location_filter = request.GET.get('location')
    category_filter = request.GET.get('category')
    condition_filter = request.GET.get('condition')
    status_filter = request.GET.get('status', 'all')  # all, available, borrowed
    low_stock_filter = request.GET.get('low_stock') == '1'
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if location_filter:
        items = items.filter(location_id=location_filter)
    if category_filter:
        items = items.filter(categories__id=category_filter).distinct()  # Add distinct to prevent duplicates
    if condition_filter:
        items = items.filter(condition=condition_filter)
    if low_stock_filter:
        items = items.filter(quantity__lt=F('min_quantity'))
    if date_from:
        items = items.filter(created_at__date__gte=date_from)
    if date_to:
        items = items.filter(created_at__date__lte=date_to)
    
    # Status filter via annotation (avoids join duplicates and is correct)
    if status_filter == 'available':
        items = items.filter(has_active_lending=False)
    elif status_filter == 'borrowed':
        items = items.filter(has_active_lending=True)
    
    # Column sorting (whitelisted fields only)
    SORTABLE_FIELDS = {
        'name': 'name',
        'location': 'location__name',
        'value': 'current_value',
        'condition': 'condition',
        'quantity': 'quantity',
        'purchase_date': 'purchase_date',
        'created': 'created_at',
    }
    sort_field = request.GET.get('sort', '')
    sort_dir = request.GET.get('dir', 'desc')
    if sort_field in SORTABLE_FIELDS:
        prefix = '' if sort_dir == 'asc' else '-'
        # Secondary ordering keeps pagination deterministic
        items = items.order_by(prefix + SORTABLE_FIELDS[sort_field], '-created_at', 'pk')
    else:
        items = items.order_by('-created_at', 'pk')
        sort_field, sort_dir = '', ''
    
    # Build sort toggle URLs preserving current filters
    def _sort_url(field):
        q = request.GET.copy()
        q['sort'] = field
        q['dir'] = 'desc' if (sort_field == field and sort_dir == 'asc') else 'asc'
        q.pop('page', None)
        return '?' + q.urlencode()
    sort_urls = {f: _sort_url(f) for f in SORTABLE_FIELDS}
    
    # Pagination - show 50 items per page
    paginator = Paginator(items, 50)
    page_number = request.GET.get('page', 1)
    items_page = paginator.get_page(page_number)
    
    # Windowed page range: first/last + current±2 with ellipsis
    page_range = _windowed_page_range(items_page.number, paginator.num_pages)
    
    # Optimize categories queryset
    categories = Category.objects.all().order_by('name')
    
    return render(request, 'items/item_list.html', {
        'items': items_page,
        'search_query': search_query,
        'total_value': total_value,
        'total_items': total_items,
        'borrowed_count': borrowed_count,
        'locations': get_available_locations(),
        'categories': categories,
        'location_filter': location_filter,
        'category_filter': category_filter,
        'condition_filter': condition_filter,
        'status_filter': status_filter,
        'low_stock_filter': low_stock_filter,
        'date_from': date_from,
        'date_to': date_to,
        'sort_field': sort_field,
        'sort_dir': sort_dir,
        'sort_urls': sort_urls,
        'page_range': page_range,
        'paginator': paginator,
    })


@login_required
def item_detail(request, pk):
    """Display details of a specific item"""
    item = get_object_or_404(Item.objects.select_related('location', 'created_by'), pk=pk)
    images = item.images.all()
    
    # Generate barcode and QR code on the fly
    barcode_svg = item.generate_barcode_svg()
    qr_code_image = item.generate_qr_code_image()
    
    # Convert QR code image to base64 for display
    qr_code_base64 = None
    if qr_code_image:
        buffer = BytesIO()
        qr_code_image.save(buffer, format='PNG')
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    # Check if item is borrowed - get all active lendings
    from apps.lending.models import Lending
    active_lendings = Lending.objects.filter(item=item, returned_date__isnull=True).select_related('borrowed_by_user')
    current_lending = active_lendings.first()
    is_borrowed = current_lending is not None
    current_borrower = current_lending.borrower_display if current_lending else None

    # Compute once - the template calls this repeatedly otherwise (one aggregate query each)
    available_quantity = item.get_available_quantity()
    
    # Build breadcrumb navigation
    from django.urls import reverse
    breadcrumbs = [{'name': 'Items', 'url': reverse('items:item_list')}]
    
    # Add location hierarchy if item has a location
    if item.location:
        # Insert location breadcrumbs before item
        location_breadcrumbs = [{'name': 'Locations', 'url': reverse('locations:location_list')}]
        
        # Add location ancestors
        ancestors = list(item.location.get_ancestors())
        for ancestor in ancestors:
            location_breadcrumbs.append({
                'name': ancestor.name,
                'url': reverse('locations:location_detail', args=[ancestor.pk])
            })
        
        # Add current location
        location_breadcrumbs.append({
            'name': item.location.name,
            'url': reverse('locations:location_detail', args=[item.location.pk])
        })
        
        # Combine: Items > Locations > [location hierarchy] > Item Name
        breadcrumbs = [{'name': 'Items', 'url': reverse('items:item_list')}] + location_breadcrumbs[1:] + [{'name': item.name, 'url': None}]
    else:
        # No location: Items > Item Name
        breadcrumbs.append({'name': item.name, 'url': None})
    
    return render(request, 'items/item_detail.html', {
        'item': item,
        'images': images,
        'barcode_svg': barcode_svg,
        'qr_code_image': qr_code_base64,
        'is_borrowed': is_borrowed,
        'current_borrower': current_borrower,
        'current_lending': current_lending,
        'active_lendings': active_lendings,
        'available_quantity': available_quantity,
        'breadcrumbs': breadcrumbs,
    })


@login_required
@editor_required
def item_create(request, location_pk=None):
    """Create a new item"""
    from apps.locations.models import Location
    
    # Get initial location if provided
    initial = {}
    if location_pk:
        location = get_object_or_404(Location, pk=location_pk)
        initial['location'] = location.pk
    
    if request.method == 'POST':
        form = ItemForm(request.POST, request.FILES, initial=initial)
        if form.is_valid():
            item = form.save(commit=False)
            item.created_by = request.user
            item.save()
            form.save_m2m()  # Save many-to-many relationships
            
            # Handle image uploads
            images = request.FILES.getlist('images')
            for i, image in enumerate(images):
                ItemImage.objects.create(
                    item=item,
                    image=image,
                    is_primary=(i == 0)  # First image is primary
                )
            
            messages.success(request, f'Item "{item.name}" created successfully.')
            return redirect('items:item_detail', pk=item.pk)
    else:
        form = ItemForm(initial=initial)
    
    return render(request, 'items/item_form.html', {
        'form': form,
        'action': 'Create',
        'location': get_object_or_404(Location, pk=location_pk) if location_pk else None
    })


@login_required
@editor_required
def item_update(request, pk):
    """Update an existing item"""
    item = get_object_or_404(Item, pk=pk)
    
    if request.method == 'POST':
        form = ItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()
            
            # Handle new image uploads
            images = request.FILES.getlist('images')
            for i, image in enumerate(images):
                ItemImage.objects.create(
                    item=item,
                    image=image,
                    is_primary=(i == 0 and not item.images.filter(is_primary=True).exists())
                )
            
            messages.success(request, f'Item "{item.name}" updated successfully.')
            return redirect('items:item_detail', pk=item.pk)
    else:
        form = ItemForm(instance=item)
    
    return render(request, 'items/item_form.html', {
        'form': form,
        'item': item,
        'action': 'Update'
    })


@login_required
@editor_required
def item_delete(request, pk):
    """Delete an item"""
    item = get_object_or_404(Item, pk=pk)
    
    if request.method == 'POST':
        item_name = item.name
        item.delete()
        messages.success(request, f'Item "{item_name}" deleted successfully.')
        return redirect('items:item_list')
    
    return render(request, 'items/item_confirm_delete.html', {'item': item})


@login_required
@editor_required
def item_bulk_action(request):
    """Apply bulk actions to selected items (delete, lending availability)."""
    from django.urls import reverse
    
    if request.method != 'POST':
        return redirect('items:item_list')
    
    item_ids = request.POST.getlist('item_ids')
    action = request.POST.get('action')
    next_url = request.POST.get('next') or reverse('items:item_list')
    # Only allow internal redirects
    if not next_url.startswith('/'):
        next_url = reverse('items:item_list')
    
    if not item_ids:
        messages.warning(request, 'No items selected.')
        return redirect(next_url)
    
    items = Item.objects.filter(pk__in=item_ids)
    
    if action == 'delete':
        from apps.lending.models import Lending
        # Skip items that are currently borrowed (lendings would be cascade-deleted)
        borrowed_ids = set(
            Lending.objects.filter(
                item__in=items, returned_date__isnull=True
            ).values_list('item_id', flat=True)
        )
        deletable = items.exclude(pk__in=borrowed_ids)
        skipped = items.count() - deletable.count()
        deleted_count = deletable.count()
        deletable.delete()
        if deleted_count:
            messages.success(request, f'{deleted_count} item(s) deleted.')
        if skipped:
            messages.warning(request, f'{skipped} item(s) skipped — currently borrowed.')
    elif action in ('allow_lending', 'disallow_lending'):
        value = action == 'allow_lending'
        updated = items.update(available_for_lending=value)
        label = 'allowed for' if value else 'disallowed for'
        messages.success(request, f'{updated} item(s) {label} external lending.')
    else:
        messages.error(request, 'Unknown bulk action.')
    
    return redirect(next_url)


@login_required
def generate_barcode(request, pk):
    """Generate and return barcode as SVG"""
    item = get_object_or_404(Item, pk=pk)
    barcode_svg = item.generate_barcode_svg()
    
    if barcode_svg:
        return HttpResponse(barcode_svg, content_type='image/svg+xml')
    return HttpResponse('Barcode not available', status=404)


@login_required
def generate_qr_code(request, pk):
    """Generate and return QR code as PNG"""
    item = get_object_or_404(Item, pk=pk)
    qr_image = item.generate_qr_code_image()
    
    if qr_image:
        buffer = BytesIO()
        qr_image.save(buffer, format='PNG')
        buffer.seek(0)
        return HttpResponse(buffer.getvalue(), content_type='image/png')
    return HttpResponse('QR code not available', status=404)


@login_required
def export_csv(request):
    """Export items to CSV for insurance purposes"""
    items = Item.objects.select_related('location', 'created_by').prefetch_related('categories')
    
    # Apply filters
    search_query = request.GET.get('search', '')
    location_filter = request.GET.get('location')
    category_filter = request.GET.get('category')
    condition_filter = request.GET.get('condition')
    
    if search_query:
        items = items.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(serial_number__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(model__icontains=search_query)
        )
    
    if location_filter:
        items = items.filter(location_id=location_filter)
    if category_filter:
        items = items.filter(categories__id=category_filter)
    if condition_filter:
        items = items.filter(condition=condition_filter)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="inventory_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Name', 'Description', 'Location', 'Categories', 'Serial Number', 'Brand', 'Model', 
                     'Barcode', 'QR Code', 'Purchase Date', 'Purchase Price', 'Current Value', 'Condition'])
    
    # Chunked iteration keeps memory bounded for large inventories
    # (prefetch_related still works per chunk since Django 4.1)
    for item in items.iterator(chunk_size=2000):
        categories = ', '.join([cat.name for cat in item.categories.all()])
        writer.writerow([
            item.name,
            item.description or '',
            item.location.name if item.location else 'N/A',
            categories,
            item.serial_number or '',
            item.brand or '',
            item.model or '',
            item.barcode or '',
            item.qr_code or '',
            item.purchase_date.strftime('%Y-%m-%d') if item.purchase_date else '',
            str(item.purchase_price) if item.purchase_price else '',
            str(item.current_value) if item.current_value else '',
            item.get_condition_display()
        ])
    
    return response


@login_required
def export_pdf(request):
    """Export items to PDF for insurance purposes"""
    from weasyprint import HTML, CSS
    from django.template.loader import render_to_string
    
    items = Item.objects.select_related('location', 'created_by').prefetch_related('categories')
    
    # Apply filters
    search_query = request.GET.get('search', '')
    location_filter = request.GET.get('location')
    category_filter = request.GET.get('category')
    condition_filter = request.GET.get('condition')
    
    if search_query:
        items = items.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(serial_number__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(model__icontains=search_query)
        )
    
    if location_filter:
        items = items.filter(location_id=location_filter)
    if category_filter:
        items = items.filter(categories__id=category_filter)
    if condition_filter:
        items = items.filter(condition=condition_filter)
    
    # Calculate total value and item count (bounded memory via COUNT query)
    total_value = items.aggregate(Sum('current_value'))['current_value__sum'] or 0
    item_count = items.count()
    
    # Group by category - chunked iteration keeps memory bounded for large inventories
    category_stats = {}
    for item in items.iterator(chunk_size=2000):
        for category in item.categories.all():
            if category.name not in category_stats:
                category_stats[category.name] = {'count': 0, 'value': 0}
            category_stats[category.name]['count'] += 1
            category_stats[category.name]['value'] += item.current_value or 0
    
    html_string = render_to_string('items/export_pdf.html', {
        'items': items.iterator(chunk_size=2000),
        'item_count': item_count,
        'total_value': total_value,
        'category_stats': category_stats,
        'export_date': datetime.now().strftime('%B %d, %Y'),
    })
    
    html = HTML(string=html_string)
    css = CSS(string='''
        @page {
            size: A4;
            margin: 1cm;
        }
        body {
            font-family: Arial, sans-serif;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }
        th {
            background-color: #f2f2f2;
        }
    ''')
    
    pdf = html.write_pdf(stylesheets=[css])
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="inventory_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf"'
    
    return response


@login_required
def print_label(request, pk):
    """Print a single item label (barcode/QR code)"""
    from PIL import Image
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    
    item = get_object_or_404(Item.objects.select_related('location'), pk=pk)
    
    # Get or create default label template
    template = LabelTemplate.objects.filter(created_by=request.user).first()
    if not template:
        template = LabelTemplate.objects.create(
            name='Default',
            created_by=request.user
        )
    
    # Create PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="label_{item.pk}.pdf"'
    
    # Create PDF with ReportLab
    buffer = BytesIO()
    c = rl_canvas.Canvas(buffer, pagesize=(template.width_mm * mm, template.height_mm * mm))
    
    # Draw label content
    y_position = template.height_mm * mm - 10 * mm  # Start from top with margin
    
    if template.include_name:
        c.setFont("Helvetica-Bold", template.font_size)
        c.setFillColor(colors.black)
        c.drawString(10 * mm, y_position, item.name[:30])
        y_position -= 8 * mm
    
    if template.include_barcode and item.barcode:
        # Generate barcode
        code128 = barcode.get('code128', writer=barcode.ImageWriter())
        barcode_io = BytesIO()
        code128.write(item.barcode, barcode_io)
        barcode_io.seek(0)
        
        # Draw barcode
        barcode_image = Image.open(barcode_io)
        barcode_image.thumbnail((template.width_mm * mm - 20 * mm, 20 * mm))
        c.drawImage(barcode_image, 10 * mm, y_position - 20 * mm)
        y_position -= 25 * mm
    
    if template.include_qr_code and item.qr_code:
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(item.qr_code)
        qr.make(fit=True)
        qr_io = BytesIO()
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_img.save(qr_io, format='PNG')
        qr_io.seek(0)
        
        # Draw QR code
        qr_image = Image.open(qr_io)
        qr_image.thumbnail((20 * mm, 20 * mm))
        c.drawImage(qr_image, template.width_mm * mm - 30 * mm, y_position - 20 * mm)
        y_position -= 25 * mm
    
    if template.include_location and item.location:
        c.setFont("Helvetica", template.font_size - 2)
        c.setFillColor(colors.gray)
        c.drawString(10 * mm, y_position, f"Location: {item.location.name[:25]}")
        y_position -= 6 * mm
    
    if template.include_description and item.description:
        c.setFont("Helvetica", template.font_size - 2)
        c.setFillColor(colors.gray)
        desc = item.description[:40] if item.description else ''
        c.drawString(10 * mm, y_position, desc)
    
    c.save()
    buffer.seek(0)
    response.write(buffer.getvalue())
    
    return response


@login_required
def print_bulk_labels(request):
    """Print labels for multiple items"""
    from PIL import Image
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from apps.locations.models import Location
    
    if request.method == 'POST':
        item_ids = request.POST.getlist('item_ids')
        if not item_ids:
            messages.error(request, 'Please select items to print labels for.')
            return redirect('items:item_list')
        
        items = Item.objects.filter(pk__in=item_ids).select_related('location')
        
        # Get or create default label template
        template = LabelTemplate.objects.filter(created_by=request.user).first()
        if not template:
            template = LabelTemplate.objects.create(
                name='Default',
                created_by=request.user
            )
        
        # Create PDF with multiple labels
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="bulk_labels.pdf"'
        
        buffer = BytesIO()
        c = rl_canvas.Canvas(buffer, pagesize=(template.width_mm * mm, template.height_mm * mm))
        
        for item in items:
            # Draw label
            c.setFillColor(colors.white)
            c.rect(0, 0, template.width_mm * mm, template.height_mm * mm, fill=True, stroke=False)
            
            y_position = template.height_mm * mm - 10 * mm
            
            if template.include_name:
                c.setFont("Helvetica-Bold", template.font_size)
                c.setFillColor(colors.black)
                c.drawString(10 * mm, y_position, item.name[:30])
                y_position -= 8 * mm
            
            if template.include_barcode and item.barcode:
                code128 = barcode.get('code128', writer=barcode.ImageWriter())
                barcode_io = BytesIO()
                code128.write(item.barcode, barcode_io)
                barcode_io.seek(0)
                
                barcode_image = Image.open(barcode_io)
                barcode_image.thumbnail((template.width_mm * mm - 20 * mm, 20 * mm))
                c.drawImage(barcode_image, 10 * mm, y_position - 20 * mm)
                y_position -= 25 * mm
            
            if template.include_qr_code and item.qr_code:
                qr = qrcode.QRCode(version=1, box_size=10, border=4)
                qr.add_data(item.qr_code)
                qr.make(fit=True)
                qr_io = BytesIO()
                qr_img = qr.make_image(fill_color="black", back_color="white")
                qr_img.save(qr_io, format='PNG')
                qr_io.seek(0)
                
                qr_image = Image.open(qr_io)
                qr_image.thumbnail((20 * mm, 20 * mm))
                c.drawImage(qr_image, template.width_mm * mm - 30 * mm, y_position - 20 * mm)
                y_position -= 25 * mm
            
            if template.include_location and item.location:
                c.setFont("Helvetica", template.font_size - 2)
                c.setFillColor(colors.gray)
                c.drawString(10 * mm, y_position, f"Location: {item.location.name[:25]}")
                y_position -= 6 * mm
            
            if template.include_description and item.description:
                c.setFont("Helvetica", template.font_size - 2)
                c.setFillColor(colors.gray)
                desc = item.description[:40] if item.description else ''
                c.drawString(10 * mm, y_position, desc)
            
            c.showPage()
        
        c.save()
        buffer.seek(0)
        response.write(buffer.getvalue())
        
        messages.success(request, f'Generated labels for {len(items)} items.')
        return redirect('items:item_list')
    
    # GET request - show item selection with location filter
    from django.core.paginator import Paginator
    
    location_filter = request.GET.get('location')
    items = Item.objects.select_related('location').all()
    
    if location_filter:
        items = items.filter(location_id=location_filter)
    
    # Paginate so the selection page stays usable with large inventories
    paginator = Paginator(items, 100)
    items_page = paginator.get_page(request.GET.get('page', 1))
    
    locations = Location.get_tree()
    
    return render(request, 'items/print_bulk_labels.html', {
        'items': items_page,
        'locations': locations,
        'location_filter': location_filter
    })


def get_available_locations():
    """Helper function to get all locations for filter dropdown"""
    from apps.locations.models import Location
    return Location.get_tree()


def _windowed_page_range(current, total, window=2):
    """Return page numbers with '…' ellipsis markers around the current page."""
    if total <= 0:
        return []
    if total <= 7:
        return list(range(1, total + 1))
    pages = {1, total}
    for p in range(current - window, current + window + 1):
        if 1 <= p <= total:
            pages.add(p)
    result = []
    prev = 0
    for p in sorted(pages):
        if p - prev > 1:
            result.append('…')
        result.append(p)
        prev = p
    return result