from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0030_profile_round_analysis_opt_in'),
    ]

    operations = [
        migrations.AddField(
            model_name='submittedround',
            name='source_title',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
