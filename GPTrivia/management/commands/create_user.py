from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils.crypto import get_random_string

class Command(BaseCommand):
    help = 'Create a new user with a temporary password'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='The email of the new user')
        parser.add_argument('username', type=str, help='The username of the new user')

    def handle(self, *args, **options):
        email = options['email']
        username = options['username']
        password = get_random_string(length=8)

        user = User.objects.create_user(username, email, password)
        user.save()

        self.stdout.write(self.style.SUCCESS(f'Created user {username} with email {email} and temporary password {password}'))
        self.stdout.write(self.style.SUCCESS(f'Hashed password: {user.password}'))