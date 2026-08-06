from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view(), name='auth-register'),
    path('token/refresh/', TokenRefreshView.as_view(), name='auth-token-refresh'),
    path('verify-otp/', views.VerifyOTPView.as_view(), name='auth-verify-otp'),
    path('resend-otp/', views.ResendOTPView.as_view(), name='auth-resend-otp'),
    path('login/check/', views.LoginCheckView.as_view(), name='auth-login-check'),
    path('login/password/', views.LoginPasswordView.as_view(), name='auth-login-password'),
    path('login/mpin/', views.LoginMpinView.as_view(), name='auth-login-mpin'),
    path('mpin/setup/', views.SetMpinView.as_view(), name='auth-mpin-setup'),
    path('logout/', views.LogoutView.as_view(), name='auth-logout'),
    path('me/', views.MeView.as_view(), name='auth-me'),
    path('users/', views.UserListView.as_view(), name='auth-user-list'),
    path('users/<int:pk>/', views.UserDetailView.as_view(), name='auth-user-detail'),
]
