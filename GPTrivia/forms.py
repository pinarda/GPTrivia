from django import forms
from .models import GPTriviaRound, Profile

class GPTriviaRoundForm(forms.ModelForm):
    class Meta:
        model = GPTriviaRound
        fields = [
            'creator', 'title', 'major_category', 'minor_category1', 'minor_category2',
            'date', 'round_number', 'max_score',
            'score_alex', 'score_ichigo', 'score_megan', 'score_zach', 'score_jenny', 'score_debi',
            'score_dan', 'score_chris', 'score_drew'
        ]

class ProfilePictureForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['profile_picture']