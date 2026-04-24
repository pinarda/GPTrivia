from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0037_answersheetentry_grade_rejections'),
    ]

    operations = [
        migrations.CreateModel(
            name='RoundAnalysisWorkerState',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(default='default', max_length=32, unique=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddField(
            model_name='roundquestionanalysisrun',
            name='batch_key',
            field=models.CharField(blank=True, db_index=True, default='', max_length=64),
        ),
        migrations.AddField(
            model_name='roundquestionanalysisrun',
            name='batch_label',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddField(
            model_name='roundquestionanalysisrun',
            name='scheduled_for',
            field=models.DateTimeField(db_index=True, default=django.utils.timezone.now),
        ),
    ]
