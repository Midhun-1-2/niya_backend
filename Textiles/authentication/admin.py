from django.contrib import admin

from .models import OTP, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'name', 'email', 'is_verified', 'is_mpin_set', 'is_active', 'date_joined')
    list_filter = ('is_verified', 'is_mpin_set', 'is_active')
    search_fields = ('phone_number', 'name', 'email')
    readonly_fields = ('date_joined', 'mpin', 'failed_mpin_attempts', 'mpin_locked_until')


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('user', 'purpose', 'created_at', 'expires_at', 'is_used', 'attempts')
    list_filter = ('purpose', 'is_used')
    search_fields = ('user__phone_number', 'user__email')
    readonly_fields = ('created_at',)
