# Generated by Django 4.1 on 2024-02-13 19:40

from django.db import migrations
import jsonfield.fields


class Migration(migrations.Migration):
    dependencies = [
        ("GPTrivia", "0005_mergedpresentation_host_mergedpresentation_notes_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mergedpresentation",
            name="player_list",
            field=jsonfield.fields.JSONField(blank=True, default=list),
        ),
    ]