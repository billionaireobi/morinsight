from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView, LoginView, ProfileView, LogoutView, GoogleLoginView,
    EmailLoginView, EmailLoginVerifyView, ManageUserProfileView,
    EmailVerificationView, ForgotPasswordView, ResetPasswordView
)

urlpatterns = [
    path('api/auth/register/', RegisterView.as_view(), name='register'),
    path('api/auth/verify-email/', EmailVerificationView.as_view(), name='email_verification'),
    path('api/auth/login/', LoginView.as_view(), name='login'),
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/profile/', ProfileView.as_view(), name='profile'),
    path('api/auth/logout/', LogoutView.as_view(), name='logout'),
    path('api/auth/google/', GoogleLoginView.as_view(), name='google_login'),
    path('api/auth/email/', EmailLoginView.as_view(), name='email_login'),
    path('api/auth/email/verify/', EmailLoginVerifyView.as_view(), name='email_login_verify'),
    path('api/auth/forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    path('api/auth/reset-password/', ResetPasswordView.as_view(), name='reset_password'),
    path('api/auth/manage-profile/<int:user_id>/', ManageUserProfileView.as_view(), name='manage_user_profile'),
]