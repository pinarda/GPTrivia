import jsonfield.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("GPTrivia", "0012_mergedpresentation_crowned_winner"),
    ]

    operations = [
        migrations.AddField(
            model_name="gptriviaround",
            name="extra_scores",
            field=jsonfield.fields.JSONField(blank=True, default=dict),
        ),
    ]
