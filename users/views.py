from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from rest_framework_simplejwt.tokens import RefreshToken
from .forms import CustomUserCreationForm, CargoForm, PickupScheduleForm, ContainerBookingForm
from .models import CustomUser, Cargo, DepotCapacity, ContainerBooking

def home(request):
    return render(request, 'home.html')

def register_view(request):
    from django.contrib import messages
    
    # Get user_type from URL and validate it
    user_type = request.GET.get('type', '').upper()
    valid_types = [choice[0] for choice in CustomUser.USER_TYPE_CHOICES]
    if user_type not in valid_types:
        messages.error(request, 'Invalid user type.')
        return redirect('home')
        
    if request.method == 'POST':
        # Add user_type to POST data
        post_data = request.POST.copy()
        post_data['user_type'] = user_type
        
        # Debug: Print POST data
        print("POST data:", post_data)
        
        form = CustomUserCreationForm(post_data)
        if not form.is_valid():
            print("Form errors:", form.errors)
            for field, errors in form.errors.items():
                messages.error(request, f"{field}: {', '.join(errors)}")
        else:
            try:
                # Save the user
                user = form.save()
                messages.success(request, 'Registration successful! Please login to continue.')
                return redirect('login')
            except Exception as e:
                print("Exception during save:", str(e))
                messages.error(request, f'Registration failed: {str(e)}')
    else:
        form = CustomUserCreationForm(initial={'user_type': user_type})
    
    return render(request, 'auth/register.html', {
        'form': form,
        'user_type': user_type
    })

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = CustomUser.objects.filter(email=email).first()
        if user and user.check_password(password):
            login(request, user)
            refresh = RefreshToken.for_user(user)
            
            # Determine the appropriate dashboard based on user type
            user_type = user.user_type.lower()
            if user_type == 'port':
                dashboard_url = 'port_dashboard'
            elif user_type == 'cfs':
                dashboard_url = 'cfs_dashboard'
            elif user_type == 'depot':
                dashboard_url = 'depot_dashboard'
            elif user_type == 'driver':
                dashboard_url = 'driver_dashboard'
            else:
                dashboard_url = 'dashboard'
            
            response = redirect(dashboard_url)
            response.set_cookie(
                'access_token',
                str(refresh.access_token),
                httponly=True
            )
            return response
        else:
            from django.contrib import messages
            messages.error(request, 'Invalid email or password.')
    return render(request, 'auth/login.html')

@login_required
def logout_view(request):
    logout(request)
    response = redirect('home')
    response.delete_cookie('access_token')
    return response

@login_required
def dashboard_view(request):
    user_type = request.user.user_type.lower()
    template_name = f'dashboard/{user_type}_dashboard.html'
    
    # Add cargo list for port and cfs users
    context = {}
    if user_type == 'port':
        context['cargo_list'] = Cargo.objects.filter(port=request.user)
    elif user_type == 'cfs':
        context['cargo_list'] = Cargo.objects.filter(storage__icontains=request.user.company_name)
    elif user_type == 'driver':
        # Show cargo for the driver's company
        context['cargo_list'] = Cargo.objects.filter(
            cargo_owner__icontains=request.user.company_name,
            driver__isnull=True  # Only show unassigned cargo
        )
    
    return render(request, template_name, context)

@login_required
def cargo_list(request):
    if request.user.user_type != 'PORT':
        messages.error(request, 'Access denied. Only port users can view cargo list.')
        return redirect('dashboard')
    
    cargo_list = Cargo.objects.filter(port=request.user)
    return render(request, 'dashboard/cargo_list.html', {'cargo_list': cargo_list})

@login_required
def cargo_create(request):
    if request.user.user_type != 'PORT':
        messages.error(request, 'Access denied. Only port users can create cargo.')
        return redirect('dashboard')
    
    if request.method == 'POST':
        form = CargoForm(request.POST)
        if form.is_valid():
            cargo = form.save(commit=False)
            cargo.port = request.user
            cargo.save()
            messages.success(request, 'Cargo created successfully.')
            return redirect('cargo_list')
    else:
        form = CargoForm()
    
    return render(request, 'dashboard/cargo_form.html', {'form': form, 'title': 'Create Cargo'})

@login_required
def cargo_update(request, pk):
    if request.user.user_type != 'PORT':
        messages.error(request, 'Access denied. Only port users can update cargo.')
        return redirect('dashboard')
    
    cargo = get_object_or_404(Cargo, pk=pk, port=request.user)
    
    if request.method == 'POST':
        form = CargoForm(request.POST, instance=cargo)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cargo updated successfully.')
            return redirect('cargo_list')
    else:
        form = CargoForm(instance=cargo)
    
    return render(request, 'dashboard/cargo_form.html', {'form': form, 'title': 'Update Cargo'})

@login_required
def cargo_delete(request, pk):
    if request.user.user_type != 'PORT':
        messages.error(request, 'Access denied. Only port users can delete cargo.')
        return redirect('dashboard')
    
    cargo = get_object_or_404(Cargo, pk=pk, port=request.user)
    
    if request.method == 'POST':
        cargo.delete()
        messages.success(request, 'Cargo deleted successfully.')
        return redirect('cargo_list')
    
    return render(request, 'dashboard/cargo_confirm_delete.html', {'cargo': cargo})

@login_required
@login_required
def container_booking_list(request):
    if request.user.user_type != 'DRIVER':
        messages.error(request, 'Access denied. Only drivers can view container bookings.')
        return redirect('dashboard')
    
    bookings = ContainerBooking.objects.filter(driver=request.user).order_by('-booking_time')
    return render(request, 'dashboard/driver/container_bookings.html', {'bookings': bookings})

@login_required
def container_booking_create(request):
    if request.user.user_type != 'DRIVER':
        messages.error(request, 'Access denied. Only drivers can book container slots.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = ContainerBookingForm(request.POST)
        if form.is_valid():
            try:
                booking = form.save(commit=False)
                booking.driver = request.user
                # Let the model use its default status of 'PENDING'
                booking.save()
                
                messages.success(request, 'Container slot booked successfully. Waiting for confirmation.')
                return redirect('container_booking_list')
            except ValidationError as e:
                if hasattr(e, 'message_dict'):
                    for field, errors in e.message_dict.items():
                        for error in errors:
                            form.add_error(field if field != '__all__' else None, error)
                else:
                    form.add_error(None, str(e))
            except Exception as e:
                form.add_error(None, f'An error occurred: {str(e)}')
    else:
        form = ContainerBookingForm()

    # Get depot capacities for context
    depot_capacities = DepotCapacity.objects.select_related('depot').all()
    depot_info = [
        {
            'name': cap.depot.company_name,
            'total': cap.total_capacity,
            'current': cap.current_capacity,
            'available': cap.available_capacity()
        }
        for cap in depot_capacities
    ]
    
    return render(request, 'dashboard/driver/container_booking_form.html', {
        'form': form,
        'depot_info': depot_info
    })

@login_required
def depot_capacity_view(request):
    if request.user.user_type != 'DEPOT':
        messages.error(request, 'Access denied. Only depot users can manage capacity.')
        return redirect('dashboard')
    
    depot_capacity, created = DepotCapacity.objects.get_or_create(
        depot=request.user,
        defaults={'total_capacity': 0}
    )
    
    # Get active bookings for this depot
    active_bookings = ContainerBooking.objects.filter(
        depot=request.user,
        status__in=['PENDING', 'CONFIRMED']
    ).select_related('driver').order_by('booking_time')
    
    if request.method == 'POST':
        try:
            total_capacity = int(request.POST.get('total_capacity', 0))
            booked_count = depot_capacity.get_booked_count()
            
            if total_capacity < booked_count:
                messages.error(request, f'Total capacity cannot be less than current bookings ({booked_count}).')
            else:
                depot_capacity.total_capacity = total_capacity
                depot_capacity.save()
                messages.success(request, 'Depot capacity updated successfully.')
                return redirect('depot_capacity')
        except ValueError:
            messages.error(request, 'Please enter a valid number for total capacity.')
    
    return render(request, 'dashboard/depot_capacity.html', {
        'depot_capacity': depot_capacity,
        'active_bookings': active_bookings
    })

def cargo_toggle_status(request, pk, status_field):
    user_type = request.user.user_type
    if user_type not in ['PORT', 'CFS']:
        messages.error(request, 'Access denied. Only port and CFS users can update cargo status.')
        return redirect('dashboard')
    
    if user_type == 'PORT':
        cargo = get_object_or_404(Cargo, pk=pk, port=request.user)
        allowed_fields = ['arrived_at_storage', 'is_picked_up']
    else:  # CFS
        cargo = get_object_or_404(Cargo, pk=pk, storage__icontains=request.user.company_name)
        allowed_fields = ['cfs_received', 'cfs_picked_up']
    
    if status_field not in allowed_fields:
        messages.error(request, 'Invalid status field.')
        return redirect('dashboard')
    
    # Update the status
    setattr(cargo, status_field, not getattr(cargo, status_field))
    if user_type == 'CFS' and status_field == 'cfs_received':
        cargo.cfs = request.user  # Assign the CFS when cargo is received
    cargo.save()
    
    # Set status name based on user type and field
    if user_type == 'PORT':
        status_name = 'Arrival at Storage' if status_field == 'arrived_at_storage' else 'Pickup'
        current_value = 'Completed' if getattr(cargo, status_field) else 'Pending'
    else:  # CFS
        status_name = 'Receipt' if status_field == 'cfs_received' else 'Pickup'
        current_value = 'Received' if status_field == 'cfs_received' else 'Picked Up'
        if not getattr(cargo, status_field):
            current_value = f'Awaiting {status_name}'
    
    messages.success(request, f'Cargo {status_name} status updated to {current_value}.')
    return redirect('dashboard')

@login_required
def driver_available_cargo(request):
    if request.user.user_type != 'DRIVER':
        messages.error(request, 'Access denied. Only drivers can view available cargo.')
        return redirect('dashboard')
    
    cargo_list = Cargo.objects.filter(
        cargo_owner__icontains=request.user.company_name,
        driver__isnull=True,
        is_picked_up=False
    )
    
    return render(request, 'dashboard/driver/available_cargo.html', {
        'cargo_list': cargo_list
    })

@login_required
def driver_scheduled_cargo(request):
    if request.user.user_type != 'DRIVER':
        messages.error(request, 'Access denied. Only drivers can view scheduled cargo.')
        return redirect('dashboard')
    
    cargo_list = Cargo.objects.filter(
        driver=request.user,
        is_picked_up=False
    ).order_by('scheduled_pickup_time')
    
    return render(request, 'dashboard/driver/scheduled_cargo.html', {
        'cargo_list': cargo_list
    })

@login_required
def driver_picked_cargo(request):
    if request.user.user_type != 'DRIVER':
        messages.error(request, 'Access denied. Only drivers can view picked up cargo.')
        return redirect('dashboard')
    
    cargo_list = Cargo.objects.filter(
        driver=request.user,
        is_picked_up=True
    ).order_by('-scheduled_pickup_time')
    
    return render(request, 'dashboard/driver/picked_cargo.html', {
        'cargo_list': cargo_list
    })

@login_required
def schedule_pickup(request, pk):
    if request.user.user_type != 'DRIVER':
        messages.error(request, 'Access denied. Only drivers can schedule pickups.')
        return redirect('dashboard')
    
    cargo = get_object_or_404(Cargo, pk=pk, cargo_owner__icontains=request.user.company_name, driver__isnull=True)
    
    if request.method == 'POST':
        form = PickupScheduleForm(request.POST)
        if form.is_valid():
            # Get the validated datetime
            pickup_datetime = form.cleaned_data['pickup_datetime']
            
            # Schedule the pickup
            cargo.scheduled_pickup_time = pickup_datetime
            cargo.driver = request.user
            cargo.save()
            
            messages.success(request, 'Pickup scheduled successfully.')
            return redirect('dashboard')
    else:
        form = PickupScheduleForm()
    
    return render(request, 'dashboard/schedule_pickup.html', {
        'form': form,
        'cargo': cargo
    })