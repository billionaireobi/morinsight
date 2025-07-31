from rest_framework import serializers
from django.contrib.auth.models import User, Group
from django.contrib.auth import authenticate
from .models import UserProfile
import re

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    email = serializers.EmailField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists")
        return value

    def validate_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long")
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter")
        if not re.search(r'[0-9]', value):
            raise serializers.ValidationError("Password must contain at least one number")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, data):
        user = authenticate(**data)
        if not user:
            raise serializers.ValidationError("Invalid credentials")
        if not user.is_active:
            raise serializers.ValidationError("Account not verified. Please check your email.")
        return user

class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    is_management = serializers.BooleanField(read_only=True)
    is_client = serializers.BooleanField(read_only=True)
    phone = serializers.CharField(allow_blank=True, allow_null=True)

    class Meta:
        model = UserProfile
        fields = ['username', 'email', 'phone', 'profile_type', 'join_date', 'gender', 'is_management', 'is_client']
        read_only_fields = ['username', 'email', 'profile_type', 'join_date', 'is_management', 'is_client']

    def validate_phone(self, value):
        if value and not re.match(r'^\+?1?\d{9,15}$', value):
            raise serializers.ValidationError("Invalid phone number format")
        return value

class SocialLoginSerializer(serializers.Serializer):
    access_token = serializers.CharField()

    def validate(self, data):
        if not data.get('access_token'):
            raise serializers.ValidationError("Access token is required")
        return data

class EmailLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No user found with this email")
        return value

class EmailLoginVerifySerializer(serializers.Serializer):
    token = serializers.CharField()
    email = serializers.EmailField()

    def validate(self, data):
        if not data.get('token'):
            raise serializers.ValidationError("Token is required")
        if not data.get('email'):
            raise serializers.ValidationError("Email is required")
        return data

class EmailVerificationSerializer(serializers.Serializer):
    token = serializers.CharField()
    email = serializers.EmailField()

    def validate(self, data):
        if not data.get('token'):
            raise serializers.ValidationError("Token is required")
        if not data.get('email'):
            raise serializers.ValidationError("Email is required")
        return data

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No user found with this email")
        return value

class ResetPasswordSerializer(serializers.Serializer):
    token = serializers.CharField()
    email = serializers.EmailField()
    new_password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate_new_password(self, value):
        if len(value) < 8:
            raise serializers.ValidationError("Password must be at least 8 characters long")
        if not re.search(r'[A-Z]', value):
            raise serializers.ValidationError("Password must contain at least one uppercase letter")
        if not re.search(r'[0-9]', value):
            raise serializers.ValidationError("Password must contain at least one number")
        return value

class ManageUserProfileSerializer(serializers.ModelSerializer):
    profile_type = serializers.ChoiceField(choices=UserProfile.PROFILE_TYPE_CHOICES)

    class Meta:
        model = UserProfile
        fields = ['profile_type']

    def update(self, instance, validated_data):
        profile_type = validated_data.get('profile_type')
        instance.profile_type = profile_type
        instance.save()
        user = instance.user
        user.groups.clear()
        group_name = 'Management' if profile_type == 'Management' else 'Clients'
        group = Group.objects.get_or_create(name=group_name)[0]
        user.groups.add(group)
        return instance