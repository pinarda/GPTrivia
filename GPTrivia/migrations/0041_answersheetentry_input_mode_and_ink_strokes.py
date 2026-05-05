from django.db import migrations, models
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0040_submittedround_shared_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='answersheetentry',
            name='ink_strokes',
            field=jsonfield.fields.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='answersheetentry',
            name='input_mode',
            field=models.CharField(choices=[('text', 'Text'), ('pencil', 'Pencil')], default='text', max_length=16),
        ),
    ]
