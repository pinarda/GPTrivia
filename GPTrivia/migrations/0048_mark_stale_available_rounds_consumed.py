import datetime

from django.db import migrations
from django.db.models import Q


STALE_AVAILABLE_ROUNDS = (
    ("Common Bond", "Ichigo", datetime.date(2026, 3, 27)),
    ("THIS IS THE TITLE", "Alex", datetime.date(2026, 3, 27)),
    ("Hodgepodge Round", "Zach", datetime.date(2026, 6, 13)),
)


def mark_stale_available_rounds_consumed(apps, schema_editor):
    submitted_round = apps.get_model("GPTrivia", "SubmittedRound")

    for title, creator, shared_date in STALE_AVAILABLE_ROUNDS:
        submitted_round.objects.filter(
            Q(title__iexact=title) | Q(source_title__iexact=title),
            creator__iexact=creator,
            shared_date=shared_date,
        ).update(
            is_consumed=True,
            is_currently_available=False,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("GPTrivia", "0047_submittedround_source_link"),
    ]

    operations = [
        migrations.RunPython(mark_stale_available_rounds_consumed, migrations.RunPython.noop),
    ]
