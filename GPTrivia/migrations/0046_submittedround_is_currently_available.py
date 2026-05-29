from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0045_homepresentationbuildjob'),
    ]

    operations = [
        migrations.AddField(
            model_name='submittedround',
            name='is_currently_available',
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
