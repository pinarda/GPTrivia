from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('GPTrivia', '0031_submittedround_source_title'),
    ]

    operations = [
        migrations.CreateModel(
            name='AnswerSheetEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('trivia_date', models.DateField(db_index=True)),
                ('answers', jsonfield.fields.JSONField(blank=True, default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('round', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='answer_sheet_entries', to='GPTrivia.gptriviaround')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='answer_sheet_entries', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['trivia_date', 'round__round_number', 'round_id'],
                'unique_together': {('user', 'round')},
            },
        ),
    ]
