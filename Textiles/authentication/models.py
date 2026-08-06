from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

phone_validator = RegexValidator(
    regex=r'^[6-9]\d{9}$',
    message='Enter a valid 10-digit mobile number.',
)


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, phone_number, name, email, password=None, **extra_fields):
        if not phone_number:
            raise ValueError('Phone number is required.')
        if not email:
            raise ValueError('Email is required.')
        email = self.normalize_email(email)
        user = self.model(phone_number=phone_number, name=name, email=email, **extra_fields)
        if password:
            user.password = make_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, phone_number, name, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(phone_number, name, email, password, **extra_fields)

    def create_superuser(self, phone_number, name, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)
        extra_fields.setdefault('is_active', True)
        return self._create_user(phone_number, name, email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    phone_number = models.CharField(max_length=10, unique=True, validators=[phone_validator])
    name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)

    house_number = models.CharField(max_length=100, verbose_name='Flat / House / Door No.')
    address = models.CharField(max_length=255, verbose_name='Street / Area')
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    pincode = models.CharField(max_length=20)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    mpin = models.CharField(max_length=128, blank=True)
    is_mpin_set = models.BooleanField(default=False)
    failed_mpin_attempts = models.PositiveSmallIntegerField(default=0)
    mpin_locked_until = models.DateTimeField(null=True, blank=True)

    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['name', 'email']

    def __str__(self):
        return f'{self.name} ({self.phone_number})'

    def set_mpin(self, raw_mpin):
        self.mpin = make_password(raw_mpin)
        self.is_mpin_set = True
        self.failed_mpin_attempts = 0
        self.mpin_locked_until = None

    def is_mpin_locked(self):
        return bool(self.mpin_locked_until and self.mpin_locked_until > timezone.now())


class OTP(models.Model):
    PURPOSE_CHOICES = [
        ('register', 'Registration'),
        ('mpin_reset', 'MPIN Reset'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='otps')
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def is_valid(self):
        return not self.is_used and timezone.now() <= self.expires_at

    def __str__(self):
        return f'{self.purpose} OTP for {self.user.phone_number}'
