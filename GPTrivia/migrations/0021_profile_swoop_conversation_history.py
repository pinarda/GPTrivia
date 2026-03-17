from django.db import migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0020_submittedround'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='swoop_conversation_history',
            field=jsonfield.fields.JSONField(blank=True, default=list),
        ),
    ]
