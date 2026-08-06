import secrets

from django.conf import settings
from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from .models import OTP

TOKEN_SALT = 'authentication.mpin-verification'

PURPOSE_COPY = {
    'register': {
        'heading': 'Verify your email',
        'intro': 'Thanks for creating a Niya Collections account. Use the code below to verify your email address.',
    },
    'mpin_reset': {
        'heading': 'Reset your MPIN',
        'intro': 'We received a request to reset your Niya Collections MPIN. Use the code below to verify it’s you.',
    },
}


def generate_otp_code():
    return f'{secrets.randbelow(10 ** settings.OTP_LENGTH):0{settings.OTP_LENGTH}d}'


def create_otp(user, purpose):
    code = generate_otp_code()
    expires_at = timezone.now() + timezone.timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
    otp = OTP.objects.create(user=user, code=code, purpose=purpose, expires_at=expires_at)
    return otp


def send_otp_email(user, otp):
    copy = PURPOSE_COPY[otp.purpose]
    context = {
        'name': user.name,
        'otp': otp.code,
        'expiry_minutes': settings.OTP_EXPIRY_MINUTES,
        'heading': copy['heading'],
        'intro': copy['intro'],
    }
    html_body = render_to_string('authentication/emails/otp_email.html', context)
    text_body = strip_tags(html_body)

    message = EmailMultiAlternatives(
        subject=f'{otp.code} is your Niya Collections verification code',
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    message.attach_alternative(html_body, 'text/html')
    message.send(fail_silently=False)


def issue_and_send_otp(user, purpose):
    otp = create_otp(user, purpose)
    send_otp_email(user, otp)
    return otp


def make_mpin_setup_token(user, purpose):
    return signing.dumps({'user_id': user.pk, 'purpose': purpose}, salt=TOKEN_SALT)


def read_mpin_setup_token(token):
    """Returns (user_id, purpose). Raises signing.BadSignature/SignatureExpired if invalid."""
    data = signing.loads(
        token, salt=TOKEN_SALT, max_age=settings.MPIN_VERIFICATION_TOKEN_MAX_AGE
    )
    return data['user_id'], data['purpose']
