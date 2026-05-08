from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import PasswordResetToken, EmailVerificationToken
import logging

logger = logging.getLogger(__name__)


@shared_task
def send_email_task(subject, message, from_email, recipient_list, html_message=None):
    """Async task to send emails"""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Email sent successfully to {recipient_list}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {recipient_list}: {str(e)}")
        return False


@shared_task
def cleanup_expired_tokens():
    """Clean up expired tokens"""
    try:
        current_time = timezone.now()
        
        # Delete expired password reset tokens
        expired_password_tokens = PasswordResetToken.objects.filter(
            expires_at__lt=current_time,
            is_used=True
        )
        password_count = expired_password_tokens.count()
        expired_password_tokens.delete()
        
        # Delete expired email verification tokens
        expired_verification_tokens = EmailVerificationToken.objects.filter(
            expires_at__lt=current_time,
            is_used=True
        )
        verification_count = expired_verification_tokens.count()
        expired_verification_tokens.delete()
        
        logger.info(f"Cleaned up {password_count} password reset tokens and {verification_count} verification tokens")
        return {
            'password_tokens_deleted': password_count,
            'verification_tokens_deleted': verification_count
        }
    
    except Exception as e:
        logger.error(f"Error cleaning up expired tokens: {str(e)}")
        return False


@shared_task
def send_password_reset_email_task(user_id, token):
    """Async task to send password reset email"""
    from .models import User
    from .utils import send_password_reset_email
    
    try:
        user = User.objects.get(id=user_id)
        result = send_password_reset_email(user, token)
        if result:
            logger.info(f"Password reset email sent to {user.email}")
        else:
            logger.error(f"Failed to send password reset email to {user.email}")
        return result
    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} not found")
        return False
    except Exception as e:
        logger.error(f"Error sending password reset email: {str(e)}")
        return False


@shared_task
def send_verification_email_task(user_id):
    """Async task to send verification email"""
    from .models import User
    from .utils import send_verification_email
    
    try:
        user = User.objects.get(id=user_id)
        result = send_verification_email(user)
        if result:
            logger.info(f"Verification email sent to {user.email}")
        else:
            logger.error(f"Failed to send verification email to {user.email}")
        return result
    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} not found")
        return False
    except Exception as e:
        logger.error(f"Error sending verification email: {str(e)}")
        return False
