from django.urls import path
from . import views

app_name = 'items'

urlpatterns = [
    path('', views.item_list, name='item_list'),
    path('create/', views.item_create, name='item_create'),
    path('create/<int:location_pk>/', views.item_create, name='item_create_for_location'),
    path('<int:pk>/', views.item_detail, name='item_detail'),
    path('<int:pk>/update/', views.item_update, name='item_update'),
    path('<int:pk>/delete/', views.item_delete, name='item_delete'),
    path('bulk-action/', views.item_bulk_action, name='item_bulk_action'),
    path('<int:pk>/barcode/', views.generate_barcode, name='generate_barcode'),
    path('<int:pk>/qr-code/', views.generate_qr_code, name='generate_qr_code'),
    path('export/csv/', views.export_csv, name='export_csv'),
    path('export/pdf/', views.export_pdf, name='export_pdf'),
    path('categories/', views.category_list, name='category_list'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/<int:pk>/update/', views.category_update, name='category_update'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
    path('import/', views.import_items, name='import_items'),
    path('label-templates/', views.label_template_list, name='label_template_list'),
    path('label-templates/create/', views.label_template_create, name='label_template_create'),
    path('label-templates/<int:pk>/update/', views.label_template_update, name='label_template_update'),
    path('label-templates/<int:pk>/delete/', views.label_template_delete, name='label_template_delete'),
    path('<int:pk>/print-label/', views.print_label, name='print_label'),
    path('print-bulk-labels/', views.print_bulk_labels, name='print_bulk_labels'),
]