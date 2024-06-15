import os
os.environ['OPENAI_API_KEY'] = 'sk-'

from django.test import TestCase, RequestFactory
from GPTrivia.models import GPTriviaRound
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
        self.assertIn('mean_values', response.json())

    def test_category(self):
        rounds = GPTriviaRound.objects.all()
        response = self.client.get(reverse('player_analysis_plot'), {
            'rounds': rounds,
            'chart_type': 'violin',
            'category': 'Test Major Category'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('mean_values', response.json())

    def test_pca(self):
        rounds = GPTriviaRound.objects.all()
        response = self.client.get(reverse('player_analysis_plot'), {
            'rounds': rounds,
            'chart_type': 'pca',
            'creator': 'Jenny'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('mean_values', response.json())

    def test_correlation_matrix(self):
        rounds = GPTriviaRound.objects.all()
        response = self.client.get(reverse('player_analysis_plot'), {
            'rounds': rounds,
            'chart_type': 'corr',
            'creator': 'Jenny'
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('mean_values', response.json())

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
class PlayerAnalysisViewTests(TestCase):
    def test_profile_view(self):
        user = User.objects.create_user(username='Alex', password='Rapt0rpusia')
        factory = RequestFactory()
        request = factory.get('/player_profile/Alex/')
        request.user = user
        response = player_profile(request, "Alex")
        self.assertEqual(response.status_code, 200)
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

    def test_create_presentation(self):  # New test method for create_presentation
        # Call the create_presentation function and get the resulting presentation_id
        new_presentation_id, creators, round_titles = create_presentation()

        # Add any necessary setup code here to authenticate with Google Slides API
        credentials = None
        # Check if the token.pickle file exists
        if os.path.exists(token_file_path):
            with open(token_file_path, 'rb') as token:
                credentials = pickle.load(token)

        # Check if the credentials have expired
        if credentials.expired and credentials.refresh_token:
            # Refresh the credentials
            credentials.refresh(Request())

            # Save the refreshed credentials back to the 'token.pickle' file
            with open(token_file_path, 'wb') as token:
                pickle.dump(credentials, token)

        # If the credentials are not available or invalid, prompt the user to authenticate again.
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
                credentials = flow.run_local_server(port=8000)
            with open(token_file_path, 'wb') as token:
                pickle.dump(credentials, token)

        # Fetch the created presentation using Google Slides API
        slides_service = build('slides', 'v1', credentials=credentials)

        created_presentation = slides_service.presentations().get(presentationId=new_presentation_id).execute()

        # Perform assertions on the created_presentation object to ensure it's correctly created
        self.assertIsNotNone(created_presentation)
        self.assertEqual(created_presentation['title'],
                         datetime.date.strftime(datetime.date.today(), '%-m.%d.%Y'))  # Replace 'Expected Title' with the expected title