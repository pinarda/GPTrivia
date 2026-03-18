from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0023_profile_profile_page_colors'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='profile_page_theme',
            field=models.CharField(
                choices=[('default', 'Current (default)'), ('light', 'Light')],
                default='default',
                max_length=16,
            ),
        ),
    ]
