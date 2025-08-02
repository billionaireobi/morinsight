from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
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
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
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
    @swagger_auto_schema(
        operation_description="Register a new user. Sends verification email on success.",
        request_body=RegisterSerializer,
        responses={
            201: openapi.Response('Registration successful', RegisterSerializer),
            400: 'Invalid input data',
            500: 'Unexpected error'
        }
    )
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
    @swagger_auto_schema(
        operation_description="Verify a user's email address using a token.",
        request_body=EmailVerificationSerializer,
        responses={
            200: 'Email verified successfully',
            400: 'Invalid or expired token',
            500: 'Unexpected error'
        }
    )
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

# class LoginView(CreateAPIView):
#     permission_classes = [AllowAny]
#     serializer_class = LoginSerializer

#     @rate_limit(key='ip', rate='50/h')
#     def create(self, request, *args, **kwargs):
#         try:
#             serializer = self.get_serializer(data=request.data)
#             if not serializer.is_valid():
#                 raise APIError("Invalid credentials")
#             user = serializer.validated_data
#             refresh = RefreshToken.for_user(user)
#             return Response({
#                 "refresh": str(refresh),
#                 "access": str(refresh.access_token),
#                 "user": {
#                     "username": user.username,
#                     "email": user.email,
#                     "profile_type": user.userprofile.profile_type,
#                     "is_management": user.userprofile.is_management(),
#                     "is_client": user.userprofile.is_client()
#                 }
#             }, status=status.HTTP_200_OK)
#         except APIError as e:
#             return Response({"error": e.message}, status=e.status_code)
#         except Exception as e:
#             logger.error(f"Unexpected error in LoginView: {str(e)}")
#             return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LoginView(CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    @rate_limit(key='ip', rate='50/h')
    @swagger_auto_schema(
        operation_description="Authenticate user with username/email and password. Returns JWT tokens.",
        request_body=LoginSerializer,
        responses={
            200: openapi.Response('Login successful', LoginSerializer),
            400: 'Invalid credentials or missing fields',
            500: 'Unexpected error'
        }
    )
    def create(self, request, *args, **kwargs):
        try:
            # Get username/email and password from request
            username_or_email = request.data.get('username') or request.data.get('email')
            password = request.data.get('password')

            if not username_or_email or not password:
                return Response({"error": "Username/Email and password are required"}, status=status.HTTP_400_BAD_REQUEST)

            # Check if input is an email and fetch username
            if '@' in username_or_email:
                try:
                    user_obj = User.objects.get(email=username_or_email)
                    username = user_obj.username
                except User.DoesNotExist:
                    return Response({"error": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)
            else:
                username = username_or_email

            # Authenticate user
            user = authenticate(username=username, password=password)
            if user is None:
                return Response({"error": "Invalid credentials"}, status=status.HTTP_400_BAD_REQUEST)

            # Generate JWT tokens
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

    @swagger_auto_schema(
        operation_description="Retrieve the authenticated user's profile.",
        responses={
            200: openapi.Response('User profile', UserProfileSerializer),
            404: 'User profile not found',
            500: 'Unexpected error'
        }
    )
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

    @swagger_auto_schema(
        operation_description="Update the authenticated user's profile.",
        responses={
            200: openapi.Response('Profile updated', UserProfileSerializer),
            400: 'Invalid input data',
            403: 'Permission denied',
            404: 'User profile not found',
            500: 'Unexpected error'
        }
    )
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

    @swagger_auto_schema(
        operation_description="Logout user by blacklisting the refresh token.",
        responses={
            205: 'Successfully logged out',
            400: 'Bad request or unexpected error',
            401: 'Authentication credentials were not provided',
            403: 'Invalid or expired token'
        }
    )
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
    @swagger_auto_schema(
        operation_description="Authenticate user via Google OAuth2. Returns JWT tokens.",
        request_body=SocialLoginSerializer,
        responses={
            200: 'Login successful',
            400: 'Invalid access token',
            403: 'Account not verified',
            500: 'Unexpected error'
        }
    )
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
    @swagger_auto_schema(
        operation_description="Send a login link to the user's email address.",
        request_body=EmailLoginSerializer,
        responses={
            200: 'Login link sent',
            400: 'Invalid email',
            403: 'Account not verified',
            404: 'No user found with this email',
            500: 'Unexpected error'
        }
    )
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
    @swagger_auto_schema(
        operation_description="Verify email login using token and email. Returns JWT tokens.",
        request_body=EmailLoginVerifySerializer,
        responses={
            200: 'Login successful',
            400: 'Invalid or expired token',
            403: 'Account not verified',
            404: 'User profile not found',
            500: 'Unexpected error'
        }
    )
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
    @swagger_auto_schema(
        operation_description="Send a password reset link to the user's email address.",
        request_body=ForgotPasswordSerializer,
        responses={
            200: 'Password reset link sent',
            400: 'Invalid email',
            403: 'Account not verified',
            404: 'No user found with this email',
            500: 'Unexpected error'
        }
    )
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
    @swagger_auto_schema(
        operation_description="Reset the user's password using a token.",
        request_body=ResetPasswordSerializer,
        responses={
            200: 'Password reset successfully',
            400: 'Invalid input data',
            403: 'Account not verified',
            404: 'User profile not found',
            500: 'Unexpected error'
        }
    )
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


# class ManageUserProfileView(APIView):
#     permission_classes = [IsAuthenticated, IsManagement]

#     @swagger_auto_schema(
#         operation_description="Update another user's profile (admin/management only).",
#         request_body=ManageUserProfileSerializer,
#         responses={
#             200: openapi.Response('Profile updated', ManageUserProfileSerializer),
#             400: 'Invalid input data',
#             404: 'User or profile not found',
#             500: 'Unexpected error'
#         }
#     )
#     def put(self, request, user_id):
#         try:
#             user = User.objects.get(id=user_id)
#             profile = user.userprofile
#             serializer = ManageUserProfileSerializer(profile, data=request.data, partial=True)
#             if not serializer.is_valid():
#                 raise APIError("Invalid input data")
#             serializer.save()
#             return Response(serializer.data, status=status.HTTP_200_OK)
#         except User.DoesNotExist:
#             raise APIError("User not found", status.HTTP_404_NOT_FOUND)
#         except UserProfile.DoesNotExist:
#             raise APIError("User profile not found", status.HTTP_404_NOT_FOUND)
#         except APIError as e:
#             return Response({"error": e.message}, status=e.status_code)
#         except Exception as e:
#             logger.error(f"Unexpected error in ManageUserProfileView: {str(e)}")
#             return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

#     # ✅ Add this method
#     def patch(self, request, user_id):
#         """
#         Allows partial updates (PATCH) using the same logic as PUT.
#         """
#         return self.put(request, user_id)
class ManageUserProfileView(APIView):
    permission_classes = [IsAuthenticated, IsManagement]

    @swagger_auto_schema(
        operation_description="Update another user's profile (admin/management only).",
        request_body=ManageUserProfileSerializer,
        responses={
            200: openapi.Response('Profile updated', ManageUserProfileSerializer),
            400: 'Invalid input data',
            404: 'User or profile not found',
            500: 'Unexpected error'
        }
    )
    def put(self, request, user_id):
        """
        Full update (requires all required fields).
        """
        return self._update_profile(request, user_id, partial=False)

    def patch(self, request, user_id):
        """
        Partial update (only send fields you want to change).
        """
        return self._update_profile(request, user_id, partial=True)

    def _update_profile(self, request, user_id, partial):
        try:
            user = User.objects.get(id=user_id)
            profile = user.userprofile

            serializer = ManageUserProfileSerializer(profile, data=request.data, partial=partial)

            if not serializer.is_valid():
                return Response(
                    {"error": "Invalid input data", "details": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )

            serializer.save()

            return Response(
                {
                    "message": "Profile updated successfully",
                    "data": serializer.data
                },
                status=status.HTTP_200_OK
            )

        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        except UserProfile.DoesNotExist:
            return Response({"error": "User profile not found"}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            logger.error(f"Unexpected error in ManageUserProfileView: {str(e)}")
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# class ManageUserProfileView(APIView):
#     permission_classes = [IsAuthenticated, IsManagement]

#     @swagger_auto_schema(
#         operation_description="Update another user's profile (admin/management only).",
#         request_body=ManageUserProfileSerializer,
#         responses={
#             200: openapi.Response('Profile updated', ManageUserProfileSerializer),
#             400: 'Invalid input data',
#             404: 'User or profile not found',
#             500: 'Unexpected error'
#         }
#     )
#     def put(self, request, user_id):
#         try:
#             user = User.objects.get(id=user_id)
#             profile = user.userprofile
#             serializer = ManageUserProfileSerializer(profile, data=request.data, partial=True)
#             if not serializer.is_valid():
#                 raise APIError("Invalid input data")
#             serializer.save()
#             return Response(serializer.data, status=status.HTTP_200_OK)
#         except User.DoesNotExist:
#             raise APIError("User not found", status.HTTP_404_NOT_FOUND)
#         except UserProfile.DoesNotExist:
#             raise APIError("User profile not found", status.HTTP_404_NOT_FOUND)
#         except APIError as e:
#             return Response({"error": e.message}, status=e.status_code)
#         except Exception as e:
#             logger.error(f"Unexpected error in ManageUserProfileView: {str(e)}")
#             return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)