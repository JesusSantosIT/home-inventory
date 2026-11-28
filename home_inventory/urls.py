from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Sum, Count, F
from django.utils import timezone
from apps.users.views import CustomLoginView

@login_required
def dashboard_view(request):
    """Comprehensive dashboard with stats and recent items"""
    from apps.items.models import Item
    from apps.locations.models import Location
    from apps.lending.models import Lending
    from apps.warranties.models import Warranty
    
    # Get statistics with optimized queries
    total_items = Item.objects.count()
    total_value = Item.objects.aggregate(Sum('current_value'))['current_value__sum'] or 0
    locations_count = Location.objects.count()
    
    # Get borrowed items with optimized queries - evaluate once, derive all stats in memory
    borrowed_list = list(
        Lending.objects.filter(
            returned_date__isnull=True
        ).select_related('item', 'borrowed_by_user')
    )
    borrowed_count = len(borrowed_list)

    # Get overdue items efficiently (is_overdue is pure Python)
    overdue_items = [l for l in borrowed_list if l.is_overdue()]
    
    # Get recent items with select_related
    recent_items = Item.objects.select_related('location').order_by('-created_at')[:5]
    
    # Get low stock items efficiently
    low_stock_items = Item.objects.filter(
        quantity__lt=F('min_quantity')
    ).select_related('location')[:5]
    
    # Get expiring warranties efficiently (within 30 days)
    from datetime import timedelta
    thirty_days_from_now = timezone.now().date() + timedelta(days=30)
    expiring_warranties = Warranty.objects.select_related('item').filter(
        expiration_date__lte=thirty_days_from_now,
        expiration_date__gte=timezone.now().date()
    ).order_by('expiration_date')[:5]
    
    return render(request, 'dashboard.html', {
        'total_items': total_items,
        'total_value': total_value,
        'locations_count': locations_count,
        'borrowed_count': borrowed_count,
        'borrowed_items': borrowed_list[:5],
        'overdue_items': overdue_items,
        'recent_items': recent_items,
        'low_stock_items': low_stock_items,
        'expiring_warranties': expiring_warranties,
    })

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('users/', include('apps.users.urls')),
    path('locations/', include('apps.locations.urls')),
    path('items/', include('apps.items.urls')),
    path('lending/', include('apps.lending.urls')),
    path('warranties/', include('apps.warranties.urls')),
    path('documents/', include('apps.documents.urls')),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('', dashboard_view, name='home'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Serve user-uploaded media in production too - waitress does not serve
# files on its own. Wrapped in login_required so uploaded photos are not
# publicly accessible by URL.
from django.views.static import serve as _media_serve
urlpatterns += [
    path('media/<path:path>', login_required(_media_serve),
         {'document_root': settings.MEDIA_ROOT}),
]