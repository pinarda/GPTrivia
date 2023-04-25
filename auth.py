from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import pickle



CLIENT_SECRET_FILE = '/Users/alex/client_secret.json'
redirect_uri = "http://localhost:8000"
SCOPES = ['https://www.googleapis.com/auth/gmail.modify',
          'https://www.googleapis.com/auth/presentations',
          'https://www.googleapis.com/auth/script.external_request',
          'https://www.googleapis.com/auth/script.projects,',
          'https://www.googleapis.com/auth/script.scriptapp']


flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)

credentials = flow.run_local_server(port=8000)

print("Access token:", credentials.token)
print("Refresh token:", credentials.refresh_token)
# Save the credentials for future use.
with open('GPTrivia/token.pickle', 'wb') as token:
    pickle.dump(credentials, token)
