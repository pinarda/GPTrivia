from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0046_submittedround_is_currently_available'),
    ]

    operations = [
        migrations.AddField(
            model_name='submittedround',
            name='source_link',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
