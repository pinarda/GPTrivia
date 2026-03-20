from django.core.management.base import BaseCommand
from GPTrivia.views import send_push_to_all, _collect_rounds
from asgiref.sync import async_to_sync


class Command(BaseCommand):
    help = 'Send trivia night push notification'


    def handle(self, *args, **kwargs):
        rounds = async_to_sync(_collect_rounds)()
        available_rounds = [round_row for round_row in rounds if round_row.get("is_new")]

        creators = sorted(set(r["creator"] for r in available_rounds if r["creator"]))
        num_creators = len(creators)
        if creators:
            creator_list = ", ".join(creators[:3])
            if len(creators) > 3:
                creator_list += f", +{len(creators) - 3} more"
            message = (
                f"We have new rounds from {num_creators} different creators ({creator_list})."
            )
        else:
            message = "No new rounds are currently available."

        full_message = f"{message}"
        send_push_to_all("Trivia at 7:30pm PST!", full_message)
