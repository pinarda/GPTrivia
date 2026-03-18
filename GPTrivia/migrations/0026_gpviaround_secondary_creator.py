from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0025_profile_profile_intro'),
    ]

    operations = [
        migrations.AddField(
            model_name='gptriviaround',
            name='secondary_creator',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]
