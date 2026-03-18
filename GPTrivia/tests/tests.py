import os
os.environ['OPENAI_API_KEY'] = 'sk-'
import inspect
from unittest.mock import patch

from django.test import TestCase, RequestFactory
from GPTrivia.models import GPTriviaRound, MergedPresentation
from GPTrivia.views import player_analysis, player_profile
from ..mail import create_presentation
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import datetime
from django.contrib.auth.models import User
from openai import OpenAI

mail_file_directory = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRET_FILE = '/Users/alex/client_secret.json'
token_file_path = os.path.join(mail_file_directory, '../token.pickle')
SCOPES = ['https://www.googleapis.com/auth/gmail.modify',
          'https://www.googleapis.com/auth/presentations',
          'https://www.googleapis.com/auth/script.external_request',
          'https://www.googleapis.com/auth/script.scriptapp',
          'https://www.googleapis.com/auth/script.projects']

from django.urls import reverse

class PlayerAnalysisPlotTests(TestCase):

    def setUp(self):
        self.analysis_threshold_patcher = patch('GPTrivia.analysis.MIN_ANALYSIS_ROUNDS', 1)
        self.analysis_threshold_patcher.start()
        self.addCleanup(self.analysis_threshold_patcher.stop)

        sample_round = GPTriviaRound.objects.create(
            creator="Megan",
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

        sample_round2 = GPTriviaRound.objects.create(
            creator="Megan",
            title="Test Title2",
            major_category="Test Major Category",
            minor_category1="Test Minor Category1",
            minor_category2="Test Minor Category2",
            date="2023-01-01",
            round_number=1,
            max_score=10,
            score_alex=7,
            score_ichigo=10,
            score_megan=10,
            score_zach=8,
            score_jenny=0,
            score_debi=9,
            score_dan=7,
            score_chris=8,
            score_drew=8,
        )

        sample_round3 = GPTriviaRound.objects.create(
            creator="Megan",
            title="Test Title3 ",
            major_category="Test Major Category 2",
            minor_category1="Test Minor Category1",
            minor_category2="Test Minor Category2",
            date="2023-01-01",
            round_number=1,
            max_score=1,
            score_alex=3,
            score_ichigo=2,
            score_megan=0,
            score_zach=2,
            score_jenny=3,
            score_debi=4,
            score_dan=3,
            score_chris=2,
            score_drew=1,
        )

        sample_round = GPTriviaRound.objects.create(
            creator="Jenny",
            title="Test Title",
            major_category="Test Major Category",
            minor_category1="Test Minor Category1",
            minor_category2="Test Minor Category2",
            date="2023-01-01",
            round_number=1,
            max_score=10,
            score_alex=1,
            score_ichigo=6,
            score_megan=-1,
            score_zach=8,
            score_jenny=9,
            score_debi=4,
            score_dan=3,
            score_chris=2,
            score_drew=1,
        )

        sample_round2 = GPTriviaRound.objects.create(
            creator="Jenny",
            title="Test Title2",
            major_category="Test Major Category",
            minor_category1="Test Minor Category1",
            minor_category2="Test Minor Category2",
            date="2023-01-01",
            round_number=1,
            max_score=10,
            score_alex=2,
            score_ichigo=10,
            score_megan=10,
            score_zach=8,
            score_jenny=0,
            score_debi=9,
            score_dan=7,
            score_chris=8,
            score_drew=8,
        )

        sample_round3 = GPTriviaRound.objects.create(
            creator="Jenny",
            title="Test Title3 ",
            major_category="Test Major Category 2",
            minor_category1="Test Minor Category1",
            minor_category2="Test Minor Category2",
            date="2023-01-01",
            round_number=1,
            max_score=1,
            score_alex=5,
            score_ichigo=2,
            score_megan=0,
            score_zach=2,
            score_jenny=3,
            score_debi=4,
            score_dan=3,
            score_chris=2,
            score_drew=1,
        )

    def test_bar_data(self):
        rounds = GPTriviaRound.objects.all()
        response = self.client.get(reverse('player_analysis_plot'), {
            'rounds': rounds,
            'chart_type': 'bar',
            'creator': 'Jenny'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('mean_values', response.json())

    def test_violin_data(self):
        rounds = GPTriviaRound.objects.all()
        response = self.client.get(reverse('player_analysis_plot'), {
            'rounds': rounds,
            'chart_type': 'violin',
            'creator': 'Jenny'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.json())

    def test_category(self):
        rounds = GPTriviaRound.objects.all()
        response = self.client.get(reverse('player_analysis_plot'), {
            'rounds': rounds,
            'chart_type': 'violin',
            'category': 'Test Major Category'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('data', response.json())

    def test_pca(self):
        rounds = GPTriviaRound.objects.all()
        response = self.client.get(reverse('player_analysis_plot'), {
            'rounds': rounds,
            'chart_type': 'pca',
            'creator': 'Jenny'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('PC1', response.json())

    def test_correlation_matrix(self):
        rounds = GPTriviaRound.objects.all()
        response = self.client.get(reverse('player_analysis_plot'), {
            'rounds': rounds,
            'chart_type': 'corr',
            'creator': 'Jenny'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('correlation_matrix', response.json())

    def test_cat_bar_data(self):
        rounds = GPTriviaRound.objects.all()
        response = self.client.get(reverse('player_analysis_plot'), {
            'rounds': rounds,
            'chart_type': 'category_bar',
            'creator': 'Jenny'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('mean_values', response.json())

    def test_creator_bar_data(self):
        rounds = GPTriviaRound.objects.all()
        response = self.client.get(reverse('player_analysis_plot'), {
            'rounds': rounds,
            'chart_type': 'creator_bar',
            'category': 'Test Major Category'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('mean_values', response.json())

    def test_player_bar_data(self):
        rounds = GPTriviaRound.objects.all()
        response = self.client.get(reverse('player_analysis_plot'), {
            'rounds': rounds,
            'chart_type': 'player_bar',
            'player': 'Megan'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('mean_values', response.json())

    def test_time_series_creator_normalizes_peer_scores_by_max_score(self):
        GPTriviaRound.objects.create(
            creator="Trend",
            title="Trend Round 1",
            major_category="Trend Category",
            minor_category1="A",
            minor_category2="B",
            date="2024-01-01",
            round_number=1,
            max_score=10,
            score_alex=5,
            score_megan=4,
            score_zach=6,
        )
        GPTriviaRound.objects.create(
            creator="Trend",
            title="Trend Round 2",
            major_category="Trend Category",
            minor_category1="A",
            minor_category2="B",
            date="2024-01-02",
            round_number=2,
            max_score=20,
            score_alex=10,
            score_megan=8,
            score_zach=12,
        )
        GPTriviaRound.objects.create(
            creator="Trend",
            title="Trend Round 3",
            major_category="Trend Category",
            minor_category1="A",
            minor_category2="B",
            date="2024-01-03",
            round_number=3,
            max_score=5,
            score_alex=5,
            score_megan=2,
            score_zach=1,
        )

        response = self.client.get(reverse('player_analysis_plot'), {
            'chart_type': 'time_series_creator',
            'creator': 'Trend',
            'player': 'Alex',
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['dates'], ['2024-01-01', '2024-01-02', '2024-01-03'])
        self.assertAlmostEqual(data['adjusted_scores'][0], -2.3333333333, places=6)
        self.assertAlmostEqual(data['adjusted_scores'][1], -2.3333333333, places=6)
        self.assertAlmostEqual(data['adjusted_scores'][2], 4.6666666667, places=6)
class PlayerAnalysisViewTests(TestCase):
    def setUp(self):
        self.views_threshold_patcher = patch('GPTrivia.views.MIN_ANALYSIS_ROUNDS', 1)
        self.views_threshold_patcher.start()
        self.addCleanup(self.views_threshold_patcher.stop)

        self.user = User.objects.create_user(username='Alex', password='Rapt0rpusia')
        self.client.force_login(self.user)

    def test_profile_view(self):
        GPTriviaRound.objects.create(
            creator="Alex",
            title="Test Title",
            major_category="Test Major Category",
            minor_category1="Test Minor Category1",
            minor_category2="Test Minor Category2",
            date="2023-01-01",
            round_number=1,
            max_score=10,
            score_alex=8,
            score_ichigo=6,
            score_megan=5,
            score_zach=7,
            score_jenny=9,
            score_debi=4,
            score_dan=3,
            score_chris=2,
            score_drew=1,
        )
        GPTriviaRound.objects.create(
            creator="Megan",
            title="Test Title 2",
            major_category="Test Major Category 2",
            minor_category1="Test Minor Category1",
            minor_category2="Test Minor Category2",
            date="2023-01-01",
            round_number=2,
            max_score=10,
            score_alex=7,
            score_ichigo=6,
            score_megan=5,
            score_zach=7,
            score_jenny=9,
            score_debi=4,
            score_dan=3,
            score_chris=2,
            score_drew=1,
        )
        response = self.client.get(reverse('player_profile', args=['Alex']))
        self.assertEqual(response.status_code, 200)

    def test_profile_view_includes_best_score_and_performance_nights(self):
        MergedPresentation.objects.create(
            name="01.01.2023",
            presentation_id="presentation-jan-01",
            round_names=["Night One Round 1", "Night One Round 2"],
            creator_list=["Megan", "Jenny"],
        )
        MergedPresentation.objects.create(
            name="01.08.2023",
            presentation_id="presentation-jan-08",
            round_names=["Night Two Round 1", "Night Two Round 2"],
            creator_list=["Megan", "Jenny"],
        )

        GPTriviaRound.objects.create(
            creator="Megan",
            title="Night One Round 1",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date="2023-01-01",
            round_number=1,
            max_score=10,
            score_alex=8,
            score_ichigo=4,
            score_megan=4,
            score_zach=4,
            score_jenny=4,
        )
        GPTriviaRound.objects.create(
            creator="Jenny",
            title="Night One Round 2",
            major_category="Science",
            minor_category1="Biology",
            minor_category2="Cells",
            date="2023-01-01",
            round_number=2,
            max_score=10,
            score_alex=8,
            score_ichigo=4,
            score_megan=4,
            score_zach=4,
            score_jenny=4,
        )
        GPTriviaRound.objects.create(
            creator="Megan",
            title="Night Two Round 1",
            major_category="History",
            minor_category1="Ancient",
            minor_category2="Rome",
            date="2023-01-08",
            round_number=1,
            max_score=10,
            score_alex=10,
            score_ichigo=8,
            score_megan=8,
            score_zach=8,
            score_jenny=8,
        )
        GPTriviaRound.objects.create(
            creator="Jenny",
            title="Night Two Round 2",
            major_category="History",
            minor_category1="Modern",
            minor_category2="Europe",
            date="2023-01-08",
            round_number=2,
            max_score=10,
            score_alex=9,
            score_ichigo=7,
            score_megan=7,
            score_zach=7,
            score_jenny=7,
        )

        response = self.client.get(reverse('player_profile', args=['Alex']))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['best_score_ever']['display_value'], '19/20 (95.0%)')
        self.assertEqual(response.context['best_score_ever']['date'], datetime.date(2023, 1, 8))
        self.assertEqual(
            response.context['best_score_ever']['scoresheet_link'],
            f"{reverse('scoresheet_new')}?date=2023-01-08",
        )
        self.assertEqual(response.context['best_performance_ever']['display_value'], '+8/20 (+40.0%)')
        self.assertEqual(response.context['best_performance_ever']['date'], datetime.date(2023, 1, 1))
        self.assertEqual(
            response.context['best_performance_ever']['scoresheet_link'],
            f"{reverse('scoresheet_new')}?date=2023-01-01",
        )
        self.assertContains(response, 'Best Score Ever')
        self.assertContains(response, 'Best Performance Ever')
        self.assertContains(response, f"{reverse('scoresheet_new')}?date=2023-01-08")
        self.assertContains(response, f"{reverse('scoresheet_new')}?date=2023-01-01")

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
        response = self.client.get(reverse('player_analysis'))
        self.assertEqual(response.status_code, 200)

    def test_create_presentation(self):  # New test method for create_presentation
        signature = inspect.signature(create_presentation)
        self.assertEqual(
            list(signature.parameters.keys()),
            ['titles', 'creators', 'links', 'presentation_name', 'old_links', 'coops'],
        )
