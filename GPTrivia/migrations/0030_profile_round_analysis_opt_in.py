from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0029_roundquestionanalysisentry_instruction_text_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='round_analysis_opt_in',
            field=models.BooleanField(default=False),
        ),
    ]
