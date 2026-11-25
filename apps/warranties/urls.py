from django.urls import path
from . import views

app_name = 'warranties'

urlpatterns = [
    path('', views.warranty_list, name='warranty_list'),
    path('create/<int:item_pk>/', views.warranty_create, name='warranty_create'),
    path('<int:pk>/', views.warranty_detail, name='warranty_detail'),
    path('<int:pk>/update/', views.warranty_update, name='warranty_update'),
    path('<int:pk>/delete/', views.warranty_delete, name='warranty_delete'),
]
