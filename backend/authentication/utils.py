from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import secrets
import string
from .models import EmailVerificationToken


def generate_token(length=32):
    """Generate a secure random token"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def send_password_reset_email(user, token):
    """Send password reset email"""
    subject = 'Password Reset Request'
    
    # Create the reset URL (you can customize this based on your frontend)
    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}" if hasattr(settings, 'FRONTEND_URL') else f"http://localhost:3000/reset-password?token={token}"
    
    # Create HTML message
    html_message = f"""
    <html>
    <body>
        <h2>Password Reset Request</h2>
        <p>Hello {user.get_full_name()},</p>
        <p>You have requested to reset your password. Please click the link below to reset your password:</p>
        <p><a href="{reset_url}" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Reset Password</a></p>
        <p>If you didn't request this, please ignore this email.</p>
        <p>This link will expire in 1 hour.</p>
        <br>
        <p>Best regards,<br>WFMonit Team</p>
    </body>
    </html>
    """
    
    # Create plain text message
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        # Log the error
        print(f"Error sending password reset email: {str(e)}")
        return False


def send_verification_email(user):
    """Send email verification email"""
    # Create verification token
    token = generate_token()
    expires_at = timezone.now() + timezone.timedelta(hours=24)
    
    EmailVerificationToken.objects.create(
        user=user,
        token=token,
        expires_at=expires_at
    )
    
    subject = 'Verify Your Email Address'
    
    # Create the verification URL
    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}" if hasattr(settings, 'FRONTEND_URL') else f"http://localhost:3000/verify-email?token={token}"
    
    # Create HTML message
    html_message = f"""
    <html>
    <body>
        <h2>Welcome to WFMonit!</h2>
        <p>Hello {user.get_full_name()},</p>
        <p>Thank you for registering with WFMonit. Please click the link below to verify your email address:</p>
        <p><a href="{verification_url}" style="background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Verify Email</a></p>
        <p>If you didn't create an account, please ignore this email.</p>
        <p>This link will expire in 24 hours.</p>
        <br>
        <p>Best regards,<br>WFMonit Team</p>
    </body>
    </html>
    """
    
    # Create plain text message
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        # Log the error
        print(f"Error sending verification email: {str(e)}")
        return False


def send_welcome_email(user):
    """Send welcome email after successful verification"""
    subject = 'Welcome to WFMonit!'
    
    html_message = f"""
    <html>
    <body>
        <h2>Welcome to WFMonit!</h2>
        <p>Hello {user.get_full_name()},</p>
        <p>Your email has been successfully verified. Welcome to WFMonit!</p>
        <p>You can now enjoy full access to all our features.</p>
        <br>
        <p>Best regards,<br>WFMonit Team</p>
    </body>
    </html>
    """
    
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending welcome email: {str(e)}")
        return False
