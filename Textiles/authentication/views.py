from django.contrib.auth.hashers import check_password
from django.core import signing
from django.db import IntegrityError, transaction
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from django.conf import settings

from .models import OTP, User
from .serializers import (
    LoginMpinSerializer,
    LoginPasswordSerializer,
    OTPVerifySerializer,
    PhoneNumberSerializer,
    ProfileUpdateSerializer,
    RegisterSerializer,
    ResendOTPSerializer,
    SetMpinSerializer,
    UserAdminSerializer,
    UserSerializer,
)
from .utils import issue_and_send_otp, make_mpin_setup_token, read_mpin_setup_token


def tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {'access': str(refresh.access_token), 'refresh': str(refresh)}


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            # Clean up any stale, never-verified registration attempts that
            # would otherwise collide on the unique phone/email constraints.
            User.objects.filter(phone_number=data['phone_number'], is_verified=False).delete()
            User.objects.filter(email__iexact=data['email'], is_verified=False).delete()

            try:
                user = User.objects.create(
                    phone_number=data['phone_number'],
                    name=data['name'],
                    email=data['email'].lower(),
                    house_number=data['house_number'],
                    address=data['address'],
                    city=data['city'],
                    state=data['state'],
                    country=data['country'],
                    pincode=data['pincode'],
                    latitude=data.get('latitude'),
                    longitude=data.get('longitude'),
                )
                user.set_password(data['password'])
                user.save()
            except IntegrityError:
                return Response(
                    {'detail': 'This phone number or email is already registered.'},
                    status=status.HTTP_409_CONFLICT,
                )

        issue_and_send_otp(user, 'register')
        return Response(
            {'message': 'Verification code sent to your email.', 'phone_number': user.phone_number},
            status=status.HTTP_201_CREATED,
        )


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data['phone_number']
        purpose = serializer.validated_data['purpose']
        submitted_code = serializer.validated_data['otp']

        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return Response({'detail': 'No account found for this phone number.'}, status=status.HTTP_404_NOT_FOUND)

        otp = OTP.objects.filter(user=user, purpose=purpose, is_used=False).order_by('-created_at').first()

        if not otp or not otp.is_valid():
            return Response({'detail': 'Code expired or not found. Please request a new one.'}, status=status.HTTP_400_BAD_REQUEST)

        if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
            return Response({'detail': 'Too many incorrect attempts. Please request a new code.'}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        if otp.code != submitted_code:
            otp.attempts += 1
            otp.save(update_fields=['attempts'])
            remaining = max(settings.OTP_MAX_ATTEMPTS - otp.attempts, 0)
            return Response({'detail': f'Incorrect code. {remaining} attempt(s) remaining.'}, status=status.HTTP_400_BAD_REQUEST)

        otp.is_used = True
        otp.save(update_fields=['is_used'])

        if purpose == 'register':
            user.is_verified = True
            user.save(update_fields=['is_verified'])

        token = make_mpin_setup_token(user, purpose)
        return Response({'message': 'Verified successfully.', 'token': token, 'mpin_set': user.is_mpin_set})


class ResendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data['phone_number']
        purpose = serializer.validated_data['purpose']

        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return Response({'detail': 'No account found for this phone number.'}, status=status.HTTP_404_NOT_FOUND)

        last_otp = OTP.objects.filter(user=user, purpose=purpose).order_by('-created_at').first()
        if last_otp:
            elapsed = (timezone.now() - last_otp.created_at).total_seconds()
            if elapsed < settings.OTP_RESEND_COOLDOWN_SECONDS:
                wait = int(settings.OTP_RESEND_COOLDOWN_SECONDS - elapsed)
                return Response({'detail': f'Please wait {wait}s before requesting another code.'}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        issue_and_send_otp(user, purpose)
        return Response({'message': 'A new code has been sent to your email.'})


class LoginCheckView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PhoneNumberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data['phone_number']

        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return Response({'detail': 'No account found for this phone number. Please register first.'}, status=status.HTTP_404_NOT_FOUND)

        if not user.is_verified:
            issue_and_send_otp(user, 'register')
            return Response({'status': 'verify_required', 'purpose': 'register', 'mpin_set': False})

        if not user.is_mpin_set:
            return Response({'status': 'password_required', 'mpin_set': False})

        if user.is_mpin_locked():
            return Response(
                {'detail': 'Too many failed attempts. Please try again later or reset your MPIN.'},
                status=status.HTTP_423_LOCKED,
            )

        return Response({'status': 'mpin_required', 'mpin_set': True})


class SetMpinView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SetMpinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['token']

        try:
            user_id, purpose = read_mpin_setup_token(token)
        except signing.SignatureExpired:
            return Response({'detail': 'This verification has expired. Please verify again.'}, status=status.HTTP_400_BAD_REQUEST)
        except signing.BadSignature:
            return Response({'detail': 'Invalid verification token.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'Account not found.'}, status=status.HTTP_404_NOT_FOUND)

        user.set_mpin(serializer.validated_data['mpin'])
        user.is_active = True
        user.save(update_fields=['mpin', 'is_mpin_set', 'failed_mpin_attempts', 'mpin_locked_until', 'is_active'])

        tokens = tokens_for_user(user)
        return Response({**tokens, 'user': UserSerializer(user).data})


class LoginMpinView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginMpinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data['phone_number']
        mpin = serializer.validated_data['mpin']

        try:
            user = User.objects.get(phone_number=phone_number)
        except User.DoesNotExist:
            return Response({'detail': 'No account found for this phone number.'}, status=status.HTTP_404_NOT_FOUND)

        if not user.is_mpin_set:
            return Response({'detail': 'MPIN not set up yet. Please complete first-time login.'}, status=status.HTTP_400_BAD_REQUEST)

        if user.is_mpin_locked():
            return Response(
                {'detail': 'Too many failed attempts. Please try again later or reset your MPIN.'},
                status=status.HTTP_423_LOCKED,
            )

        if not check_password(mpin, user.mpin):
            user.failed_mpin_attempts += 1
            if user.failed_mpin_attempts >= settings.MPIN_MAX_FAILED_ATTEMPTS:
                user.mpin_locked_until = timezone.now() + timezone.timedelta(minutes=settings.MPIN_LOCKOUT_MINUTES)
                user.save(update_fields=['failed_mpin_attempts', 'mpin_locked_until'])
                return Response(
                    {'detail': 'Too many failed attempts. Your account is temporarily locked.'},
                    status=status.HTTP_423_LOCKED,
                )
            user.save(update_fields=['failed_mpin_attempts'])
            remaining = settings.MPIN_MAX_FAILED_ATTEMPTS - user.failed_mpin_attempts
            return Response({'detail': f'Incorrect MPIN. {remaining} attempt(s) remaining.'}, status=status.HTTP_401_UNAUTHORIZED)

        user.failed_mpin_attempts = 0
        user.mpin_locked_until = None
        user.save(update_fields=['failed_mpin_attempts', 'mpin_locked_until'])

        tokens = tokens_for_user(user)
        return Response({**tokens, 'user': UserSerializer(user).data})


class LoginPasswordView(APIView):
    """
    Verifies the account password and, on success, returns a short-lived
    token to set the MPIN. Used for first-time login, before an MPIN has
    ever been set. The "forgot MPIN" flow uses an email OTP instead — see
    VerifyOTPView with purpose='mpin_reset'.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone_number = serializer.validated_data['phone_number']
        password = serializer.validated_data['password']

        try:
            user = User.objects.get(phone_number=phone_number, is_verified=True)
        except User.DoesNotExist:
            return Response({'detail': 'No account found for this phone number.'}, status=status.HTTP_404_NOT_FOUND)

        if user.is_mpin_locked():
            return Response(
                {'detail': 'Too many failed attempts. Please try again later.'},
                status=status.HTTP_423_LOCKED,
            )

        if not user.check_password(password):
            user.failed_mpin_attempts += 1
            if user.failed_mpin_attempts >= settings.MPIN_MAX_FAILED_ATTEMPTS:
                user.mpin_locked_until = timezone.now() + timezone.timedelta(minutes=settings.MPIN_LOCKOUT_MINUTES)
                user.save(update_fields=['failed_mpin_attempts', 'mpin_locked_until'])
                return Response(
                    {'detail': 'Too many failed attempts. Your account is temporarily locked.'},
                    status=status.HTTP_423_LOCKED,
                )
            user.save(update_fields=['failed_mpin_attempts'])
            remaining = settings.MPIN_MAX_FAILED_ATTEMPTS - user.failed_mpin_attempts
            return Response({'detail': f'Incorrect password. {remaining} attempt(s) remaining.'}, status=status.HTTP_401_UNAUTHORIZED)

        user.failed_mpin_attempts = 0
        user.mpin_locked_until = None
        user.save(update_fields=['failed_mpin_attempts', 'mpin_locked_until'])

        token = make_mpin_setup_token(user, 'login')
        return Response({'message': 'Password verified.', 'token': token})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({'detail': 'Refresh token is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            RefreshToken(refresh_token).blacklist()
        except Exception:
            return Response({'detail': 'Invalid or already-invalidated token.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_205_RESET_CONTENT)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = ProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        for field, value in serializer.validated_data.items():
            setattr(user, field, value)
        user.save(update_fields=list(serializer.validated_data.keys()))

        return Response(UserSerializer(user).data)


def _users_with_order_stats():
    return User.objects.annotate(
        order_count=Count('orders', distinct=True),
        total_spent=Sum('orders__total'),
    )


class UserListView(generics.ListAPIView):
    serializer_class = UserAdminSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return _users_with_order_stats().order_by('-date_joined')


class UserDetailView(generics.RetrieveAPIView):
    serializer_class = UserAdminSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return _users_with_order_stats()
