from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0018_presentationbuildstate'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='site_theme',
            field=models.CharField(
                choices=[('default', 'Current (default)'), ('light', 'Light')],
                default='default',
                max_length=16,
            ),
        ),
    ]
