from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from .models import PasswordResetToken, EmailVerificationToken
from .utils import generate_token
from django.utils import timezone

User = get_user_model()


class UserModelTest(TestCase):
    """Test cases for User model"""
    
    def setUp(self):
        self.user_data = {
            'email': 'test@example.com',
            'username': 'testuser',
            'first_name': 'Test',
            'last_name': 'User',
            'password': 'testpass123'
        }
    
    def test_create_user(self):
        user = User.objects.create_user(**self.user_data)
        self.assertEqual(user.email, self.user_data['email'])
        self.assertEqual(user.username, self.user_data['username'])
        self.assertTrue(user.check_password(self.user_data['password']))
        self.assertFalse(user.is_verified)
        self.assertTrue(user.is_active)
    
    def test_create_superuser(self):
        user = User.objects.create_superuser(**self.user_data)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
    
    def test_user_string_representation(self):
        user = User.objects.create_user(**self.user_data)
        expected = f"{user.email} - {user.get_full_name()}"
        self.assertEqual(str(user), expected)


class AuthenticationAPITest(APITestCase):
    """Test cases for authentication API endpoints"""
    
    def setUp(self):
        self.register_url = reverse('user-register')
        self.login_url = reverse('user-login')
        self.profile_url = reverse('user-profile')
        self.user_data = {
            'email': 'test@example.com',
            'username': 'testuser',
            'first_name': 'Test',
            'last_name': 'User',
            'password': 'testpass123',
            'password_confirm': 'testpass123'
        }
    
    def test_user_registration(self):
        response = self.client.post(self.register_url, self.user_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('tokens', response.data)
        self.assertIn('user', response.data)
        
        # Check if user was created
        user = User.objects.get(email=self.user_data['email'])
        self.assertEqual(user.username, self.user_data['username'])
        self.assertFalse(user.is_verified)
    
    def test_user_registration_password_mismatch(self):
        data = self.user_data.copy()
        data['password_confirm'] = 'differentpass'
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_user_registration_duplicate_email(self):
        # Create first user
        User.objects.create_user(
            email=self.user_data['email'],
            username='firstuser',
            password='pass123'
        )
        
        response = self.client.post(self.register_url, self.user_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_user_login(self):
        # Create user first
        user = User.objects.create_user(
            email=self.user_data['email'],
            username=self.user_data['username'],
            password=self.user_data['password']
        )
        
        login_data = {
            'email': self.user_data['email'],
            'password': self.user_data['password']
        }
        response = self.client.post(self.login_url, login_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('tokens', response.data)
    
    def test_user_login_invalid_credentials(self):
        login_data = {
            'email': 'nonexistent@example.com',
            'password': 'wrongpass'
        }
        response = self.client.post(self.login_url, login_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_user_profile_access(self):
        # Create and authenticate user
        user = User.objects.create_user(
            email=self.user_data['email'],
            username=self.user_data['username'],
            password=self.user_data['password']
        )
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], user.email)
    
    def test_user_profile_unauthorized(self):
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PasswordResetTest(APITestCase):
    """Test cases for password reset functionality"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='oldpass123'
        )
        self.forgot_password_url = reverse('forgot-password')
        self.reset_password_url = reverse('reset-password')
    
    def test_forgot_password(self):
        data = {'email': self.user.email}
        response = self.client.post(self.forgot_password_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check if token was created
        self.assertTrue(
            PasswordResetToken.objects.filter(user=self.user).exists()
        )
    
    def test_forgot_password_invalid_email(self):
        data = {'email': 'nonexistent@example.com'}
        response = self.client.post(self.forgot_password_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_reset_password(self):
        # Create reset token
        token = generate_token()
        expires_at = timezone.now() + timezone.timedelta(hours=1)
        PasswordResetToken.objects.create(
            user=self.user,
            token=token,
            expires_at=expires_at
        )
        
        data = {
            'token': token,
            'new_password': 'newpass123',
            'confirm_password': 'newpass123'
        }
        response = self.client.post(self.reset_password_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check if password was changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newpass123'))


class EmailVerificationTest(APITestCase):
    """Test cases for email verification"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='pass123'
        )
        self.verify_email_url = reverse('verify-email')
    
    def test_verify_email(self):
        # Create verification token
        token = generate_token()
        expires_at = timezone.now() + timezone.timedelta(hours=24)
        EmailVerificationToken.objects.create(
            user=self.user,
            token=token,
            expires_at=expires_at
        )
        
        data = {'token': token}
        response = self.client.post(self.verify_email_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check if user is verified
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_verified)
    
    def test_verify_email_invalid_token(self):
        data = {'token': 'invalid-token'}
        response = self.client.post(self.verify_email_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_verify_email_expired_token(self):
        # Create expired token
        token = generate_token()
        expires_at = timezone.now() - timezone.timedelta(hours=1)
        EmailVerificationToken.objects.create(
            user=self.user,
            token=token,
            expires_at=expires_at
        )
        
        data = {'token': token}
        response = self.client.post(self.verify_email_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
