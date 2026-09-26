from django.db import migrations, models
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0050_submittedround_gmail_identity'),
    ]

    operations = [
        migrations.AddField(
            model_name='mergedpresentation',
            name='source_round_ids',
            field=jsonfield.fields.JSONField(blank=True, default=list),
        ),
        migrations.AlterField(
            model_name='homepresentationbuildjob',
            name='action',
            field=models.CharField(
                choices=[
                    ('generate', 'Generate'),
                    ('update', 'Update'),
                    ('replace', 'Replace'),
                ],
                max_length=16,
            ),
        ),
    ]
