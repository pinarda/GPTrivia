from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import HttpRequest
import httplib2
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.errors import HttpError
import google.auth
import pytz


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
    'zach': 'Zach',
    'Debi': 'Debi',
    'Dan': 'Dan',
    'Chris': 'Chris',
    'Drew': 'Drew',
    'doodlwagon': "Jenny",
    'Paige': "Paige",
    'Tom': "Tom",
    'Hail': "Swooper"
}


SCOPES = ['https://www.googleapis.com/auth/gmail.modify',
          'https://www.googleapis.com/auth/presentations',
          'https://www.googleapis.com/auth/script.external_request',
          'https://www.googleapis.com/auth/script.scriptapp',
          'https://www.googleapis.com/auth/script.projects',
          'https://www.googleapis.com/auth/drive']
# # Replace with your actual client_secret file
# CLIENT_SECRET_FILE = '../../../../client_secret.json'
CLIENT_SECRET_FILE = '/Users/alex/client_secret.json'

APPS_SCRIPT_ID = '1MWXrSq2Uf5GkMsmMeOHowiU-nY21LxGom6VWJ9WaPg7hBQZqBgD_HS_K'

mail_file_directory = os.path.dirname(os.path.abspath(__file__))
token_file_path = os.path.join(mail_file_directory, 'token.pickle')
pst = pytz.timezone('America/Los_Angeles')
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
            'title': datetime.date.strftime(datetime.datetime.now(pst).date(), '%-m.%d.%Y')
        }
        presentation = service.presentations() \
            .create(body=presentation_body).execute()

        presentation_id = presentation.get('presentationId')
        print(f"Created presentation with ID: {presentation_id}")
        return presentation_id

    except HttpError as error:
        print(f'An error occurred: {error}')
        return None


def find_shared_presentations(credentials, processed_senders=[], selected_links=[], old_links=[]):
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

                if sender == "Alex" or sender == "Hail" or sender not in processed_senders:
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
                            new_presentation_url = convert_shared_presentation(presentation_url, credentials)
                            presentation_urls.append(new_presentation_url)
                        if presentation_url in (selected_links + old_links):
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

def update_slide_permissions(slide_id, credentials):
    try:
        # Authenticate and create a service object
        # creds, _ = google.auth.default()
        service = build('drive', 'v3', credentials=credentials)

        # Define the new permissions
        new_permission = {
            'type': 'anyone',
            'role': 'reader'
        }

        # Update the permissions for the given slide
        service.permissions().create(
            fileId=slide_id,
            body=new_permission
        ).execute()

        print(f"Slide {slide_id} access set to 'Anyone with a link'.")

    except HttpError as error:
        print(f"An error occurred: {error}")
        return None

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


def update_merged_presentation(merged_presentation_id, merged_creators, titles, creators, links, old_links):
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

    swapped_creators = [key for creator in creators for key, value in MAIL_NAME_MAP.items() if value == creator]
    creators = swapped_creators

    # Remove the last slide
    slides_service = build('slides', 'v1', credentials=credentials)
    presentation = slides_service.presentations().get(presentationId=merged_presentation_id).execute()
    last_slide_id = presentation['slides'][-1]['objectId']
    delete_slide_request = {'deleteObject': {'objectId': last_slide_id}}
    slides_service.presentations().batchUpdate(presentationId=merged_presentation_id, body={'requests': [delete_slide_request]}).execute()

    # Append any new shared slides from new creators
    print("finding shared presentations for shared presentation...")
    # shared_urls, creators = find_shared_presentations(credentials, merged_creators)
    find_shared_presentations(credentials, merged_creators, links, old_links)
    shared_urls = links

    script_service = build('script', 'v1', credentials=credentials)
    FUNCTION_NAME = 'copySlides'

    round_titles = []
    copied_links = []  # List to store links to the first slide of each copied presentation in the new presentation

    i = 0
    for url in shared_urls:
        shared_presentation_id = url.split('/')[-2]
        request = {
            'function': FUNCTION_NAME,
            'parameters': [shared_presentation_id, merged_presentation_id],
            'devMode': True
        }
        # response = script_service.scripts().run(scriptId=APPS_SCRIPT_ID, body=request).execute()

        shared_presentation = slides_service.presentations().get(presentationId=shared_presentation_id).execute()
        a_new_presentation = slides_service.presentations().get(presentationId=merged_presentation_id).execute()

        current_slide_count = len(a_new_presentation['slides'])

        # Get the first slide of the presentation
        first_slide = shared_presentation['slides'][0]

        # Extract the title text from the first slide
        title_text = ""
        flag=0
        for element in first_slide['pageElements']:
            if 'shape' in element and 'text' in element['shape']:
                text = element['shape']['text']['textElements']
                if flag:
                    break
                for text_element in text:
                    if 'textRun' in text_element and 'content' in text_element['textRun']:
                        flag=1
                        title_text += text_element['textRun']['content']
                        break

        # Clean up the title text by removing excess whitespace and line breaks
        title_text = re.sub(r'\s+', ' ', title_text).strip()
        title_text = titles[i]
        i += 1

        # Add the title to the list of round titles
        round_titles.append(title_text)

        response = script_service.scripts().run(scriptId=APPS_SCRIPT_ID, body=request).execute()
        slides = slides_service.presentations().get(presentationId=merged_presentation_id).execute().get('slides', [])
        copied_slide_id = slides[current_slide_count]['objectId']
        # Construct the link for the first slide of the copied presentation in the new presentation
        link_to_copied_slide = f"https://docs.google.com/presentation/d/{merged_presentation_id}/edit#slide=id.{copied_slide_id}"
        copied_links.append(link_to_copied_slide)


    # update the second slide with the round titles and creators
    merged_pres = slides_service.presentations().get(presentationId=merged_presentation_id).execute()

    second_slide = merged_pres['slides'][1]
    second_slide_id = second_slide['objectId']
    second_slide_elements = second_slide['pageElements']

    # Define placeholders for the rounds and creators
    round_placeholders = ['ROUND1', 'ROUND2', 'ROUND3', 'ROUND4', 'ROUND5', 'ROUND6']
    creator_placeholders = ['CREATOR1', 'CREATOR2', 'CREATOR3', 'CREATOR4', 'CREATOR5', 'CREATOR6']
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

                            if len(new_text) > 30:
                                # Add a request to modify the font size; you can adjust the font size value as needed
                                font_size_request = {
                                    "updateTextStyle": {
                                        "objectId": element_id,
                                        "textRange": {
                                            "type": "FIXED_RANGE",  # Explicitly specifying the range type
                                            "startIndex": round_start_index,
                                            "endIndex": round_start_index + len(new_text)
                                        },
                                        "style": {
                                            "fontSize": {
                                                "magnitude": 20,  # Change this to your desired font size
                                                "unit": "PT"
                                            }
                                        },
                                        "fields": "fontSize"
                                    }
                                }
                                delete_insert_requests.append(font_size_request)
                            elif len(new_text) > 40:
                                # Add a request to modify the font size; you can adjust the font size value as needed
                                font_size_request = {
                                    "updateTextStyle": {
                                        "objectId": element_id,
                                        "textRange": {
                                            "type": "FIXED_RANGE",  # Explicitly specifying the range type
                                            "startIndex": round_start_index,
                                            "endIndex": round_start_index + len(new_text)
                                        },
                                        "style": {
                                            "fontSize": {
                                                "magnitude": 16,  # Change this to your desired font size
                                                "unit": "PT"
                                            }
                                        },
                                        "fields": "fontSize"
                                    }
                                }
                                delete_insert_requests.append(font_size_request)
                            elif len(new_text) > 70:
                                # Add a request to modify the font size; you can adjust the font size value as needed
                                font_size_request = {
                                    "updateTextStyle": {
                                        "objectId": element_id,
                                        "textRange": {
                                            "type": "FIXED_RANGE",  # Explicitly specifying the range type
                                            "startIndex": round_start_index,
                                            "endIndex": round_start_index + len(new_text)
                                        },
                                        "style": {
                                            "fontSize": {
                                                "magnitude": 10,  # Change this to your desired font size
                                                "unit": "PT"
                                            }
                                        },
                                        "fields": "fontSize"
                                    }
                                }
                                delete_insert_requests.append(font_size_request)

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

    return merged_presentation_id, creator_names, round_titles, copied_links


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

def copy_template(template_id, copy_title, qas, icon_links):
    credentials=None
    # Check if the token.pickle file exists
    if os.path.exists(token_file_path):
        with open(token_file_path, 'rb') as token:
            credentials = pickle.load(token)

    # If the credentials are not available or invalid, prompt the user to authenticate again.
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            credentials = flow.run_local_server(port=8080)
        with open(token_file_path, 'wb') as token:
            pickle.dump(credentials, token)

    # Check if the credentials have expired
    if credentials.expired and credentials.refresh_token:
        # Refresh the credentials
        credentials.refresh(Request())

        # Save the refreshed credentials back to the 'token.pickle' file
        with open(token_file_path, 'wb') as token:
            pickle.dump(credentials, token)


    try:
        service = build('slides', 'v1', credentials=credentials)
        http = httplib2.Http(timeout=300)
        authorized_http = AuthorizedHttp(credentials, http=http)
        script_service = build('script', 'v1', http=authorized_http)
        # Copy the presentation
        presentation = service.presentations().create(
            body={
                'title': copy_title
            }
        ).execute()
        new_presentation_id = presentation.get('presentationId')

        # Step 2: Get the slides from the original presentation
        original_presentation = service.presentations().get(
            presentationId=template_id
        ).execute()
        slides = original_presentation.get('slides')

        # Step 3: Copy the slides to the new presentation
        request = {
            'function': 'copySlides',
            'parameters': [template_id, new_presentation_id],
            'devMode': True
        }
        response = script_service.scripts().run(scriptId=APPS_SCRIPT_ID, body=request).execute()
        print(f"RESPONSE: {response}")

        remove_first_slide(credentials, new_presentation_id)

        the_new_presentation = service.presentations().get(
            presentationId=new_presentation_id
        ).execute()
        new_slides = the_new_presentation.get('slides')

        # update text on slides:

        requests = []
        for slide in slides:
            for shape in slide.get('pageElements', []):
                if 'shape' in shape and 'text' in shape['shape']:
                    text_content = shape['shape']['text']['textElements']
                    # Concatenate text elements to get full text
                    full_text = ''.join([elem.get('textRun', {}).get('content', '') for elem in text_content])
                     # Check for placeholder text
                    for qa_label, new_text in qas.items():
                        if qa_label in full_text:
                            # Step 4: Build update request
                            requests.append({
                                'replaceAllText': {
                                    'containsText': {
                                        'text': qa_label,
                                        'matchCase': True,
                                    },
                                    'replaceText': new_text,
                                    #'pageObjectIds': [page_id],  # Restrict to current page
                                }
                            })

        k=0
        for slide in new_slides:
            if k==0 or k==11:
                k+=1
                continue
            if icon_links is not None:
                if icon_links[f"Question{k%11}"] is not None:
                    image_id = f"MyImage_{k}"
                    emu4M = {"magnitude": 2743200, "unit": "EMU"}
                    requests.append(
                        {
                            "createImage": {
                                "objectId": image_id,
                                "url": icon_links[f"Question{k%11}"],
                                "elementProperties": {
                                    "pageObjectId": slide["objectId"],
                                    "size": {"height": emu4M, "width": emu4M},
                                    "transform": {
                                        "scaleX": 1,
                                        "scaleY": 1,
                                        "translateX": 220312,
                                        "translateY": 1384032,
                                        "unit": "EMU",
                                    },
                                },
                            }
                        }
                    )
            k+=1

        replace_round_title_request = {
            'replaceAllText': {
                'containsText': {
                    'text': 'RoundTitle',  # The text to be replaced
                    'matchCase': True,
                },
                'replaceText': copy_title,  # The new text
                # Omitting 'pageObjectIds' to apply replacement throughout the presentation
            }
        }
        requests.append(replace_round_title_request)

        # Step 5: Send update requests
        if requests:
            response = service.presentations().batchUpdate(
                presentationId=new_presentation_id,
                body={'requests': requests}
            ).execute()
            print(f"Final Response: {response}")

        drive_service = build('drive', 'v3', credentials=credentials)
        # Create the permission object
        permission = {
            'type': 'anyone',
            'role': 'writer'
        }

        # Update permissions
        drive_service.permissions().create(
            fileId=new_presentation_id,
            body=permission,
            fields='id'
        ).execute()

        # Get the link to the copied presentation
        return new_presentation_id

    except HttpError as error:
        print(f'An error occurred: {error}')
        return None

def build_credentials():
    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRET_FILE, SCOPES)
    return flow.run_local_server(port=8080)

def share_slides(presId):
    credentials=None
    # Check if the token.pickle file exists
    if os.path.exists(token_file_path):
        with open(token_file_path, 'rb') as token:
            credentials = pickle.load(token)

    # If the credentials are not available or invalid, prompt the user to authenticate again.
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            credentials = flow.run_local_server(port=8080)
        with open(token_file_path, 'wb') as token:
            pickle.dump(credentials, token)

    # Check if the credentials have expired
    if credentials.expired and credentials.refresh_token:
        # Refresh the credentials
        credentials.refresh(Request())

        # Save the refreshed credentials back to the 'token.pickle' file
        with open(token_file_path, 'wb') as token:
            pickle.dump(credentials, token)


    try:
        # Share the copied presentation with yourself
        drive_service = build('drive', 'v3', credentials=credentials)
        drive_service.permissions().create(
            fileId=presId,
            body={
                'type': 'user',
                'role': 'writer',
                'emailAddress': 'hailsciencetrivia@gmail.com'
            },
            fields='id'
        ).execute()
        return True
    except HttpError as error:
        print(f'An error occurred: {error}')
        return None



def create_presentation(titles, creators, links, presentation_name, old_links):
    credentials = None
    # Check if the token.pickle file exists
    if os.path.exists(token_file_path):
        with open(token_file_path, 'rb') as token:
            credentials = pickle.load(token)

    swapped_creators = [key for creator in creators for key, value in MAIL_NAME_MAP.items() if value == creator]
    creators = swapped_creators

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
    # shared_urls, creators = find_shared_presentations(credentials, [])
    find_shared_presentations(credentials, [], links, old_links)
    shared_urls = links
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
                        # get the text in this element
                        date_text = content
                        len_date_text = len(date_text)
                        break

    # Update the date text
    date_text = datetime.datetime.now(pst).date().strftime("%B %d, %Y")

    delete_text_request = {
        'deleteText': {
            'objectId': date_element_id,
            'textRange': {
                'type': 'FIXED_RANGE',
                'startIndex': 0,
                'endIndex': len_date_text-1
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
    copied_links = []  # List to store links to the first slide of each copied presentation in the new presentation

    i = 0
    for url in shared_urls:
        shared_presentation_id = url.split('/')[-2]
        request = {
            'function': FUNCTION_NAME,  # Replace with your function name
            'parameters': [shared_presentation_id, new_presentation_id],  # Replace with your actual parameters
            'devMode': True
        }

        shared_presentation = slides_service.presentations().get(presentationId=shared_presentation_id).execute()
        a_new_presentation = slides_service.presentations().get(presentationId=new_presentation_id).execute()

        current_slide_count = len(a_new_presentation['slides'])

        # Get the first slide of the presentation
        first_slide = shared_presentation['slides'][0]

        # Extract the title text from the first slide
        title_text = ""
        flag = 0
        for element in first_slide['pageElements']:
            if 'shape' in element and 'text' in element['shape']:
                text = element['shape']['text']['textElements']
                if flag:
                    break
                for text_element in text:
                    if 'textRun' in text_element and 'content' in text_element['textRun']:
                        flag=1
                        title_text += text_element['textRun']['content']
                        break



        # Clean up the title text by removing excess whitespace and line breaks
        title_text = re.sub(r'\s+', ' ', title_text).strip()

        title_text = titles[i]
        i += 1

        # Add the title to the list of round titles
        round_titles.append(title_text)

        response = script_service.scripts().run(scriptId=APPS_SCRIPT_ID, body=request).execute()
        slides = slides_service.presentations().get(presentationId=new_presentation_id).execute().get('slides', [])
        copied_slide_id = slides[current_slide_count]['objectId']
        # Construct the link for the first slide of the copied presentation in the new presentation
        link_to_copied_slide = f"https://docs.google.com/presentation/d/{new_presentation_id}/edit#slide=id.{copied_slide_id}"
        copied_links.append(link_to_copied_slide)

    creators_list = list(creators)


    # HERE IS WHERE I WANT TO ADD THE CODE TO MODIFY THE SECOND SLIDE TO REPLACE THE PLACEHOLDER NAMES
    # WITH THE NAMES FROM THE CREATOR LIST AND THE ROUND TITLES WITH THE ROUND TITLES LIST
    # Get the second slide
    second_slide = new_pres['slides'][2]
    second_slide_id = second_slide['objectId']
    second_slide_elements = second_slide['pageElements']

    # Define placeholders for the rounds and creators
    round_placeholders = ['ROUND1', 'ROUND2', 'ROUND3', 'ROUND4', 'ROUND5', 'ROUND6']
    creator_placeholders = ['CREATOR1', 'CREATOR2', 'CREATOR3', 'CREATOR4', 'CREATOR5', 'CREATOR6']

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

                            if len(new_text) > 30:
                                # Add a request to modify the font size; you can adjust the font size value as needed
                                font_size_request = {
                                    "updateTextStyle": {
                                        "objectId": element_id,
                                        "textRange": {
                                            "type": "FIXED_RANGE",  # Explicitly specifying the range type
                                            "startIndex": round_start_index,
                                            "endIndex": round_start_index + len(new_text)
                                        },
                                        "style": {
                                            "fontSize": {
                                                "magnitude": 20,  # Change this to your desired font size
                                                "unit": "PT"
                                            }
                                        },
                                        "fields": "fontSize"
                                    }
                                }
                                delete_insert_requests.append(font_size_request)
                            elif len(new_text) > 40:
                                # Add a request to modify the font size; you can adjust the font size value as needed
                                font_size_request = {
                                    "updateTextStyle": {
                                        "objectId": element_id,
                                        "textRange": {
                                            "type": "FIXED_RANGE",  # Explicitly specifying the range type
                                            "startIndex": round_start_index,
                                            "endIndex": round_start_index + len(new_text)
                                        },
                                        "style": {
                                            "fontSize": {
                                                "magnitude": 16,  # Change this to your desired font size
                                                "unit": "PT"
                                            }
                                        },
                                        "fields": "fontSize"
                                    }
                                }
                                delete_insert_requests.append(font_size_request)

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

    update_slide_permissions(new_presentation_id, credentials)

    return new_presentation_id

def convert_shared_presentation(presentation_url, credentials):
    try:
        # Extract the file ID from the presentation URL
        file_id = presentation_url.split('/')[-2]

        # Initialize the Drive service
        drive_service = build('drive', 'v3', credentials=credentials)

        # Get file metadata
        file_metadata = drive_service.files().get(fileId=file_id, fields='mimeType').execute()
        mime_type = file_metadata.get('mimeType')

        # Check if the file is not already a Google Slides presentation
        if mime_type != 'application/vnd.google-apps.presentation':
            # Convert to Google Slides format
            converted_file = drive_service.files().copy(
                fileId=file_id,
                body={'mimeType': 'application/vnd.google-apps.presentation'}
            ).execute()

            # Return the new Google Slides URL
            new_presentation_url = f"https://docs.google.com/presentation/d/{converted_file['id']}/edit"
            return new_presentation_url

        # If it's already a Google Slides presentation, return the original URL
        return presentation_url

    except HttpError as error:
        print(f'An error occurred: {error}')
        return None

def get_round_titles_and_links(processed_senders=[]):
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

    http = httplib2.Http(timeout=300)
    authorized_http = AuthorizedHttp(credentials, http=http)
    script_service = build('script', 'v1', http=authorized_http)
    slides_service = build('slides', 'v1', credentials=credentials)

    print(processed_senders)
    try:
        new_senders = []
        presentation_urls = []
        old_urls = []
        round_titles = []

        gmail_service = build('gmail', 'v1', credentials=credentials)
        query = 'subject:"Presentation shared with you:.*" is:unread'
        response = gmail_service.users().messages().list(userId='me', q=query).execute()

        if 'messages' in response:
            messages_with_date = []
            for message in response['messages']:
                msg_id = message['id']
                msg = gmail_service.users().messages().get(userId='me', id=msg_id, format='metadata', metadataHeaders=['From', 'internalDate']).execute()
                messages_with_date.append((msg, msg['internalDate']))

            messages_with_date.sort(key=lambda x: x[1])

            for msg, _ in messages_with_date:
                msg_id = msg['id']
                headers = msg['payload']['headers']
                sender = [header['value'] for header in headers if header['name'] == 'From'][0]
                sender = sender.split()[0]
                sender = sender[1:]

                new_senders.append(sender)
                msg = gmail_service.users().messages().get(userId='me', id=msg_id, format='full').execute()
                parts = msg['payload']['parts']

                for part in parts:
                    if part['mimeType'] == 'text/plain':
                        data = part['body']['data']
                        if data:
                            msg_str = base64.urlsafe_b64decode(data.encode('ASCII'))
                            url_pattern = r'(https?://docs\.google\.com/presentation/d/[^\s]+)'
                            # 'https://docs.google.com/presentation/d/1ECVqOMtgWEbzMOtzNLDQCRSSOA8BXbhRdJ_9yNWzgj0/edit?u'
                            # url_pattern = r'(https?://docs\.google\.com/presentation/d/[\w-]+)'
                            # 'https://docs.google.com/presentation/d/1ECVqOMtgWEbzMOtzNLDQCRSSOA8BXbhRdJ_9yNWzgj0'
                            url_match = re.search(url_pattern, msg_str.decode('utf-8'))

                            if url_match:
                                presentation_url = url_match.group(1)
                                new_presentation_url = convert_shared_presentation(presentation_url, credentials)
                                presentation_urls.append(new_presentation_url)
                                old_urls.append(presentation_url)
                                # Extract round title
                                shared_presentation_id = new_presentation_url.split('/')[-2]
                                # request = {
                                #     'function': FUNCTION_NAME,
                                #     'parameters': [shared_presentation_id, merged_presentation_id],
                                #     'devMode': True
                                # }
                                # response = script_service.scripts().run(scriptId=APPS_SCRIPT_ID, body=request).execute()
                                shared_presentation = slides_service.presentations().get(presentationId=shared_presentation_id).execute()
                                first_slide = shared_presentation['slides'][0]

                                title_text = ""
                                flag=0
                                for element in first_slide['pageElements']:
                                    if 'shape' in element and 'text' in element['shape']:
                                        text = element['shape']['text']['textElements']
                                        if flag:
                                            break
                                        for text_element in text:
                                            if 'textRun' in text_element and 'content' in text_element['textRun']:
                                                flag=1
                                                title_text += text_element['textRun']['content']
                                                break

                                title_text = re.sub(r'\\s+', ' ', title_text).strip()
                                round_titles.append(title_text)

        # replace the sender using mail name map with the current name as the key and the name we want to return as the value
        # unless the sender is not in the mail name map, then we just return "Unknown"
        new_senders = [MAIL_NAME_MAP[sender] if sender in MAIL_NAME_MAP else "Unknown" for sender in new_senders]

        print(presentation_urls, round_titles, new_senders, old_urls)
        return presentation_urls, round_titles, new_senders, old_urls

    except HttpError as error:
        print(f"An error occurred: {error}")
        return None, None, None, None


if __name__ == '__main__':
    # get_round_titles_and_links([])
    # create_presentation()
    questions_answers = {
        'Question1': "Pterodactyl, brontosaurus or trex?",
        'Answer2': "Dinos",
        'Question2': 'What is the capital of France?',
        'Answer2': 'Paris',
        'Question3': 'Who was Harry Houdini?',
        'Answer3': 'A magician',
        'Question4': 'Who was Harry Houdini?',
        'Answer4': 'A magician',
        'Question5': 'Who was Harry Houdini?',
        'Answer5': 'A magician',
        'Question6': 'Who was Harry Houdini?',
        'Answer6': 'A magician',
        'Question7': 'Who was Harry Houdini?',
        'Answer7': 'A magician',
        'Question8': 'Who was Harry Houdini?',
        'Answer8': 'A magician',
        'Question9': 'Who was Harry Houdini?',
        'Answer9': 'A magician',
        'Question310': 'Who was Harry Houdini?',
        'Answer10': 'A magician',
        # ... and so on for each question and answer
    }
    copy_template('1x8J9cEpFeMMYAJ_Inxw4Z_2-zYBwa5NMfOsN8pZKVHQ', 'test', questions_answers, {"Question1": "https://oaidalleapiprodscus.blob.core.windows.net/private/org-22TlJ3O0EJC9AMJoee51xI0K/user-CLr6W6GiRSX9UXWCDXdyDC34/img-qUyE8YkaEu3il601ISOsqtkr.png?st=2023-12-02T21%3A55%3A49Z&se=2023-12-02T23%3A55%3A49Z&sp=r&sv=2021-08-06&sr=b&rscd=inline&rsct=image/png&skoid=6aaadede-4fb3-4698-a8f6-684d7786b067&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2023-12-02T22%3A55%3A01Z&ske=2023-12-03T22%3A55%3A01Z&sks=b&skv=2021-08-06&sig=bJPLh7lOmznTcXc82ZCQ4c1Qcqle6c6WV93je0hmelc%3D",
                                                                                              "Question2": "https://oaidalleapiprodscus.blob.core.windows.net/private/org-22TlJ3O0EJC9AMJoee51xI0K/user-CLr6W6GiRSX9UXWCDXdyDC34/img-qUyE8YkaEu3il601ISOsqtkr.png?st=2023-12-02T21%3A55%3A49Z&se=2023-12-02T23%3A55%3A49Z&sp=r&sv=2021-08-06&sr=b&rscd=inline&rsct=image/png&skoid=6aaadede-4fb3-4698-a8f6-684d7786b067&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2023-12-02T22%3A55%3A01Z&ske=2023-12-03T22%3A55%3A01Z&sks=b&skv=2021-08-06&sig=bJPLh7lOmznTcXc82ZCQ4c1Qcqle6c6WV93je0hmelc%3D",
                                                                                              "Question3": "https://oaidalleapiprodscus.blob.core.windows.net/private/org-22TlJ3O0EJC9AMJoee51xI0K/user-CLr6W6GiRSX9UXWCDXdyDC34/img-qUyE8YkaEu3il601ISOsqtkr.png?st=2023-12-02T21%3A55%3A49Z&se=2023-12-02T23%3A55%3A49Z&sp=r&sv=2021-08-06&sr=b&rscd=inline&rsct=image/png&skoid=6aaadede-4fb3-4698-a8f6-684d7786b067&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2023-12-02T22%3A55%3A01Z&ske=2023-12-03T22%3A55%3A01Z&sks=b&skv=2021-08-06&sig=bJPLh7lOmznTcXc82ZCQ4c1Qcqle6c6WV93je0hmelc%3D",
                                                                                              "Question4": "https://oaidalleapiprodscus.blob.core.windows.net/private/org-22TlJ3O0EJC9AMJoee51xI0K/user-CLr6W6GiRSX9UXWCDXdyDC34/img-qUyE8YkaEu3il601ISOsqtkr.png?st=2023-12-02T21%3A55%3A49Z&se=2023-12-02T23%3A55%3A49Z&sp=r&sv=2021-08-06&sr=b&rscd=inline&rsct=image/png&skoid=6aaadede-4fb3-4698-a8f6-684d7786b067&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2023-12-02T22%3A55%3A01Z&ske=2023-12-03T22%3A55%3A01Z&sks=b&skv=2021-08-06&sig=bJPLh7lOmznTcXc82ZCQ4c1Qcqle6c6WV93je0hmelc%3D",
                                                                                              "Question5": "https://oaidalleapiprodscus.blob.core.windows.net/private/org-22TlJ3O0EJC9AMJoee51xI0K/user-CLr6W6GiRSX9UXWCDXdyDC34/img-qUyE8YkaEu3il601ISOsqtkr.png?st=2023-12-02T21%3A55%3A49Z&se=2023-12-02T23%3A55%3A49Z&sp=r&sv=2021-08-06&sr=b&rscd=inline&rsct=image/png&skoid=6aaadede-4fb3-4698-a8f6-684d7786b067&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2023-12-02T22%3A55%3A01Z&ske=2023-12-03T22%3A55%3A01Z&sks=b&skv=2021-08-06&sig=bJPLh7lOmznTcXc82ZCQ4c1Qcqle6c6WV93je0hmelc%3D",
                                                                                              "Question6": "https://oaidalleapiprodscus.blob.core.windows.net/private/org-22TlJ3O0EJC9AMJoee51xI0K/user-CLr6W6GiRSX9UXWCDXdyDC34/img-qUyE8YkaEu3il601ISOsqtkr.png?st=2023-12-02T21%3A55%3A49Z&se=2023-12-02T23%3A55%3A49Z&sp=r&sv=2021-08-06&sr=b&rscd=inline&rsct=image/png&skoid=6aaadede-4fb3-4698-a8f6-684d7786b067&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2023-12-02T22%3A55%3A01Z&ske=2023-12-03T22%3A55%3A01Z&sks=b&skv=2021-08-06&sig=bJPLh7lOmznTcXc82ZCQ4c1Qcqle6c6WV93je0hmelc%3D",
                                                                                              "Question7": "https://oaidalleapiprodscus.blob.core.windows.net/private/org-22TlJ3O0EJC9AMJoee51xI0K/user-CLr6W6GiRSX9UXWCDXdyDC34/img-qUyE8YkaEu3il601ISOsqtkr.png?st=2023-12-02T21%3A55%3A49Z&se=2023-12-02T23%3A55%3A49Z&sp=r&sv=2021-08-06&sr=b&rscd=inline&rsct=image/png&skoid=6aaadede-4fb3-4698-a8f6-684d7786b067&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2023-12-02T22%3A55%3A01Z&ske=2023-12-03T22%3A55%3A01Z&sks=b&skv=2021-08-06&sig=bJPLh7lOmznTcXc82ZCQ4c1Qcqle6c6WV93je0hmelc%3D",
                                                                                              "Question8": "https://oaidalleapiprodscus.blob.core.windows.net/private/org-22TlJ3O0EJC9AMJoee51xI0K/user-CLr6W6GiRSX9UXWCDXdyDC34/img-qUyE8YkaEu3il601ISOsqtkr.png?st=2023-12-02T21%3A55%3A49Z&se=2023-12-02T23%3A55%3A49Z&sp=r&sv=2021-08-06&sr=b&rscd=inline&rsct=image/png&skoid=6aaadede-4fb3-4698-a8f6-684d7786b067&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2023-12-02T22%3A55%3A01Z&ske=2023-12-03T22%3A55%3A01Z&sks=b&skv=2021-08-06&sig=bJPLh7lOmznTcXc82ZCQ4c1Qcqle6c6WV93je0hmelc%3D",
                                                                                              "Question9": "https://oaidalleapiprodscus.blob.core.windows.net/private/org-22TlJ3O0EJC9AMJoee51xI0K/user-CLr6W6GiRSX9UXWCDXdyDC34/img-qUyE8YkaEu3il601ISOsqtkr.png?st=2023-12-02T21%3A55%3A49Z&se=2023-12-02T23%3A55%3A49Z&sp=r&sv=2021-08-06&sr=b&rscd=inline&rsct=image/png&skoid=6aaadede-4fb3-4698-a8f6-684d7786b067&sktid=a48cca56-e6da-484e-a814-9c849652bcb3&skt=2023-12-02T22%3A55%3A01Z&ske=2023-12-03T22%3A55%3A01Z&sks=b&skv=2021-08-06&sig=bJPLh7lOmznTcXc82ZCQ4c1Qcqle6c6WV93je0hmelc%3D",
                                                                                              "Question10": None})
    # share_slides("1sZkp63495N6XRVWoe6_56fch-0nGZ2KF9YWWqgc_PdE")