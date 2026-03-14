from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("GPTrivia", "0017_mergedpresentation_status_and_error_message"),
    ]

    operations = [
        migrations.CreateModel(
            name="PresentationBuildState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(default="home_page", max_length=32, unique=True)),
                ("is_active", models.BooleanField(default=False)),
                ("action", models.CharField(blank=True, default="", max_length=16)),
                ("presentation_name", models.CharField(blank=True, default="", max_length=255)),
                ("presentation_id", models.CharField(blank=True, default="", max_length=255)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
