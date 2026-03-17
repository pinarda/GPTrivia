from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0021_profile_swoop_conversation_history'),
    ]

    operations = [
        migrations.AddField(
            model_name='submittedround',
            name='is_consumed',
            field=models.BooleanField(default=False),
        ),
    ]
