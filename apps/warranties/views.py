from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.core.paginator import Paginator
from .models import Warranty
from .forms import WarrantyForm
from apps.items.models import Item
from apps.users.decorators import editor_required


@login_required
def warranty_list(request):
    """List all warranties (paginated, DB-level expiry filters)"""
    warranties = Warranty.objects.select_related('item', 'created_by').all()

    # Filter by expiration status at the DB level
    show_expiring = request.GET.get('expiring')
    show_expired = request.GET.get('expired')
    today = timezone.now().date()

    if show_expiring:
        warranties = warranties.filter(
            expiration_date__gte=today,
            expiration_date__lte=today + timedelta(days=30)
        )
    if show_expired:
        warranties = warranties.filter(expiration_date__lt=today)

    paginator = Paginator(warranties, 50)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'warranties/warranty_list.html', {
        'warranties': page_obj,
        'show_expiring': show_expiring,
        'show_expired': show_expired,
    })


@login_required
def warranty_detail(request, pk):
    """View warranty details"""
    warranty = get_object_or_404(
        Warranty.objects.select_related('item', 'created_by'),
        pk=pk
    )
    
    # Build breadcrumb navigation
    from django.urls import reverse
    breadcrumbs = [
        {'name': 'Warranties', 'url': reverse('warranties:warranty_list')},
        {'name': warranty.item.name, 'url': reverse('items:item_detail', args=[warranty.item.pk])},
        {'name': f'{warranty.provider} Warranty', 'url': None}
    ]
    
    return render(request, 'warranties/warranty_detail.html', {
        'warranty': warranty,
        'is_active': warranty.is_active(),
        'days_remaining': warranty.days_remaining(),
        'is_expiring_soon': warranty.is_expiring_soon(),
        'breadcrumbs': breadcrumbs,
    })


@login_required
@editor_required
def warranty_create(request, item_pk):
    """Create a new warranty for an item"""
    item = get_object_or_404(Item, pk=item_pk)
    
    # Check if warranty already exists
    if hasattr(item, 'warranty'):
        messages.warning(request, f'A warranty already exists for {item.name}.')
        return redirect('item_detail', pk=item.pk)
    
    if request.method == 'POST':
        form = WarrantyForm(request.POST)
        if form.is_valid():
            warranty = form.save(commit=False)
            warranty.item = item
            warranty.created_by = request.user
            warranty.save()
            messages.success(request, f'Warranty for {item.name} created successfully.')
            return redirect('item_detail', pk=item.pk)
    else:
        form = WarrantyForm()
    
    return render(request, 'warranties/warranty_form.html', {
        'form': form,
        'item': item,
        'action': 'Create'
    })


@login_required
@editor_required
def warranty_update(request, pk):
    """Update an existing warranty"""
    warranty = get_object_or_404(Warranty, pk=pk)
    
    if request.method == 'POST':
        form = WarrantyForm(request.POST, instance=warranty)
        if form.is_valid():
            form.save()
            messages.success(request, f'Warranty for {warranty.item.name} updated successfully.')
            return redirect('warranty_detail', pk=warranty.pk)
    else:
        form = WarrantyForm(instance=warranty)
    
    return render(request, 'warranties/warranty_form.html', {
        'form': form,
        'warranty': warranty,
        'action': 'Update'
    })


@login_required
@editor_required
def warranty_delete(request, pk):
    """Delete a warranty"""
    warranty = get_object_or_404(Warranty, pk=pk)
    
    if request.method == 'POST':
        item_name = warranty.item.name
        warranty.delete()
        messages.success(request, f'Warranty for {item_name} deleted successfully.')
        return redirect('warranty_list')
    
    return render(request, 'warranties/warranty_confirm_delete.html', {'warranty': warranty})