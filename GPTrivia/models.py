from django.db import models
import jsonfield
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# Signal handlers
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    profile_picture = models.ImageField(upload_to='profile_pics', default='./default.jpg')

    def __str__(self):
        return f'{self.user.username} Profile'


    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)  # Call the "real" save() method

class GPTriviaRound(models.Model):
    creator = models.CharField(max_length=100)
    title = models.CharField(max_length=150)
    major_category = models.CharField(max_length=100)
    minor_category1 = models.CharField(max_length=100)
    minor_category2 = models.CharField(max_length=100)
    date = models.DateField()
    # The round number is an integer
    round_number = models.IntegerField()
    # The max score is float
    max_score = models.FloatField(null=True)
    # The remainder can be floats
    score_alex = models.FloatField(null=True)
    score_ichigo = models.FloatField(null=True)
    score_megan = models.FloatField(null=True)
    score_zach = models.FloatField(null=True)
    score_jenny = models.FloatField(null=True)
    score_debi = models.FloatField(null=True)
    score_dan = models.FloatField(null=True)
    score_chris = models.FloatField(null=True)
    score_drew = models.FloatField(null=True)
    score_jeff = models.FloatField(null=True)
    score_dillon = models.FloatField(null=True)
    score_paige = models.FloatField(null=True)
    score_tom = models.FloatField(null=True)
    replay = models.BooleanField(default=False)
    cooperative = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    link = models.CharField(max_length=255, blank=True, default='https://docs.google.com/presentation/d/1gC9DR9TmQK_9ls8Npw8Sc99qKI6YN9nRqLuVj0W07ns/embed?start=false&slide=id.g717c8ec4cb_2_0')

    def __str__(self):
        return self.title


class MergedPresentation(models.Model):
    name = models.CharField(max_length=255)
    presentation_id = models.CharField(max_length=255)
    round_names = jsonfield.JSONField(default=list)
    creator_list = jsonfield.JSONField(default=list)
    joker_round_indices = jsonfield.JSONField(null=True, blank=True)
    player_list = jsonfield.JSONField(null=True, blank=True)
    host = models.CharField(max_length=100, default='Unknown')
    scorekeeper = models.CharField(max_length=100, default='Unknown')
    style_points = jsonfield.JSONField(null=True, blank=True)
    notes = models.TextField(blank=True)
    tiebreak_winner = models.CharField(max_length=100, blank=True)


    def __str__(self):
        return self.name


class JeopardyRound(models.Model):
    JEOPARDY = 'JEOPARDY'
    DOUBLE_JEOPARDY = 'DOUBLE_JEOPARDY'
    FINAL_JEOPARDY = 'FINAL_JEOPARDY'
    ROUND_TYPES = [
        (JEOPARDY, 'Jeopardy'),
        (DOUBLE_JEOPARDY, 'Double Jeopardy'),
        (FINAL_JEOPARDY, 'Final Jeopardy'),
    ]
    title = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=ROUND_TYPES, default=JEOPARDY)


class JeopardyQuestion(models.Model):
    round = models.ForeignKey(JeopardyRound, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    is_active = models.BooleanField(default=True)  # Track if the question is still active
    daily_double = models.BooleanField(default=False)  # New field
