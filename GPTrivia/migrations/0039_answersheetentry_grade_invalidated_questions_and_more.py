from django.db import migrations, models
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0038_roundanalysisworkerstate_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='answersheetentry',
            name='grade_invalidated_questions',
            field=jsonfield.fields.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='answersheetentry',
            name='was_graded',
            field=models.BooleanField(default=False),
        ),
    ]
