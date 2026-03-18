from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0024_profile_profile_page_theme'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='profile_intro',
            field=models.TextField(blank=True, default=''),
        ),
    ]
