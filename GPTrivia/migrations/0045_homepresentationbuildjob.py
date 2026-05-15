from django.db import migrations, models
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0044_answersheetentry_ink_deleted_stroke_ids'),
    ]

    operations = [
        migrations.CreateModel(
            name='HomePresentationBuildJob',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('action', models.CharField(choices=[('generate', 'Generate'), ('update', 'Update')], max_length=16)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('running', 'Running'), ('completed', 'Completed'), ('failed', 'Failed')], db_index=True, default='pending', max_length=16)),
                ('presentation_name', models.CharField(max_length=255)),
                ('presentation_id', models.CharField(blank=True, default='', max_length=255)),
                ('selected_presentation_id', models.CharField(blank=True, default='', max_length=255)),
                ('requested_by', models.CharField(blank=True, default='', max_length=100)),
                ('round_payload', jsonfield.fields.JSONField(blank=True, default=list)),
                ('result_presentation_id', models.CharField(blank=True, default='', max_length=255)),
                ('error_message', models.TextField(blank=True, default='')),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['created_at', 'id'],
            },
        ),
    ]
