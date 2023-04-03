from django.db import models

class GPTriviaRound(models.Model):
    creator = models.CharField(max_length=100)
    title = models.CharField(max_length=100)
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
    replay = False
    cooperative = False

    def __str__(self):
        return self.title