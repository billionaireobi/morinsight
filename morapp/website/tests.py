from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth.models import User
from django.core.cache import cache
from website.models import UserProfile
from django.core import mail
import re
import uuid

class AuthAPITests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.client.defaults['REMOTE_ADDR'] = '127.0.0.1'  # Ensure consistent IP for rate-limiting
        self.register_url = '/api/auth/register/'
        self.verify_email_url = '/api/auth/verify-email/'
        self.login_url = '/api/auth/login/'
        self.profile_url = '/api/auth/profile/'
        self.logout_url = '/api/auth/logout/'
        self.email_login_url = '/api/auth/email/'
        self.email_login_verify_url = '/api/auth/email/verify/'
        self.forgot_password_url = '/api/auth/forgot-password/'
        self.reset_password_url = '/api/auth/reset-password/'
        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'Test1234'
        }
        mail.outbox.clear()  # Clear outbox at start of each test

    def test_register(self):
        response = self.client.post(self.register_url, self.user_data, format='json')
        print(f"test_register: mail.outbox length={len(mail.outbox)}")  # Debug
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['message'], 'Registration successful. Please check your email to verify your account.')
        self.assertEqual(response.data['user']['username'], 'testuser')
        self.assertEqual(len(mail.outbox), 1)  # Verify email sent
        self.assertIn('Verify Your Account', mail.outbox[0].subject)

    def test_register_rate_limit(self):
        cache.clear()  # Clear cache before test
        for i in range(10):
            data = {
                'username': f'testuser{i}',
                'email': f'test{i}@example.com',
                'password': 'Test1234'
            }
            response = self.client.post(self.register_url, data, format='json')
            print(f"test_register_rate_limit: request {i+1}, mail.outbox length={len(mail.outbox)}")  # Debug
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # 11th request should hit rate limit
        data = {
            'username': 'testuser10',
            'email': 'test10@example.com',
            'password': 'Test1234'
        }
        response = self.client.post(self.register_url, data, format='json')
        print(f"test_register_rate_limit: 11th request, status={response.status_code}, mail.outbox length={len(mail.outbox)}")  # Debug
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(response.data['error'], 'Rate limit exceeded. Try again later.')

    def test_verify_email(self):
        cache.clear()  # Clear cache to reset rate limit
        response = self.client.post(self.register_url, self.user_data, format='json')
        print(f"test_verify_email: after register, mail.outbox length={len(mail.outbox)}")  # Debug
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1, f"Expected 1 email, got {len(mail.outbox)}")
        email = mail.outbox[0].body
        token = re.search(r'token=([a-f0-9-]+)', email).group(1)
        data = {'token': token, 'email': 'test@example.com'}
        response = self.client.post(self.verify_email_url, data, format='json')
        print(f"test_verify_email: after verify, mail.outbox length={len(mail.outbox)}")  # Debug
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Account verified successfully')
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        user = User.objects.get(username='testuser')
        self.assertTrue(user.is_active)

    def test_login(self):
        response = self.client.post(self.register_url, self.user_data, format='json')
        print(f"test_login: after register, mail.outbox length={len(mail.outbox)}")  # Debug
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0].body
        token = re.search(r'token=([a-f0-9-]+)', email).group(1)
        self.client.post(self.verify_email_url, {'token': token, 'email': 'test@example.com'}, format='json')
        print(f"test_login: after verify, mail.outbox length={len(mail.outbox)}")  # Debug
        data = {'username': 'testuser', 'password': 'Test1234'}
        response = self.client.post(self.login_url, data, format='json')
        print(f"test_login: after login, mail.outbox length={len(mail.outbox)}")  # Debug
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_profile(self):
        # Register and verify user
        response = self.client.post(self.register_url, self.user_data, format='json')
        print(f"test_profile: after register, mail.outbox length={len(mail.outbox)}")  # Debug
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0].body
        token = re.search(r'token=([a-f0-9-]+)', email).group(1)
        verify_response = self.client.post(self.verify_email_url, {'token': token, 'email': 'test@example.com'}, format='json')
        print(f"test_profile: after verify, mail.outbox length={len(mail.outbox)}")  # Debug
        access_token = verify_response.data['access']
        # Test GET profile
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.get(self.profile_url, format='json')
        print("Profile GET response:", response.status_code, response.data)  # Debug
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')
        self.assertEqual(response.data['profile_type'], 'Client')
        # Test PUT profile
        update_data = {'phone': '+1234567890'}  # Valid phone format
        response = self.client.put(self.profile_url, update_data, format='json')
        print("Profile PUT response:", response.status_code, response.data)  # Debug
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['phone'], '+1234567890')

    def test_logout(self):
        response = self.client.post(self.register_url, self.user_data, format='json')
        print(f"test_logout: after register, mail.outbox length={len(mail.outbox)}")  # Debug
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0].body
        token = re.search(r'token=([a-f0-9-]+)', email).group(1)
        verify_response = self.client.post(self.verify_email_url, {'token': token, 'email': 'test@example.com'}, format='json')
        print(f"test_logout: after verify, mail.outbox length={len(mail.outbox)}")  # Debug
        refresh_token = verify_response.data['refresh']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {verify_response.data["access"]}')
        response = self.client.post(self.logout_url, {'refresh': refresh_token}, format='json')
        print(f"test_logout: after logout, mail.outbox length={len(mail.outbox)}")  # Debug
        self.assertEqual(response.status_code, status.HTTP_205_RESET_CONTENT)
        self.assertEqual(response.data['message'], 'Successfully logged out')

    def test_email_login(self):
        response = self.client.post(self.register_url, self.user_data, format='json')
        print(f"test_email_login: after register, mail.outbox length={len(mail.outbox)}")  # Debug
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0].body
        token = re.search(r'token=([a-f0-9-]+)', email).group(1)
        self.client.post(self.verify_email_url, {'token': token, 'email': 'test@example.com'}, format='json')
        print(f"test_email_login: after verify, mail.outbox length={len(mail.outbox)}")  # Debug
        response = self.client.post(self.email_login_url, {'email': 'test@example.com'}, format='json')
        print(f"test_email_login: after email login, mail.outbox length={len(mail.outbox)}")  # Debug
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Login link sent to your email')
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('Login to Your Account', mail.outbox[1].subject)

    def test_email_login_verify(self):
        response = self.client.post(self.register_url, self.user_data, format='json')
        print(f"test_email_login_verify: after register, mail.outbox length={len(mail.outbox)}")  # Debug
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0].body
        token = re.search(r'token=([a-f0-9-]+)', email).group(1)
        self.client.post(self.verify_email_url, {'token': token, 'email': 'test@example.com'}, format='json')
        print(f"test_email_login_verify: after verify, mail.outbox length={len(mail.outbox)}")  # Debug
        self.client.post(self.email_login_url, {'email': 'test@example.com'}, format='json')
        print(f"test_email_login_verify: after email login, mail.outbox length={len(mail.outbox)}")  # Debug
        login_email = mail.outbox[1].body
        login_token = re.search(r'token=([a-f0-9-]+)', login_email).group(1)
        data = {'token': login_token, 'email': 'test@example.com'}
        response = self.client.post(self.email_login_verify_url, data, format='json')
        print(f"test_email_login_verify: after verify login, mail.outbox length={len(mail.outbox)}")  # Debug
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_forgot_password(self):
        response = self.client.post(self.register_url, self.user_data, format='json')
        print(f"test_forgot_password: after register, mail.outbox length={len(mail.outbox)}")  # Debug
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0].body
        token = re.search(r'token=([a-f0-9-]+)', email).group(1)
        self.client.post(self.verify_email_url, {'token': token, 'email': 'test@example.com'}, format='json')
        print(f"test_forgot_password: after verify, mail.outbox length={len(mail.outbox)}")  # Debug
        response = self.client.post(self.forgot_password_url, {'email': 'test@example.com'}, format='json')
        print(f"test_forgot_password: after forgot password, mail.outbox length={len(mail.outbox)}")  # Debug
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Password reset link sent to your email')
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('Reset Your Password', mail.outbox[1].subject)

    def test_reset_password(self):
        cache.clear()  # Clear cache to reset rate limit
        response = self.client.post(self.register_url, self.user_data, format='json')
        print(f"test_reset_password: after register, mail.outbox length={len(mail.outbox)}")  # Debug
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1, f"Expected 1 email, got {len(mail.outbox)}")
        email = mail.outbox[0].body
        token = re.search(r'token=([a-f0-9-]+)', email).group(1)
        self.client.post(self.verify_email_url, {'token': token, 'email': 'test@example.com'}, format='json')
        print(f"test_reset_password: after verify, mail.outbox length={len(mail.outbox)}")  # Debug
        self.client.post(self.forgot_password_url, {'email': 'test@example.com'}, format='json')
        print(f"test_reset_password: after forgot password, mail.outbox length={len(mail.outbox)}")  # Debug
        self.assertEqual(len(mail.outbox), 2)
        reset_email = mail.outbox[1].body
        reset_token = re.search(r'token=([a-f0-9-]+)', reset_email).group(1)
        data = {'token': reset_token, 'email': 'test@example.com', 'new_password': 'NewTest1234'}
        response = self.client.post(self.reset_password_url, data, format='json')
        print(f"test_reset_password: after reset password, mail.outbox length={len(mail.outbox)}")  # Debug
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Password reset successfully')
        # Verify new password works
        login_data = {'username': 'testuser', 'password': 'NewTest1234'}
        response = self.client.post(self.login_url, login_data, format='json')
        print(f"test_reset_password: after login, mail.outbox length={len(mail.outbox)}")  # Debug
        self.assertEqual(response.status_code, status.HTTP_200_OK)