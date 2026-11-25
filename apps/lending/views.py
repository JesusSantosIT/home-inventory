from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Sum, Q
from datetime import timedelta
from .models import Lending
from .forms import LendingForm
from apps.items.models import Item
from apps.users.decorators import editor_required, lender_or_above, viewer_required


@login_required
def lending_dashboard(request):
    """Dashboard showing lending status"""
    # Refresh stale status fields (overdue transitions happen with time, not saves)
    Lending.sync_statuses()

    # Get search query and filters
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', 'active')  # Default to active (excludes returned)
    view_filter = request.GET.get('view', 'all')  # all, borrowed, lent
    
    # Base queryset - all lendings involving the current user with optimized queries
    from django.db.models import Q
    base_queryset = Lending.objects.filter(
        Q(borrowed_by_user=request.user) | Q(item__created_by=request.user)
    ).select_related('item', 'borrowed_by_user', 'item__location')
    
    # Apply search filter (searches both borrower name and item name)
    if search_query:
        base_queryset = base_queryset.filter(
            Q(borrower_name__icontains=search_query) |
            Q(item__name__icontains=search_query)
        )
    
    # Apply status filter
    if status_filter == 'active':
        base_queryset = base_queryset.filter(returned_date__isnull=True)
    elif status_filter == 'overdue':
        base_queryset = base_queryset.filter(returned_date__isnull=True, due_date__lt=timezone.now())
    elif status_filter == 'returned':
        base_queryset = base_queryset.filter(returned_date__isnull=False)
    
    # Apply view filter
    if view_filter == 'borrowed':
        lendings = base_queryset.filter(borrowed_by_user=request.user)
    elif view_filter == 'lent':
        lendings = base_queryset.filter(item__created_by=request.user)
    else:
        lendings = base_queryset
    
    # Get frequent borrowers for autocomplete
    from django.db.models import Count
    frequent_borrowers = Lending.objects.values('borrower_name').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Calculate statistics efficiently using aggregate functions
    total_borrowed = Lending.objects.filter(
        borrowed_by_user=request.user, 
        returned_date__isnull=True
    ).count()
    
    total_lent = Lending.objects.filter(
        item__created_by=request.user, 
        returned_date__isnull=True
    ).count()
    
    total_overdue = Lending.objects.filter(
        returned_date__isnull=True, 
        due_date__lt=timezone.now()
    ).count()
    
    return render(request, 'lending/dashboard.html', {
        'lendings': lendings,
        'frequent_borrowers': frequent_borrowers,
        'search_query': search_query,
        'status_filter': status_filter,
        'view_filter': view_filter,
        'total_borrowed': total_borrowed,
        'total_lent': total_lent,
        'total_overdue': total_overdue,
    })


@login_required
@lender_or_above
def lending_create(request, item_pk):
    """Create a new lending record"""
    item = get_object_or_404(Item, pk=item_pk)
    
    # Check if user is a Lender role and item is not available for lending
    if request.user.profile.is_lender() and not item.available_for_lending:
        messages.error(request, f'{item.name} is not available for external lending.')
        return redirect('items:item_detail', pk=item.pk)
    
    # Calculate available quantity
    lent_quantity = Lending.objects.filter(
        item=item,
        returned_date__isnull=True
    ).aggregate(total=Sum('quantity'))['total'] or 0
    available_quantity = item.quantity - lent_quantity
    
    if available_quantity <= 0:
        messages.error(request, f'{item.name} has no available quantity to lend. Total: {item.quantity}, Lent: {lent_quantity}')
        return redirect('items:item_detail', pk=item.pk)
    
    # Get frequent borrowers for autocomplete
    from django.db.models import Count
    frequent_borrowers = Lending.objects.values('borrower_name').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    if request.method == 'POST':
        form = LendingForm(request.POST)
        if form.is_valid():
            quantity = form.cleaned_data.get('quantity', 1)
            
            # Validate quantity
            if quantity > available_quantity:
                messages.error(request, f'Cannot lend {quantity} items. Only {available_quantity} available.')
                return render(request, 'lending/lending_form.html', {
                    'form': form,
                    'item': item,
                    'available_quantity': available_quantity,
                    'frequent_borrowers': frequent_borrowers,
                    'action': 'Lend Item'
                })
            
            lending = form.save(commit=False)
            lending.item = item
            lending.created_by = request.user
            lending.save()
            borrower_name = lending.borrower_display
            messages.success(request, f'{quantity}x {item.name} has been lent to {borrower_name}.')
            return redirect('items:item_detail', pk=item.pk)
    else:
        form = LendingForm(initial={'due_date': timezone.now() + timedelta(days=7), 'quantity': 1})
    
    return render(request, 'lending/lending_form.html', {
        'form': form,
        'item': item,
        'available_quantity': available_quantity,
        'frequent_borrowers': frequent_borrowers,
        'action': 'Lend Item',
    })


@login_required
@editor_required
def lending_return(request, pk):
    """Mark an item as returned"""
    lending = get_object_or_404(Lending, pk=pk)
    
    if request.method == 'POST':
        lending.returned_date = timezone.now()
        lending.save()
        messages.success(request, f'{lending.item.name} has been marked as returned.')
        return redirect('lending:dashboard')
    
    return render(request, 'lending/lending_confirm_return.html', {'lending': lending})


@login_required
@viewer_required
def lending_detail(request, pk):
    """View lending details"""
    lending = get_object_or_404(
        Lending.objects.select_related('item', 'borrowed_by_user', 'created_by'),
        pk=pk
    )
    
    # Build breadcrumb navigation
    from django.urls import reverse
    breadcrumbs = [
        {'name': 'Lending', 'url': reverse('lending:dashboard')},
        {'name': lending.item.name, 'url': reverse('items:item_detail', args=[lending.item.pk])},
        {'name': f'Lent to {lending.borrowed_by_user.get_full_name or lending.borrowed_by_user.username}', 'url': None}
    ]
    
    return render(request, 'lending/lending_detail.html', {
        'lending': lending,
        'is_overdue': lending.is_overdue(),
        'days_overdue': lending.days_overdue(),
        'days_remaining': lending.days_remaining(),
        'breadcrumbs': breadcrumbs,
    })