# Generated by Django 4.1 on 2024-02-13 19:44

from django.db import migrations
import jsonfield.fields


class Migration(migrations.Migration):
    dependencies = [
        ("GPTrivia", "0006_alter_mergedpresentation_player_list"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mergedpresentation",
            name="player_list",
            field=jsonfield.fields.JSONField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="mergedpresentation",
            name="style_points",
            field=jsonfield.fields.JSONField(blank=True, null=True),
        ),
    ]