import datetime

from django.db import migrations
from django.db.models import Q


def mark_decorated_hodgepodge_round_consumed(apps, schema_editor):
    submitted_round = apps.get_model("GPTrivia", "SubmittedRound")

    submitted_round.objects.filter(
        Q(title__icontains="Hodgepodge Round") | Q(source_title__icontains="Hodgepodge Round"),
        creator__iexact="Zach",
        shared_date=datetime.date(2026, 6, 13),
    ).update(
        is_consumed=True,
        is_currently_available=False,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("GPTrivia", "0048_mark_stale_available_rounds_consumed"),
    ]

    operations = [
        migrations.RunPython(mark_decorated_hodgepodge_round_consumed, migrations.RunPython.noop),
    ]
