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
        self.analysis_current_date_patcher = patch('GPTrivia.analysis._analysis_current_trivia_date', return_value=datetime.date(2023, 6, 1))
        self.analysis_current_date_patcher.start()
        self.addCleanup(self.analysis_current_date_patcher.stop)

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
        payload = response.json()
        self.assertIn('correlation_matrix', payload)
        matrix = payload['correlation_matrix']
        score_fields = list(matrix.keys())
        off_diagonal_values = []
        for row_name in score_fields:
            self.assertAlmostEqual(matrix[row_name][row_name], 1.0, places=6)
            for col_name in score_fields:
                if row_name != col_name:
                    off_diagonal_values.append(matrix[row_name][col_name])
        self.assertTrue(off_diagonal_values)
        self.assertAlmostEqual(sum(off_diagonal_values) / len(off_diagonal_values), 0.0, places=6)

    def test_cat_bar_data(self):
        rounds = GPTriviaRound.objects.all()
        response = self.client.get(reverse('player_analysis_plot'), {
            'rounds': rounds,
            'chart_type': 'category_bar',
            'creator': 'Jenny'
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('mean_values', payload)
        self.assertEqual(payload['yaxis'], 'Mean Normalized Score (0-10)')
        self.assertIn('Mean Normalized Score', payload['title'])

    def test_creator_bar_data(self):
        rounds = GPTriviaRound.objects.all()
        response = self.client.get(reverse('player_analysis_plot'), {
            'rounds': rounds,
            'chart_type': 'creator_bar',
            'category': 'Test Major Category'
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('mean_values', payload)
        self.assertEqual(payload['yaxis'], 'Mean Normalized Score (0-10)')
        self.assertIn('Mean Normalized Score', payload['title'])

    def test_analysis_excludes_coop_rounds_unless_requested(self):
        GPTriviaRound.objects.create(
            creator="CoopTest",
            title="Solo Round",
            major_category="Coop Category",
            minor_category1="A",
            minor_category2="B",
            date="2024-03-01",
            round_number=1,
            max_score=10,
            cooperative=False,
            score_alex=10,
            score_megan=0,
        )
        GPTriviaRound.objects.create(
            creator="CoopTest",
            title="Co-op Round",
            major_category="Coop Category",
            minor_category1="A",
            minor_category2="B",
            date="2024-03-08",
            round_number=2,
            max_score=10,
            cooperative=True,
            score_alex=0,
            score_megan=0,
        )

        default_response = self.client.get(reverse('player_analysis_plot'), {
            'chart_type': 'category_bar',
            'creator': 'CoopTest',
        })
        self.assertEqual(default_response.status_code, 200)
        default_payload = default_response.json()
        self.assertEqual(list(default_payload['categories']), ['Coop Category'])
        self.assertAlmostEqual(default_payload['mean_values'][0], 5.0, places=6)

        include_coop_response = self.client.get(reverse('player_analysis_plot'), {
            'chart_type': 'category_bar',
            'creator': 'CoopTest',
            'misc': 'include_coop',
        })
        self.assertEqual(include_coop_response.status_code, 200)
        include_coop_payload = include_coop_response.json()
        self.assertEqual(list(include_coop_payload['categories']), ['Coop Category'])
        self.assertAlmostEqual(include_coop_payload['mean_values'][0], 2.5, places=6)

    def test_creator_bar_excludes_inactive_creators_unless_requested(self):
        GPTriviaRound.objects.create(
            creator="Alex",
            title="Recent Alex Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Motion",
            date="2023-05-01",
            round_number=1,
            max_score=10,
            score_alex=8,
            score_megan=6,
        )
        GPTriviaRound.objects.create(
            creator="Jeff",
            title="Old Jeff Round",
            major_category="History",
            minor_category1="Ancient",
            minor_category2="Rome",
            date="2021-01-01",
            round_number=1,
            max_score=10,
            score_jeff=7,
            score_alex=5,
        )

        default_response = self.client.get(reverse('player_analysis_plot'), {
            'chart_type': 'creator_bar',
        })
        self.assertEqual(default_response.status_code, 200)
        default_payload = default_response.json()
        self.assertIn('Alex', list(default_payload['categories']))
        self.assertNotIn('Jeff', list(default_payload['categories']))

        include_inactive_response = self.client.get(reverse('player_analysis_plot'), {
            'chart_type': 'creator_bar',
            'misc': 'include_inactive',
        })
        self.assertEqual(include_inactive_response.status_code, 200)
        include_inactive_payload = include_inactive_response.json()
        self.assertIn('Alex', list(include_inactive_payload['categories']))
        self.assertIn('Jeff', list(include_inactive_payload['categories']))

    def test_category_violin_summary_data(self):
        response = self.client.get(reverse('player_analysis_plot'), {
            'chart_type': 'category_violin_summary',
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['yaxis'], 'Normalized Score (0-10)')
        self.assertIn('Distribution of Normalized Scores', payload['title'])
        self.assertTrue(payload['plot_data'])
        self.assertIn('Raw score:', payload['hover_texts'][0][0])

    def test_creator_violin_summary_data(self):
        response = self.client.get(reverse('player_analysis_plot'), {
            'chart_type': 'creator_violin_summary',
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['yaxis'], 'Normalized Score (0-10)')
        self.assertIn('Distribution of Normalized Scores', payload['title'])
        self.assertTrue(payload['plot_data'])
        self.assertIn('Player:', payload['hover_texts'][0][0])

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

    def test_joker_creator_and_category_summaries(self):
        GPTriviaRound.objects.create(
            creator="Jenny",
            title="Joker Round A",
            major_category="History",
            minor_category1="A",
            minor_category2="B",
            date="2024-02-01",
            round_number=1,
            max_score=10,
            score_alex=8,
            score_jenny=0,
            score_megan=6,
            score_zach=5,
        )
        GPTriviaRound.objects.create(
            creator="Jenny",
            title="Joker Round B",
            major_category="History",
            minor_category1="A",
            minor_category2="B",
            date="2024-02-08",
            round_number=2,
            max_score=10,
            score_alex=9,
            score_jenny=0,
            score_megan=5,
            score_zach=7,
        )
        GPTriviaRound.objects.create(
            creator="Chris",
            title="Joker Round C",
            major_category="Science",
            minor_category1="A",
            minor_category2="B",
            date="2024-02-15",
            round_number=3,
            max_score=10,
            score_alex=10,
            score_chris=0,
            score_megan=7,
            score_zach=8,
        )
        GPTriviaRound.objects.create(
            creator="Zach",
            title="Joker Round D",
            major_category="Sports",
            minor_category1="A",
            minor_category2="B",
            date="2024-02-22",
            round_number=4,
            max_score=10,
            score_alex=7,
            score_zach=0,
            score_megan=6,
            score_chris=5,
        )

        MergedPresentation.objects.create(
            name="02.01.2024",
            presentation_id="pres-1",
            round_names=["Joker Round A"],
            creator_list=["Jenny"],
            joker_round_indices={"alex": "Joker Round A"},
        )
        MergedPresentation.objects.create(
            name="02.08.2024",
            presentation_id="pres-2",
            round_names=["Joker Round B"],
            creator_list=["Jenny"],
            joker_round_indices={"alex": "Joker Round B"},
        )
        MergedPresentation.objects.create(
            name="02.15.2024",
            presentation_id="pres-3",
            round_names=["Joker Round C"],
            creator_list=["Chris"],
            joker_round_indices={"alex": "Joker Round C"},
        )
        MergedPresentation.objects.create(
            name="02.22.2024",
            presentation_id="pres-4",
            round_names=["Joker Round D"],
            creator_list=["Zach"],
            joker_round_indices={"alex": "Joker Round D"},
        )

        creator_response = self.client.get(reverse('player_analysis_plot'), {
            'chart_type': 'joker_creator_summary',
            'player': 'Alex',
        })
        self.assertEqual(creator_response.status_code, 200)
        creator_data = creator_response.json()
        self.assertEqual(creator_data['labels'], ['Jenny', 'Chris', 'Zach'])
        self.assertEqual(creator_data['counts'], [2, 1, 1])
        self.assertEqual(creator_data['best_labels'], ['Jenny'])
        self.assertEqual(len(creator_data['avg_jokered_scores']), 3)
        self.assertEqual(len(creator_data['avg_overall_scores']), 3)
        self.assertAlmostEqual(creator_data['avg_jokered_scores'][0], 0.85, places=6)
        self.assertAlmostEqual(creator_data['avg_jokered_scores'][1], 1.0, places=6)
        self.assertAlmostEqual(creator_data['avg_jokered_scores'][2], 0.7, places=6)
        self.assertAlmostEqual(creator_data['avg_overall_scores'][0], 1.4, places=6)
        self.assertAlmostEqual(creator_data['avg_overall_scores'][1], 1.0, places=6)
        self.assertAlmostEqual(creator_data['avg_overall_scores'][2], 0.7, places=6)
        self.assertEqual(
            creator_data['top_labels'],
            [
                {'label': 'Jenny', 'rank': 1},
                {'label': 'Chris', 'rank': 2},
                {'label': 'Zach', 'rank': 3},
            ],
        )

        category_response = self.client.get(reverse('player_analysis_plot'), {
            'chart_type': 'joker_category_summary',
            'player': 'Alex',
        })
        self.assertEqual(category_response.status_code, 200)
        category_data = category_response.json()
        self.assertEqual(category_data['labels'], ['History', 'Science', 'Sports'])
        self.assertEqual(category_data['counts'], [2, 1, 1])
        self.assertEqual(category_data['best_labels'], ['Science'])
        self.assertEqual(len(category_data['avg_jokered_scores']), 3)
        self.assertEqual(len(category_data['avg_overall_scores']), 3)
        self.assertAlmostEqual(category_data['avg_jokered_scores'][0], 0.85, places=6)
        self.assertAlmostEqual(category_data['avg_jokered_scores'][1], 1.0, places=6)
        self.assertAlmostEqual(category_data['avg_jokered_scores'][2], 0.7, places=6)
        self.assertAlmostEqual(category_data['avg_overall_scores'][0], 0.85, places=6)
        self.assertAlmostEqual(category_data['avg_overall_scores'][1], 1.0, places=6)
        self.assertAlmostEqual(category_data['avg_overall_scores'][2], 0.7, places=6)
        self.assertEqual(category_data['colors'], ['#8b5a2b', '#7b4bcc', '#2f6fdf'])
        self.assertEqual(
            category_data['top_labels'],
            [
                {'label': 'Science', 'rank': 1},
                {'label': 'History', 'rank': 2},
                {'label': 'Sports', 'rank': 3},
            ],
        )

        filtered_creator_response = self.client.get(reverse('player_analysis_plot'), {
            'chart_type': 'joker_creator_summary',
            'player': 'Alex',
            'category': 'Science',
        })
        self.assertEqual(filtered_creator_response.status_code, 200)
        filtered_creator_data = filtered_creator_response.json()
        self.assertEqual(filtered_creator_data['labels'], ['Chris'])
        self.assertEqual(filtered_creator_data['counts'], [1])

        filtered_category_response = self.client.get(reverse('player_analysis_plot'), {
            'chart_type': 'joker_category_summary',
            'player': 'Alex',
            'creator': 'Jenny',
        })
        self.assertEqual(filtered_category_response.status_code, 200)
        filtered_category_data = filtered_category_response.json()
        self.assertEqual(filtered_category_data['labels'], ['History'])
        self.assertEqual(filtered_category_data['counts'], [2])

    @patch('GPTrivia.analysis._analysis_current_trivia_date', return_value=datetime.date(2025, 3, 1))
    def test_joker_creator_summary_hides_inactive_creators(self, _mock_current_date):
        GPTriviaRound.objects.create(
            creator="Jenny",
            title="Recent Joker Round",
            major_category="History",
            minor_category1="A",
            minor_category2="B",
            date="2024-10-01",
            round_number=1,
            max_score=10,
            score_alex=8,
            score_jenny=0,
            score_megan=6,
        )
        GPTriviaRound.objects.create(
            creator="Inactive",
            title="Old Joker Round",
            major_category="Science",
            minor_category1="A",
            minor_category2="B",
            date="2024-10-08",
            round_number=2,
            max_score=10,
            score_alex=9,
            score_megan=7,
        )
        MergedPresentation.objects.create(
            name="10.01.2024",
            presentation_id="recent-pres",
            round_names=["Recent Joker Round"],
            creator_list=["Jenny"],
            joker_round_indices={"alex": "Recent Joker Round"},
        )
        MergedPresentation.objects.create(
            name="10.08.2024",
            presentation_id="old-pres",
            round_names=["Old Joker Round"],
            creator_list=["Inactive"],
            joker_round_indices={"alex": "Old Joker Round"},
        )

        response = self.client.get(reverse('player_analysis_plot'), {
            'chart_type': 'joker_creator_summary',
            'player': 'Alex',
        })

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['labels'], ['Jenny'])
        self.assertEqual(payload['counts'], [1])

    def test_joker_creator_summary_excludes_coop_rounds_unless_requested(self):
        GPTriviaRound.objects.create(
            creator="Jenny",
            title="Solo Joker Round",
            major_category="History",
            minor_category1="A",
            minor_category2="B",
            date="2024-11-01",
            round_number=1,
            max_score=10,
            cooperative=False,
            score_alex=8,
            score_jenny=0,
            score_megan=6,
        )
        GPTriviaRound.objects.create(
            creator="Chris",
            title="Co-op Joker Round",
            major_category="Science",
            minor_category1="A",
            minor_category2="B",
            date="2024-11-08",
            round_number=2,
            max_score=10,
            cooperative=True,
            score_alex=9,
            score_chris=0,
            score_megan=7,
        )
        MergedPresentation.objects.create(
            name="11.01.2024",
            presentation_id="solo-pres",
            round_names=["Solo Joker Round"],
            creator_list=["Jenny"],
            joker_round_indices={"alex": "Solo Joker Round"},
        )
        MergedPresentation.objects.create(
            name="11.08.2024",
            presentation_id="coop-pres",
            round_names=["Co-op Joker Round"],
            creator_list=["Chris"],
            joker_round_indices={"alex": "Co-op Joker Round"},
        )

        default_response = self.client.get(reverse('player_analysis_plot'), {
            'chart_type': 'joker_creator_summary',
            'player': 'Alex',
        })
        self.assertEqual(default_response.status_code, 200)
        self.assertEqual(default_response.json()['labels'], ['Jenny'])

        include_coop_response = self.client.get(reverse('player_analysis_plot'), {
            'chart_type': 'joker_creator_summary',
            'player': 'Alex',
            'misc': 'include_coop',
        })
        self.assertEqual(include_coop_response.status_code, 200)
        self.assertEqual(include_coop_response.json()['labels'], ['Chris', 'Jenny'])
class PlayerAnalysisViewTests(TestCase):
    def setUp(self):
        self.views_threshold_patcher = patch('GPTrivia.views.MIN_ANALYSIS_ROUNDS', 1)
        self.views_threshold_patcher.start()
        self.addCleanup(self.views_threshold_patcher.stop)
        self.current_trivia_date_patcher = patch('GPTrivia.views._current_trivia_date', return_value=datetime.date(2023, 6, 1))
        self.current_trivia_date_patcher.start()
        self.addCleanup(self.current_trivia_date_patcher.stop)

        self.user = User.objects.create_user(username='Alex', password='Rapt0rpusia')
        self.client.force_login(self.user)

    def get_profile_stats_payload(self, player_name):
        response = self.client.get(
            reverse('player_profile_stats', args=[player_name]),
            HTTP_ACCEPT='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        return payload

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
        self.assertContains(response, '?player=Alex')
        self.assertContains(response, '?creator=Alex')
        self.assertContains(response, reverse('player_profile_stats', args=['Alex']))
        self.assertContains(response, reverse('player_profile_creator_panels', args=['Alex']))
        self.assertContains(response, 'Reset Page Colors to Default')
        self.assertTrue(response.context['defer_profile_stats'])
        self.assertTrue(response.context['defer_profile_creator_panels'])
        self.assertNotContains(response, 'Test Title')

    def test_profile_creator_panels_load_separately(self):
        GPTriviaRound.objects.create(
            creator="Alex",
            title="Loaded Later Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Motion",
            date="2023-01-01",
            round_number=1,
            max_score=10,
            score_alex=8,
            score_megan=6,
        )

        response = self.client.get(
            reverse('player_profile_creator_panels', args=['Alex']),
            HTTP_ACCEPT='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertIn('Loaded Later Round', payload['created_rounds_html'])
        self.assertIn('Created Round Categories', payload['created_categories_html'])

    def test_player_analysis_prefills_from_query_params(self):
        GPTriviaRound.objects.create(
            creator="Alex",
            title="Creator Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Motion",
            date="2023-01-01",
            round_number=1,
            max_score=10,
            score_alex=8,
            score_megan=5,
        )
        GPTriviaRound.objects.create(
            creator="Megan",
            title="Player Round",
            major_category="History",
            minor_category1="Ancient",
            minor_category2="Rome",
            date="2023-01-08",
            round_number=2,
            max_score=10,
            score_alex=7,
            score_megan=None,
        )

        response = self.client.get(reverse('player_analysis'), {
            'creator': 'Alex',
            'player': 'Alex',
            'include_coop': '1',
            'include_inactive': '1',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['initial_creator_selection'], 'Alex')
        self.assertEqual(response.context['initial_player_selection'], 'Alex')
        self.assertTrue(response.context['initial_include_coop'])
        self.assertTrue(response.context['initial_include_inactive'])
        self.assertContains(response, '<option value="Alex" selected>Alex</option>', html=True)
        self.assertContains(response, 'id="include-coop-checkbox" checked', html=False)
        self.assertContains(response, 'id="include-inactive-checkbox" checked', html=False)
        self.assertContains(response, reverse('player_profile', args=['__PROFILE_NAME__']))
        self.assertContains(response, 'buildAnalysisTitle')
        self.assertContains(response, '"creator": "Alex"')
        self.assertNotContains(response, ': None')

    def test_player_analysis_dropdown_includes_inactive_players(self):
        GPTriviaRound.objects.create(
            creator="Alex",
            title="Recent Active Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Motion",
            date="2023-05-01",
            round_number=1,
            max_score=10,
            score_alex=8,
        )
        GPTriviaRound.objects.create(
            creator="Jeff",
            title="Old Jeff Round",
            major_category="History",
            minor_category1="Ancient",
            minor_category2="Rome",
            date="2021-01-01",
            round_number=1,
            max_score=10,
            score_jeff=7,
        )

        response = self.client.get(reverse('player_analysis'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('Alex', response.context['players'])
        self.assertIn('Jeff', response.context['players'])

    def test_profile_view_includes_secondary_created_rounds(self):
        GPTriviaRound.objects.create(
            creator="Megan",
            secondary_creator="Alex",
            title="Shared Creation Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Motion",
            date="2023-01-01",
            round_number=1,
            max_score=10,
            score_alex=None,
            score_megan=None,
            score_jenny=8,
        )
        GPTriviaRound.objects.create(
            creator="Jenny",
            title="Alex Played Round",
            major_category="History",
            minor_category1="Modern",
            minor_category2="Europe",
            date="2023-01-01",
            round_number=2,
            max_score=10,
            score_alex=7,
            score_jenny=None,
        )

        response = self.client.get(reverse('player_profile', args=['Alex']))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['created_rounds_count'], 1)
        panels_response = self.client.get(
            reverse('player_profile_creator_panels', args=['Alex']),
            HTTP_ACCEPT='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(panels_response.status_code, 200)
        payload = panels_response.json()
        self.assertIn('Shared Creation Round', payload['created_rounds_html'])
        self.assertIn('Science', payload['created_categories_html'])

    def test_profile_view_shows_intro_and_streak_timeline(self):
        self.user.profile.profile_intro = "Trivia goblin with a science streak."
        self.user.profile.save(update_fields=['profile_intro'])

        GPTriviaRound.objects.create(
            creator="Alex",
            title="Night One Creator Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Motion",
            date="2023-01-01",
            round_number=1,
            max_score=10,
            score_alex=None,
            score_megan=8,
        )
        GPTriviaRound.objects.create(
            creator="Megan",
            title="Night One Played Round",
            major_category="Science",
            minor_category1="Chemistry",
            minor_category2="Atoms",
            date="2023-01-01",
            round_number=2,
            max_score=10,
            score_alex=7,
            score_megan=None,
        )
        GPTriviaRound.objects.create(
            creator="Alex",
            title="Night Two Creator Round",
            major_category="History",
            minor_category1="Ancient",
            minor_category2="Rome",
            date="2023-01-08",
            round_number=1,
            max_score=10,
            score_alex=None,
            score_megan=7,
        )
        GPTriviaRound.objects.create(
            creator="Jenny",
            title="Night Two Played Round",
            major_category="History",
            minor_category1="Modern",
            minor_category2="Europe",
            date="2023-01-08",
            round_number=2,
            max_score=10,
            score_alex=9,
            score_jenny=None,
        )
        GPTriviaRound.objects.create(
            creator="Megan",
            title="Night Three Missed Round",
            major_category="Games",
            minor_category1="Board",
            minor_category2="Abstract",
            date="2023-01-15",
            round_number=1,
            max_score=10,
            score_alex=None,
            score_megan=8,
        )
        GPTriviaRound.objects.create(
            creator="Alex",
            title="Night Four Creator Round",
            major_category="Music",
            minor_category1="Rock",
            minor_category2="Classic",
            date="2023-01-22",
            round_number=1,
            max_score=10,
            score_alex=None,
            score_megan=6,
        )
        GPTriviaRound.objects.create(
            creator="Megan",
            title="Night Four Played Round",
            major_category="Music",
            minor_category1="Pop",
            minor_category2="Hits",
            date="2023-01-22",
            round_number=2,
            max_score=10,
            score_alex=8,
            score_megan=None,
        )
        MergedPresentation.objects.create(
            name="01.29.2023",
            presentation_id="presentation-jan-29",
            joker_round_indices={"score_alex": "Joker Only Round"},
            creator_list=["Megan"],
            style_points={"Alex": 2.5},
        )

        response = self.client.get(reverse('player_profile', args=['Alex']))
        payload = self.get_profile_stats_payload('Alex')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['profile_intro'], "Trivia goblin with a science streak.")
        self.assertEqual(payload['stats']['longest_play_streak'], 2)
        self.assertEqual(payload['stats']['longest_creator_streak'], 2)
        self.assertEqual(payload['stats']['style_points_total'], 2.5)
        self.assertEqual(len(payload['stats']['streak_timeline']), 5)
        self.assertEqual(
            [(entry['played'], entry['created']) for entry in payload['stats']['streak_timeline']],
            [(True, True), (True, True), (False, False), (True, True), (True, False)],
        )
        self.assertContains(response, 'About Alex')
        self.assertContains(response, 'Trivia goblin with a science streak.')
        self.assertNotContains(response, 'Summary Stats')
        self.assertNotContains(response, 'class="profile-page-title"')
        self.assertIn('Trivia Night Timeline', payload['timeline_html'])
        self.assertIn(
            f'{reverse("scoresheet_new")}?date=2023-01-01',
            payload['timeline_html'],
        )

    def test_profile_view_counts_player_list_for_blank_presentation_night(self):
        GPTriviaRound.objects.create(
            creator="Megan",
            title="Warmup Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Motion",
            date="2023-01-29",
            round_number=1,
            max_score=10,
            score_alex=8,
            score_megan=None,
        )
        MergedPresentation.objects.create(
            name="02.05.2023",
            presentation_id="presentation-feb-05",
            player_list={"Alex": "Alex", "Megan": "Megan"},
            creator_list=["Megan"],
        )

        response = self.client.get(reverse('player_profile', args=['Alex']))
        payload = self.get_profile_stats_payload('Alex')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['stats']['longest_play_streak'], 2)
        self.assertEqual(
            payload['stats']['streak_timeline'],
            [
                {'date': '2023-01-29', 'played': True, 'created': False},
                {'date': '2023-02-05', 'played': True, 'created': False},
            ],
        )

    def test_profile_intro_autosave_returns_json(self):
        response = self.client.post(
            reverse('update_profile_intro', args=['Alex']),
            {'profile_intro': 'Add a short intro.'},
            HTTP_ACCEPT='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.user.profile.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'ok': True,
            'profile_intro': 'Add a short intro.',
        })
        self.assertEqual(self.user.profile.profile_intro, 'Add a short intro.')

    def test_profile_view_includes_best_score_night_and_counts_coop_rounds(self):
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
            score_debi=0,
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
            cooperative=True,
            score_alex=9,
            score_ichigo=7,
            score_megan=7,
            score_zach=7,
            score_jenny=7,
        )
        MergedPresentation.objects.create(
            name="01.15.2023",
            presentation_id="presentation-jan-15",
            round_names=["Night Three Round 1", "Night Three Round 2"],
            creator_list=["Megan", "Zach"],
            player_list={"score_alex": "score_alex", "score_megan": "score_megan", "score_zach": "score_zach"},
        )
        GPTriviaRound.objects.create(
            creator="Megan",
            title="Night Three Round 1",
            major_category="Games",
            minor_category1="Board",
            minor_category2="Abstract",
            date="2023-01-15",
            round_number=1,
            max_score=10,
            score_alex=9,
            score_megan=None,
            score_zach=9,
        )
        GPTriviaRound.objects.create(
            creator="Zach",
            title="Night Three Round 2",
            major_category="Games",
            minor_category1="Video",
            minor_category2="Retro",
            date="2023-01-15",
            round_number=2,
            max_score=10,
            score_alex=9,
            score_megan=9,
            score_zach=None,
        )

        response = self.client.get(reverse('player_profile', args=['Alex']))
        payload = self.get_profile_stats_payload('Alex')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['stats']['best_score_ever']['display_value'], '19/20 (95.0%)')
        self.assertEqual(payload['stats']['best_score_ever']['date'], '2023-01-08')
        self.assertEqual(
            payload['stats']['best_score_ever']['scoresheet_link'],
            f"{reverse('scoresheet_new')}?date=2023-01-08",
        )
        self.assertEqual(payload['stats']['best_performance_ever']['display_value'], '+4 points')
        self.assertEqual(payload['stats']['best_performance_ever']['date'], '2023-01-01')
        self.assertEqual(
            payload['stats']['best_performance_ever']['scoresheet_link'],
            f"{reverse('scoresheet_new')}?date=2023-01-01",
        )
        self.assertIn('Creator Favoritism Toward Alex', payload['summary_html'])
        self.assertIn('Players Favored by Creator Alex', payload['summary_html'])
        self.assertNotContains(response, 'Biggest Win')

    def test_profile_creator_stats_ignore_players_inactive_for_over_a_year(self):
        GPTriviaRound.objects.create(
            creator="Megan",
            title="Recent Active Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Space",
            date="2023-05-01",
            round_number=1,
            max_score=10,
            score_alex=6,
            score_megan=5,
        )
        GPTriviaRound.objects.create(
            creator="Debi",
            title="Old Inactive Round",
            major_category="Science",
            minor_category1="Chemistry",
            minor_category2="Atoms",
            date="2021-01-01",
            round_number=1,
            max_score=10,
            score_alex=10,
            score_debi=2,
        )

        response = self.client.get(reverse('player_profile', args=['Alex']))
        payload = self.get_profile_stats_payload('Alex')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['stats']['max_cat_avg'], 'Megan')
        self.assertNotEqual(payload['stats']['max_cat_avg'], 'Debi')

    def test_profile_owner_can_update_created_round_category(self):
        trivia_round = GPTriviaRound.objects.create(
            creator="Alex",
            title="Category Update Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Motion",
            date="2023-05-01",
            round_number=1,
            max_score=10,
            score_alex=None,
            score_megan=7,
        )
        GPTriviaRound.objects.create(
            creator="Megan",
            title="Existing History Round",
            major_category="History",
            minor_category1="Ancient",
            minor_category2="Rome",
            date="2023-05-08",
            round_number=1,
            max_score=10,
            score_alex=8,
            score_megan=None,
        )

        response = self.client.post(
            reverse('update_profile_round_category', args=[trivia_round.id]),
            {
                'major_category': 'History',
                'next_panel': 'created-rounds-panel',
            },
        )

        trivia_round.refresh_from_db()
        self.assertRedirects(
            response,
            f"{reverse('player_profile', args=['Alex'])}?panel=created-rounds-panel",
        )
        self.assertEqual(trivia_round.major_category, 'History')

    def test_profile_secondary_creator_can_update_created_round_category(self):
        trivia_round = GPTriviaRound.objects.create(
            creator="Megan",
            secondary_creator="Alex",
            title="Secondary Category Update Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Motion",
            date="2023-05-01",
            round_number=1,
            max_score=10,
            score_alex=None,
            score_megan=None,
            score_jenny=7,
        )

        response = self.client.post(
            reverse('update_profile_round_category', args=[trivia_round.id]),
            {
                'major_category': 'History',
                'next_panel': 'created-rounds-panel',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        trivia_round.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(trivia_round.major_category, 'History')

    def test_profile_alex_can_update_other_players_round_category(self):
        GPTriviaRound.objects.create(
            creator="Jenny",
            title="Existing History Round",
            major_category="History",
            minor_category1="Empires",
            minor_category2="Expansion",
            date="2023-05-08",
            round_number=1,
            max_score=10,
            score_alex=8,
            score_jenny=None,
        )
        trivia_round = GPTriviaRound.objects.create(
            creator="Megan",
            title="Locked Category Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Motion",
            date="2023-05-01",
            round_number=1,
            max_score=10,
            score_alex=8,
            score_megan=None,
        )

        response = self.client.post(
            reverse('update_profile_round_category', args=[trivia_round.id]),
            {
                'major_category': 'History',
                'next_panel': 'created-rounds-panel',
            },
        )

        trivia_round.refresh_from_db()
        self.assertRedirects(
            response,
            f"{reverse('player_profile', args=['Megan'])}?panel=created-rounds-panel",
            fetch_redirect_response=False,
        )
        self.assertEqual(trivia_round.major_category, 'History')

    def test_profile_alex_can_update_other_players_minor_categories_via_ajax(self):
        GPTriviaRound.objects.create(
            creator="Jenny",
            title="Existing History Round",
            major_category="History",
            minor_category1="Ancient",
            minor_category2="Rome",
            date="2023-05-08",
            round_number=1,
            max_score=10,
            score_alex=8,
            score_jenny=None,
        )
        trivia_round = GPTriviaRound.objects.create(
            creator="Megan",
            title="Locked Category Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Motion",
            date="2023-05-01",
            round_number=1,
            max_score=10,
            score_alex=8,
            score_megan=None,
        )

        response = self.client.post(
            reverse('update_profile_round_category', args=[trivia_round.id]),
            {
                'major_category': 'History',
                'minor_category1': 'Empires',
                'minor_category2': 'Expansion',
                'next_panel': 'created-rounds-panel',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        trivia_round.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'success': True,
            'round_id': trivia_round.id,
            'fields': {
                'major_category': 'History',
                'minor_category1': 'Empires',
                'minor_category2': 'Expansion',
            },
            'panel': 'created-rounds-panel',
        })
        self.assertEqual(trivia_round.major_category, 'History')
        self.assertEqual(trivia_round.minor_category1, 'Empires')
        self.assertEqual(trivia_round.minor_category2, 'Expansion')

    def test_non_alex_cannot_update_other_players_round_category(self):
        other_user = User.objects.create_user(username='Jenny', password='Rapt0rpusia')
        self.client.force_login(other_user)

        trivia_round = GPTriviaRound.objects.create(
            creator="Megan",
            title="Locked Category Round",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Motion",
            date="2023-05-01",
            round_number=1,
            max_score=10,
            score_alex=8,
            score_megan=None,
        )

        response = self.client.post(
            reverse('update_profile_round_category', args=[trivia_round.id]),
            {
                'major_category': 'History',
                'next_panel': 'created-rounds-panel',
            },
        )

        trivia_round.refresh_from_db()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(trivia_round.major_category, 'Science')

    def test_profile_best_night_stats_use_jokers_and_allow_creator_blanks(self):
        MergedPresentation.objects.create(
            name="02.06.2023",
            presentation_id="presentation-feb-06",
            round_names=["Night Four Round 1", "Night Four Round 2", "Night Four Round 3"],
            creator_list=["Alex", "Debi", "Megan"],
            player_list={
                "score_alex": "score_alex",
                "score_debi": "score_debi",
                "score_megan": "score_megan",
            },
            joker_round_indices={
                "alex": "Night Four Round 3",
                "debi": "Night Four Round 1",
            },
        )

        GPTriviaRound.objects.create(
            creator="Alex",
            title="Night Four Round 1",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Motion",
            date="2023-02-06",
            round_number=1,
            max_score=10,
            score_alex=None,
            score_debi=10,
            score_megan=9,
        )
        GPTriviaRound.objects.create(
            creator="Debi",
            title="Night Four Round 2",
            major_category="Science",
            minor_category1="Chemistry",
            minor_category2="Elements",
            date="2023-02-06",
            round_number=2,
            max_score=10,
            score_alex=9,
            score_debi=None,
            score_megan=8,
        )
        GPTriviaRound.objects.create(
            creator="Megan",
            title="Night Four Round 3",
            major_category="Science",
            minor_category1="Biology",
            minor_category2="Cells",
            date="2023-02-06",
            round_number=3,
            max_score=10,
            score_alex=10,
            score_debi=9.5,
            score_megan=None,
        )

        response = self.client.get(reverse('player_profile', args=['Debi']))
        payload = self.get_profile_stats_payload('Debi')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['stats']['best_score_ever']['display_value'], '29.5/30 (98.3%)')
        self.assertEqual(payload['stats']['best_score_ever']['date'], '2023-02-06')
        self.assertEqual(
            payload['stats']['best_score_ever']['scoresheet_link'],
            f"{reverse('scoresheet_new')}?date=2023-02-06",
        )
        self.assertEqual(payload['stats']['best_performance_ever']['display_value'], '-0.5 points')
        self.assertEqual(payload['stats']['best_performance_ever']['date'], '2023-02-06')
        self.assertEqual(
            payload['stats']['best_performance_ever']['scoresheet_link'],
            f"{reverse('scoresheet_new')}?date=2023-02-06",
        )

    def test_profile_best_night_stats_double_count_creator_bonus_when_joker_matches_creator_round(self):
        MergedPresentation.objects.create(
            name="02.13.2023",
            presentation_id="presentation-feb-13",
            round_names=["Overlap Round 1", "Overlap Round 2"],
            creator_list=["Alex", "Megan"],
            player_list={
                "score_alex": "score_alex",
                "score_debi": "score_debi",
                "score_megan": "score_megan",
            },
            joker_round_indices={
                "alex": "Overlap Round 1",
            },
        )

        GPTriviaRound.objects.create(
            creator="Alex",
            title="Overlap Round 1",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Motion",
            date="2023-02-13",
            round_number=1,
            max_score=10,
            score_alex=None,
            score_debi=8,
            score_megan=9,
        )
        GPTriviaRound.objects.create(
            creator="Megan",
            title="Overlap Round 2",
            major_category="Science",
            minor_category1="Chemistry",
            minor_category2="Elements",
            date="2023-02-13",
            round_number=2,
            max_score=10,
            score_alex=7,
            score_debi=6,
            score_megan=None,
        )

        response = self.client.get(reverse('player_profile', args=['Alex']))
        payload = self.get_profile_stats_payload('Alex')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['stats']['best_score_ever']['display_value'], '15.5/20 (77.5%)')
        self.assertEqual(payload['stats']['best_score_ever']['date'], '2023-02-13')
        self.assertEqual(payload['stats']['best_performance_ever']['display_value'], '+8.5 points')
        self.assertEqual(payload['stats']['best_performance_ever']['date'], '2023-02-13')

    def test_profile_best_night_stats_split_double_jokers_evenly(self):
        MergedPresentation.objects.create(
            name="02.20.2023",
            presentation_id="presentation-feb-20",
            round_names=["Dual Joker Round 1", "Dual Joker Round 2", "Dual Joker Round 3"],
            creator_list=["Megan", "Jenny", "Debi"],
            player_list={
                "score_alex": "score_alex",
                "score_debi": "score_debi",
                "score_megan": "score_megan",
                "score_jenny": "score_jenny",
            },
            joker_round_indices={
                "alex": ["Dual Joker Round 1", "Dual Joker Round 2"],
            },
        )

        GPTriviaRound.objects.create(
            creator="Megan",
            title="Dual Joker Round 1",
            major_category="Science",
            minor_category1="Physics",
            minor_category2="Motion",
            date="2023-02-20",
            round_number=1,
            max_score=10,
            score_alex=8,
            score_debi=7,
            score_megan=None,
            score_jenny=6,
        )
        GPTriviaRound.objects.create(
            creator="Jenny",
            title="Dual Joker Round 2",
            major_category="Science",
            minor_category1="Chemistry",
            minor_category2="Elements",
            date="2023-02-20",
            round_number=2,
            max_score=10,
            score_alex=6,
            score_debi=5,
            score_megan=7,
            score_jenny=None,
        )
        GPTriviaRound.objects.create(
            creator="Debi",
            title="Dual Joker Round 3",
            major_category="Science",
            minor_category1="Biology",
            minor_category2="Cells",
            date="2023-02-20",
            round_number=3,
            max_score=10,
            score_alex=9,
            score_debi=None,
            score_megan=8,
            score_jenny=7,
        )

        response = self.client.get(reverse('player_profile', args=['Alex']))
        payload = self.get_profile_stats_payload('Alex')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['stats']['best_score_ever']['display_value'], '30/40 (75.0%)')
        self.assertEqual(payload['stats']['best_score_ever']['date'], '2023-02-20')

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
