from rest_framework import serializers
from GPTrivia.models import GPTriviaRound, MergedPresentation
import json

class GPTriviaRoundSerializer(serializers.ModelSerializer):
    class Meta:
        model = GPTriviaRound
        fields = '__all__' # Or specify the fields you want to expose in the API

class MergedPresentationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MergedPresentation
        fields = '__all__' # Or specify the fields you want to expose in the API