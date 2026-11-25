from django.urls import path
from . import views
from . import api_views

app_name = 'users'

urlpatterns = [
    path('profile/', views.profile_view, name='profile'),
    path('admin/roles/', views.admin_manage_roles, name='admin_manage_roles'),
    path('households/', views.household_list, name='household_list'),
    path('households/create/', views.household_create, name='household_create'),
    path('households/<int:pk>/', views.household_detail, name='household_detail'),
    path('households/<int:pk>/invite/', views.household_invite, name='household_invite'),
    # External households
    path('external-households/', views.external_households, name='external_households'),
    path('external-households/manage/', views.external_households_manage, name='external_households_manage'),
    path('external-households/all-items/', views.external_households_all_items, name='external_households_all_items'),
    path('external-households/create/', views.external_household_create, name='external_household_create'),
    path('external-households/<int:pk>/update/', views.external_household_update, name='external_household_update'),
    path('external-households/<int:pk>/items/', views.external_household_items, name='external_household_items'),
    path('external-households/<int:pk>/request-item/', views.external_household_request_item, name='external_household_request_item'),
    path('external-households/<int:pk>/delete/', views.external_household_delete, name='external_household_delete'),
    path('external-households/<int:pk>/regenerate-key/', views.external_household_regenerate_key, name='external_household_regenerate_key'),
    path('instance-api-key/regenerate/', views.instance_api_key_regenerate, name='instance_api_key_regenerate'),
    # API endpoints for external households
    path('api/v1/available-items/', api_views.api_available_items, name='api_available_items'),
    path('api/v1/request-lending/', api_views.api_request_lending, name='api_request_lending'),
    path('api/v1/items/<int:item_id>/', api_views.api_item_detail, name='api_item_detail'),
]