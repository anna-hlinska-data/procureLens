from rest_framework import status, generics, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth import login
from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiExample
from django.core.cache import cache
from django.conf import settings
import logging

from .models import User, PasswordResetToken, EmailVerificationToken
from .serializers import (
    UserRegistrationSerializer,
    UserLoginSerializer,
    UserProfileSerializer,
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
    EmailVerificationSerializer
)
from .utils import generate_token, send_password_reset_email, send_verification_email

logger = logging.getLogger(__name__)


class UserRegistrationView(generics.CreateAPIView):
    """User registration endpoint"""
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Register a new user",
        description="Create a new user account with email verification",
        examples=[
            OpenApiExample(
                "Registration Example",
                value={
                    "email": "user@example.com",
                    "username": "john_doe",
                    "first_name": "John",
                    "last_name": "Doe",
                    "password": "securepassword123",
                    "password_confirm": "securepassword123"
                }
            )
        ]
    )
    def post(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                user = serializer.save()
                
                # Send verification email
                send_verification_email(user)
                
                # Generate JWT tokens
                refresh = RefreshToken.for_user(user)
                access_token = refresh.access_token
                
                logger.info(f"New user registered: {user.email}")
                
                return Response({
                    'message': 'User registered successfully. Please check your email for verification.',
                    'user': UserProfileSerializer(user).data,
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(access_token),
                    }
                }, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Error during user registration: {str(e)}")
            return Response(
                {'error': 'An error occurred during registration'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserLoginView(TokenObtainPairView):
    """User login endpoint"""
    serializer_class = UserLoginSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="User login",
        description="Authenticate user and return JWT tokens",
        examples=[
            OpenApiExample(
                "Login Example",
                value={
                    "email": "user@example.com",
                    "password": "securepassword123"
                }
            )
        ]
    )
    def post(self, request, *args, **kwargs):
        try:
            serializer = UserLoginSerializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                user = serializer.validated_data['user']
                
                # Update last login
                user.last_login = timezone.now()
                user.save(update_fields=['last_login'])
                
                # Generate JWT tokens
                refresh = RefreshToken.for_user(user)
                access_token = refresh.access_token
                
                # Cache user session
                cache_key = f"user_session_{user.id}"
                cache.set(cache_key, {
                    'user_id': str(user.id),
                    'email': user.email,
                    'last_login': user.last_login.isoformat() if user.last_login else None
                }, timeout=settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds())
                
                logger.info(f"User logged in: {user.email}")
                
                return Response({
                    'message': 'Login successful',
                    'user': UserProfileSerializer(user).data,
                    'tokens': {
                        'refresh': str(refresh),
                        'access': str(access_token),
                    }
                }, status=status.HTTP_200_OK)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Error during user login: {str(e)}")
            return Response(
                {'error': 'An error occurred during login'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserProfileView(generics.RetrieveUpdateAPIView):
    """User profile endpoint"""
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    @extend_schema(
        summary="Get user profile",
        description="Retrieve authenticated user's profile information"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Update user profile",
        description="Update authenticated user's profile information"
    )
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)


class ChangePasswordView(APIView):
    """Change password endpoint"""
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Change password",
        description="Change user's password",
        request=ChangePasswordSerializer,
        examples=[
            OpenApiExample(
                "Change Password Example",
                value={
                    "old_password": "oldpassword123",
                    "new_password": "newpassword123",
                    "confirm_password": "newpassword123"
                }
            )
        ]
    )
    def post(self, request):
        try:
            serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                user = request.user
                user.set_password(serializer.validated_data['new_password'])
                user.save()
                
                logger.info(f"Password changed for user: {user.email}")
                
                return Response({
                    'message': 'Password changed successfully'
                }, status=status.HTTP_200_OK)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Error during password change: {str(e)}")
            return Response(
                {'error': 'An error occurred while changing password'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ForgotPasswordView(APIView):
    """Forgot password endpoint"""
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Forgot password",
        description="Send password reset email to user",
        request=ForgotPasswordSerializer,
        examples=[
            OpenApiExample(
                "Forgot Password Example",
                value={"email": "user@example.com"}
            )
        ]
    )
    def post(self, request):
        try:
            serializer = ForgotPasswordSerializer(data=request.data)
            if serializer.is_valid():
                user = serializer.context['user']
                
                # Invalidate existing reset tokens
                PasswordResetToken.objects.filter(user=user, is_used=False).update(is_used=True)
                
                # Create new reset token
                token = generate_token()
                expires_at = timezone.now() + timezone.timedelta(hours=1)
                
                PasswordResetToken.objects.create(
                    user=user,
                    token=token,
                    expires_at=expires_at
                )
                
                # Send password reset email
                send_password_reset_email(user, token)
                
                logger.info(f"Password reset email sent to: {user.email}")
                
                return Response({
                    'message': 'Password reset email sent successfully'
                }, status=status.HTTP_200_OK)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Error during forgot password: {str(e)}")
            return Response(
                {'error': 'An error occurred while processing request'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ResetPasswordView(APIView):
    """Reset password endpoint"""
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Reset password",
        description="Reset user password using token",
        request=ResetPasswordSerializer,
        examples=[
            OpenApiExample(
                "Reset Password Example",
                value={
                    "token": "reset-token-here",
                    "new_password": "newpassword123",
                    "confirm_password": "newpassword123"
                }
            )
        ]
    )
    def post(self, request):
        try:
            serializer = ResetPasswordSerializer(data=request.data)
            if serializer.is_valid():
                token = serializer.validated_data['token']
                new_password = serializer.validated_data['new_password']
                
                try:
                    reset_token = PasswordResetToken.objects.get(token=token)
                    
                    if not reset_token.is_valid:
                        return Response({
                            'error': 'Invalid or expired reset token'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Reset password
                    user = reset_token.user
                    user.set_password(new_password)
                    user.save()
                    
                    # Mark token as used
                    reset_token.is_used = True
                    reset_token.save()
                    
                    logger.info(f"Password reset successful for user: {user.email}")
                    
                    return Response({
                        'message': 'Password reset successfully'
                    }, status=status.HTTP_200_OK)
                
                except PasswordResetToken.DoesNotExist:
                    return Response({
                        'error': 'Invalid reset token'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Error during password reset: {str(e)}")
            return Response(
                {'error': 'An error occurred while resetting password'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VerifyEmailView(APIView):
    """Email verification endpoint"""
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Verify email",
        description="Verify user email using token",
        request=EmailVerificationSerializer,
        examples=[
            OpenApiExample(
                "Verify Email Example",
                value={"token": "verification-token-here"}
            )
        ]
    )
    def post(self, request):
        try:
            serializer = EmailVerificationSerializer(data=request.data)
            if serializer.is_valid():
                token = serializer.validated_data['token']
                
                try:
                    verification_token = EmailVerificationToken.objects.get(token=token)
                    
                    if not verification_token.is_valid:
                        return Response({
                            'error': 'Invalid or expired verification token'
                        }, status=status.HTTP_400_BAD_REQUEST)
                    
                    # Verify user email
                    user = verification_token.user
                    user.is_verified = True
                    user.save()
                    
                    # Mark token as used
                    verification_token.is_used = True
                    verification_token.save()
                    
                    logger.info(f"Email verified for user: {user.email}")
                    
                    return Response({
                        'message': 'Email verified successfully'
                    }, status=status.HTTP_200_OK)
                
                except EmailVerificationToken.DoesNotExist:
                    return Response({
                        'error': 'Invalid verification token'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Error during email verification: {str(e)}")
            return Response(
                {'error': 'An error occurred while verifying email'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class LogoutView(APIView):
    """User logout endpoint"""
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="User logout",
        description="Logout user and blacklist refresh token"
    )
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            
            # Clear user session cache
            cache_key = f"user_session_{request.user.id}"
            cache.delete(cache_key)
            
            logger.info(f"User logged out: {request.user.email}")
            
            return Response({
                'message': 'Logout successful'
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error during logout: {str(e)}")
            return Response({
                'message': 'Logout successful'  # Always return success for logout
            }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def health_check(request):
    """Health check endpoint"""
    return Response({
        'status': 'healthy',
        'user': request.user.email,
        'timestamp': timezone.now()
    })
