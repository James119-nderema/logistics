from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import CustomUser, Cargo

class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    list_display = ('email', 'username', 'user_type', 'is_staff', 'is_active',)
    list_filter = ('user_type', 'is_staff', 'is_active',)
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Permissions', {'fields': ('is_staff', 'is_active')}),
        ('Personal Info', {'fields': ('user_type', 'phone', 'company_name')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2', 'user_type', 'phone', 'company_name', 'is_staff', 'is_active')}
        ),
    )
    search_fields = ('email', 'username')
    ordering = ('email',)

admin.site.register(CustomUser, CustomUserAdmin)

@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ('cargo_number', 'cargo_owner', 'storage', 'arrival_date', 'pickup_date', 'arrived_at_storage', 'is_picked_up', 'port')
    list_filter = ('arrived_at_storage', 'is_picked_up', 'port')
    search_fields = ('cargo_number', 'cargo_owner', 'storage')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)