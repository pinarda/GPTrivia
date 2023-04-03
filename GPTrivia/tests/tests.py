from django.test import TestCase, RequestFactory
from GPTrivia.models import GPTriviaRound
from GPTrivia.views import player_analysis

class PlayerAnalysisViewTests(TestCase):
    def test_creators_list_not_empty(self):
        # create a sample GPTriviaRound instance
        sample_round = GPTriviaRound.objects.create(
            creator="Alex",
            title="Test Title",
            major_category="Test Major Category",
            minor_category1="Test Minor Category1",
            minor_category2="Test Minor Category2",
            date="2023-01-01",
            round_number=1,
            max_score=10,
            score_alex=0,
            score_ichigo=6,
            score_megan=-1,
            score_zach=8,
            score_jenny=9,
            score_debi=4,
            score_dan=3,
            score_chris=2,
            score_drew=1,
        )

        factory = RequestFactory()
        request = factory.get('/player_analysis/')
        response = player_analysis(request)
        self.assertEqual(response.status_code, 200)