from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta
from django.utils import timezone
from .models import CustomUser, Cargo, ContainerBooking, DepotCapacity

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone = forms.CharField(max_length=15, required=False)
    company_name = forms.CharField(max_length=100, required=False)
    user_type = forms.ChoiceField(choices=CustomUser.USER_TYPE_CHOICES, required=True)

    class Meta:
        model = CustomUser
        fields = ('email', 'username', 'password1', 'password2', 'user_type', 'phone', 'company_name')
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'initial' in kwargs and 'user_type' in kwargs['initial']:
            self.fields['user_type'].initial = kwargs['initial']['user_type']
            self.fields['user_type'].widget = forms.HiddenInput()

    def clean_user_type(self):
        user_type = self.cleaned_data.get('user_type')
        if user_type not in [choice[0] for choice in CustomUser.USER_TYPE_CHOICES]:
            raise ValidationError('Invalid user type selected.')
        return user_type

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.user_type = self.cleaned_data['user_type']
        user.phone = self.cleaned_data.get('phone', '')
        user.company_name = self.cleaned_data.get('company_name', '')
        if commit:
            user.save()
        return user

class CustomUserChangeForm(UserChangeForm):
    class Meta:
        model = CustomUser
        fields = ('email', 'username', 'user_type', 'phone', 'company_name')

class CargoForm(forms.ModelForm):
    arrival_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    pickup_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

    class Meta:
        model = Cargo
        fields = ['cargo_number', 'cargo_owner', 'storage', 'arrival_date', 'pickup_date']

class ContainerBookingForm(forms.ModelForm):
    booking_time = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'form-control'
        }),
        input_formats=['%Y-%m-%dT%H:%M']
    )
    depot = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(user_type='DEPOT'),
        empty_label="Select Depot",
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = ContainerBooking
        fields = ['depot', 'booking_time']

    def clean_booking_time(self):
        booking_time = self.cleaned_data.get('booking_time')
        if booking_time and booking_time < timezone.now():
            raise forms.ValidationError('Booking time must be in the future.')
        return booking_time

    def clean(self):
        cleaned_data = super().clean()
        if 'depot' not in cleaned_data or 'booking_time' not in cleaned_data:
            return cleaned_data

        depot = cleaned_data['depot']
        booking_time = cleaned_data['booking_time']

        # Check depot capacity
        depot_capacity, _ = DepotCapacity.objects.get_or_create(
            depot=depot,
            defaults={'total_capacity': 1}
        )
        if depot_capacity.is_full():
            self.add_error('depot', 'This depot is currently at full capacity.')

        # Check time slot availability
        bookings_count = ContainerBooking.get_bookings_in_timeslot(depot, booking_time)
        if bookings_count >= 3:
            self.add_error('booking_time', 'This time slot is full (maximum 3 bookings per hour).')

        return cleaned_data

        if not booking_time:
            raise forms.ValidationError('Booking time is required.')

        # Check if booking is in the future
        if booking_time < timezone.now():
            raise forms.ValidationError('Booking time must be in the future.')

        if depot:
            # Check depot capacity
            depot_capacity = depot.depot_capacity
            if depot_capacity.is_full():
                raise forms.ValidationError('Selected depot is currently at full capacity.')

            # Check number of bookings in the same time slot
            bookings_count = ContainerBooking.get_bookings_in_timeslot(depot, booking_time)
            if bookings_count >= 3:
                raise forms.ValidationError('Maximum bookings reached for this time slot. Please select another time.')

        return booking_time

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

class PickupScheduleForm(forms.Form):
    pickup_date = forms.DateField(widget=forms.DateInput(attrs={
        'type': 'date',
        'class': 'form-control',
        'min': datetime.now().strftime('%Y-%m-%d')
    }))
    pickup_time = forms.TimeField(widget=forms.TimeInput(attrs={
        'type': 'time',
        'class': 'form-control',
        'step': '3600'  # 1 hour steps
    }))

    def clean(self):
        cleaned_data = super().clean()
        pickup_date = cleaned_data.get('pickup_date')
        pickup_time = cleaned_data.get('pickup_time')

        if pickup_date and pickup_time:
            # Combine date and time
            from django.utils import timezone
            pickup_datetime = timezone.make_aware(
                datetime.combine(pickup_date, pickup_time)
            )

            # Check if datetime is in the past
            if pickup_datetime < timezone.now():
                raise forms.ValidationError('Cannot schedule pickup in the past')

            # Check if slot is available
            if Cargo.get_pickup_slot_count(pickup_datetime) >= 3:
                raise forms.ValidationError('This time slot is fully booked. Please select another time.')

            cleaned_data['pickup_datetime'] = pickup_datetime

        return cleaned_data