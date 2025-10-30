from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('dashboard/port/', views.dashboard_view, name='port_dashboard'),
    path('dashboard/cfs/', views.dashboard_view, name='cfs_dashboard'),
    path('dashboard/depot/', views.dashboard_view, name='depot_dashboard'),
    path('dashboard/driver/', views.dashboard_view, name='driver_dashboard'),
    path('dashboard/driver/available/', views.driver_available_cargo, name='driver_available_cargo'),
    path('dashboard/driver/scheduled/', views.driver_scheduled_cargo, name='driver_scheduled_cargo'),
    path('dashboard/driver/picked/', views.driver_picked_cargo, name='driver_picked_cargo'),
    
    # Cargo management URLs
    path('cargo/', views.cargo_list, name='cargo_list'),
    path('cargo/create/', views.cargo_create, name='cargo_create'),
    path('cargo/<int:pk>/update/', views.cargo_update, name='cargo_update'),
    path('cargo/<int:pk>/delete/', views.cargo_delete, name='cargo_delete'),
    path('cargo/<int:pk>/toggle/<str:status_field>/', views.cargo_toggle_status, name='cargo_toggle_status'),
    path('cargo/<int:pk>/schedule-pickup/', views.schedule_pickup, name='schedule_pickup'),
    
    # Depot capacity management
    path('depot/capacity/', views.depot_capacity_view, name='depot_capacity'),
    
    # Container booking
    path('driver/container-bookings/', views.container_booking_list, name='container_booking_list'),
    path('driver/container-bookings/create/', views.container_booking_create, name='container_booking_create'),
]