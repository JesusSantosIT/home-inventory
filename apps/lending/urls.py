from django.urls import path
from . import views

app_name = 'lending'

urlpatterns = [
    path('', views.lending_dashboard, name='dashboard'),
    path('create/<int:item_pk>/', views.lending_create, name='create'),
    path('<int:pk>/return/', views.lending_return, name='return'),
    path('<int:pk>/', views.lending_detail, name='detail'),
]