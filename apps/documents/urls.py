from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    path('', views.document_list, name='document_list'),
    path('create/', views.document_create, name='document_create'),
    path('item/<int:item_pk>/create/', views.document_create, name='document_create_for_item'),
    path('<int:pk>/', views.document_detail, name='document_detail'),
    path('<int:pk>/update/', views.document_update, name='document_update'),
    path('<int:pk>/delete/', views.document_delete, name='document_delete'),
    path('<int:pk>/download/', views.document_download, name='document_download'),
]
