from django.contrib.auth.models import AbstractUser
from django.db import models
from datetime import timedelta

class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ('PORT', 'Port'),
        ('CFS', 'CFS'),
        ('DEPOT', 'Depot'),
        ('DRIVER', 'Truck Driver'),
    )
    
    user_type = models.CharField(max_length=10, choices=USER_TYPE_CHOICES)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, blank=True)
    company_name = models.CharField(max_length=100, blank=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'user_type']

class Cargo(models.Model):
    cargo_number = models.CharField(max_length=100, unique=True)
    cargo_owner = models.CharField(max_length=200)
    storage = models.CharField(max_length=200)
    arrival_date = models.DateField()
    pickup_date = models.DateField()
    scheduled_pickup_time = models.DateTimeField(null=True, blank=True)
    arrived_at_storage = models.BooleanField(default=False)
    is_picked_up = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    port = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'user_type': 'PORT'}, related_name='port_cargos')
    cfs = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'user_type': 'CFS'}, related_name='cfs_cargos', null=True, blank=True)
    driver = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, limit_choices_to={'user_type': 'DRIVER'}, related_name='driver_cargos', null=True, blank=True)
    cfs_received = models.BooleanField(default=False)
    cfs_picked_up = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.cargo_number} - {self.cargo_owner}"

    @classmethod
    def get_pickup_slot_count(cls, pickup_time):
        from django.utils import timezone
        start_time = pickup_time.replace(second=0, microsecond=0)
        end_time = start_time + timezone.timedelta(minutes=59, seconds=59)
        return cls.objects.filter(scheduled_pickup_time__range=(start_time, end_time)).count()

    class Meta:
        ordering = ['-created_at']

class DepotCapacity(models.Model):
    depot = models.OneToOneField(CustomUser, on_delete=models.CASCADE, limit_choices_to={'user_type': 'DEPOT'}, related_name='depot_capacity')
    total_capacity = models.PositiveIntegerField(help_text='Total number of containers that can be stored')
    current_capacity = models.PositiveIntegerField(default=0, help_text='Current number of containers stored')
    last_updated = models.DateTimeField(auto_now=True)

    def get_booked_count(self):
        """Get the count of active bookings for this depot"""
        return ContainerBooking.objects.filter(
            depot=self.depot,
            status__in=['PENDING', 'CONFIRMED']
        ).count()

    def available_capacity(self):
        """Calculate available capacity based on total capacity and current bookings"""
        return self.total_capacity - self.get_booked_count()

    def is_full(self):
        """Check if depot is at capacity based on current bookings"""
        return self.available_capacity() <= 0

    def __str__(self):
        booked = self.get_booked_count()
        return f"{self.depot.company_name} Capacity: {booked}/{self.total_capacity} ({self.available_capacity()} available)"

    class Meta:
        verbose_name_plural = 'Depot Capacities'

class ContainerBooking(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('CONFIRMED', 'Confirmed'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    )

    driver = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'user_type': 'DRIVER'}, related_name='container_bookings')
    depot = models.ForeignKey(CustomUser, on_delete=models.CASCADE, limit_choices_to={'user_type': 'DEPOT'}, related_name='depot_bookings')
    booking_time = models.DateTimeField()
    container_number = models.CharField(max_length=100, default='1')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Booking for {self.container_number} at {self.depot.company_name}"

    def save(self, *args, **kwargs):
        if not self.container_number:
            import uuid
            self.container_number = str(uuid.uuid4().hex[:8])
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # If deleting a confirmed booking, decrease capacity
        if self.status == 'CONFIRMED':
            depot_capacity = self.depot.depot_capacity
            depot_capacity.current_capacity = max(0, depot_capacity.current_capacity - 1)
            depot_capacity.save()
        super().delete(*args, **kwargs)

    @classmethod
    def get_bookings_in_timeslot(cls, depot, booking_time):
        # Get number of bookings in the same hour
        start_time = booking_time.replace(minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(hours=1)
        return cls.objects.filter(
            depot=depot,
            booking_time__gte=start_time,
            booking_time__lt=end_time,
            status__in=['PENDING', 'CONFIRMED']
        ).count()

    def clean(self):
        from django.core.exceptions import ValidationError
        # Check depot capacity
        depot_capacity = self.depot.depot_capacity
        if depot_capacity.is_full() and (self._state.adding or self.status == 'CONFIRMED'):
            raise ValidationError({
                'depot': 'This depot is currently at full capacity. Please choose another depot or try later.'
            })

        # Check time slot availability
        if self.booking_time:
            bookings_count = self.__class__.get_bookings_in_timeslot(self.depot, self.booking_time)
            if bookings_count >= 3 and (self._state.adding or self._loaded_values.get('booking_time') != self.booking_time):
                raise ValidationError({
                    'booking_time': 'This time slot is full (maximum 3 bookings per hour). Please select another time.'
                })

    class Meta:
        ordering = ['-booking_time']