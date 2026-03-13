from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("GPTrivia", "0011_pushsubscription"),
    ]

    operations = [
        migrations.AddField(
            model_name="mergedpresentation",
            name="crowned_winner",
            field=models.CharField(blank=True, default="", max_length=100),
            preserve_default=False,
        ),
    ]
