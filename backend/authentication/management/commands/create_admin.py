from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Create a superuser with environment variables or prompts'

    def add_arguments(self, parser):
        parser.add_argument('--email', type=str, help='Email for the superuser')
        parser.add_argument('--username', type=str, help='Username for the superuser')
        parser.add_argument('--password', type=str, help='Password for the superuser')

    def handle(self, *args, **options):
        email = options['email'] or input('Email: ')
        username = options['username'] or input('Username: ')
        
        if User.objects.filter(email=email).exists():
            self.stdout.write(
                self.style.WARNING(f'User with email {email} already exists')
            )
            return
        
        if User.objects.filter(username=username).exists():
            self.stdout.write(
                self.style.WARNING(f'User with username {username} already exists')
            )
            return

        password = options['password']
        if not password:
            import getpass
            password = getpass.getpass('Password: ')

        user = User.objects.create_superuser(
            email=email,
            username=username,
            password=password,
            first_name='Super',
            last_name='Admin'
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'Superuser {user.email} created successfully')
        )
