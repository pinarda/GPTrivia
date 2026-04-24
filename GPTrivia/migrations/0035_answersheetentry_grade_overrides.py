from django.db import migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0034_answersheetentry_is_diverged'),
    ]

    operations = [
        migrations.AddField(
            model_name='answersheetentry',
            name='grade_overrides',
            field=jsonfield.fields.JSONField(blank=True, default=list),
        ),
    ]
