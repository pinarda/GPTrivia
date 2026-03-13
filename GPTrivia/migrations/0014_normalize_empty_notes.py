from django.db import migrations


EMPTY_NOTE_MARKERS = ("{}",)


def normalize_empty_notes(apps, schema_editor):
    GPTriviaRound = apps.get_model("GPTrivia", "GPTriviaRound")
    MergedPresentation = apps.get_model("GPTrivia", "MergedPresentation")

    GPTriviaRound.objects.filter(notes__in=EMPTY_NOTE_MARKERS).update(notes="")
    MergedPresentation.objects.filter(notes__in=EMPTY_NOTE_MARKERS).update(notes="")


def restore_empty_note_markers(apps, schema_editor):
    GPTriviaRound = apps.get_model("GPTrivia", "GPTriviaRound")
    MergedPresentation = apps.get_model("GPTrivia", "MergedPresentation")

    GPTriviaRound.objects.filter(notes="").update(notes="{}")
    MergedPresentation.objects.filter(notes="").update(notes="{}")


class Migration(migrations.Migration):

    dependencies = [
        ("GPTrivia", "0013_gptriviaround_extra_scores"),
    ]

    operations = [
        migrations.RunPython(normalize_empty_notes, restore_empty_note_markers),
    ]
