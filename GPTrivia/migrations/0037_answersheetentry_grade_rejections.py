from django.db import migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0036_alter_mergedpresentation_crowned_winner_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='answersheetentry',
            name='grade_rejections',
            field=jsonfield.fields.JSONField(blank=True, default=list),
        ),
    ]
