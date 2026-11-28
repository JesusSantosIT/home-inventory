from django.urls import path
from . import views

app_name = 'locations'

urlpatterns = [
    path('', views.location_list, name='location_list'),
    path('create/', views.location_create, name='location_create'),
    path('<int:pk>/', views.location_detail, name='location_detail'),
    path('<int:pk>/update/', views.location_update, name='location_update'),
    path('<int:pk>/delete/', views.location_delete, name='location_delete'),
    path('<int:pk>/images/<int:image_pk>/delete/', views.location_delete_image, name='delete_image'),
    path('create/<int:parent_pk>/', views.location_create, name='location_create_child'),
    path('<int:pk>/barcode/', views.generate_barcode, name='generate_barcode'),
    path('<int:pk>/qr-code/', views.generate_qr_code, name='generate_qr_code'),
    path('<int:pk>/children/', views.load_children, name='load_children'),
    path('scan/', views.scan_page, name='scan_page'),
    path('lookup/<path:code>/', views.lookup_code, name='lookup_code'),
    path('move/', views.move_location, name='move_location'),
    path('import/', views.import_locations, name='import_locations'),
]