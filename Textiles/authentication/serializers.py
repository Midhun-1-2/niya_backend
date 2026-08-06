import re

from rest_framework import serializers

from .models import User, phone_validator

MPIN_REGEX = re.compile(r'^\d{4}$')


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'name', 'phone_number', 'email',
            'house_number', 'address', 'city', 'state', 'country', 'pincode',
            'latitude', 'longitude', 'is_mpin_set', 'is_staff',
        ]


class UserAdminSerializer(serializers.ModelSerializer):
    """Admin-only view of a customer — includes order stats annotated onto the queryset."""

    order_count = serializers.SerializerMethodField()
    total_spent = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'name', 'phone_number', 'email',
            'house_number', 'address', 'city', 'state', 'country', 'pincode',
            'is_active', 'is_verified', 'is_staff', 'date_joined',
            'order_count', 'total_spent',
        ]

    def get_order_count(self, obj):
        return getattr(obj, 'order_count', 0) or 0

    def get_total_spent(self, obj):
        return getattr(obj, 'total_spent', 0) or 0


class RegisterSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(validators=[phone_validator])
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, max_length=128)
    confirm_password = serializers.CharField(min_length=8, max_length=128)
    house_number = serializers.CharField(max_length=100)
    address = serializers.CharField(max_length=255)
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100)
    country = serializers.CharField(max_length=100)
    pincode = serializers.CharField(max_length=20)
    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Password and confirmation do not match.'})

        phone_number = attrs['phone_number']
        email = attrs['email'].lower()

        phone_owner = User.objects.filter(phone_number=phone_number).first()
        if phone_owner and phone_owner.is_verified:
            raise serializers.ValidationError({'phone_number': 'This phone number is already registered. Please sign in instead.'})

        email_owner = User.objects.filter(email__iexact=email).first()
        if email_owner and email_owner.is_verified and email_owner.phone_number != phone_number:
            raise serializers.ValidationError({'email': 'This email is already in use with another account.'})

        return attrs


class PhoneNumberSerializer(serializers.Serializer):
    phone_number = serializers.CharField(validators=[phone_validator])


class OTPVerifySerializer(serializers.Serializer):
    PURPOSE_CHOICES = ['register', 'mpin_reset']

    phone_number = serializers.CharField(validators=[phone_validator])
    otp = serializers.CharField(min_length=4, max_length=6)
    purpose = serializers.ChoiceField(choices=PURPOSE_CHOICES)


class ResendOTPSerializer(serializers.Serializer):
    PURPOSE_CHOICES = ['register', 'mpin_reset']

    phone_number = serializers.CharField(validators=[phone_validator])
    purpose = serializers.ChoiceField(choices=PURPOSE_CHOICES)


class SetMpinSerializer(serializers.Serializer):
    token = serializers.CharField()
    mpin = serializers.CharField()
    confirm_mpin = serializers.CharField()

    def validate_mpin(self, value):
        if not MPIN_REGEX.match(value):
            raise serializers.ValidationError('MPIN must be exactly 4 digits.')
        return value

    def validate(self, attrs):
        if attrs['mpin'] != attrs['confirm_mpin']:
            raise serializers.ValidationError({'confirm_mpin': 'MPIN and confirmation do not match.'})
        return attrs


class LoginMpinSerializer(serializers.Serializer):
    phone_number = serializers.CharField(validators=[phone_validator])
    mpin = serializers.CharField()

    def validate_mpin(self, value):
        if not MPIN_REGEX.match(value):
            raise serializers.ValidationError('MPIN must be exactly 4 digits.')
        return value


class LoginPasswordSerializer(serializers.Serializer):
    phone_number = serializers.CharField(validators=[phone_validator])
    password = serializers.CharField()


class ProfileUpdateSerializer(serializers.Serializer):
    """Phone number and email are intentionally excluded — not editable here."""

    name = serializers.CharField(max_length=150)
    house_number = serializers.CharField(max_length=100)
    address = serializers.CharField(max_length=255)
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100)
    country = serializers.CharField(max_length=100)
    pincode = serializers.CharField(max_length=20)
    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)
