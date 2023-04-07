from rest_framework import serializers
from GPTrivia.models import GPTriviaRound

class GPTriviaRoundSerializer(serializers.ModelSerializer):
    class Meta:
        model = GPTriviaRound
        fields = '__all__' # Or specify the fields you want to expose in the API

