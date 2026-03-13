from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0014_normalize_empty_notes'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='profile_icon',
            field=models.ImageField(blank=True, default='', upload_to='profile_icons'),
        ),
    ]
