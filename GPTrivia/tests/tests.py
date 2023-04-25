from django.test import TestCase, RequestFactory
from GPTrivia.models import GPTriviaRound
from GPTrivia.views import player_analysis
from ..mail import create_presentation
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os
import pickle
import datetime

mail_file_directory = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRET_FILE = '/Users/alex/client_secret.json'
token_file_path = os.path.join(mail_file_directory, '../token.pickle')
SCOPES = ['https://www.googleapis.com/auth/gmail.modify',
          'https://www.googleapis.com/auth/presentations',
          'https://www.googleapis.com/auth/script.external_request',
          'https://www.googleapis.com/auth/script.scriptapp',
          'https://www.googleapis.com/auth/script.projects']

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