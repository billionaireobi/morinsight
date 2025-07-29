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

class IsManagement(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.userprofile.is_management()

class RegisterView(CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    @rate_limit(key='ip', rate='10/h')
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        # Set user as inactive until email verification
        user.is_active = False
        user.save()
        # Generate verification token
        token = str(uuid.uuid4())
        cache.set(f"verify_token_{token}", user.id, timeout=24*3600)  # 24-hour expiry
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
            return Response({"error": f"Failed to send verification email: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
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

class EmailVerificationView(APIView):
    permission_classes = [AllowAny]
    serializer_class = EmailVerificationSerializer

    @rate_limit(key='ip', rate='50/h')
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['token']
        email = serializer.validated_data['email']
        user_id = cache.get(f"verify_token_{token}")
        if user_id:
            try:
                user = User.objects.get(id=user_id, email=email)
                if user.is_active:
                    return Response({"error": "Account already verified"}, status=status.HTTP_400_BAD_REQUEST)
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
                return Response({"error": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"error": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST)

class LoginView(CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    @rate_limit(key='ip', rate='50/h')
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data
        if not user.is_active:
            return Response({"error": "Account not verified. Please check your email."}, status=status.HTTP_403_FORBIDDEN)
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

class ProfileView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get_object(self):
        try:
            return self.request.user.userprofile
        except UserProfile.DoesNotExist:
            return Response({"error": "User profile not found"}, status=status.HTTP_404_NOT_FOUND)

    def get(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
            if isinstance(instance, Response):
                return instance
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        try:
            partial = kwargs.pop('partial', False)
            instance = self.get_object()
            if isinstance(instance, Response):
                return instance
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            if not request.user.has_perm('website.can_change_profile_type') and 'profile_type' in request.data:
                return Response({"error": "You do not have permission to change profile type"}, status=status.HTTP_403_FORBIDDEN)
            self.perform_update(serializer)
            return Response(serializer.data)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Successfully logged out"}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    @rate_limit(key='ip', rate='50/h')
    def post(self, request):
        serializer = SocialLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        access_token = serializer.validated_data['access_token']
        strategy = load_strategy(request)
        backend = load_backend(strategy, 'google-oauth2', redirect_uri=settings.SOCIAL_AUTH_REDIRECT_URI)
        try:
            user = backend.auth_complete(access_token=access_token)
            if not hasattr(user, 'userprofile'):
                UserProfile.objects.create(user=user, profile_type='Client')
                group = Group.objects.get_or_create(name='Clients')[0]
                user.groups.add(group)
            if not user.is_active:
                return Response({"error": "Account not verified. Please check your email."}, status=status.HTTP_403_FORBIDDEN)
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
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class EmailLoginView(APIView):
    permission_classes = [AllowAny]

    @rate_limit(key='ip', rate='10/h')
    def post(self, request):
        serializer = EmailLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email=email)
            if not user.is_active:
                return Response({"error": "Account not verified. Please check your email."}, status=status.HTTP_403_FORBIDDEN)
            token = str(uuid.uuid4())
            cache.set(f"login_token_{token}", user.id, timeout=600)
            login_url = f"{settings.FRONTEND_URL}/auth/verify-email?token={token}&email={email}"
            try:
                send_mail(
                    subject="Login to Your Account",
                    message=f"Click this link to login: {login_url}\nThis link expires in 10 minutes.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
                logger.info(f"Sent login email to {email}")
            except Exception as e:
                logger.error(f"Failed to send login email to {email}: {str(e)}")
                return Response({"error": f"Failed to send login email: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response({"message": "Login link sent to your email"}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "No user found with this email"}, status=status.HTTP_404_NOT_FOUND)

class EmailLoginVerifyView(APIView):
    permission_classes = [AllowAny]

    @rate_limit(key='ip', rate='50/h')
    def post(self, request):
        serializer = EmailLoginVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['token']
        email = serializer.validated_data['email']
        user_id = cache.get(f"login_token_{token}")
        if user_id:
            try:
                user = User.objects.get(id=user_id, email=email)
                if not user.is_active:
                    return Response({"error": "Account not verified. Please check your email."}, status=status.HTTP_403_FORBIDDEN)
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
                return Response({"error": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"error": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST)

class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    @rate_limit(key='ip', rate='10/h')
    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data['email']
        try:
            user = User.objects.get(email=email)
            if not user.is_active:
                return Response({"error": "Account not verified. Please verify your account first."}, status=status.HTTP_403_FORBIDDEN)
            token = str(uuid.uuid4())
            cache.set(f"reset_token_{token}", user.id, timeout=3600)  # 1-hour expiry
            reset_url = f"{settings.FRONTEND_URL}/auth/reset-password?token={token}&email={email}"
            try:
                send_mail(
                    subject="Reset Your Password",
                    message=f"Click this link to reset your password: {reset_url}\nThis link expires in 1 hour.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=False,
                )
                logger.info(f"Sent password reset email to {email}")
            except Exception as e:
                logger.error(f"Failed to send password reset email to {email}: {str(e)}")
                return Response({"error": f"Failed to send password reset email: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            return Response({"message": "Password reset link sent to your email"}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "No user found with this email"}, status=status.HTTP_404_NOT_FOUND)

class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    @rate_limit(key='ip', rate='10/h')
    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data['token']
        email = serializer.validated_data['email']
        new_password = serializer.validated_data['new_password']
        user_id = cache.get(f"reset_token_{token}")
        if user_id:
            try:
                user = User.objects.get(id=user_id, email=email)
                if not user.is_active:
                    return Response({"error": "Account not verified. Please verify your account first."}, status=status.HTTP_403_FORBIDDEN)
                user.set_password(new_password)
                user.save()
                cache.delete(f"reset_token_{token}")
                return Response({"message": "Password reset successfully"}, status=status.HTTP_200_OK)
            except User.DoesNotExist:
                return Response({"error": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"error": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST)

class ManageUserProfileView(APIView):
    permission_classes = [IsAuthenticated, IsManagement]

    def put(self, request, user_id):
        try:
            user = User.objects.get(id=user_id)
            profile = user.userprofile
            serializer = ManageUserProfileSerializer(profile, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)