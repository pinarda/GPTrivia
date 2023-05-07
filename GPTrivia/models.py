from django.db import models
import jsonfield

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


    def __str__(self):
        return self.name
