def user_role_processor(request):
    """Add user role information to all templates"""
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        return {
            'user_role': request.user.profile.role,
            'is_admin': request.user.profile.is_admin(),
            'is_editor': request.user.profile.is_editor(),
            'is_viewer': request.user.profile.is_viewer(),
            'is_lender': request.user.profile.is_lender(),
        }
    return {
        'user_role': None,
        'is_admin': False,
        'is_editor': False,
        'is_viewer': False,
        'is_lender': False,
    }
