from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import HttpRequest
import httplib2
from google_auth_httplib2 import AuthorizedHttp


from google.oauth2 import service_account
import base64
import re
import datetime

import os
import pickle

MAIL_NAME_MAP = {
    'Alex': 'Alex',
    'I': 'Ichigo',
    'Megan': 'Megan',
    'Zach': 'Zach',
    'Jenny': 'Jenny',
    'Debi': 'Debi',
    'Dan': 'Dan',
    'Chris': 'Chris',
    'Drew': 'Drew'
}


SCOPES = ['https://www.googleapis.com/auth/gmail.modify',
          'https://www.googleapis.com/auth/presentations',
          'https://www.googleapis.com/auth/script.external_request',
          'https://www.googleapis.com/auth/script.scriptapp',
          'https://www.googleapis.com/auth/script.projects']
# # Replace with your actual client_secret file
# CLIENT_SECRET_FILE = '../../../../client_secret.json'
CLIENT_SECRET_FILE = '/Users/alex/client_secret.json'

APPS_SCRIPT_ID = '1MWXrSq2Uf5GkMsmMeOHowiU-nY21LxGom6VWJ9WaPg7hBQZqBgD_HS_K'

mail_file_directory = os.path.dirname(os.path.abspath(__file__))
token_file_path = os.path.join(mail_file_directory, 'token.pickle')

def list_subjects(credentials):
    try:
        service = build('gmail', 'v1', credentials=credentials)
        results = service.users().messages().list(userId='me', labelIds=['INBOX'], maxResults=10).execute()
        messages = results.get('messages', [])

        for message in messages:
            msg = service.users().messages().get(userId='me', id=message['id']).execute()
            headers = msg['payload']['headers']
            subject = next(header['value'] for header in headers if header['name'] == 'Subject')
            print(f'Subject: {subject}')

    except HttpError as error:
        print(f'An error occurred: {error}')

def new_presentation(credentials):
    try:
        service = build('slides', 'v1', credentials=credentials)
        presentation_body = {
            'title': datetime.date.strftime(datetime.date.today(), '%-m.%d.%Y')
        }
        presentation = service.presentations() \
            .create(body=presentation_body).execute()

        presentation_id = presentation.get('presentationId')
        print(f"Created presentation with ID: {presentation_id}")
        return presentation_id

    except HttpError as error:
        print(f'An error occurred: {error}')
        return None


def find_shared_presentations(credentials, processed_senders=[]):
    print(processed_senders)
    try:
        new_senders = []
        presentation_urls = []

        gmail_service = build('gmail', 'v1', credentials=credentials)
        query = 'subject:"Presentation shared with you:.*" is:unread'
        response = gmail_service.users().messages().list(userId='me', q=query).execute()

        if 'messages' in response:
            # Fetch messages with their internalDate and sort them
            messages_with_date = []
            for message in response['messages']:
                msg_id = message['id']
                msg = gmail_service.users().messages().get(userId='me', id=msg_id, format='metadata',
                                                           metadataHeaders=['From', 'internalDate']).execute()
                messages_with_date.append((msg, msg['internalDate']))

            messages_with_date.sort(key=lambda x: x[1])

            for msg, _ in messages_with_date:
                msg_id = msg['id']

                # Get sender's email address
                headers = msg['payload']['headers']
                sender = [header['value'] for header in headers if header['name'] == 'From'][0]
                # Get the first word in the sender's email address (creator's first name)
                sender = sender.split()[0]
                sender = sender[1:]

                if sender not in processed_senders:
                    # print(f"1: Found new presentation from {sender}")
                    print("found new sender")
                    new_senders.append(sender)
                    processed_senders.append(sender)
                    msg = gmail_service.users().messages().get(userId='me', id=msg_id, format='full').execute()

                    parts = msg['payload']['parts']
                    data = None

                    for part in parts:
                        if part['mimeType'] == 'text/plain':
                            data = part['body']['data']
                            break
                    if data is not None:
                        msg_str = base64.urlsafe_b64decode(data.encode('ASCII'))

                        url_pattern = r'(https?://docs\.google\.com/presentation/d/[^\s]+)'
                        url_match = re.search(url_pattern, msg_str.decode('utf-8'))

                        if url_match:
                            # print(f"3: Found presentation URL: {url_match.group(1)}")
                            presentation_url = url_match.group(1)
                            presentation_urls.append(presentation_url)
                        mark_as_read(gmail_service, msg_id)

        print(f"Found {len(presentation_urls)} new presentations from creators: {processed_senders}")

        return presentation_urls, new_senders

    except HttpError as error:
        print(f"An error occurred: {error}")
        return None


# def combine_slides(credentials):
#     gmail_service = build('gmail', 'v1', credentials=credentials)
#     results = gmail_service.users().messages().list(userId='me', q="Presentation shared with you: .*").execute()
#     messages = results.get('messages', [])
#     # Find Google Slides URLs in the email body.
#     for message in messages:
#         msg = gmail_service.users().messages().get(userId='me', id=message['id']).execute()
#         body = msg['snippet']
#         slide_url = find_shared_presentation(body)
#
#         if slide_url:
#             slide_id = re.search(r'https://docs\.google\.com/presentation/d/([\w-]+)', slide_url).group(1)
#             print(f"Slide ID: {slide_id}")
#             # Use the Google Slides API to merge the presentations (currently this just prints the slide ID)

def mark_as_read(gmail_service, msg_id):
    gmail_service.users().messages().modify(
        userId='me',
        id=msg_id,
        body={'removeLabelIds': ['UNREAD']}
    ).execute()

def remove_first_slide(credentials, presentation_id):
    slides_service = build('slides', 'v1', credentials=credentials)

    # Get the ID of the first slide
    presentation = slides_service.presentations().get(presentationId=presentation_id).execute()
    first_slide_id = presentation['slides'][0]['objectId']

    # Remove the first slide
    delete_request = {
        'deleteObject': {
            'objectId': first_slide_id
        }
    }
    slides_service.presentations().batchUpdate(presentationId=presentation_id, body={'requests': [delete_request]}).execute()


def update_merged_presentation(merged_presentation_id, merged_creators):
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

    # Remove the last slide
    slides_service = build('slides', 'v1', credentials=credentials)
    presentation = slides_service.presentations().get(presentationId=merged_presentation_id).execute()
    last_slide_id = presentation['slides'][-1]['objectId']
    delete_slide_request = {'deleteObject': {'objectId': last_slide_id}}
    slides_service.presentations().batchUpdate(presentationId=merged_presentation_id, body={'requests': [delete_slide_request]}).execute()

    # Append any new shared slides from new creators
    print("finding shared presentations for shared presentation...")
    shared_urls, creators = find_shared_presentations(credentials, merged_creators)

    script_service = build('script', 'v1', credentials=credentials)
    FUNCTION_NAME = 'copySlides'

    round_titles = []

    for url in shared_urls:
        shared_presentation_id = url.split('/')[-2]
        request = {
            'function': FUNCTION_NAME,
            'parameters': [shared_presentation_id, merged_presentation_id],
            'devMode': True
        }
        response = script_service.scripts().run(scriptId=APPS_SCRIPT_ID, body=request).execute()

        shared_presentation = slides_service.presentations().get(presentationId=shared_presentation_id).execute()

        # Get the first slide of the presentation
        first_slide = shared_presentation['slides'][0]

        # Extract the title text from the first slide
        title_text = ""
        for element in first_slide['pageElements']:
            if 'shape' in element and 'text' in element['shape']:
                text = element['shape']['text']['textElements']
                for text_element in text:
                    if 'textRun' in text_element and 'content' in text_element['textRun']:
                        title_text += text_element['textRun']['content']

        # Clean up the title text by removing excess whitespace and line breaks
        title_text = re.sub(r'\s+', ' ', title_text).strip()

        # Add the title to the list of round titles
        round_titles.append(title_text)


    # update the second slide with the round titles and creators
    merged_pres = slides_service.presentations().get(presentationId=merged_presentation_id).execute()

    second_slide = merged_pres['slides'][1]
    second_slide_id = second_slide['objectId']
    second_slide_elements = second_slide['pageElements']

    # Define placeholders for the rounds and creators
    round_placeholders = ['ROUND1', 'ROUND2', 'ROUND3', 'ROUND4', 'ROUND5']
    creator_placeholders = ['CREATOR1', 'CREATOR2', 'CREATOR3', 'CREATOR4', 'CREATOR5']
    print(round_titles)
    print(creators)
    print(merged_creators)

    for element in second_slide_elements:
        if 'shape' in element and 'text' in element['shape']:
            element_id = element['objectId']
            text_elements = element['shape']['text']['textElements']

            element_len = 0  # Subtract 7 to account for the placeholder text
            for idx, text_element in enumerate(text_elements):
                if idx != 1:
                    continue
                if 'textRun' in text_element and 'content' in text_element['textRun']:
                    content = text_element['textRun']['content']
                    element_len += len(content)

                    # Check if the content contains any of the placeholders
                    for i in range(len(round_placeholders)):
                        round_placeholder = round_placeholders[i]
                        creator_placeholder = creator_placeholders[i]

                        if round_placeholder in content and len(round_titles) > 0:
                            new_text = round_titles.pop(0)
                            round_start_index = content.index(round_placeholder)
                            round_end_index = round_start_index + len(round_placeholder)
                            delete_insert_requests = create_delete_insert_text_requests(
                                element_id, round_start_index, round_end_index, new_text)
                            slides_service.presentations().batchUpdate(
                                presentationId=merged_presentation_id,
                                body={'requests': delete_insert_requests}
                            ).execute()

                            # Update the content variable with the updated text from the API
                            updated_text = slides_service.presentations().get(
                                presentationId=merged_presentation_id).execute()
                            for slide in updated_text['slides']:
                                for elem in slide['pageElements']:
                                    if 'shape' in elem and 'text' in elem['shape'] and elem['objectId'] == element_id:
                                        content = "".join([text_elem['textRun']['content'] for text_elem in
                                                           elem['shape']['text']['textElements'] if
                                                           'textRun' in text_elem])

                        if creator_placeholder in content and len(creators) > 0:
                            new_text = MAIL_NAME_MAP[creators.pop(0)]
                            creator_start_index = content.index(creator_placeholder)  # + element_len + 2
                            creator_end_index = creator_start_index + len(creator_placeholder)

                            print(f"creator_start_index: {creator_start_index}")
                            print(f"creator_end_index: {creator_end_index}")
                            print(f"content: {content}")
                            print(f"new_text: {new_text}")

                            delete_insert_requests = create_delete_insert_text_requests(
                                element_id, creator_start_index, creator_end_index, new_text)

                            response = slides_service.presentations().batchUpdate(presentationId=merged_presentation_id,
                                                                                  body={
                                                                                      'requests': delete_insert_requests}).execute()
                            break

    # add the outro slide
    outro_id = '1BSOudw2JxjVcHxfHX-yfJqmuh0Pp4iKMmYY5klW5zLI'
    request = {
        'function': FUNCTION_NAME,
        'parameters': [outro_id, merged_presentation_id],
        'devMode': True
    }
    response = script_service.scripts().run(scriptId=APPS_SCRIPT_ID, body=request).execute()

    creator_names = [MAIL_NAME_MAP[creator] for creator in creators]

    return merged_presentation_id, creator_names, round_titles


def create_delete_insert_text_requests(element_id, start_index, end_index, new_text):
    delete_text_request = {
        'deleteText': {
            'objectId': element_id,
            'textRange': {
                'type': 'FIXED_RANGE',
                'startIndex': start_index,
                'endIndex': end_index
            },
        }
    }

    insert_text_request = {
        'insertText': {
            'objectId': element_id,
            'insertionIndex': start_index,
            'text': new_text
        }
    }

    return [delete_text_request, insert_text_request]

def build_credentials():
    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRET_FILE, SCOPES)
    return flow.run_local_server(port=8080)

def create_presentation():
    credentials = None
    # Check if the token.pickle file exists
    if os.path.exists(token_file_path):
        with open(token_file_path, 'rb') as token:
            credentials = pickle.load(token)

    # Check if the credentials have expired
    if credentials.expired and credentials.refresh_token:
        try:
            # Refresh the credentials
            credentials.refresh(Request())

            # Save the refreshed credentials back to the 'token.pickle' file
            with open(token_file_path, 'wb') as token:
                pickle.dump(credentials, token)
        except Exception as e:
            print("Failed to refresh the token, getting new credentials")
            credentials = build_credentials()
            with open(token_file_path, 'wb') as token:
                pickle.dump(credentials, token)

    # If the credentials are not available or invalid, prompt the user to authenticate again.
    if not credentials or not credentials.valid:
        credentials = build_credentials()
        with open(token_file_path, 'wb') as token:
            pickle.dump(credentials, token)

    intro_id = '1sXOpGumQ9nIDj3tDgU7J5U_bHiTu48YL50MtILw6ngo'
    outro_id = '1BSOudw2JxjVcHxfHX-yfJqmuh0Pp4iKMmYY5klW5zLI'

    new_presentation_id = new_presentation(credentials)
    print("finding shared presentations for new presentation...")
    shared_urls, creators = find_shared_presentations(credentials, [])

    # Build the service or the Apps Script API
    http = httplib2.Http(timeout=300)
    authorized_http = AuthorizedHttp(credentials, http=http)
    script_service = build('script', 'v1', http=authorized_http)
    slides_service = build('slides', 'v1', credentials=credentials)

    # The name of the function you want to execute
    FUNCTION_NAME = 'copySlides'

    # Copy the extra slides to the beginning of the new presentation
    request = {
        'function': FUNCTION_NAME,
        'parameters': [intro_id, new_presentation_id],
        'devMode': True
    }
    response = script_service.scripts().run(scriptId=APPS_SCRIPT_ID, body=request).execute()




    ### MODIFYING THE DATE



    # Fetch the new presentation
    new_pres = slides_service.presentations().get(presentationId=new_presentation_id).execute()

    # Get the first slide
    first_slide = new_pres['slides'][1]
    first_slide_id = first_slide['objectId']

    # Find the date text element
    date_element_id = None
    for element in first_slide['pageElements']:
        if 'shape' in element and 'text' in element['shape']:
            text = element['shape']['text']['textElements']
            for text_element in text:
                if 'textRun' in text_element and 'content' in text_element['textRun']:
                    content = text_element['textRun']['content']
                    if "April" in content:
                        date_element_id = element['objectId']
                        break

    # Update the date text
    date_text = datetime.datetime.now().strftime("%B %d, %Y")

    delete_text_request = {
        'deleteText': {
            'objectId': date_element_id,
            'textRange': {
                'type': 'FIXED_RANGE',
                'startIndex': 0,
                'endIndex': len(date_text)
            },
        }
    }

    # now modify slide 2



    insert_text_request = {
        'insertText': {
            'objectId': date_element_id,
            'insertionIndex': 0,
            'text': date_text
        }
    }

    slides_service.presentations().batchUpdate(
        presentationId=new_presentation_id,
        body={'requests': [delete_text_request, insert_text_request]}
    ).execute()




    round_titles = []

    for url in shared_urls:
        shared_presentation_id = url.split('/')[-2]
        request = {
            'function': FUNCTION_NAME,  # Replace with your function name
            'parameters': [shared_presentation_id, new_presentation_id],  # Replace with your actual parameters
            'devMode': True
        }

        shared_presentation = slides_service.presentations().get(presentationId=shared_presentation_id).execute()

        # Get the first slide of the presentation
        first_slide = shared_presentation['slides'][0]

        # Extract the title text from the first slide
        title_text = ""
        for element in first_slide['pageElements']:
            if 'shape' in element and 'text' in element['shape']:
                text = element['shape']['text']['textElements']
                for text_element in text:
                    if 'textRun' in text_element and 'content' in text_element['textRun']:
                        title_text += text_element['textRun']['content']

        # Clean up the title text by removing excess whitespace and line breaks
        title_text = re.sub(r'\s+', ' ', title_text).strip()

        # Add the title to the list of round titles
        round_titles.append(title_text)

        response = script_service.scripts().run(scriptId=APPS_SCRIPT_ID, body=request).execute()

    creators_list = list(creators)

    # HERE IS WHERE I WANT TO ADD THE CODE TO MODIFY THE SECOND SLIDE TO REPLACE THE PLACEHOLDER NAMES
    # WITH THE NAMES FROM THE CREATOR LIST AND THE ROUND TITLES WITH THE ROUND TITLES LIST
    # Get the second slide
    second_slide = new_pres['slides'][2]
    second_slide_id = second_slide['objectId']
    second_slide_elements = second_slide['pageElements']

    # Define placeholders for the rounds and creators
    round_placeholders = ['ROUND1', 'ROUND2', 'ROUND3', 'ROUND4', 'ROUND5']
    creator_placeholders = ['CREATOR1', 'CREATOR2', 'CREATOR3', 'CREATOR4', 'CREATOR5']

    # Iterate through the page elements in the second slide
    for element in second_slide_elements:
        if 'shape' in element and 'text' in element['shape']:
            element_id = element['objectId']
            text_elements = element['shape']['text']['textElements']

            element_len = 0  # Subtract 7 to account for the placeholder text
            for idx, text_element in enumerate(text_elements):
                if idx != 1:
                    continue
                if 'textRun' in text_element and 'content' in text_element['textRun']:
                    content = text_element['textRun']['content']
                    element_len += len(content)

                    # Check if the content contains any of the placeholders
                    for i in range(len(round_placeholders)):
                        round_placeholder = round_placeholders[i]
                        creator_placeholder = creator_placeholders[i]

                        if round_placeholder in content and len(round_titles) > i:
                            new_text = round_titles[i]
                            round_start_index = content.index(round_placeholder)
                            round_end_index = round_start_index + len(round_placeholder)
                            delete_insert_requests = create_delete_insert_text_requests(
                                element_id, round_start_index, round_end_index, new_text)
                            slides_service.presentations().batchUpdate(
                                presentationId=new_presentation_id,
                                body={'requests': delete_insert_requests}
                            ).execute()

                            # Update the content variable with the updated text from the API
                            updated_text = slides_service.presentations().get(
                                presentationId=new_presentation_id).execute()
                            for slide in updated_text['slides']:
                                for elem in slide['pageElements']:
                                    if 'shape' in elem and 'text' in elem['shape'] and elem['objectId'] == element_id:
                                        content = "".join([text_elem['textRun']['content'] for text_elem in
                                                           elem['shape']['text']['textElements'] if
                                                           'textRun' in text_elem])

                        if creator_placeholder in content and len(creators_list) > i:
                            new_text = MAIL_NAME_MAP[creators_list[i]]
                            creator_start_index = content.index(creator_placeholder)# + element_len + 2
                            creator_end_index = creator_start_index + len(creator_placeholder)

                            print(f"creator_start_index: {creator_start_index}")
                            print(f"creator_end_index: {creator_end_index}")
                            print(f"content: {content}")
                            print(f"new_text: {new_text}")

                            delete_insert_requests = create_delete_insert_text_requests(
                                element_id, creator_start_index, creator_end_index, new_text)

                            response = slides_service.presentations().batchUpdate(presentationId=new_presentation_id, body={'requests': delete_insert_requests}).execute()
                            break

    # Copy the extra slides to the end of the new presentation
    request = {
        'function': FUNCTION_NAME,
        'parameters': [outro_id, new_presentation_id],
        'devMode': True
    }
    response = script_service.scripts().run(scriptId=APPS_SCRIPT_ID, body=request).execute()

    remove_first_slide(credentials, new_presentation_id)

    creator_names = [MAIL_NAME_MAP[creator] for creator in creators_list]

    return new_presentation_id, creator_names, round_titles

if __name__ == '__main__':
    create_presentation()