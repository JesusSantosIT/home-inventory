from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.urls import reverse
from io import BytesIO
from .models import Location, LocationImage
from .forms import LocationForm
from apps.users.decorators import editor_required, viewer_required
import pandas as pd


@login_required
def import_locations(request):
    """Import locations from CSV or Excel file"""
    if request.method == 'POST':
        file = request.FILES.get('file')
        if not file:
            messages.error(request, 'Please select a file to import.')
            return redirect('locations:location_list')
        
        try:
            # Read file based on extension
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            elif file.name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file)
            else:
                messages.error(request, 'Unsupported file format. Please use CSV or Excel.')
                return redirect('locations:location_list')
            
            # Process the data
            imported_count = 0
            errors = []
            
            for index, row in df.iterrows():
                try:
                    # Create location
                    location = Location.objects.create(
                        name=row.get('name', ''),
                        location_type=row.get('location_type', 'other') if pd.notna(row.get('location_type')) else 'other',
                        description=row.get('description', '') if pd.notna(row.get('description')) else '',
                        created_by=request.user
                    )
                    
                    imported_count += 1
                    
                except Exception as e:
                    errors.append(f"Row {index + 1}: {str(e)}")
            
            if errors:
                messages.warning(request, f'Imported {imported_count} locations with {len(errors)} errors.')
            else:
                messages.success(request, f'Successfully imported {imported_count} locations.')
            
            return redirect('locations:location_list')
            
        except Exception as e:
            messages.error(request, f'Error processing file: {str(e)}')
            return redirect('locations:location_list')
    
    return render(request, 'locations/import_locations.html')


def _build_location_tree():
    """
    Load all locations once and build the parent/child tree in Python.

    Returns (roots, all_locations) where each node has extra attributes:
      tree_children     - list of direct child nodes
      tree_parent       - parent node or None
      tree_has_children - bool
      tree_direct_items - items located exactly at this node
      tree_item_total   - items in this node + all descendants
      tree_desc_count   - number of descendant locations
      tree_path_label   - 'House → Room → ...' full path string

    Uses 3 queries total regardless of tree size (locations, item counts).
    """
    from apps.items.models import Item
    from django.db.models import Count

    all_locations = list(Location.get_tree())  # DFS order by path

    # Items per location in a single grouped query
    item_counts = dict(
        Item.objects.values('location_id')
        .annotate(c=Count('id'))
        .values_list('location_id', 'c')
    )

    # Build tree: nodes arrive in DFS order, so parent is the nearest
    # preceding node with depth-1 (maintained via stack)
    stack = []
    roots = []
    for node in all_locations:
        node.tree_children = []
        node.tree_parent = None
        node.tree_direct_items = item_counts.get(node.pk, 0)
        depth = node.get_depth()
        while stack and stack[-1][0] >= depth:
            stack.pop()
        if stack:
            parent = stack[-1][1]
            parent.tree_children.append(node)
            node.tree_parent = parent
        else:
            roots.append(node)
        stack.append((depth, node))

    # Post-order pass (reverse DFS = children before parents): subtree sums
    for node in reversed(all_locations):
        node.tree_item_total = node.tree_direct_items + sum(c.tree_item_total for c in node.tree_children)
        node.tree_desc_count = sum(1 + c.tree_desc_count for c in node.tree_children)
        node.tree_has_children = bool(node.tree_children)
        # Full path label via in-memory parent walk (no queries)
        parts = []
        p = node
        while p is not None:
            parts.append(p.name)
            p = p.tree_parent
        node.tree_path_label = ' → '.join(reversed(parts))

    return roots, all_locations


@login_required
@viewer_required
def location_list(request):
    """Display locations as a lazily-loaded tree (children fetched on expand)."""
    from django.core.paginator import Paginator
    
    roots, all_locations = _build_location_tree()
    houses = roots
    
    # Get selected house from query params or default to first house
    selected_house = None
    selected_house_id = request.GET.get('house')
    if selected_house_id:
        try:
            sid = int(selected_house_id)
            selected_house = next((n for n in all_locations if n.pk == sid), None)
        except (ValueError, TypeError):
            selected_house = None
    elif len(roots) == 1:
        # Auto-select if only one house exists
        selected_house = roots[0]
    
    # Pool of locations in scope (selected house subtree, or everything)
    if selected_house:
        pool = [n for n in all_locations if n.path.startswith(selected_house.path)]
    else:
        pool = list(all_locations)
    
    # Apply type filter
    location_type_filter = request.GET.get('type', '')
    if location_type_filter:
        pool = [n for n in pool if n.location_type == location_type_filter]
    
    # Apply search filter (name substring, in-memory over the loaded tree)
    search_query = request.GET.get('search', '')
    if search_query:
        q = search_query.lower()
        pool = [n for n in pool if q in n.name.lower()]
    
    is_searching = bool(search_query)
    total_count = len(pool)
    
    if not is_searching:
        # Tree view: paginate root nodes only (children lazy-load via AJAX)
        if selected_house:
            root_locations = selected_house.tree_children
        else:
            root_locations = roots
        
        paginator = Paginator(root_locations, 20)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
    else:
        # Searching: flat paginated results
        paginator = Paginator(pool, 50)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)
    
    return render(request, 'locations/location_list.html', {
        'houses': houses,
        'selected_house': selected_house,
        'root_locations': page_obj if not is_searching else None,
        'search_results': page_obj if is_searching else None,
        'search_query': search_query,
        'location_type_filter': location_type_filter,
        'total_count': total_count,
        'is_searching': is_searching,
        # All locations for the move modal (drag & drop / move button).
        # 'path' lets the client exclude the node itself + its descendants.
        'movable_locations': [
            {'id': n.pk, 'name': n.name, 'path': n.path, 'label': n.tree_path_label}
            for n in all_locations
        ],
    })


@login_required
def location_detail(request, pk):
    """Display details of a specific location and its items"""
    location = get_object_or_404(Location, pk=pk)
    
    # Get search query
    search_query = request.GET.get('search', '')
    
    # Get items in this location directly with optimized queries
    from apps.items.models import Item
    from apps.lending.models import Lending
    from django.db.models import Q, Exists, OuterRef
    from django.core.paginator import Paginator
    
    # EXISTS annotation avoids N+1 lending queries in the template
    active_lending = Lending.objects.filter(
        item=OuterRef('pk'), returned_date__isnull=True
    )
    
    direct_items = Item.objects.filter(location=location).select_related(
        'location', 'created_by'
    ).prefetch_related('categories', 'images').annotate(
        has_active_lending=Exists(active_lending)
    )
    
    # Apply search to direct items
    if search_query:
        direct_items = direct_items.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(serial_number__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(model__icontains=search_query) |
            Q(barcode__icontains=search_query)
        )
    
    # Get items in sub-locations with optimized queries
    descendant_ids = [loc.pk for loc in location.get_descendants(include_self=False)]
    sublocation_items = Item.objects.filter(location_id__in=descendant_ids).select_related(
        'location', 'created_by'
    ).prefetch_related('categories', 'images').annotate(
        has_active_lending=Exists(active_lending)
    )
    
    # Apply search to sub-location items
    if search_query:
        sublocation_items = sublocation_items.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(serial_number__icontains=search_query) |
            Q(brand__icontains=search_query) |
            Q(model__icontains=search_query) |
            Q(barcode__icontains=search_query)
        )
    
    # Group sub-location items by their location.
    # Single pass with chunked iteration: keeps only the first N items per
    # location (memory-bounded) while counting totals exactly.
    SUBLOCATION_PREVIEW_LIMIT = 10
    sublocation_groups = {}
    for item in sublocation_items.iterator(chunk_size=2000):
        loc = item.location
        group = sublocation_groups.setdefault(
            loc, {'location': loc, 'items': [], 'total': 0}
        )
        group['total'] += 1
        if len(group['items']) < SUBLOCATION_PREVIEW_LIMIT:
            group['items'].append(item)
    sublocation_items_by_location = list(sublocation_groups.values())
    
    # Combine items for total count (single COUNT query reused below)
    sublocation_count = sublocation_items.count()
    total_items_count = direct_items.count() + sublocation_count
    
    # Pagination for direct items
    paginator = Paginator(direct_items, 50)
    page_number = request.GET.get('page', 1)
    direct_items_page = paginator.get_page(page_number)
    
    # Get location images
    images = location.images.all()
    
    # Build item create URL for this location
    from django.urls import reverse
    item_create_url = reverse('items:item_create_for_location', args=[location.pk])
    
    # Build breadcrumb navigation
    breadcrumbs = [{'name': 'Locations', 'url': reverse('locations:location_list')}]
    
    # Add location hierarchy to breadcrumbs
    ancestors = list(location.get_ancestors())
    for ancestor in ancestors:
        breadcrumbs.append({
            'name': ancestor.name,
            'url': reverse('locations:location_detail', args=[ancestor.pk])
        })
    
    # Add current location (no URL for current page)
    breadcrumbs.append({'name': location.name, 'url': None})
    
    return render(request, 'locations/location_detail.html', {
        'location': location,
        'direct_items': direct_items_page,
        'direct_count': direct_items.count(),
        'sublocation_items': sublocation_items,
        'sublocation_items_by_location': sublocation_items_by_location,
        'sublocation_count': sublocation_count,
        'total_items': total_items_count,
        'search_query': search_query,
        'images': images,
        'item_create_url': item_create_url,
        'breadcrumbs': breadcrumbs,
    })


@login_required
@editor_required
def location_create(request, parent_pk=None):
    """Create a new location"""
    parent = None
    if parent_pk:
        parent = get_object_or_404(Location, pk=parent_pk)
    else:
        # If no parent_pk provided, check if a house is selected
        selected_house_id = request.GET.get('house')
        if selected_house_id:
            parent = Location.objects.filter(pk=selected_house_id).first()
    
    if request.method == 'POST':
        form = LocationForm(request.POST)
        if form.is_valid():
            location = form.save(commit=False)
            location.created_by = request.user
            
            # Get parent from form or use the one from URL/house selection
            parent_from_form = form.cleaned_data.get('parent')
            final_parent = parent_from_form if parent_from_form else parent
            
            if final_parent:
                location = final_parent.add_child(instance=location)
            else:
                location = Location.add_root(instance=location)
            
            # Handle image uploads
            if request.FILES.getlist('images'):
                for image_file in request.FILES.getlist('images'):
                    LocationImage.objects.create(
                        location=location,
                        image=image_file
                    )
            
            messages.success(request, f'Location "{location.name}" created successfully.')
            return redirect('locations:location_detail', pk=location.pk)
    else:
        # Pre-select parent if provided
        initial = {}
        if parent:
            initial['parent'] = parent.pk
        form = LocationForm(initial=initial)
    
    return render(request, 'locations/location_form.html', {
        'form': form,
        'parent': parent,
        'action': 'Create'
    })


@login_required
@editor_required
def location_update(request, pk):
    """Update an existing location"""
    location = get_object_or_404(Location, pk=pk)
    old_parent = location.get_parent()
    
    if request.method == 'POST':
        form = LocationForm(request.POST, instance=location)
        if form.is_valid():
            # Get the new parent from the form
            new_parent = form.cleaned_data.get('parent')
            
            # Update the location fields
            location.name = form.cleaned_data['name']
            location.location_type = form.cleaned_data['location_type']
            location.description = form.cleaned_data['description']
            
            # Handle parent change using treebeard's move method
            # Only move if parent is explicitly changed in the form
            parent_submitted = request.POST.get('parent')
            
            if parent_submitted == '':
                # User explicitly cleared the parent - move to root
                if old_parent:
                    location.move(Location.get_root_nodes().first(), pos='left')
            elif parent_submitted:
                # User selected a new parent
                if new_parent and new_parent != old_parent:
                    # Prevent moving a location to be its own descendant
                    ancestors = list(new_parent.get_ancestors())
                    if location in ancestors or location == new_parent:
                        messages.error(request, 'Cannot move a location to be a child of its own descendant.')
                        return render(request, 'locations/location_form.html', {
                            'form': form,
                            'location': location,
                            'action': 'Update'
                        })
                    # Move to be a child of the new parent
                    location.move(new_parent, pos='last-child')
            # If parent_submitted is None or same as old_parent, don't move
            
            # Save any other field changes
            location.save()
            
            # Handle image uploads
            if request.FILES.getlist('images'):
                for image_file in request.FILES.getlist('images'):
                    LocationImage.objects.create(
                        location=location,
                        image=image_file
                    )
            
            messages.success(request, f'Location "{location.name}" updated successfully.')
            return redirect('locations:location_detail', pk=location.pk)
    else:
        form = LocationForm(instance=location)
    
    return render(request, 'locations/location_form.html', {
        'form': form,
        'location': location,
        'action': 'Update'
    })


@login_required
def location_delete_image(request, pk, image_pk):
    """Delete a location image"""
    location = get_object_or_404(Location, pk=pk)
    image = get_object_or_404(LocationImage, pk=image_pk, location=location)
    
    if request.method == 'POST':
        image.delete()
        messages.success(request, 'Image deleted successfully.')
        return redirect('locations:location_detail', pk=location.pk)
    
    return render(request, 'locations/location_image_confirm_delete.html', {
        'location': location,
        'image': image
    })


@login_required
@editor_required
def location_delete(request, pk):
    """Delete a location"""
    location = get_object_or_404(Location, pk=pk)
    
    if request.method == 'POST':
        location_name = location.name
        location.delete()
        messages.success(request, f'Location "{location_name}" deleted successfully.')
        return redirect('locations:location_list')
    
    return render(request, 'locations/location_confirm_delete.html', {'location': location})


@login_required
def generate_barcode(request, pk):
    """Generate and return barcode as SVG"""
    location = get_object_or_404(Location, pk=pk)
    barcode_svg = location.get_barcode_svg()
    
    if barcode_svg:
        return HttpResponse(barcode_svg, content_type='image/svg+xml')
    return HttpResponse('Barcode not available', status=404)


@login_required
def generate_qr_code(request, pk):
    """Generate and return QR code as PNG"""
    location = get_object_or_404(Location, pk=pk)
    qr_image = location.generate_qr_code_image()
    
    if qr_image:
        buffer = BytesIO()
        qr_image.save(buffer, format='PNG')
        buffer.seek(0)
        return HttpResponse(buffer.getvalue(), content_type='image/png')
    return HttpResponse('QR code not available', status=404)


@login_required
def load_children(request, pk):
    """Load direct children of a location via AJAX for lazy tree expansion."""
    from django.template.loader import render_to_string

    _, all_locations = _build_location_tree()
    node = next((n for n in all_locations if n.pk == pk), None)
    if node is None:
        return HttpResponse('')

    # Render each child with the shared (non-recursive) node template;
    # grandchildren load on demand when the user expands the child
    html = ''.join(
        render_to_string('locations/tree_node.html', {'location': child, 'level': 1})
        for child in node.tree_children
    )
    return HttpResponse(html)


@login_required
def scan_page(request):
    """Barcode/QR code scanning page"""
    return render(request, 'locations/scan_page.html')


@login_required
def lookup_code(request, code):
    """Lookup a barcode or QR code and return the item/location"""
    from apps.items.models import Item
    
    # Try to find location by barcode or QR code
    location = Location.objects.filter(barcode=code).first()
    if not location:
        location = Location.objects.filter(qr_code=code).first()
    
    # Try to find item by barcode or QR code
    item = Item.objects.filter(barcode=code).first()
    if not item:
        item = Item.objects.filter(qr_code=code).first()
    
    if location:
        return render(request, 'locations/scan_result.html', {
            'type': 'location',
            'location': location,
            'code': code
        })
    elif item:
        return render(request, 'locations/scan_result.html', {
            'type': 'item',
            'item': item,
            'code': code
        })
    else:
        return render(request, 'locations/scan_result.html', {
            'type': 'not_found',
            'code': code
        })


@login_required
@editor_required
def move_location(request):
    """Move a location to a new parent via AJAX (for drag and drop)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    
    from django.http import JsonResponse
    
    location_id = request.POST.get('location_id')
    new_parent_id = request.POST.get('new_parent_id')
    
    if not location_id:
        return JsonResponse({'success': False, 'error': 'location_id required'}, status=400)
    
    try:
        location = Location.objects.get(pk=location_id)
    except Location.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Location not found'}, status=404)
    
    # Get new parent (None means move to root)
    new_parent = None
    if new_parent_id and new_parent_id != 'root':
        try:
            new_parent = Location.objects.get(pk=new_parent_id)
        except Location.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'New parent not found'}, status=404)
    
    # Prevent moving a location to be its own descendant
    if new_parent:
        # Check if the location is in the new parent's ancestors (which would create a cycle)
        ancestors = list(new_parent.get_ancestors())
        if location in ancestors or location == new_parent:
            return JsonResponse({'success': False, 'error': 'Cannot move a location to be a child of its own descendant'}, status=400)
    
    # Move the location
    old_parent = location.get_parent()
    
    if new_parent != old_parent:
        if new_parent:
            location.move(new_parent, pos='last-child')
        else:
            # Move to root level
            if not location.is_root():
                location.move(Location.get_root_nodes().first(), pos='left')
        
        return JsonResponse({'success': True, 'message': f'Location "{location.name}" moved successfully'})
    
    return JsonResponse({'success': True, 'message': 'Location already in correct position'})