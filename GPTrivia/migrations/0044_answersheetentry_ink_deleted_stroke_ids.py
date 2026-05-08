from django.db import migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0043_answersheetentry_graded_input_mode'),
    ]

    operations = [
        migrations.AddField(
            model_name='answersheetentry',
            name='ink_deleted_stroke_ids',
            field=jsonfield.fields.JSONField(blank=True, default=list),
        ),
    ]
