from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0033_roundquestionanalysisentry_possible_answers'),
    ]

    operations = [
        migrations.AddField(
            model_name='answersheetentry',
            name='is_diverged',
            field=models.BooleanField(default=False),
        ),
    ]
