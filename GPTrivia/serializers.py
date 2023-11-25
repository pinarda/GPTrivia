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

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        # Serialize round_names and creator_list as JSON if they are not None
        if ret['joker_round_indices'] is not None:
            ret['joker_round_indices'] = json.loads(ret['joker_round_indices'])
        return ret