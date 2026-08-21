import datetime

from django.db import migrations, models
from django.db.models import Q


def populate_source_creator_and_clear_stale_hodgepodge(apps, schema_editor):
    submitted_round = apps.get_model("GPTrivia", "SubmittedRound")

    for round_row in submitted_round.objects.filter(source_creator="").iterator():
        round_row.source_creator = round_row.creator
        round_row.save(update_fields=["source_creator"])

    submitted_round.objects.filter(
        Q(title__icontains="Hodgepodge Round")
        | Q(source_title__icontains="Hodgepodge Round"),
        Q(creator__iexact="Zach") | Q(source_creator__iexact="Zach"),
        shared_date=datetime.date(2026, 6, 13),
    ).update(
        is_consumed=True,
        is_currently_available=False,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("GPTrivia", "0049_mark_decorated_hodgepodge_available_round_consumed"),
    ]

    operations = [
        migrations.AddField(
            model_name="submittedround",
            name="gmail_message_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="submittedround",
            name="source_creator",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.RunPython(
            populate_source_creator_and_clear_stale_hodgepodge,
            migrations.RunPython.noop,
        ),
    ]
