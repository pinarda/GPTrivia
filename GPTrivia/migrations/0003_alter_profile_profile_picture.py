# Generated by Django 4.1.7 on 2023-11-23 21:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0002_alter_gptriviaround_title_profile'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='profile_picture',
            field=models.ImageField(default='./default.jpg', upload_to='profile_pics'),
        ),
    ]
