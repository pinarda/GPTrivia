from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('GPTrivia', '0022_submittedround_is_consumed'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='profile_page_chrome_color',
            field=models.CharField(blank=True, default='', max_length=7),
        ),
        migrations.AddField(
            model_name='profile',
            name='profile_page_trivia_color_one',
            field=models.CharField(blank=True, default='', max_length=7),
        ),
        migrations.AddField(
            model_name='profile',
            name='profile_page_trivia_color_two',
            field=models.CharField(blank=True, default='', max_length=7),
        ),
        migrations.AddField(
            model_name='profile',
            name='profile_page_trivia_color_three',
            field=models.CharField(blank=True, default='', max_length=7),
        ),
    ]
