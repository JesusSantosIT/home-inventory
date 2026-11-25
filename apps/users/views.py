from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.views import LoginView as BaseLoginView
from django.http import HttpResponse
from .models import UserProfile, Household, HouseholdMember, ExternalHousehold
from .forms import UserProfileForm, UserProfileAdminForm, HouseholdForm
from .middleware import is_account_locked, reset_failed_login_attempts
from .decorators import admin_required
import hashlib
import secrets
from django_ratelimit.decorators import ratelimit
from django.contrib.auth.models import User


def rate_limited(request, exception):
    """Handler for django-ratelimit exceeded requests (RATELIMIT_VIEW)."""
    return HttpResponse(
        '<h1>429 - Too Many Requests</h1><p>Please slow down and try again later.</p>',
        status=429,
        content_type='text/html'
    )


def _hash_api_key(key):
    """SHA-256 hash for API key storage/lookup (keys are high-entropy tokens)."""
    return hashlib.sha256(key.encode()).hexdigest()


class CustomLoginView(BaseLoginView):
    """Custom login view with account lockout and rate limiting"""
    template_name = 'registration/login.html'
    
    @ratelimit(key='post:username', rate='5/m', method='POST', block=True)
    def post(self, request, *args, **kwargs):
        username = request.POST.get('username')
        
        # Check if account is locked
        if is_account_locked(username):
            messages.error(request, 'Account locked due to too many failed login attempts. Please try again in 30 minutes.')
            return self.get(request, *args, **kwargs)
        
        response = super().post(request, *args, **kwargs)
        
        # If login successful, reset failed attempts
        if response.status_code == 302:  # Redirect on success
            reset_failed_login_attempts(username)
        
        return response


@login_required
def profile_view(request):
    """View and edit user profile"""
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('users:profile')
    else:
        form = UserProfileForm(instance=profile)
    
    return render(request, 'users/profile.html', {'form': form, 'profile': profile})


@login_required
def admin_manage_roles(request):
    """Admin-only view to manage user roles"""
    if not request.user.is_superuser and not request.user.profile.is_admin():
        messages.error(request, 'You do not have permission to manage user roles.')
        return redirect('dashboard')
    
    users = UserProfile.objects.select_related('user').all()
    
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        new_role = request.POST.get('new_role')
        
        if user_id and new_role:
            try:
                profile = UserProfile.objects.get(user_id=user_id)
                if new_role not in dict(UserProfile.ROLE_CHOICES):
                    messages.error(request, 'Invalid role selected.')
                    return redirect('users:admin_manage_roles')
                if profile.user_id == request.user.id and new_role != 'admin':
                    messages.error(request, 'You cannot remove your own admin role.')
                    return redirect('users:admin_manage_roles')
                profile.role = new_role
                profile.save()
                messages.success(request, f'Role updated for {profile.user.username} to {new_role}.')
            except UserProfile.DoesNotExist:
                messages.error(request, 'User profile not found.')
        
        return redirect('users:admin_manage_roles')
    
    return render(request, 'users/admin_manage_roles.html', {
        'users': users,
        'role_choices': UserProfile.ROLE_CHOICES
    })


@login_required
def household_list(request):
    """List all households for the current user"""
    if request.user.is_superuser:
        # Admin can see all households
        households = Household.objects.all()
    else:
        # Regular users can only see households they're members of
        households = Household.objects.filter(members=request.user)
    
    return render(request, 'users/household_list.html', {
        'households': households
    })


@login_required
def household_create(request):
    """Create a new household"""
    if request.method == 'POST':
        form = HouseholdForm(request.POST)
        if form.is_valid():
            household = form.save(commit=False)
            household.created_by = request.user
            household.save()
            HouseholdMember.objects.create(
                household=household,
                user=request.user,
                role='admin'
            )
            messages.success(request, f'Household "{household.name}" created successfully.')
            return redirect('users:household_detail', pk=household.pk)
    else:
        form = HouseholdForm()
    
    return render(request, 'users/household_form.html', {'form': form})


@login_required
def household_detail(request, pk):
    """View household details"""
    household = get_object_or_404(Household, pk=pk)
    
    # Check if user is a member
    if not request.user.is_superuser:
        member = HouseholdMember.objects.filter(household=household, user=request.user).first()
        if not member:
            messages.error(request, 'You do not have permission to view this household.')
            return redirect('users:household_list')
    
    members = HouseholdMember.objects.filter(household=household).select_related('user')
    
    # Build breadcrumb navigation
    from django.urls import reverse
    breadcrumbs = [
        {'name': 'Households', 'url': reverse('users:household_list')},
        {'name': household.name, 'url': None}
    ]
    
    return render(request, 'users/household_detail.html', {
        'household': household,
        'members': members,
        'member': member if not request.user.is_superuser else None,
        'breadcrumbs': breadcrumbs,
    })


@login_required
def household_invite(request, pk):
    """Invite a user to a household"""
    household = get_object_or_404(Household, pk=pk)
    
    # Check if user is an admin of the household
    if not request.user.is_superuser:
        member = HouseholdMember.objects.filter(household=household, user=request.user).first()
        if not member or member.role != 'admin':
            messages.error(request, 'Only admins can invite users to households.')
            return redirect('users:household_detail', pk=pk)
    
    if request.method == 'POST':
        username = request.POST.get('username')
        role = request.POST.get('role', 'member')
        
        try:
            user_to_invite = User.objects.get(username=username)
            # Check if already a member
            if household.members.filter(id=user_to_invite.id).exists():
                messages.warning(request, f'{username} is already a member.')
            else:
                HouseholdMember.objects.create(
                    household=household,
                    user=user_to_invite,
                    role=role
                )
                messages.success(request, f'{username} has been added to the household.')
        except User.DoesNotExist:
            messages.error(request, f'User {username} not found.')
        
        return redirect('users:household_detail', pk=pk)
    
    return render(request, 'users/household_invite.html', {'household': household})


@admin_required
def external_households(request):
    """Browse connected external households - click one to see their items."""
    households = ExternalHousehold.objects.filter(is_instance_key=False)

    return render(request, 'users/external_households_browse.html', {
        'households': households
    })


@admin_required
def external_households_manage(request):
    """Manage external household connections (keys, URLs, IPs, etc.)"""
    households = ExternalHousehold.objects.filter(is_instance_key=False)
    instance_household = ExternalHousehold.objects.filter(is_instance_key=True).first()

    return render(request, 'users/external_households.html', {
        'households': households,
        'instance_household': instance_household
    })


@admin_required
def instance_api_key_regenerate(request):
    """Generate or rotate the shared instance API key.

    This single key can be shared with any external household - they use it
    as X-API-Key when calling this instance's API endpoints."""
    if request.method != 'POST':
        return redirect('users:external_households')

    household = ExternalHousehold.objects.filter(is_instance_key=True).first()
    if household is None:
        household = ExternalHousehold.objects.create(
            name='Instance (shared key)',
            base_url=request.build_absolute_uri('/'),
            is_instance_key=True,
        )

    api_key = secrets.token_urlsafe(32)
    household.api_key_hash = _hash_api_key(api_key)
    household.api_key_for_them = api_key
    household.active = True
    household.save()

    messages.success(request, 'Instance API key generated. Share it with households that should access your inventory.')
    messages.info(request, f'Instance API key: {api_key}')
    return redirect('users:external_households')


@admin_required
def external_household_create(request):
    """Create a new external household connection"""
    if request.method == 'POST':
        name = request.POST.get('name')
        base_url = request.POST.get('base_url')
        remote_api_key = request.POST.get('remote_api_key', '').strip()
        allowed_ips = request.POST.get('allowed_ips', '')
        api_key_expires = request.POST.get('api_key_expires')
        
        if not name or not base_url:
            messages.error(request, 'Name and base URL are required.')
            return redirect('users:external_households')
        
        # Generate one API key: stored hashed for lookup, plaintext copy kept
        # in api_key_for_them so admins can view/copy/share it
        api_key = secrets.token_urlsafe(32)

        # Parse expiration date if provided
        expires_date = None
        if api_key_expires:
            try:
                from datetime import datetime
                expires_date = datetime.fromisoformat(api_key_expires)
            except ValueError:
                messages.warning(request, 'Invalid expiration date format. Key will not expire.')

        ExternalHousehold.objects.create(
            name=name,
            base_url=base_url,
            api_key_hash=_hash_api_key(api_key),
            api_key_for_them=api_key,
            remote_api_key=remote_api_key,
            allowed_ips=allowed_ips,
            api_key_expires=expires_date
        )
        
        messages.success(request, f'External household "{name}" created successfully.')
        messages.info(request, f'Your API key for them: {api_key}')
        return redirect('users:external_households')
    
    return render(request, 'users/external_household_form.html')


@admin_required
def external_household_update(request, pk):
    """Edit an external household connection (name, URL, their API key, etc.)"""
    household = get_object_or_404(ExternalHousehold, pk=pk, is_instance_key=False)

    if request.method == 'POST':
        household.name = request.POST.get('name', household.name).strip() or household.name
        household.base_url = request.POST.get('base_url', household.base_url).strip() or household.base_url
        # Empty remote_api_key field means "keep existing"
        remote_key = request.POST.get('remote_api_key', '').strip()
        if remote_key:
            household.remote_api_key = remote_key
        household.allowed_ips = request.POST.get('allowed_ips', '')
        household.active = bool(request.POST.get('active'))

        api_key_expires = request.POST.get('api_key_expires', '')
        if api_key_expires:
            try:
                from datetime import datetime
                household.api_key_expires = datetime.fromisoformat(api_key_expires)
            except ValueError:
                messages.warning(request, 'Invalid expiration date format - unchanged.')
        else:
            household.api_key_expires = None

        household.save()
        messages.success(request, f'External household "{household.name}" updated.')
        return redirect('users:external_households')

    # Prefill datetime-local input value
    expires_value = ''
    if household.api_key_expires:
        expires_value = household.api_key_expires.strftime('%Y-%m-%dT%H:%M')

    return render(request, 'users/external_household_form.html', {
        'household': household,
        'expires_value': expires_value,
    })


@admin_required
def external_households_all_items(request):
    """Browse/search items across ALL connected households at once.

    Fetches each active household's available-items in parallel and merges
    the results, tagged with the household they came from."""
    from concurrent.futures import ThreadPoolExecutor
    from .remote_api import fetch_available_items, RemoteAPIError

    households = (
        ExternalHousehold.objects
        .filter(is_instance_key=False, active=True)
        .exclude(remote_api_key='')
    )

    def fetch(household):
        try:
            data = fetch_available_items(household)
            return household, data.get('items', []), None
        except RemoteAPIError as e:
            return household, [], str(e)

    all_items = []
    errors = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        for household, items, error in executor.map(fetch, households):
            if error:
                errors.append({'household': household, 'error': error})
            for item in items:
                item['household_pk'] = household.pk
                item['household_name'] = household.name
                all_items.append(item)

    # Server-side search across merged results
    search = request.GET.get('search', '').strip().lower()
    if search:
        def matches(item):
            haystack = ' '.join(str(item.get(f) or '') for f in
                                ('name', 'description', 'location', 'brand', 'model', 'serial_number'))
            return search in haystack.lower()
        all_items = [i for i in all_items if matches(i)]

    all_items.sort(key=lambda i: (i['household_name'].lower(), i['name'].lower()))

    from django.urls import reverse
    breadcrumbs = [
        {'name': 'External Households', 'url': reverse('users:external_households')},
        {'name': 'All Items', 'url': None},
    ]

    return render(request, 'users/external_households_all_items.html', {
        'items': all_items,
        'errors': errors,
        'search': request.GET.get('search', ''),
        'households_count': households.count(),
        'breadcrumbs': breadcrumbs,
    })


@admin_required
def external_household_items(request, pk):
    """Browse items a remote household has available for lending.

    Calls the remote instance's API using the remote_api_key stored on the
    household record. Fails closed: without a valid key the remote side
    returns 401 and nothing is shown."""
    from .remote_api import fetch_available_items, RemoteAPIError

    household = get_object_or_404(
        ExternalHousehold, pk=pk, is_instance_key=False
    )

    items = []
    error = None
    try:
        data = fetch_available_items(household)
        items = data.get('items', [])
    except RemoteAPIError as e:
        error = str(e)

    # Build breadcrumb navigation
    from django.urls import reverse
    breadcrumbs = [
        {'name': 'External Households', 'url': reverse('users:external_households')},
        {'name': household.name, 'url': None},
        {'name': 'Available Items', 'url': None},
    ]

    return render(request, 'users/external_household_items.html', {
        'household': household,
        'items': items,
        'error': error,
        'breadcrumbs': breadcrumbs,
    })


@admin_required
def external_household_request_item(request, pk):
    """Request to borrow an item from a remote household (outbound API call)."""
    from .remote_api import request_lending, fetch_item_detail, RemoteAPIError

    household = get_object_or_404(
        ExternalHousehold, pk=pk, is_instance_key=False
    )

    item_id = request.GET.get('item_id') or request.POST.get('item_id')
    item_info = None
    if item_id:
        try:
            item_info = fetch_item_detail(household, item_id)
        except RemoteAPIError:
            item_info = {'id': item_id, 'name': f'Item #{item_id}'}

    result = None
    error = None

    if request.method == 'POST':
        quantity = request.POST.get('quantity', '1')
        borrower_name = request.POST.get('borrower_name', '').strip()
        due_date = request.POST.get('due_date', '').strip()

        if not borrower_name:
            error = 'Borrower name is required.'
        else:
            try:
                quantity = max(1, int(quantity))
            except (TypeError, ValueError):
                quantity = 1
                error = 'Invalid quantity - using 1.'

            if not error:
                try:
                    result = request_lending(
                        household, item_id, quantity, borrower_name,
                        due_date=due_date or None,
                    )
                except RemoteAPIError as e:
                    error = str(e)

    from django.urls import reverse
    breadcrumbs = [
        {'name': 'External Households', 'url': reverse('users:external_households')},
        {'name': household.name, 'url': reverse('users:external_household_items', args=[household.pk])},
        {'name': 'Request Item', 'url': None},
    ]

    return render(request, 'users/external_household_request.html', {
        'household': household,
        'item_id': item_id,
        'item_info': item_info,
        'result': result,
        'error': error,
        'default_borrower': request.user.get_full_name() or request.user.username,
        'breadcrumbs': breadcrumbs,
    })


@admin_required
def external_household_delete(request, pk):
    """Delete an external household connection"""
    household = get_object_or_404(ExternalHousehold, pk=pk)
    
    if request.method == 'POST':
        household.delete()
        messages.success(request, f'External household "{household.name}" deleted.')
        return redirect('users:external_households')
    
    return render(request, 'users/external_household_confirm_delete.html', {
        'household': household
    })


@admin_required
def external_household_regenerate_key(request, pk):
    """Regenerate API key for an external household"""
    household = get_object_or_404(ExternalHousehold, pk=pk)

    if request.method == 'POST':
        # Generate one new API key (hash for lookup + plaintext for sharing)
        api_key = secrets.token_urlsafe(32)
        household.api_key_hash = _hash_api_key(api_key)
        household.api_key_for_them = api_key
        household.save()
        
        messages.success(request, f'API key regenerated for "{household.name}".')
        messages.info(request, f'New API key for them: {household.api_key_for_them}')
        return redirect('users:external_households')
    
    return render(request, 'users/external_household_regenerate_key.html', {
        'household': household
    })
