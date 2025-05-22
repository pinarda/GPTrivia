from django.core.management.base import BaseCommand
from GPTrivia.views import send_push_to_all  # Update path as needed

class Command(BaseCommand):
    help = 'Send trivia night push notification'

    def handle(self, *args, **kwargs):
        send_push_to_all("It's Trivia Night!", "Don't forget to play tonight at 7:30pm PST!")
