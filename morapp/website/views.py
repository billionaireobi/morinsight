from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import (
    RegisterSerializer, LoginSerializer, UserProfileSerializer, SocialLoginSerializer,
    EmailLoginSerializer, EmailLoginVerifySerializer, ManageUserProfileSerializer,
    EmailVerificationSerializer, ForgotPasswordSerializer, ResetPasswordSerializer
)
from social_django.utils import load_strategy, load_backend
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.models import User, Group
from .models import UserProfile
import uuid
from django.core.cache import cache
from rest_framework.permissions import BasePermission
from .utils import rate_limit
import logging

logger = logging.getLogger(__name__)

class APIError(Exception):
    def __init__(self, message, status_code=status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class IsManagement(BasePermission):
    def has_permission(self, request, view):
        try:
            return request.user and request.user.is_authenticated and request.user.userprofile.is_management()
        except UserProfile.DoesNotExist:
            logger.warning(f"User {request.user.username} has no UserProfile")
            return False

class RegisterView(CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    @rate_limit(key='ip', rate='10/h')
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            if not serializer.is_valid():
                raise APIError("Invalid input data")
            user = serializer.save()
            user.is_active = False
            user.save()
            token = str(uuid.uuid4())
            cache.set(f"verify_token_{token}", user.id, timeout=24*3600)
            verify_url = f"{settings.FRONTEND_URL}/auth/verify-email?token={token}&email={user.email}"
            try:
                send_mail(
                    subject="Verify Your Account",
                    message=f"Click this link to verify your account: {verify_url}\nThis link expires in 24 hours.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
                logger.info(f"Sent verification email to {user.email}")
            except Exception as e:
                logger.error(f"Failed to send verification email to {user.email}: {str(e)}")
                raise APIError(f"Failed to send verification email: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response({
                "message": "Registration successful. Please check your email to verify your account.",
                "user": {
                    "username": user.username,
                    "email": user.email,
                    "profile_type": user.userprofile.profile_type,
                    "is_management": user.userprofile.is_management(),
                    "is_client": user.userprofile.is_client()
                }
            }, status=status.HTTP_201_CREATED)
        except APIError as e:
            return Response({"error": e.message}, status=e.status_code)
        except Exception as e:
            logger.error(f"Unexpected error in RegisterView: {str(e)}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class EmailVerificationView(APIView):
    permission_classes = [AllowAny]
    serializer_class = EmailVerificationSerializer

    @rate_limit(key='ip', rate='50/h')
    def post(self, request):
        try:
            serializer = self.serializer_class(data=request.data)
            if not serializer.is_valid():
                raise APIError("Invalid token or email")
            token = serializer.validated_data['token']
            email = serializer.validated_data['email']
            user_id = cache.get(f"verify_token_{token}")
            if not user_id:
                raise APIError("Invalid or expired token")
            try:
                user = User.objects.get(id=user_id, email=email)
                if user.is_active:
                    raise APIError("Account already verified")
                user.is_active = True
                user.save()
                cache.delete(f"verify_token_{token}")
                refresh = RefreshToken.for_user(user)
                return Response({
                    "message": "Account verified successfully",
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "user": {
                        "username": user.username,
                        "email": user.email,
                        "profile_type": user.userprofile.profile_type,
                        "is_management": user.userprofile.is_management(),
                        "is_client": user.userprofile.is_client()
                    }
                }, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                raise APIError("Invalid or expired token")
            except UserProfile.DoesNotExist:
                raise APIError("User profile not found", status.HTTP_404_NOT_FOUND)
        except APIError as e:
            return Response({"error": e.message}, status=e.status_code)
        except Exception as e:
            logger.error(f"Unexpected error in EmailVerificationView: {str(e)}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class LoginView(CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    @rate_limit(key='ip', rate='50/h')
    def create(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            if not serializer.is_valid():
                raise APIError("Invalid credentials")
            user = serializer.validated_data
            refresh = RefreshToken.for_user(user)
            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": {
                    "username": user.username,
                    "email": user.email,
                    "profile_type": user.userprofile.profile_type,
                    "is_management": user.userprofile.is_management(),
                    "is_client": user.userprofile.is_client()
                }
            }, status=status.HTTP_200_OK)
        except APIError as e:
            return Response({"error": e.message}, status=e.status_code)
        except Exception as e:
            logger.error(f"Unexpected error in LoginView: {str(e)}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ProfileView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get_object(self):
        try:
            return self.request.user.userprofile
        except UserProfile.DoesNotExist:
            raise APIError("User profile not found", status.HTTP_404_NOT_FOUND)

    def get(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        except APIError as e:
            return Response({"error": e.message}, status=e.status_code)
        except Exception as e:
            logger.error(f"Unexpected error in ProfileView.get: {str(e)}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            if not serializer.is_valid():
                raise APIError("Invalid input data")
            if not request.user.has_perm('website.can_change_profile_type') and 'profile_type' in request.data:
                raise APIError("You do not have permission to change profile type", status.HTTP_403_FORBIDDEN)
            self.perform_update(serializer)
            return Response(serializer.data)
        except APIError as e:
            return Response({"error": e.message}, status=e.status_code)
        except Exception as e:
            logger.error(f"Unexpected error in ProfileView.update: {str(e)}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                raise APIError("Refresh token is required")
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Successfully logged out"}, status=status.HTTP_205_RESET_CONTENT)
        except APIError as e:
            return Response({"error": e.message}, status=e.status_code)
        except Exception as e:
            logger.error(f"Unexpected error in LogoutView: {str(e)}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_400_BAD_REQUEST)

class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    @rate_limit(key='ip', rate='50/h')
    def post(self, request):
        try:
            serializer = SocialLoginSerializer(data=request.data)
            if not serializer.is_valid():
                raise APIError("Invalid access token")
            access_token = serializer.validated_data['access_token']
            strategy = load_strategy(request)
            backend = load_backend(strategy, 'google-oauth2', redirect_uri=settings.SOCIAL_AUTH_REDIRECT_URI)
            user = backend.auth_complete(access_token=access_token)
            if not user.is_active:
                raise APIError("Account not verified. Please check your email.", status.HTTP_403_FORBIDDEN)
            refresh = RefreshToken.for_user(user)
            return Response({
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": {
                    "username": user.username,
                    "email": user.email,
                    "profile_type": user.userprofile.profile_type,
                    "is_management": user.userprofile.is_management(),
                    "is_client": user.userprofile.is_client()
                }
            }, status=status.HTTP_200_OK)
        except APIError as e:
            return Response({"error": e.message}, status=e.status_code)
        except Exception as e:
            logger.error(f"Unexpected error in GoogleLoginView: {str(e)}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_400_BAD_REQUEST)

class EmailLoginView(APIView):
    permission_classes = [AllowAny]

    @rate_limit(key='ip', rate='10/h')
    def post(self, request):
        try:
            serializer = EmailLoginSerializer(data=request.data)
            if not serializer.is_valid():
                raise APIError("Invalid email")
            email = serializer.validated_data['email']
            try:
                user = User.objects.get(email=email)
                if not user.is_active:
                    raise APIError("Account not verified. Please check your email.", status.HTTP_403_FORBIDDEN)
                token = str(uuid.uuid4())
                cache.set(f"login_token_{token}", user.id, timeout=600)
                login_url = f"{settings.FRONTEND_URL}/auth/email/verify?token={token}&email={email}"
                try:
                    send_mail(
                        subject="Login to Your Account",
                        message=f"Click this link to login: {login_url}\nThis link expires in 10 minutes.",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[email],
                        fail_silently=False,
                    )
                    logger.info(f"Sent login email to {user.email}")
                except Exception as e:
                    logger.error(f"Failed to send login email to {user.email}: {str(e)}")
                    raise APIError(f"Failed to send login email: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)
                return Response({"message": "Login link sent to your email"}, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                raise APIError("No user found with this email", status.HTTP_404_NOT_FOUND)
        except APIError as e:
            return Response({"error": e.message}, status=e.status_code)
        except Exception as e:
            logger.error(f"Unexpected error in EmailLoginView: {str(e)}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class EmailLoginVerifyView(APIView):
    permission_classes = [AllowAny]

    @rate_limit(key='ip', rate='50/h')
    def post(self, request):
        try:
            serializer = EmailLoginVerifySerializer(data=request.data)
            if not serializer.is_valid():
                raise APIError("Invalid token or email")
            token = serializer.validated_data['token']
            email = serializer.validated_data['email']
            user_id = cache.get(f"login_token_{token}")
            if not user_id:
                raise APIError("Invalid or expired token")
            try:
                user = User.objects.get(id=user_id, email=email)
                if not user.is_active:
                    raise APIError("Account not verified. Please check your email.", status.HTTP_403_FORBIDDEN)
                cache.delete(f"login_token_{token}")
                refresh = RefreshToken.for_user(user)
                return Response({
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "user": {
                        "username": user.username,
                        "email": user.email,
                        "profile_type": user.userprofile.profile_type,
                        "is_management": user.userprofile.is_management(),
                        "is_client": user.userprofile.is_client()
                    }
                }, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                raise APIError("Invalid or expired token")
            except UserProfile.DoesNotExist:
                raise APIError("User profile not found", status.HTTP_404_NOT_FOUND)
        except APIError as e:
            return Response({"error": e.message}, status=e.status_code)
        except Exception as e:
            logger.error(f"Unexpected error in EmailLoginVerifyView: {str(e)}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    @rate_limit(key='ip', rate='10/h')
    def post(self, request):
        try:
            serializer = ForgotPasswordSerializer(data=request.data)
            if not serializer.is_valid():
                raise APIError("Invalid email")
            email = serializer.validated_data['email']
            try:
                user = User.objects.get(email=email)
                if not user.is_active:
                    raise APIError("Account not verified. Please verify your account first.", status.HTTP_403_FORBIDDEN)
                token = str(uuid.uuid4())
                cache.set(f"reset_token_{token}", user.id, timeout=3600)
                reset_url = f"{settings.FRONTEND_URL}/auth/reset-password?token={token}&email={email}"
                try:
                    send_mail(
                        subject="Reset Your Password",
                        message=f"Click this link to reset your password: {reset_url}\nThis link expires in 1 hour.",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[email],
                        fail_silently=False,
                    )
                    logger.info(f"Sent password reset email to {user.email}")
                except Exception as e:
                    logger.error(f"Failed to send password reset email to {user.email}: {str(e)}")
                    raise APIError(f"Failed to send password reset email: {str(e)}", status.HTTP_500_INTERNAL_SERVER_ERROR)
                return Response({"message": "Password reset link sent to your email"}, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                raise APIError("No user found with this email", status.HTTP_404_NOT_FOUND)
        except APIError as e:
            return Response({"error": e.message}, status=e.status_code)
        except Exception as e:
            logger.error(f"Unexpected error in ForgotPasswordView: {str(e)}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    @rate_limit(key='ip', rate='10/h')
    def post(self, request):
        try:
            serializer = ResetPasswordSerializer(data=request.data)
            if not serializer.is_valid():
                raise APIError("Invalid input data")
            token = serializer.validated_data['token']
            email = serializer.validated_data['email']
            new_password = serializer.validated_data['new_password']
            user_id = cache.get(f"reset_token_{token}")
            if not user_id:
                raise APIError("Invalid or expired token")
            try:
                user = User.objects.get(id=user_id, email=email)
                if not user.is_active:
                    raise APIError("Account not verified. Please verify your account first.", status.HTTP_403_FORBIDDEN)
                user.set_password(new_password)
                user.save()
                cache.delete(f"reset_token_{token}")
                return Response({"message": "Password reset successfully"}, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                raise APIError("Invalid or expired token")
            except UserProfile.DoesNotExist:
                raise APIError("User profile not found", status.HTTP_404_NOT_FOUND)
        except APIError as e:
            return Response({"error": e.message}, status=e.status_code)
        except Exception as e:
            logger.error(f"Unexpected error in ResetPasswordView: {str(e)}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ManageUserProfileView(APIView):
    permission_classes = [IsAuthenticated, IsManagement]

    def put(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            profile = user.userprofile
            serializer = ManageUserProfileSerializer(profile, data=request.data, partial=True)
            if not serializer.is_valid():
                raise APIError("Invalid input data")
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            raise APIError("User not found", status.HTTP_404_NOT_FOUND)
        except UserProfile.DoesNotExist:
            raise APIError("User profile not found", status.HTTP_404_NOT_FOUND)
        except APIError as e:
            return Response({"error": e.message}, status=e.status_code)
        except Exception as e:
            logger.error(f"Unexpected error in ManageUserProfileView: {str(e)}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)