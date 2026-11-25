import hashlib
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from django.conf import settings
from django_ratelimit.decorators import ratelimit
from datetime import timedelta
from django.db.models import Sum, OuterRef, Subquery, IntegerField
from django.db.models.functions import Coalesce
from apps.items.models import Item
from apps.lending.models import Lending
from .models import ExternalHousehold


def _hash_api_key(key):
    return hashlib.sha256(key.encode()).hexdigest()


def validate_api_key(request):
    """Validate API key (hash lookup), check expiration, IP whitelist, log access"""
    api_key = request.headers.get('X-API-Key')

    if not api_key:
        return None, JsonResponse({'error': 'API key required'}, status=401)

    try:
        household = ExternalHousehold.objects.get(api_key_hash=_hash_api_key(api_key))
    except ExternalHousehold.DoesNotExist:
        return None, JsonResponse({'error': 'Invalid API key'}, status=401)
    
    # Check if key is valid (active and not expired)
    if not household.is_key_valid():
        return None, JsonResponse({'error': 'API key expired or inactive'}, status=401)
    
    # Check IP whitelist
    client_ip = request.META.get('REMOTE_ADDR')
    if not household.is_ip_allowed(client_ip):
        return None, JsonResponse({'error': 'IP address not allowed'}, status=403)
    
    # Update access tracking
    household.last_accessed = timezone.now()
    household.access_count += 1
    household.save(update_fields=['last_accessed', 'access_count'])
    
    # Check HTTPS in production
    if not request.is_secure() and not settings.DEBUG:
        return None, JsonResponse({'error': 'HTTPS required'}, status=403)
    
    return household, None


@csrf_exempt
@require_GET
@ratelimit(key='ip', rate='100/h', method='GET', block=True)
def api_available_items(request):
    """API endpoint for external households to get available items"""
    household, error_response = validate_api_key(request)
    if error_response:
        return error_response

    # Lent quantities for active lendings, aggregated in one subquery
    # (avoids an aggregate query per item)
    lent_subquery = (
        Lending.objects.filter(item=OuterRef('pk'), returned_date__isnull=True)
        .values('item')
        .annotate(total=Sum('quantity'))
        .values('total')[:1]
    )

    items = (
        Item.objects.filter(available_for_lending=True, quantity__gt=0)
        .select_related('location')
        .annotate(lent_qty=Coalesce(Subquery(lent_subquery, output_field=IntegerField()), 0))
    )

    items_list = []
    for item in items:
        available = item.quantity - item.lent_qty
        if available > 0:
            items_list.append({
                'id': item.pk,
                'name': item.name,
                'description': item.description,
                'quantity': item.quantity,
                'available': available,
                'location': item.location.name if item.location else None,
                'location_id': item.location.pk if item.location else None,
                'brand': item.brand,
                'model': item.model,
                'serial_number': item.serial_number,
                'barcode': item.barcode,
                'qr_code': item.qr_code,
                'condition': item.get_condition_display() if item.condition else None,
                'current_value': float(item.current_value) if item.current_value else None,
            })
    
    return JsonResponse({
        'household': household.name,
        'items': items_list,
        'count': len(items_list)
    })


@csrf_exempt
@require_POST
@ratelimit(key='ip', rate='100/h', method='POST', block=True)
def api_request_lending(request):
    """API endpoint for external households to request lending"""
    household, error_response = validate_api_key(request)
    if error_response:
        return error_response

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    item_id = data.get('item_id')
    quantity = data.get('quantity', 1)
    borrower_name = data.get('borrower_name')
    due_date = data.get('due_date')

    if not item_id or not borrower_name:
        return JsonResponse({'error': 'item_id and borrower_name required'}, status=400)

    try:
        quantity = int(quantity)
        if quantity < 1:
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse({'error': 'quantity must be a positive integer'}, status=400)

    # Parse due_date if provided (ISO format)
    parsed_due = None
    if due_date:
        try:
            from django.utils.dateparse import parse_datetime
            parsed_due = parse_datetime(due_date)
            if parsed_due is None:
                raise ValueError
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Invalid due_date format (use ISO 8601)'}, status=400)

    try:
        item = Item.objects.get(pk=item_id, available_for_lending=True)
    except Item.DoesNotExist:
        return JsonResponse({'error': 'Item not found or not available for lending'}, status=404)

    # Check availability (lent quantity in one aggregate)
    lent_quantity = Lending.objects.filter(
        item=item, returned_date__isnull=True
    ).aggregate(total=Sum('quantity'))['total'] or 0

    available = item.quantity - lent_quantity

    if available < quantity:
        return JsonResponse({
            'error': f'Only {available} items available',
            'available': available
        }, status=400)

    # Create lending record
    lending = Lending.objects.create(
        item=item,
        borrower_name=borrower_name,
        quantity=quantity,
        due_date=parsed_due or (timezone.now() + timedelta(days=30)),
        external_household=household
    )

    return JsonResponse({
        'success': True,
        'lending_id': lending.pk,
        'message': f'Successfully borrowed {quantity}x {item.name}'
    })


@csrf_exempt
@require_GET
@ratelimit(key='ip', rate='100/h', method='GET', block=True)
def api_item_detail(request, item_id):
    """API endpoint to get details of a specific item"""
    household, error_response = validate_api_key(request)
    if error_response:
        return error_response
    
    try:
        item = Item.objects.get(pk=item_id, available_for_lending=True)
    except Item.DoesNotExist:
        return JsonResponse({'error': 'Item not found or not available for lending'}, status=404)
    
    # Calculate available quantity
    lent_quantity = Lending.objects.filter(
        item=item, returned_date__isnull=True
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    available = item.quantity - lent_quantity
    
    return JsonResponse({
        'id': item.pk,
        'name': item.name,
        'description': item.description,
        'quantity': item.quantity,
        'available': available,
        'location': item.location.name if item.location else None,
        'location_id': item.location.pk if item.location else None,
        'brand': item.brand,
        'model': item.model,
        'serial_number': item.serial_number,
        'barcode': item.barcode,
        'qr_code': item.qr_code,
        'condition': item.get_condition_display() if item.condition else None,
        'current_value': float(item.current_value) if item.current_value else None,
        'purchase_date': item.purchase_date.isoformat() if item.purchase_date else None,
        'purchase_price': float(item.purchase_price) if item.purchase_price else None,
    })
