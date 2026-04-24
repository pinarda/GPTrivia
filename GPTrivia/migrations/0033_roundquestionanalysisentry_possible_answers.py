from django.db import migrations
import jsonfield.fields


def _populate_possible_answers(apps, schema_editor):
    from GPTrivia.round_analysis import _build_possible_answers

    RoundQuestionAnalysisEntry = apps.get_model('GPTrivia', 'RoundQuestionAnalysisEntry')
    for entry in RoundQuestionAnalysisEntry.objects.all().only('id', 'answer_text', 'possible_answers'):
        if entry.possible_answers:
            continue
        generated_answers = _build_possible_answers(entry.answer_text)
        if not generated_answers:
            continue
        entry.possible_answers = generated_answers
        entry.save(update_fields=['possible_answers'])


def _clear_possible_answers(apps, schema_editor):
    RoundQuestionAnalysisEntry = apps.get_model('GPTrivia', 'RoundQuestionAnalysisEntry')
    RoundQuestionAnalysisEntry.objects.update(possible_answers=[])


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0032_answersheetentry'),
    ]

    operations = [
        migrations.AddField(
            model_name='roundquestionanalysisentry',
            name='possible_answers',
            field=jsonfield.fields.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(_populate_possible_answers, _clear_possible_answers),
    ]
