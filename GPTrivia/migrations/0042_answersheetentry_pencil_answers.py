from django.db import migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0041_answersheetentry_input_mode_and_ink_strokes'),
    ]

    operations = [
        migrations.AddField(
            model_name='answersheetentry',
            name='pencil_answers',
            field=jsonfield.fields.JSONField(blank=True, default=list),
        ),
    ]
