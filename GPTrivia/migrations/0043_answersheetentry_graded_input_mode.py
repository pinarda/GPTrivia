from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0042_answersheetentry_pencil_answers'),
    ]

    operations = [
        migrations.AddField(
            model_name='answersheetentry',
            name='graded_input_mode',
            field=models.CharField(blank=True, choices=[('text', 'Text'), ('pencil', 'Pencil')], default='', max_length=16),
        ),
    ]
