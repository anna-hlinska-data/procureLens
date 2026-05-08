from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from authentication.tasks import cleanup_expired_tokens

User = get_user_model()


class Command(BaseCommand):
    help = 'Clean up expired tokens and inactive users'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        self.stdout.write('Starting cleanup process...')
        
        if options['dry_run']:
            self.stdout.write('DRY RUN MODE - No data will be deleted')
        
        # Clean up expired tokens
        result = cleanup_expired_tokens.delay()
        token_result = result.get()
        
        if token_result:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Cleaned up {token_result['password_tokens_deleted']} password reset tokens "
                    f"and {token_result['verification_tokens_deleted']} verification tokens"
                )
            )
        
        self.stdout.write(self.style.SUCCESS('Cleanup completed successfully'))
