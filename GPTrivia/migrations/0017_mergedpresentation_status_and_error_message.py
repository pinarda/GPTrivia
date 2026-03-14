from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0016_profile_profile_color'),
    ]

    operations = [
        migrations.AddField(
            model_name='mergedpresentation',
            name='error_message',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='mergedpresentation',
            name='status',
            field=models.CharField(
                choices=[('ready', 'Ready'), ('failed', 'Failed')],
                default='ready',
                max_length=16,
            ),
        ),
    ]
