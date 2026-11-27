from django.contrib.auth.signals import user_login_failed
from django.core.cache import cache
from django.dispatch import receiver
from .models import UserProfile


class ForceSecureMiddleware:
    """Treat every request as HTTPS.

    For deployments where TLS is always terminated upstream and the app
    is not directly reachable over plain HTTP (e.g. Synology's reverse
    proxy, which doesn't send X-Forwarded-Proto). Enable with
    ASSUME_HTTPS=1. Must run before SecurityMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # WSGIRequest._get_scheme() reads wsgi.url_scheme from the environ
        # (same dict as META) - setting it makes scheme/is_secure() return
        # 'https'/'True' for every request.
        request.META['wsgi.url_scheme'] = 'https'
        return self.get_response(request)


class EnsureUserProfileMiddleware:
    """Middleware to automatically create UserProfile for new users"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Ensure authenticated users have a profile
        if request.user.is_authenticated and not hasattr(request.user, 'profile'):
            UserProfile.objects.get_or_create(user=request.user)
        
        response = self.get_response(request)
        return response


@receiver(user_login_failed)
def track_failed_login(sender, credentials, request, **kwargs):
    """Track failed login attempts and lock account after too many failures"""
    username = credentials.get('username')
    if username:
        # Increment failed attempts counter
        cache_key = f'failed_login_{username}'
        attempts = cache.get(cache_key, 0) + 1
        cache.set(cache_key, attempts, timeout=300)  # 5 minutes
        
        # Lock account after 5 failed attempts
        if attempts >= 5:
            cache.set(f'locked_{username}', True, timeout=1800)  # Lock for 30 minutes


def is_account_locked(username):
    """Check if an account is locked due to too many failed login attempts"""
    return cache.get(f'locked_{username}', False)


def reset_failed_login_attempts(username):
    """Reset failed login attempts after successful login"""
    cache.delete(f'failed_login_{username}')
    cache.delete(f'locked_{username}')
