from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages


def role_required(*allowed_roles):
    """Decorator to require specific user roles"""
    def decorator(view_func):
        @login_required
        def wrapper(request, *args, **kwargs):
            # Superusers always have admin-level access regardless of profile role
            if request.user.is_superuser and 'admin' in allowed_roles:
                return view_func(request, *args, **kwargs)

            if not hasattr(request.user, 'profile'):
                messages.error(request, 'You need to complete your profile first.')
                return redirect('users:profile')

            user_role = request.user.profile.role
            if user_role not in allowed_roles:
                messages.error(request, 'You do not have permission to access this page.')
                return redirect('dashboard')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def admin_required(view_func):
    """Decorator to require admin role"""
    return role_required('admin')(view_func)


def editor_required(view_func):
    """Decorator to require editor or admin role"""
    return role_required('admin', 'editor')(view_func)


def viewer_required(view_func):
    """Decorator to require viewer, editor, or admin role"""
    return role_required('admin', 'editor', 'viewer', 'lender')(view_func)


def lender_or_above(view_func):
    """Decorator to require lender, viewer, editor, or admin role"""
    return role_required('admin', 'editor', 'viewer', 'lender')(view_func)
