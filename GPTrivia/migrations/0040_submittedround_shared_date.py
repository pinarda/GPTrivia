from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0039_answersheetentry_grade_invalidated_questions_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='submittedround',
            name='shared_date',
            field=models.DateField(blank=True, db_index=True, null=True),
        ),
    ]
