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
import logging
import pprint

import os
import pickle
from urllib.parse import urlparse

from django.db.models import Q
from .swoop_templates import SMART_TRIVIAL_PURSUIT_CATEGORIES, SMART_TRIVIAL_PURSUIT_TEMPLATE_ID

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
CONVERTED_SOURCE_FILE_PROPERTY = 'converted_from_file_id'
ROUND_SOURCE_WHOLE_PRESENTATION = 'whole_presentation'
ROUND_SOURCE_MERGED_DECK = 'merged_round_start'
ROUND_SOURCE_UNKNOWN = 'unknown'
GOOGLE_SLIDES_PRESENTATION_PATTERN = re.compile(r'/presentation/d/([a-zA-Z0-9_-]+)')
GOOGLE_SLIDES_SLIDE_FRAGMENT_PATTERN = re.compile(r'(?:^|&)slide=id\.([a-zA-Z0-9_:-]+)')
logger = logging.getLogger(__name__)


class PresentationBuildError(Exception):
    def __init__(
        self,
        message,
        *,
        presentation_id=None,
        creators=None,
        round_titles=None,
        round_links=None,
        step=None,
    ):
        super().__init__(message)
        self.presentation_id = presentation_id
        self.creators = creators or []
        self.round_titles = round_titles or []
        self.round_links = round_links or []
        self.step = step


def _current_pacific_date():
    return datetime.datetime.now(pst).date()


def _format_pacific_timestamp(timestamp_ms):
    return datetime.datetime.fromtimestamp(int(timestamp_ms) / 1000, tz=pst).strftime("%B %d, %Y")


def _sanitize_slides_text(text):
    if text is None:
        return ''

    sanitized_chars = []
    for char in text:
        codepoint = ord(char)
        if codepoint in (0x09, 0x0A, 0x0D):
            sanitized_chars.append(char)
            continue
        if 0x00 <= codepoint < 0x20 or 0x7F <= codepoint < 0xA0:
            continue
        if 0xE000 <= codepoint <= 0xF8FF:
            continue
        sanitized_chars.append(char)

    return ''.join(sanitized_chars)


def _utf16_code_units(text):
    return len(text.encode('utf-16-le')) // 2


def _utf16_placeholder_range(content, placeholder):
    start_index = content.index(placeholder)
    end_index = start_index + len(placeholder)
    return (
        _utf16_code_units(content[:start_index]),
        _utf16_code_units(content[:end_index]),
    )


def _inserted_text_end_index(start_index, new_text):
    return start_index + _utf16_code_units(_sanitize_slides_text(new_text))


def _build_black_text_style_request(element_id, start_index, new_text, font_size=None):
    style = {
        "foregroundColor": {
            "opaqueColor": {
                "rgbColor": {
                    "red": 0,
                    "green": 0,
                    "blue": 0,
                }
            }
        }
    }
    fields = ["foregroundColor"]

    if font_size is not None:
        style["fontSize"] = {
            "magnitude": font_size,
            "unit": "PT",
        }
        fields.append("fontSize")

    return {
        "updateTextStyle": {
            "objectId": element_id,
            "textRange": {
                "type": "FIXED_RANGE",
                "startIndex": start_index,
                "endIndex": _inserted_text_end_index(start_index, new_text),
            },
            "style": style,
            "fields": ",".join(fields),
        }
    }


def _extract_presentation_link_parts(presentation_url):
    if not presentation_url:
        return None, None

    presentation_match = GOOGLE_SLIDES_PRESENTATION_PATTERN.search(presentation_url)
    presentation_id = presentation_match.group(1) if presentation_match else None

    parsed_url = urlparse(presentation_url)
    slide_match = None
    for slide_source in (parsed_url.fragment or '', parsed_url.query or ''):
        slide_match = GOOGLE_SLIDES_SLIDE_FRAGMENT_PATTERN.search(slide_source)
        if slide_match:
            break
    slide_id = slide_match.group(1) if slide_match else None

    return presentation_id, slide_id


def _normalize_round_title(text):
    if not text:
        return ''
    return re.sub(r'[^a-z0-9]+', ' ', text.lower()).strip()


def _extract_slide_text(slide):
    return ' '.join(_extract_page_text_chunks(slide.get('pageElements', []))).strip()


def _extract_text_elements_content(text_elements):
    text_chunks = []
    for text_element in text_elements or []:
        text_run = text_element.get('textRun')
        auto_text = text_element.get('autoText')
        if text_run and 'content' in text_run:
            text_chunks.append(text_run['content'])
        elif auto_text and 'content' in auto_text:
            text_chunks.append(auto_text['content'])
    return text_chunks


def _extract_table_text_chunks(table):
    table_chunks = []
    for row in table.get('tableRows', []) or []:
        for cell in row.get('tableCells', []) or []:
            table_chunks.extend(
                _extract_text_elements_content(
                    ((cell or {}).get('text') or {}).get('textElements', [])
                )
            )
    return table_chunks


def _extract_page_element_text_chunks(element):
    text_chunks = []
    shape = element.get('shape') or {}
    if shape:
        text_chunks.extend(
            _extract_text_elements_content(
                (shape.get('text') or {}).get('textElements', [])
            )
        )

    table = element.get('table') or {}
    if table:
        text_chunks.extend(_extract_table_text_chunks(table))

    word_art = element.get('wordArt') or {}
    if word_art.get('renderedText'):
        text_chunks.append(word_art['renderedText'])

    element_group = element.get('elementGroup') or {}
    if element_group:
        text_chunks.extend(_extract_page_text_chunks(element_group.get('children', [])))

    element_title = str(element.get('title') or '').strip()
    element_description = str(element.get('description') or '').strip()
    if element_title:
        text_chunks.append(element_title)
    if element_description:
        text_chunks.append(element_description)

    return text_chunks


def _extract_page_text_chunks(page_elements):
    text_chunks = []
    for element in page_elements or []:
        text_chunks.extend(_extract_page_element_text_chunks(element))
    return [
        text_chunk
        for text_chunk in text_chunks
        if str(text_chunk or '').strip()
    ]


def _extract_speaker_notes_text(slide):
    notes_page = ((slide.get('slideProperties') or {}).get('notesPage') or {})
    speaker_notes_object_id = ((notes_page.get('notesProperties') or {}).get('speakerNotesObjectId') or '').strip()
    if not speaker_notes_object_id:
        return ''

    for element in notes_page.get('pageElements', []) or []:
        if element.get('objectId') != speaker_notes_object_id:
            continue
        return ' '.join(_extract_page_element_text_chunks(element)).strip()
    return ''


def _get_shape_text_content(presentation, element_id):
    for slide in presentation.get('slides', []):
        for element in slide.get('pageElements', []):
            if element.get('objectId') != element_id:
                continue
            shape = element.get('shape', {})
            text_elements = shape.get('text', {}).get('textElements', [])
            return ''.join(
                text_element['textRun']['content']
                for text_element in text_elements
                if 'textRun' in text_element and 'content' in text_element['textRun']
            )
    return None


def _pop_is_coop(coop_values):
    if not coop_values:
        return False
    return coop_values.pop(0) == 'on'


def _build_update_summary_entries(existing_round_count, titles, creator_keys, coops, max_slots=6):
    entries = []
    for offset, (title, creator_key) in enumerate(zip(titles, creator_keys)):
        slot_index = existing_round_count + offset
        if slot_index >= max_slots:
            break
        entries.append(
            {
                "round_placeholder": f"ROUND{slot_index + 1}",
                "creator_placeholder": f"CREATOR{slot_index + 1}",
                "title": title,
                "creator_key": creator_key,
                "coop": bool(coops[offset] == "on") if offset < len(coops) else False,
                "round_done": False,
                "creator_done": False,
            }
        )
    return entries


def _find_slide_index_for_round_title(slides, round_title, min_index=0):
    normalized_round_title = _normalize_round_title(round_title)
    if not normalized_round_title:
        return None

    for index in range(max(min_index, 0), len(slides)):
        slide_text = _normalize_round_title(_extract_slide_text(slides[index]))
        if not slide_text:
            continue
        if normalized_round_title in slide_text or slide_text in normalized_round_title:
            return index

    return None


def _classify_round_source_link(presentation_url):
    presentation_id, slide_id = _extract_presentation_link_parts(presentation_url)

    if presentation_id and slide_id:
        return {
            'source_type': ROUND_SOURCE_MERGED_DECK,
            'presentation_id': presentation_id,
            'slide_id': slide_id,
        }

    if presentation_id:
        return {
            'source_type': ROUND_SOURCE_WHOLE_PRESENTATION,
            'presentation_id': presentation_id,
            'slide_id': None,
        }

    return {
        'source_type': ROUND_SOURCE_UNKNOWN,
        'presentation_id': None,
        'slide_id': None,
    }


def _infer_historical_round_slide_range(
    slides,
    round_start_slide_id,
    sibling_round_links,
    next_round_title=None,
):
    slide_index_by_id = {
        slide.get('objectId'): index
        for index, slide in enumerate(slides)
        if slide.get('objectId')
    }

    if round_start_slide_id not in slide_index_by_id:
        raise ValueError(f"Could not locate slide {round_start_slide_id} in source presentation.")

    start_index = slide_index_by_id[round_start_slide_id]
    sibling_start_indices = sorted(
        {
            slide_index_by_id[slide_id]
            for link in sibling_round_links
            for _, slide_id in [_extract_presentation_link_parts(link)]
            if slide_id in slide_index_by_id
        }
    )

    next_start_index = next(
        (index for index in sibling_start_indices if index > start_index),
        None,
    )

    if next_start_index is not None:
        end_index = next_start_index - 1
    elif next_round_title:
        title_matched_index = _find_slide_index_for_round_title(
            slides,
            next_round_title,
            min_index=start_index + 1,
        )
        if title_matched_index is not None:
            end_index = title_matched_index - 1
        elif len(slides) > start_index + 1:
            # Historical merged decks end with an outro slide that should not be copied.
            end_index = len(slides) - 2
        else:
            end_index = start_index
    elif len(slides) > start_index + 1:
        # Historical merged decks end with an outro slide that should not be copied.
        end_index = len(slides) - 2
    else:
        end_index = start_index

    return start_index, max(start_index, end_index)


def _historical_round_links_for_presentation(presentation_id):
    from .models import GPTriviaRound

    presentation_fragment = f'/presentation/d/{presentation_id}'
    return list(
        GPTriviaRound.objects.filter(link__icontains=presentation_fragment)
        .values_list('link', flat=True)
    )


def _get_historical_round_context(round_link, presentation_id, slide_id):
    from .models import GPTriviaRound

    presentation_fragment = f'/presentation/d/{presentation_id}'
    current_round = None

    if slide_id:
        current_round = (
            GPTriviaRound.objects.filter(
                Q(link__icontains=presentation_fragment)
                & Q(link__icontains=f'slide=id.{slide_id}')
            )
            .order_by('date', 'round_number', 'id')
            .first()
        )

    if current_round is None and round_link:
        current_round = (
            GPTriviaRound.objects.filter(link=round_link)
            .order_by('date', 'round_number', 'id')
            .first()
        )

    if current_round is None or not current_round.date:
        return current_round, [], None

    sibling_rounds = list(
        GPTriviaRound.objects.filter(date=current_round.date)
        .order_by('round_number', 'id')
    )
    next_round = next(
        (
            sibling
            for sibling in sibling_rounds
            if sibling.round_number > current_round.round_number
        ),
        None,
    )
    return current_round, sibling_rounds, next_round


def _copy_presentation_via_apps_script(script_service, source_presentation_id, destination_presentation_id):
    request = {
        'function': 'copySlides',
        'parameters': [source_presentation_id, destination_presentation_id],
        'devMode': True,
    }
    return script_service.scripts().run(scriptId=APPS_SCRIPT_ID, body=request).execute()


def _create_temporary_round_copy(
    drive_service,
    slides_service,
    source_presentation_id,
    start_index,
    end_index,
):
    temp_presentation = drive_service.files().copy(
        fileId=source_presentation_id,
        body={'name': f"Temporary round copy {source_presentation_id} {start_index + 1}-{end_index + 1}"},
    ).execute()
    temp_presentation_id = temp_presentation['id']

    temp_slides = slides_service.presentations().get(
        presentationId=temp_presentation_id
    ).execute().get('slides', [])
    delete_requests = [
        {'deleteObject': {'objectId': slide['objectId']}}
        for index, slide in enumerate(temp_slides)
        if index < start_index or index > end_index
    ]

    if delete_requests:
        slides_service.presentations().batchUpdate(
            presentationId=temp_presentation_id,
            body={'requests': delete_requests},
        ).execute()

    return temp_presentation_id


def _delete_drive_file(drive_service, file_id):
    if not file_id:
        return

    try:
        drive_service.files().delete(fileId=file_id).execute()
    except HttpError as error:
        print(f"Failed to delete temporary file {file_id}: {error}")


def _copy_round_into_presentation(
    round_link,
    destination_presentation_id,
    script_service,
    slides_service,
    drive_service,
):
    link_info = _classify_round_source_link(round_link)
    source_presentation_id = link_info['presentation_id']
    temporary_presentation_id = None

    if link_info['source_type'] == ROUND_SOURCE_MERGED_DECK:
        source_presentation = slides_service.presentations().get(
            presentationId=source_presentation_id
        ).execute()
        source_slides = source_presentation.get('slides', [])
        _, sibling_rounds, next_round = _get_historical_round_context(
            round_link,
            source_presentation_id,
            link_info['slide_id'],
        )
        sibling_round_links = [
            sibling.link for sibling in sibling_rounds
            if sibling.link and f'/presentation/d/{source_presentation_id}' in sibling.link
        ] or _historical_round_links_for_presentation(source_presentation_id)
        start_index, end_index = _infer_historical_round_slide_range(
            source_slides,
            link_info['slide_id'],
            sibling_round_links,
            next_round_title=next_round.title if next_round else None,
        )
        temporary_presentation_id = _create_temporary_round_copy(
            drive_service,
            slides_service,
            source_presentation_id,
            start_index,
            end_index,
        )
        source_presentation_id = temporary_presentation_id
    elif not source_presentation_id:
        source_presentation_id = round_link.split('/')[-2]

    current_slide_count = len(
        slides_service.presentations().get(
            presentationId=destination_presentation_id
        ).execute().get('slides', [])
    )

    try:
        _copy_presentation_via_apps_script(
            script_service,
            source_presentation_id,
            destination_presentation_id,
        )
    finally:
        _delete_drive_file(drive_service, temporary_presentation_id)

    destination_slides = slides_service.presentations().get(
        presentationId=destination_presentation_id
    ).execute().get('slides', [])
    copied_slide_id = destination_slides[current_slide_count]['objectId']
    return (
        f"https://docs.google.com/presentation/d/{destination_presentation_id}"
        f"/edit#slide=id.{copied_slide_id}"
    )


def _prepare_update_round_sources(
    round_links,
    destination_presentation_id,
    slides_service,
    drive_service,
):
    prepared_links = []
    temporary_presentation_ids = []

    if not round_links:
        return prepared_links, temporary_presentation_ids

    destination_presentation = None
    destination_slides = None

    for round_link in round_links:
        link_info = _classify_round_source_link(round_link)
        if link_info["presentation_id"] != destination_presentation_id:
            prepared_links.append(round_link)
            continue

        if destination_presentation is None:
            destination_presentation = slides_service.presentations().get(
                presentationId=destination_presentation_id
            ).execute()
            destination_slides = destination_presentation.get("slides", [])

        if link_info["source_type"] == ROUND_SOURCE_MERGED_DECK:
            _, sibling_rounds, next_round = _get_historical_round_context(
                round_link,
                destination_presentation_id,
                link_info["slide_id"],
            )
            sibling_round_links = [
                sibling.link for sibling in sibling_rounds
                if sibling.link and f'/presentation/d/{destination_presentation_id}' in sibling.link
            ] or _historical_round_links_for_presentation(destination_presentation_id)
            start_index, end_index = _infer_historical_round_slide_range(
                destination_slides,
                link_info["slide_id"],
                sibling_round_links,
                next_round_title=next_round.title if next_round else None,
            )
            temporary_presentation_id = _create_temporary_round_copy(
                drive_service,
                slides_service,
                destination_presentation_id,
                start_index,
                end_index,
            )
        else:
            temporary_copy = drive_service.files().copy(
                fileId=destination_presentation_id,
                body={'name': f"Temporary update source copy {destination_presentation_id}"},
            ).execute()
            temporary_presentation_id = temporary_copy['id']

        temporary_presentation_ids.append(temporary_presentation_id)
        prepared_links.append(
            f"https://docs.google.com/presentation/d/{temporary_presentation_id}/edit"
        )

    return prepared_links, temporary_presentation_ids


def _find_existing_converted_presentation(drive_service, file_id):
    query = (
        "mimeType = 'application/vnd.google-apps.presentation' "
        f"and appProperties has {{ key='{CONVERTED_SOURCE_FILE_PROPERTY}' and value='{file_id}' }} "
        "and trashed = false"
    )
    response = drive_service.files().list(
        q=query,
        spaces='drive',
        fields='files(id)',
        pageSize=1,
    ).execute()
    files = response.get('files', [])
    return files[0]['id'] if files else None


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
            'title': datetime.date.strftime(_current_pacific_date(), '%-m.%d.%Y')
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


def ensure_presentation_public_by_link(presentation_link, credentials):
    presentation_id, _ = _extract_presentation_link_parts(presentation_link)
    if not presentation_id:
        return False

    try:
        service = build('drive', 'v3', credentials=credentials)
        permissions = service.permissions().list(
            fileId=presentation_id,
            fields='permissions(id,type,role,allowFileDiscovery)',
            supportsAllDrives=True,
        ).execute().get('permissions', [])

        anyone_permission = next(
            (permission for permission in permissions if permission.get('type') == 'anyone'),
            None,
        )

        if anyone_permission:
            role = anyone_permission.get('role')
            allow_file_discovery = anyone_permission.get('allowFileDiscovery')
            if role in {'reader', 'writer', 'commenter'} and allow_file_discovery is False:
                return True

            service.permissions().update(
                fileId=presentation_id,
                permissionId=anyone_permission['id'],
                body={
                    'role': 'reader',
                    'allowFileDiscovery': False,
                },
                supportsAllDrives=True,
            ).execute()
            return True

        service.permissions().create(
            fileId=presentation_id,
            body={
                'type': 'anyone',
                'role': 'reader',
                'allowFileDiscovery': False,
            },
            fields='id',
            supportsAllDrives=True,
        ).execute()
        return True

    except HttpError as error:
        logger.warning(
            "Failed to make source presentation public for %s: %s",
            presentation_link,
            error,
        )
        return False


def ensure_round_links_public(round_links, credentials):
    if not round_links:
        return

    seen_links = set()
    for round_link in round_links:
        if not round_link or round_link in seen_links:
            continue
        seen_links.add(round_link)
        ensure_presentation_public_by_link(round_link, credentials)

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


def update_merged_presentation(merged_presentation_id, merged_creators, titles, creators, links, old_links, coops):
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

    ensure_round_links_public(links, credentials)

    creator_keys = [key for creator in creators for key, value in MAIL_NAME_MAP.items() if value == creator]
    existing_round_count = len(list(merged_creators))
    round_titles_for_return = list(titles)
    creator_names_for_return = [MAIL_NAME_MAP[creator] for creator in creator_keys]
    slides_service = build('slides', 'v1', credentials=credentials)
    drive_service = build('drive', 'v3', credentials=credentials)
    prepared_shared_urls, prepared_temp_ids = _prepare_update_round_sources(
        links,
        merged_presentation_id,
        slides_service,
        drive_service,
    )

    # Remove the last slide
    presentation = slides_service.presentations().get(presentationId=merged_presentation_id).execute()
    last_slide_id = presentation['slides'][-1]['objectId']
    delete_slide_request = {'deleteObject': {'objectId': last_slide_id}}
    slides_service.presentations().batchUpdate(presentationId=merged_presentation_id, body={'requests': [delete_slide_request]}).execute()

    # Append any new shared slides from new creators
    print("finding shared presentations for shared presentation...")
    # shared_urls, creators = find_shared_presentations(credentials, merged_creators)
    find_shared_presentations(credentials, list(merged_creators), prepared_shared_urls, old_links)
    shared_urls = prepared_shared_urls

    script_service = build('script', 'v1', credentials=credentials)
    copied_links = []  # List to store links to the first slide of each copied presentation in the new presentation

    try:
        for url in shared_urls:
            copied_links.append(
                _copy_round_into_presentation(
                    url,
                    merged_presentation_id,
                    script_service,
                    slides_service,
                    drive_service,
                )
            )
    finally:
        for temporary_presentation_id in prepared_temp_ids:
            _delete_drive_file(drive_service, temporary_presentation_id)


    # update the second slide with the round titles and creators
    merged_pres = slides_service.presentations().get(presentationId=merged_presentation_id).execute()

    second_slide = merged_pres['slides'][1]
    second_slide_id = second_slide['objectId']
    second_slide_elements = second_slide['pageElements']

    # Define placeholders for the rounds and creators
    round_placeholders = ['ROUND1', 'ROUND2', 'ROUND3', 'ROUND4', 'ROUND5', 'ROUND6']
    creator_placeholders = ['CREATOR1', 'CREATOR2', 'CREATOR3', 'CREATOR4', 'CREATOR5', 'CREATOR6']
    summary_round_titles = list(round_titles_for_return)
    summary_creator_keys = list(creator_keys)
    summary_entries = _build_update_summary_entries(
        existing_round_count,
        summary_round_titles,
        summary_creator_keys,
        coops,
        max_slots=len(round_placeholders),
    )
    print(summary_round_titles)
    print(summary_creator_keys)
    print(merged_creators)

    j=0
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
                        matching_entry = next(
                            (
                                entry for entry in summary_entries
                                if entry["round_placeholder"] == round_placeholder
                            ),
                            None,
                        )
                        if matching_entry is None:
                            continue

                        if round_placeholder in content and not matching_entry["round_done"]:
                            new_text = _sanitize_slides_text(matching_entry["title"])
                            round_start_index, round_end_index = _utf16_placeholder_range(
                                content, round_placeholder
                            )
                            delete_insert_requests = create_delete_insert_text_requests(
                                element_id, round_start_index, round_end_index, new_text)

                            if len(new_text) > 30:
                                delete_insert_requests.append(
                                    _build_black_text_style_request(
                                        element_id,
                                        round_start_index,
                                        new_text,
                                        font_size=20,
                                    )
                                )
                            elif len(new_text) > 40:
                                delete_insert_requests.append(
                                    _build_black_text_style_request(
                                        element_id,
                                        round_start_index,
                                        new_text,
                                        font_size=16,
                                    )
                                )
                            elif len(new_text) > 70:
                                delete_insert_requests.append(
                                    _build_black_text_style_request(
                                        element_id,
                                        round_start_index,
                                        new_text,
                                        font_size=10,
                                    )
                                )
                            else:
                                delete_insert_requests.append(
                                    _build_black_text_style_request(
                                        element_id,
                                        round_start_index,
                                        new_text,
                                    )
                                )

                            slides_service.presentations().batchUpdate(
                                presentationId=merged_presentation_id,
                                body={'requests': delete_insert_requests}
                            ).execute()

                            # Update the content variable with the updated text from the API
                            updated_text = slides_service.presentations().get(
                                presentationId=merged_presentation_id).execute()
                            updated_content = _get_shape_text_content(updated_text, element_id)
                            if updated_content is not None:
                                content = updated_content
                            matching_entry["round_done"] = True

                        if creator_placeholder in content and not matching_entry["creator_done"]:
                            new_text = _sanitize_slides_text(MAIL_NAME_MAP[matching_entry["creator_key"]])
                            creator_start_index, creator_end_index = _utf16_placeholder_range(
                                content, creator_placeholder
                            )

                            if matching_entry["coop"]:
                                new_text = new_text + " - Co-op"
                            j+=1

                            print(f"creator_start_index: {creator_start_index}")
                            print(f"creator_end_index: {creator_end_index}")
                            print(f"content: {content}")
                            print(f"new_text: {new_text}")

                            delete_insert_requests = create_delete_insert_text_requests(
                                element_id, creator_start_index, creator_end_index, new_text)
                            delete_insert_requests.append(
                                _build_black_text_style_request(
                                    element_id,
                                    creator_start_index,
                                    new_text,
                                )
                            )

                            response = slides_service.presentations().batchUpdate(presentationId=merged_presentation_id,
                                                                                  body={
                                                                                      'requests': delete_insert_requests}).execute()
                            matching_entry["creator_done"] = True
                            break

    # add the outro slide
    outro_id = '1BSOudw2JxjVcHxfHX-yfJqmuh0Pp4iKMmYY5klW5zLI'
    _copy_presentation_via_apps_script(script_service, outro_id, merged_presentation_id)

    return (
        merged_presentation_id,
        creator_names_for_return,
        round_titles_for_return,
        copied_links,
    )


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

def copy_template(template_id, copy_title, qas, icon_links, smart_category_plan=None):
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

        if template_id == SMART_TRIVIAL_PURSUIT_TEMPLATE_ID:
            _apply_smart_trivial_pursuit_layout(
                service,
                new_presentation_id,
                copy_title,
                smart_category_plan or [],
            )

            drive_service = build('drive', 'v3', credentials=credentials)
            permission = {
                'type': 'anyone',
                'role': 'writer'
            }
            drive_service.permissions().create(
                fileId=new_presentation_id,
                body=permission,
                fields='id'
            ).execute()
            return new_presentation_id

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


def _classify_smart_template_slide(slide):
    slide_text = re.sub(r'\s+', ' ', _extract_slide_text(slide)).upper()
    if not slide_text:
        return '', ''

    for category_name in SMART_TRIVIAL_PURSUIT_CATEGORIES:
        if re.search(rf'{re.escape(category_name)}\s*ANSWER\b', slide_text):
            return category_name, 'answer'
    for category_name in SMART_TRIVIAL_PURSUIT_CATEGORIES:
        if re.search(rf'{re.escape(category_name)}\s*QUESTION\b', slide_text):
            return category_name, 'question'
    return '', ''


def _build_smart_template_slide_map(slides):
    category_slide_map = {}
    first_category_index = None

    for index, slide in enumerate(slides or []):
        category_name, slide_kind = _classify_smart_template_slide(slide)
        if not category_name or not slide_kind:
            continue
        if first_category_index is None:
            first_category_index = index
        category_slide_map.setdefault(category_name, {})[slide_kind] = slide.get('objectId')

    if first_category_index is None:
        first_category_index = len(slides or [])

    return category_slide_map, first_category_index


def _find_smart_template_answers_divider_index(slides, excluded_slide_ids=None):
    excluded_ids = set(excluded_slide_ids or [])
    for index, slide in enumerate(slides or []):
        slide_id = slide.get('objectId')
        if slide_id in excluded_ids:
            continue
        slide_text = re.sub(r'\s+', ' ', _extract_slide_text(slide)).upper()
        if re.search(r'\bANSWERS\b', slide_text):
            return index
    return None


def _build_smart_template_slide_map_from_expected_order(slides):
    slides = slides or []
    divider_index = _find_smart_template_answers_divider_index(slides)
    category_count = len(SMART_TRIVIAL_PURSUIT_CATEGORIES)
    if divider_index is None:
        return {}, len(slides)

    question_start_index = divider_index - category_count
    answer_start_index = divider_index + 1
    answer_end_index = answer_start_index + category_count
    if question_start_index < 0 or answer_end_index > len(slides):
        return {}, len(slides)

    category_slide_map = {}
    for offset, category_name in enumerate(SMART_TRIVIAL_PURSUIT_CATEGORIES):
        question_slide_id = slides[question_start_index + offset].get('objectId')
        answer_slide_id = slides[answer_start_index + offset].get('objectId')
        if not question_slide_id or not answer_slide_id:
            return {}, len(slides)
        category_slide_map[category_name] = {
            'question': question_slide_id,
            'answer': answer_slide_id,
        }

    return category_slide_map, question_start_index


def _smart_template_slide_map_is_complete(category_slide_map):
    for category_name in SMART_TRIVIAL_PURSUIT_CATEGORIES:
        slide_pair = category_slide_map.get(category_name) or {}
        if not slide_pair.get('question') or not slide_pair.get('answer'):
            return False
    return True


def _resolve_smart_template_slide_map(slides):
    category_slide_map, first_category_index = _build_smart_template_slide_map(slides)
    if _smart_template_slide_map_is_complete(category_slide_map):
        return category_slide_map, first_category_index

    ordered_slide_map, ordered_first_category_index = _build_smart_template_slide_map_from_expected_order(slides)
    if _smart_template_slide_map_is_complete(ordered_slide_map):
        return ordered_slide_map, ordered_first_category_index

    return category_slide_map, first_category_index


def _find_smart_template_answers_insertion_index(slides, excluded_slide_ids=None):
    divider_index = _find_smart_template_answers_divider_index(slides, excluded_slide_ids=excluded_slide_ids)
    if divider_index is None:
        return len(slides or [])
    return divider_index + 1


def _build_targeted_replace_text_request(slide_id, placeholder_text, replacement_text):
    return {
        'replaceAllText': {
            'containsText': {
                'text': placeholder_text,
                'matchCase': True,
            },
            'replaceText': _sanitize_slides_text(replacement_text),
            'pageObjectIds': [slide_id],
        }
    }


def _move_slide_to_index(service, presentation_id, slide_id, insertion_index):
    service.presentations().batchUpdate(
        presentationId=presentation_id,
        body={
            'requests': [
                {
                    'updateSlidesPosition': {
                        'slideObjectIds': [slide_id],
                        'insertionIndex': insertion_index,
                    }
                }
            ]
        },
    ).execute()


def _duplicate_slide_and_get_new_id(service, presentation_id, source_slide_id, known_slide_ids):
    service.presentations().batchUpdate(
        presentationId=presentation_id,
        body={
            'requests': [
                {
                    'duplicateObject': {
                        'objectId': source_slide_id,
                    }
                }
            ]
        },
    ).execute()

    refreshed_presentation = service.presentations().get(
        presentationId=presentation_id
    ).execute()
    for slide in refreshed_presentation.get('slides', []) or []:
        slide_id = slide.get('objectId')
        if slide_id and slide_id not in known_slide_ids:
            known_slide_ids.add(slide_id)
            return slide_id
    raise RuntimeError(f"Could not identify duplicated slide for {source_slide_id}.")


def _apply_smart_trivial_pursuit_layout(service, presentation_id, copy_title, smart_category_plan):
    presentation = service.presentations().get(presentationId=presentation_id).execute()
    slides = presentation.get('slides', []) or []
    category_slide_map, question_insertion_index = _resolve_smart_template_slide_map(slides)

    known_slide_ids = {
        slide.get('objectId')
        for slide in slides
        if slide.get('objectId')
    }
    category_source_slide_ids = {
        slide_id
        for slide_pair in category_slide_map.values()
        for slide_id in slide_pair.values()
        if slide_id
    }
    replace_requests = [
        {
            'replaceAllText': {
                'containsText': {
                    'text': 'RoundTitle',
                    'matchCase': True,
                },
                'replaceText': copy_title,
            }
        }
    ]

    for display_number, question_row in enumerate(smart_category_plan or [], start=1):
        category_name = str(question_row.get('category') or '').upper().strip()
        slide_pair = category_slide_map.get(category_name) or {}
        question_source_id = slide_pair.get('question')
        if not question_source_id:
            raise RuntimeError(f"Smart template is missing a question slide for {category_name}.")

        duplicated_question_id = _duplicate_slide_and_get_new_id(
            service,
            presentation_id,
            question_source_id,
            known_slide_ids,
        )
        _move_slide_to_index(service, presentation_id, duplicated_question_id, question_insertion_index)
        question_insertion_index += 1
        replace_requests.append(
            _build_targeted_replace_text_request(
                duplicated_question_id,
                f"{category_name}QUESTION",
                str(question_row.get('question_text') or ''),
            )
        )
        replace_requests.append(
            _build_targeted_replace_text_request(
                duplicated_question_id,
                '#',
                str(display_number),
            )
        )

    refreshed_presentation = service.presentations().get(presentationId=presentation_id).execute()
    answer_insertion_index = _find_smart_template_answers_insertion_index(
        refreshed_presentation.get('slides', []) or [],
        excluded_slide_ids=category_source_slide_ids,
    )

    for display_number, question_row in enumerate(smart_category_plan or [], start=1):
        category_name = str(question_row.get('category') or '').upper().strip()
        slide_pair = category_slide_map.get(category_name) or {}
        answer_source_id = slide_pair.get('answer')
        if not answer_source_id:
            raise RuntimeError(f"Smart template is missing a slide pair for {category_name}.")

        duplicated_answer_id = _duplicate_slide_and_get_new_id(
            service,
            presentation_id,
            answer_source_id,
            known_slide_ids,
        )
        _move_slide_to_index(service, presentation_id, duplicated_answer_id, answer_insertion_index)
        answer_insertion_index += 1
        replace_requests.append(
            _build_targeted_replace_text_request(
                duplicated_answer_id,
                f"{category_name}QUESTION",
                str(question_row.get('question_text') or ''),
            )
        )
        replace_requests.append(
            _build_targeted_replace_text_request(
                duplicated_answer_id,
                f"{category_name}ANSWER",
                str(question_row.get('answer_text') or ''),
            )
        )
        replace_requests.append(
            _build_targeted_replace_text_request(
                duplicated_answer_id,
                '#',
                str(display_number),
            )
        )

    delete_requests = []
    for slide_pair in category_slide_map.values():
        for source_slide_id in slide_pair.values():
            if source_slide_id:
                delete_requests.append({'deleteObject': {'objectId': source_slide_id}})

    request_batch = replace_requests + delete_requests
    if request_batch:
        service.presentations().batchUpdate(
            presentationId=presentation_id,
            body={'requests': request_batch},
        ).execute()

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



def create_presentation(titles, creators, links, presentation_name, old_links, coops):
    credentials = None
    new_presentation_id = None
    copied_links = []
    current_step = "loading credentials"
    logger.info(
        "Starting presentation generation for %s with %s rounds",
        presentation_name,
        len(titles),
    )
    # Check if the token.pickle file exists
    if os.path.exists(token_file_path):
        with open(token_file_path, 'rb') as token:
            credentials = pickle.load(token)

    creator_keys = [key for creator in creators for key, value in MAIL_NAME_MAP.items() if value == creator]
    creator_names_for_return = [MAIL_NAME_MAP[creator] for creator in creator_keys]
    round_titles_for_return = list(titles)

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

    ensure_round_links_public(links, credentials)

    # intro_id = '1sXOpGumQ9nIDj3tDgU7J5U_bHiTu48YL50MtILw6ngo'
    intro_id = '1I3ONljiYpyHJloW_11rWayLs3j9gxRPc-WU_UPqfrt4'
    outro_id = '1BSOudw2JxjVcHxfHX-yfJqmuh0Pp4iKMmYY5klW5zLI'

    try:
        current_step = "creating destination presentation"
        new_presentation_id = new_presentation(credentials)
        logger.info(
            "Created destination presentation %s for %s",
            new_presentation_id,
            presentation_name,
        )
        current_step = "finding shared presentations"
        print("finding shared presentations for new presentation...")
        find_shared_presentations(credentials, [], links, old_links)
        shared_urls = links
        http = httplib2.Http(timeout=300)
        authorized_http = AuthorizedHttp(credentials, http=http)
        script_service = build('script', 'v1', http=authorized_http)
        slides_service = build('slides', 'v1', credentials=credentials)
        drive_service = build('drive', 'v3', credentials=credentials)

        current_step = "copying intro slides"
        response = _copy_presentation_via_apps_script(
            script_service,
            intro_id,
            new_presentation_id,
        )

        print("Apps Script response:\n" + pprint.pformat(response), flush=True)

        new_pres = slides_service.presentations().get(presentationId=new_presentation_id).execute()
        first_slide = new_pres['slides'][1]

        current_step = "updating intro date slide"
        date_element_id = None
        for element in first_slide['pageElements']:
            if 'shape' in element and 'text' in element['shape']:
                text = element['shape']['text']['textElements']
                for text_element in text:
                    if 'textRun' in text_element and 'content' in text_element['textRun']:
                        content = text_element['textRun']['content']
                        if "June" in content:
                            date_element_id = element['objectId']
                            date_text = content
                            len_date_text = len(date_text)
                            break

        date_text = _current_pacific_date().strftime("%B %d, %Y")

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

        for index, url in enumerate(shared_urls):
            current_step = (
                f"copying round {index + 1}/{len(shared_urls)}"
                f" ({titles[index] if index < len(titles) else url})"
            )
            copied_links.append(
                _copy_round_into_presentation(
                    url,
                    new_presentation_id,
                    script_service,
                    slides_service,
                    drive_service,
                )
            )
            logger.info(
                "Copied round %s/%s into %s from %s",
                index + 1,
                len(shared_urls),
                new_presentation_id,
                url,
            )

        creators_list = list(creator_keys)
        summary_round_titles = list(round_titles_for_return)
        summary_creator_keys = list(creators_list)
        summary_coops = list(coops)

        current_step = "updating summary slide"
        second_slide = new_pres['slides'][2]
        second_slide_elements = second_slide['pageElements']

        round_placeholders = ['ROUND1', 'ROUND2', 'ROUND3', 'ROUND4', 'ROUND5', 'ROUND6']
        creator_placeholders = ['CREATOR1', 'CREATOR2', 'CREATOR3', 'CREATOR4', 'CREATOR5', 'CREATOR6']

        for element in second_slide_elements:
            if 'shape' in element and 'text' in element['shape']:
                element_id = element['objectId']
                text_elements = element['shape']['text']['textElements']

                element_len = 0
                for idx, text_element in enumerate(text_elements):
                    if idx != 1:
                        continue
                    if 'textRun' in text_element and 'content' in text_element['textRun']:
                        content = text_element['textRun']['content']
                        element_len += len(content)

                        for i in range(len(round_placeholders)):
                            round_placeholder = round_placeholders[i]
                            creator_placeholder = creator_placeholders[i]

                            if round_placeholder in content and len(summary_round_titles) > i:
                                new_text = _sanitize_slides_text(summary_round_titles[i])
                                round_start_index, round_end_index = _utf16_placeholder_range(
                                    content, round_placeholder
                                )
                                delete_insert_requests = create_delete_insert_text_requests(
                                    element_id, round_start_index, round_end_index, new_text)

                                if len(new_text) > 30:
                                    delete_insert_requests.append(
                                        _build_black_text_style_request(
                                            element_id,
                                            round_start_index,
                                            new_text,
                                            font_size=20,
                                        )
                                    )
                                elif len(new_text) > 40:
                                    delete_insert_requests.append(
                                        _build_black_text_style_request(
                                            element_id,
                                            round_start_index,
                                            new_text,
                                            font_size=16,
                                        )
                                    )
                                else:
                                    delete_insert_requests.append(
                                        _build_black_text_style_request(
                                            element_id,
                                            round_start_index,
                                            new_text,
                                        )
                                    )

                                slides_service.presentations().batchUpdate(
                                    presentationId=new_presentation_id,
                                    body={'requests': delete_insert_requests}
                                ).execute()

                                updated_text = slides_service.presentations().get(
                                    presentationId=new_presentation_id).execute()
                                updated_content = _get_shape_text_content(updated_text, element_id)
                                if updated_content is not None:
                                    content = updated_content

                            if creator_placeholder in content and len(summary_creator_keys) > i:
                                new_text = _sanitize_slides_text(MAIL_NAME_MAP[summary_creator_keys[i]])
                                creator_start_index, creator_end_index = _utf16_placeholder_range(
                                    content, creator_placeholder
                                )

                                if _pop_is_coop(summary_coops):
                                    new_text = f"{new_text} - Co-op"

                                print(f"creator_start_index: {creator_start_index}")
                                print(f"creator_end_index: {creator_end_index}")
                                print(f"content: {content}")
                                print(f"new_text: {new_text}")

                                delete_insert_requests = create_delete_insert_text_requests(
                                    element_id, creator_start_index, creator_end_index, new_text)
                                delete_insert_requests.append(
                                    _build_black_text_style_request(
                                        element_id,
                                        creator_start_index,
                                        new_text,
                                    )
                                )

                                slides_service.presentations().batchUpdate(
                                    presentationId=new_presentation_id,
                                    body={'requests': delete_insert_requests}
                                ).execute()
                                break

        current_step = "copying outro slide"
        _copy_presentation_via_apps_script(
            script_service,
            outro_id,
            new_presentation_id,
        )

        current_step = "removing blank first slide"
        remove_first_slide(credentials, new_presentation_id)

        current_step = "updating presentation permissions"
        update_slide_permissions(new_presentation_id, credentials)
        logger.info(
            "Completed presentation generation for %s (%s)",
            presentation_name,
            new_presentation_id,
        )

        return (
            new_presentation_id,
            creator_names_for_return,
            round_titles_for_return,
            copied_links,
        )
    except PresentationBuildError:
        raise
    except Exception as error:
        logger.exception(
            "Presentation generation failed during %s for %s (%s)",
            current_step,
            presentation_name,
            new_presentation_id,
        )
        raise PresentationBuildError(
            f"Slide generation stopped during {current_step}: {error}",
            presentation_id=new_presentation_id,
            creators=creator_names_for_return,
            round_titles=round_titles_for_return,
            round_links=copied_links,
            step=current_step,
        ) from error

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
            existing_converted_id = _find_existing_converted_presentation(drive_service, file_id)
            if existing_converted_id:
                return f"https://docs.google.com/presentation/d/{existing_converted_id}/edit"

            # Convert to Google Slides format
            converted_file = drive_service.files().copy(
                fileId=file_id,
                body={'mimeType': 'application/vnd.google-apps.presentation'}
            ).execute()

            drive_service.files().update(
                fileId=converted_file['id'],
                body={'appProperties': {CONVERTED_SOURCE_FILE_PROPERTY: file_id}},
            ).execute()

            # Return the new Google Slides URL
            new_presentation_url = f"https://docs.google.com/presentation/d/{converted_file['id']}/edit"
            return new_presentation_url

        # If it's already a Google Slides presentation, return the original URL
        return presentation_url

    except HttpError as error:
        print(f'An error occurred: {error}')
        return None

# Pre-compile the regex pattern outside the loop for efficiency
URL_PATTERN = re.compile(r'(https?://docs\.google\.com/presentation/d/[^\s]+)')

# Assuming MAIL_NAME_MAP is defined elsewhere
# Example:
# MAIL_NAME_MAP = {
#     "sender@example.com": "Desired Name",
#     # Add more mappings as needed
# }

def get_round_titles_and_links(processed_senders=[]):
    credentials = None
    # Check if the token.pickle file exists
    if os.path.exists(token_file_path):
        with open(token_file_path, 'rb') as token:
            credentials = pickle.load(token)

    # Check if the credentials have expired
    if credentials and credentials.expired and credentials.refresh_token:
        try:
            # Refresh the credentials
            credentials.refresh(Request())

            # Save the refreshed credentials back to the 'token.pickle' file
            with open(token_file_path, 'wb') as token:
                pickle.dump(credentials, token)
        except Exception as e:
            print("Failed to refresh the token, getting new credentials:", e)
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
        response = gmail_service.users().messages().list(userId='me', q=query, maxResults=500).execute()  # Increased maxResults for batching

        if 'messages' in response:
            messages = response['messages']
            messages_with_date = []

            # Function to handle batch responses for metadata
            def metadata_callback(request_id, response, exception):
                if exception is not None:
                    print(f"Error fetching metadata for message ID {request_id}: {exception}")
                else:
                    internal_date = response.get('internalDate', '0')
                    messages_with_date.append((response, internal_date))

            # Create a batch request for fetching message metadata
            batch = gmail_service.new_batch_http_request(callback=metadata_callback)

            for message in messages:
                msg_id = message['id']
                batch.add(gmail_service.users().messages().get(
                    userId='me',
                    id=msg_id,
                    format='metadata',
                    metadataHeaders=['From', 'internalDate']
                ), request_id=msg_id)

            # Execute the batch request
            batch.execute()

            # Sort messages by internalDate
            messages_with_date.sort(key=lambda x: x[1])

            # Function to handle batch responses for full messages
            def fullmsg_callback(request_id, response, exception):
                if exception is not None:
                    print(f"Error fetching full message for ID {request_id}: {exception}")
                else:
                    process_full_message(response)

            # Function to process each full message
            def process_full_message(msg):
                msg_id = msg['id']
                headers = msg['payload']['headers']
                try:
                    # Optimized header extraction using generator expression
                    sender = next(header['value'] for header in headers if header['name'] == 'From')
                    sender = sender.split()[0][1:]
                except StopIteration:
                    sender = "Unknown"

                new_senders.append(sender)

                parts = msg['payload'].get('parts', [])

                for part in parts:
                    if part.get('mimeType') == 'text/plain':
                        data = part.get('body', {}).get('data')
                        if data:
                            try:
                                msg_str = base64.urlsafe_b64decode(data.encode('ASCII')).decode('utf-8')
                            except (base64.binascii.Error, UnicodeDecodeError) as e:
                                print(f"Decoding error for message {msg_id}: {e}")
                                continue

                            url_match = URL_PATTERN.search(msg_str)
                            if url_match:
                                presentation_url = url_match.group(1)
                                new_presentation_url = convert_shared_presentation(presentation_url, credentials)
                                presentation_urls.append(new_presentation_url)
                                old_urls.append(presentation_url)

                                shared_presentation_id = new_presentation_url.split('/')[-2]
                                try:
                                    shared_presentation = slides_service.presentations().get(presentationId=shared_presentation_id).execute()
                                except HttpError as e:
                                    print(f"Failed to fetch presentation {shared_presentation_id}: {e}")
                                    continue

                                slides = shared_presentation.get('slides', [])
                                if not slides:
                                    print(f"No slides found in presentation {shared_presentation_id}")
                                    continue

                                first_slide = slides[0]

                                # Extract title_text
                                title_text = ""
                                for element in first_slide.get('pageElements', []):
                                    shape = element.get('shape', {})
                                    text = shape.get('text', {}).get('textElements', [])
                                    for text_element in text:
                                        if 'textRun' in text_element and 'content' in text_element['textRun']:
                                            title_text += text_element['textRun']['content']
                                            break
                                    if title_text:
                                        break

                                title_text = re.sub(r'\s+', ' ', title_text).strip()
                                round_titles.append(title_text)

            # Create a batch request for fetching full messages
            fullmsg_batch = gmail_service.new_batch_http_request(callback=fullmsg_callback)

            for msg, _ in messages_with_date:
                msg_id = msg['id']
                fullmsg_batch.add(gmail_service.users().messages().get(
                    userId='me',
                    id=msg_id,
                    format='full'
                ), request_id=msg_id)

            # Execute the batch request for full messages
            fullmsg_batch.execute()

        # Replace the sender using MAIL_NAME_MAP
        new_senders = [MAIL_NAME_MAP.get(sender, "Unknown") for sender in new_senders]

        print(presentation_urls, round_titles, new_senders, old_urls)

        # convert the messages_with_date dates from a string containing a unix timestamp to a string with the month, day and year
        newdates = []
        for i in range(len(messages_with_date)):
            newdates.append(_format_pacific_timestamp(messages_with_date[i][1]))


        return presentation_urls, round_titles, new_senders, old_urls, newdates

    except HttpError as error:
        print(f"An error occurred: {error}")
        return None, None, None, None

# def get_round_titles_and_links(processed_senders=[]):
#     credentials = None
#     # Check if the token.pickle file exists
#     if os.path.exists(token_file_path):
#         with open(token_file_path, 'rb') as token:
#             credentials = pickle.load(token)
#
#     # Check if the credentials have expired
#     if credentials.expired and credentials.refresh_token:
#         try:
#             # Refresh the credentials
#             credentials.refresh(Request())
#
#             # Save the refreshed credentials back to the 'token.pickle' file
#             with open(token_file_path, 'wb') as token:
#                 pickle.dump(credentials, token)
#         except Exception as e:
#             print("Failed to refresh the token, getting new credentials")
#             credentials = build_credentials()
#             with open(token_file_path, 'wb') as token:
#                 pickle.dump(credentials, token)
#
#     # If the credentials are not available or invalid, prompt the user to authenticate again.
#     if not credentials or not credentials.valid:
#         credentials = build_credentials()
#         with open(token_file_path, 'wb') as token:
#             pickle.dump(credentials, token)
#
#     http = httplib2.Http(timeout=300)
#     authorized_http = AuthorizedHttp(credentials, http=http)
#     script_service = build('script', 'v1', http=authorized_http)
#     slides_service = build('slides', 'v1', credentials=credentials)
#
#     print(processed_senders)
#     try:
#         new_senders = []
#         presentation_urls = []
#         old_urls = []
#         round_titles = []
#
#         gmail_service = build('gmail', 'v1', credentials=credentials)
#         query = 'subject:"Presentation shared with you:.*" is:unread'
#         response = gmail_service.users().messages().list(userId='me', q=query).execute()
#
#         if 'messages' in response:
#             messages_with_date = []
#             for message in response['messages']:
#                 msg_id = message['id']
#                 msg = gmail_service.users().messages().get(userId='me', id=msg_id, format='metadata', metadataHeaders=['From', 'internalDate']).execute()
#                 messages_with_date.append((msg, msg['internalDate']))
#
#             messages_with_date.sort(key=lambda x: x[1])
#
#             for msg, _ in messages_with_date:
#                 msg_id = msg['id']
#                 headers = msg['payload']['headers']
#                 sender = [header['value'] for header in headers if header['name'] == 'From'][0]
#                 sender = sender.split()[0]
#                 sender = sender[1:]
#
#                 new_senders.append(sender)
#                 msg = gmail_service.users().messages().get(userId='me', id=msg_id, format='full').execute()
#                 parts = msg['payload']['parts']
#
#                 for part in parts:
#                     if part['mimeType'] == 'text/plain':
#                         data = part['body']['data']
#                         if data:
#                             msg_str = base64.urlsafe_b64decode(data.encode('ASCII'))
#                             url_pattern = r'(https?://docs\.google\.com/presentation/d/[^\s]+)'
#                             # 'https://docs.google.com/presentation/d/1ECVqOMtgWEbzMOtzNLDQCRSSOA8BXbhRdJ_9yNWzgj0/edit?u'
#                             # url_pattern = r'(https?://docs\.google\.com/presentation/d/[\w-]+)'
#                             # 'https://docs.google.com/presentation/d/1ECVqOMtgWEbzMOtzNLDQCRSSOA8BXbhRdJ_9yNWzgj0'
#                             url_match = re.search(url_pattern, msg_str.decode('utf-8'))
#
#                             if url_match:
#                                 presentation_url = url_match.group(1)
#                                 new_presentation_url = convert_shared_presentation(presentation_url, credentials)
#                                 presentation_urls.append(new_presentation_url)
#                                 old_urls.append(presentation_url)
#                                 # Extract round title
#                                 shared_presentation_id = new_presentation_url.split('/')[-2]
#                                 # request = {
#                                 #     'function': FUNCTION_NAME,
#                                 #     'parameters': [shared_presentation_id, merged_presentation_id],
#                                 #     'devMode': True
#                                 # }
#                                 # response = script_service.scripts().run(scriptId=APPS_SCRIPT_ID, body=request).execute()
#                                 shared_presentation = slides_service.presentations().get(presentationId=shared_presentation_id).execute()
#                                 first_slide = shared_presentation['slides'][0]
#
#                                 title_text = ""
#                                 flag=0
#                                 for element in first_slide['pageElements']:
#                                     if 'shape' in element and 'text' in element['shape']:
#                                         text = element['shape']['text']['textElements']
#                                         if flag:
#                                             break
#                                         for text_element in text:
#                                             if 'textRun' in text_element and 'content' in text_element['textRun']:
#                                                 flag=1
#                                                 title_text += text_element['textRun']['content']
#                                                 break
#
#                                 title_text = re.sub(r'\\s+', ' ', title_text).strip()
#                                 round_titles.append(title_text)
#
#         # replace the sender using mail name map with the current name as the key and the name we want to return as the value
#         # unless the sender is not in the mail name map, then we just return "Unknown"
#         new_senders = [MAIL_NAME_MAP[sender] if sender in MAIL_NAME_MAP else "Unknown" for sender in new_senders]
#
#         print(presentation_urls, round_titles, new_senders, old_urls)
#         return presentation_urls, round_titles, new_senders, old_urls
#
#     except HttpError as error:
#         print(f"An error occurred: {error}")
#         return None, None, None, None


if __name__ == '__main__':
    # get_round_titles_and_links([])
    create_presentation(["title1"], ["creator1"], ["link1"], "name", ["oldlink1"], ["no"])
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
