from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .utils import send_welcome_email
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    """Signal handler for user post save"""
    if created:
        logger.info(f"New user created: {instance.email}")
    
    # Send welcome email when user is verified
    if not created and instance.is_verified:
        # Check if this is the first time the user is being verified
        if 'is_verified' in kwargs.get('update_fields', []) or hasattr(instance, '_state') and instance._state.fields_cache.get('is_verified') != instance.is_verified:
            try:
                send_welcome_email(instance)
                logger.info(f"Welcome email sent to verified user: {instance.email}")
            except Exception as e:
                logger.error(f"Failed to send welcome email to {instance.email}: {str(e)}")
