from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0015_profile_profile_icon'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='profile_color',
            field=models.CharField(blank=True, default='', max_length=7),
        ),
    ]
