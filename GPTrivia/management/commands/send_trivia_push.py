from django.core.management.base import BaseCommand
from GPTrivia.views import send_push_to_all, _collect_rounds
from asgiref.sync import async_to_sync
class Command(BaseCommand):
    help = 'Send trivia night push notification'


    def handle(self, *args, **kwargs):
        rounds = async_to_sync(_collect_rounds)()

        num_rounds = len(rounds)
        creators = sorted(set(r["creator"] for r in rounds if r["creator"]))
        num_creators = len(creators)
        creator_list = ", ".join(creators[:3])
        if len(creators) > 3:
            creator_list += f", +{len(creators) - 3} more"

        message = (
            f"We currently have {num_rounds} trivia rounds "
            f"from {num_creators} different creators ({creator_list})!"
        )

        full_message = f"Don’t forget to play tonight at 7:30pm PST!\n\n{message}"
        send_push_to_all("It’s Trivia Night!", full_message)
