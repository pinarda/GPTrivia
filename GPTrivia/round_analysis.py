import base64
import json
import logging
import mimetypes
import os
import posixpath
import pickle
import re
import threading
import traceback
import uuid
import zipfile
from io import BytesIO
from itertools import chain
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree

import requests
from django.core.files.base import ContentFile
from django.db import close_old_connections, transaction
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone
import httplib2
from PIL import Image, ImageOps

from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google_auth_httplib2 import AuthorizedHttp

from .models import (
    GPTriviaRound,
    MergedPresentation,
    PushSubscription,
    RoundAnalysisWorkerState,
    RoundQuestionAnalysisEntry,
    RoundQuestionAnalysisRun,
)
from .player_scores import display_name_for_player_field, get_all_player_fields


logger = logging.getLogger(__name__)
ANALYSIS_NOTIFICATION_USERNAME = 'Alex'
ROUND_ANALYSIS_IMAGE_MAX_DIMENSION = 512
ROUND_ANALYSIS_IMAGE_JPEG_QUALITY = 72
ROUND_ANALYSIS_THUMBNAIL_SIZE = 'LARGE'
PPTX_EXPORT_MIME_TYPE = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
ROUND_ANALYSIS_AUTO_DELAY_SECONDS = 300
ROUND_ANALYSIS_WORKER_IDLE_WAIT_SECONDS = 2
ROUND_ANALYSIS_WORKER_MAX_SLEEP_SECONDS = 60
ROUND_ANALYSIS_WORKER_KEY = 'default'

_ROUND_ANALYSIS_WORKER_LOCK = threading.Lock()
_ROUND_ANALYSIS_WORKER_WAKE_EVENT = threading.Event()
_ROUND_ANALYSIS_WORKER_THREAD = None


def _google_slide_url(presentation_id, slide_id=''):
    if presentation_id and slide_id:
        return f"https://docs.google.com/presentation/d/{presentation_id}/edit#slide=id.{slide_id}"
    if presentation_id:
        return f"https://docs.google.com/presentation/d/{presentation_id}/edit"
    return ''


def _classify_media_asset_kind(path_or_url, relationship_type=''):
    normalized_relationship_type = str(relationship_type or '').lower()
    suffix = Path(urlparse(str(path_or_url or '')).path).suffix.lower()
    guessed_type = mimetypes.guess_type(str(path_or_url or ''))[0] or ''

    if 'audio' in normalized_relationship_type or guessed_type.startswith('audio/'):
        return 'audio'
    if 'video' in normalized_relationship_type or guessed_type.startswith('video/'):
        return 'video'
    if guessed_type.startswith('image/'):
        return 'image'

    if suffix in {'.mp3', '.wav', '.m4a', '.aac', '.ogg', '.oga', '.flac', '.wma'}:
        return 'audio'
    if suffix in {'.mp4', '.mov', '.m4v', '.avi', '.wmv', '.webm', '.mkv'}:
        return 'video'
    if suffix in {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp', '.tif', '.tiff'}:
        return 'image'
    return 'media'


def queue_round_analysis(round_id, *, trigger_type=RoundQuestionAnalysisRun.TRIGGER_MANUAL, initiated_by=''):
    return queue_round_analysis_batch(
        [round_id],
        trigger_type=trigger_type,
        initiated_by=initiated_by,
    )


def queue_round_analysis_batch(
    round_ids,
    *,
    trigger_type=RoundQuestionAnalysisRun.TRIGGER_AUTO,
    initiated_by='',
    batch_label='',
    scheduled_for=None,
    delay_seconds=0,
):
    normalized_ids = []
    seen_ids = set()
    for round_id in round_ids or []:
        try:
            parsed_id = int(round_id)
        except (TypeError, ValueError):
            continue
        if parsed_id in seen_ids:
            continue
        seen_ids.add(parsed_id)
        normalized_ids.append(parsed_id)

    if not normalized_ids:
        return []

    scheduled_for_value = _resolve_round_analysis_scheduled_for(
        scheduled_for=scheduled_for,
        delay_seconds=delay_seconds,
    )
    queueable_rounds = {
        round_obj.id: round_obj
        for round_obj in GPTriviaRound.objects.filter(id__in=normalized_ids, replay=False)
    }
    active_round_ids = set(
        RoundQuestionAnalysisRun.objects.filter(
            round_id__in=queueable_rounds.keys(),
            status__in=[
                RoundQuestionAnalysisRun.STATUS_PENDING,
                RoundQuestionAnalysisRun.STATUS_RUNNING,
            ],
        ).values_list('round_id', flat=True)
    )

    normalized_batch_label = str(batch_label or '').strip()
    batch_key = uuid.uuid4().hex if normalized_batch_label else ''
    queued_run_ids = []
    for round_id in normalized_ids:
        if round_id not in queueable_rounds or round_id in active_round_ids:
            continue
        run = RoundQuestionAnalysisRun.objects.create(
            round_id=round_id,
            trigger_type=trigger_type,
            initiated_by=initiated_by or '',
            status=RoundQuestionAnalysisRun.STATUS_PENDING,
            scheduled_for=scheduled_for_value,
            batch_key=batch_key,
            batch_label=normalized_batch_label,
        )
        queued_run_ids.append(run.id)

    if not queued_run_ids:
        return []

    ensure_round_analysis_worker_running()
    return queued_run_ids


def schedule_auto_round_analysis_batch(round_ids, *, initiated_by='', batch_label=''):
    return queue_round_analysis_batch(
        round_ids,
        trigger_type=RoundQuestionAnalysisRun.TRIGGER_AUTO,
        initiated_by=initiated_by,
        batch_label=batch_label,
        delay_seconds=ROUND_ANALYSIS_AUTO_DELAY_SECONDS,
    )


def _resolve_round_analysis_scheduled_for(*, scheduled_for=None, delay_seconds=0):
    base_time = scheduled_for or timezone.now()
    if delay_seconds:
        return base_time + timezone.timedelta(seconds=max(int(delay_seconds), 0))
    return base_time


def ensure_round_analysis_worker_running():
    global _ROUND_ANALYSIS_WORKER_THREAD

    with _ROUND_ANALYSIS_WORKER_LOCK:
        worker_thread = _ROUND_ANALYSIS_WORKER_THREAD
        if worker_thread and worker_thread.is_alive():
            _ROUND_ANALYSIS_WORKER_WAKE_EVENT.set()
            return False

        _ROUND_ANALYSIS_WORKER_WAKE_EVENT.clear()
        _ROUND_ANALYSIS_WORKER_THREAD = threading.Thread(
            target=_round_analysis_worker_loop,
            daemon=True,
            name='round-analysis-worker',
        )
        _ROUND_ANALYSIS_WORKER_THREAD.start()
        return True


def _round_analysis_worker_loop():
    close_old_connections()
    try:
        while True:
            try:
                processed_any = _claim_and_process_next_round_analysis_run()
                if processed_any:
                    continue

                wait_seconds = _next_round_analysis_worker_wait_seconds()
                if wait_seconds is None:
                    return

                _ROUND_ANALYSIS_WORKER_WAKE_EVENT.wait(
                    timeout=max(1, min(wait_seconds, ROUND_ANALYSIS_WORKER_MAX_SLEEP_SECONDS))
                )
                _ROUND_ANALYSIS_WORKER_WAKE_EVENT.clear()
            except (OperationalError, ProgrammingError):
                logger.exception("Round analysis worker could not access its tables yet.")
                return
    finally:
        close_old_connections()
        global _ROUND_ANALYSIS_WORKER_THREAD
        with _ROUND_ANALYSIS_WORKER_LOCK:
            if _ROUND_ANALYSIS_WORKER_THREAD is threading.current_thread():
                _ROUND_ANALYSIS_WORKER_THREAD = None


def _claim_and_process_next_round_analysis_run():
    run_id = _claim_next_due_round_analysis_run_id()
    if run_id is None:
        return False

    try:
        _run_single_round_analysis(run_id, already_running=True)
    except Exception:
        logger.exception("Round analysis failed for run %s", run_id)
    finally:
        _notify_round_analysis_completion_if_ready(run_id)
    return True


def _claim_next_due_round_analysis_run_id():
    now = timezone.now()
    with transaction.atomic():
        worker_state, _ = RoundAnalysisWorkerState.objects.get_or_create(key=ROUND_ANALYSIS_WORKER_KEY)
        RoundAnalysisWorkerState.objects.select_for_update().get(pk=worker_state.pk)

        if RoundQuestionAnalysisRun.objects.filter(status=RoundQuestionAnalysisRun.STATUS_RUNNING).exists():
            return None

        candidate_run = (
            RoundQuestionAnalysisRun.objects.filter(
                status=RoundQuestionAnalysisRun.STATUS_PENDING,
                scheduled_for__lte=now,
            )
            .order_by('scheduled_for', 'id')
            .first()
        )
        if candidate_run is None:
            return None

        updated = RoundQuestionAnalysisRun.objects.filter(
            id=candidate_run.id,
            status=RoundQuestionAnalysisRun.STATUS_PENDING,
        ).update(
            status=RoundQuestionAnalysisRun.STATUS_RUNNING,
            started_at=now,
            completed_at=None,
            error_message='',
        )
        if not updated:
            return None
        return candidate_run.id


def _next_round_analysis_worker_wait_seconds():
    if RoundQuestionAnalysisRun.objects.filter(status=RoundQuestionAnalysisRun.STATUS_RUNNING).exists():
        return ROUND_ANALYSIS_WORKER_IDLE_WAIT_SECONDS

    next_pending_run = (
        RoundQuestionAnalysisRun.objects.filter(status=RoundQuestionAnalysisRun.STATUS_PENDING)
        .order_by('scheduled_for', 'id')
        .only('scheduled_for')
        .first()
    )
    if next_pending_run is None:
        return None

    remaining_seconds = (next_pending_run.scheduled_for - timezone.now()).total_seconds()
    if remaining_seconds <= 0:
        return ROUND_ANALYSIS_WORKER_IDLE_WAIT_SECONDS
    return remaining_seconds


def _run_single_round_analysis(run_id, *, already_running=False):
    run = RoundQuestionAnalysisRun.objects.select_related('round').get(id=run_id)
    if not already_running:
        run.status = RoundQuestionAnalysisRun.STATUS_RUNNING
        run.started_at = timezone.now()
        run.completed_at = None
        run.error_message = ''
        run.save(update_fields=['status', 'started_at', 'completed_at', 'error_message', 'updated_at'])

    try:
        slide_payload = _build_round_slide_payload(run.round)
        analysis_payload = _analyze_round_slides(run.round, slide_payload)
        _store_round_analysis(run, slide_payload, analysis_payload)
    except Exception as exc:
        run.status = RoundQuestionAnalysisRun.STATUS_FAILED
        run.completed_at = timezone.now()
        run.error_message = f"{exc}\n\n{traceback.format_exc(limit=10)}"
        run.save(update_fields=['status', 'completed_at', 'error_message', 'updated_at'])
        raise


def _notify_round_analysis_completion_if_ready(run_id):
    run = RoundQuestionAnalysisRun.objects.select_related('round').filter(id=run_id).first()
    if run is None or run.status not in {
        RoundQuestionAnalysisRun.STATUS_COMPLETED,
        RoundQuestionAnalysisRun.STATUS_FAILED,
    }:
        return

    if run.batch_key:
        grouped_runs = list(
            RoundQuestionAnalysisRun.objects.select_related('round')
            .filter(batch_key=run.batch_key)
            .order_by('id')
        )
        if any(
            grouped_run.status in {
                RoundQuestionAnalysisRun.STATUS_PENDING,
                RoundQuestionAnalysisRun.STATUS_RUNNING,
            }
            for grouped_run in grouped_runs
        ):
            return
        _notify_alex_round_analysis_finished(
            grouped_runs,
            batch_label=run.batch_label,
            success_count=sum(
                1 for grouped_run in grouped_runs
                if grouped_run.status == RoundQuestionAnalysisRun.STATUS_COMPLETED
            ),
            failed_count=sum(
                1 for grouped_run in grouped_runs
                if grouped_run.status == RoundQuestionAnalysisRun.STATUS_FAILED
            ),
        )
        return

    _notify_alex_round_analysis_finished(
        [run],
        batch_label=run.batch_label,
        success_count=1 if run.status == RoundQuestionAnalysisRun.STATUS_COMPLETED else 0,
        failed_count=1 if run.status == RoundQuestionAnalysisRun.STATUS_FAILED else 0,
    )


def _load_google_credentials():
    from .mail import build_credentials, token_file_path

    credentials = None
    if os.path.exists(token_file_path):
        with open(token_file_path, 'rb') as token_handle:
            credentials = pickle.load(token_handle)

    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())
        except Exception:
            credentials = None

    if not credentials or not credentials.valid:
        credentials = build_credentials()
        with open(token_file_path, 'wb') as token_handle:
            pickle.dump(credentials, token_handle)

    return credentials


def _build_script_service(credentials):
    http = httplib2.Http(timeout=60)
    authorized_http = AuthorizedHttp(credentials, http=http)
    return build('script', 'v1', http=authorized_http, cache_discovery=False)


def _run_apps_script_function(function_name, parameters):
    from .mail import APPS_SCRIPT_ID

    credentials = _load_google_credentials()
    script_service = _build_script_service(credentials)
    request = {
        'function': function_name,
        'parameters': parameters,
        'devMode': True,
    }
    response = script_service.scripts().run(scriptId=APPS_SCRIPT_ID, body=request).execute()
    if response.get('error'):
        raise RuntimeError(response['error'])
    return ((response.get('response') or {}).get('result')) or []


def _dimension_magnitude(dimension):
    try:
        return float((dimension or {}).get('magnitude') or 0)
    except (TypeError, ValueError):
        return 0.0


def _likely_audio_control_image(*, element_title='', element_description='', width=0.0, height=0.0, image=None):
    descriptor_text = f"{element_title} {element_description}".casefold()
    if any(keyword in descriptor_text for keyword in ['audio', 'music', 'song', 'listen', 'track', 'clip', 'sound']):
        return True

    image = image or {}
    source_url = str(image.get('sourceUrl') or '').strip().lower()
    if source_url and any(keyword in source_url for keyword in ['audio', 'music', 'song', 'listen', 'track']):
        return True

    max_dimension = max(width, height)
    min_dimension = min(width, height)
    return bool(max_dimension and max_dimension <= 72 and min_dimension <= 72)


def _looks_like_google_image_asset(url):
    normalized_url = str(url or '').strip().lower()
    if not normalized_url:
        return False
    return any(
        domain in normalized_url
        for domain in [
            'googleusercontent.com',
            'lh3.googleusercontent.com',
            'lh4.googleusercontent.com',
            'lh5.googleusercontent.com',
            'lh6.googleusercontent.com',
            'gstatic.com',
        ]
    )


def _collect_nested_urls(value, *, parent_key=''):
    discovered_urls = []
    if isinstance(value, dict):
        for key, nested_value in value.items():
            nested_parent_key = str(key or '')
            if isinstance(nested_value, str):
                normalized_candidate = nested_value.strip()
                if normalized_candidate.startswith(('http://', 'https://')):
                    discovered_urls.append((parent_key, nested_parent_key, normalized_candidate))
            else:
                discovered_urls.extend(
                    _collect_nested_urls(
                        nested_value,
                        parent_key=nested_parent_key,
                    )
                )
    elif isinstance(value, list):
        for nested_value in value:
            discovered_urls.extend(_collect_nested_urls(nested_value, parent_key=parent_key))
    return discovered_urls


def _extract_playable_media_url(element, *, placeholder_urls=None):
    placeholder_url_set = {
        str(url or '').strip()
        for url in (placeholder_urls or [])
        if str(url or '').strip()
    }
    direct_link_candidates = []
    fallback_candidates = []
    for container_key, url_key, candidate_url in _collect_nested_urls(element):
        normalized_container_key = str(container_key or '').casefold()
        normalized_url_key = str(url_key or '').casefold()
        if candidate_url in placeholder_url_set:
            continue
        if normalized_url_key in {'contenturl', 'sourceurl'}:
            continue

        is_linkish = normalized_container_key == 'link' or normalized_url_key in {
            'url',
            'uri',
            'href',
            'embedurl',
            'mediaurl',
            'resourceurl',
        }
        if is_linkish:
            direct_link_candidates.append(candidate_url)
        else:
            fallback_candidates.append(candidate_url)

    for candidate_list in [direct_link_candidates, fallback_candidates]:
        for candidate_url in candidate_list:
            if not _looks_like_google_image_asset(candidate_url):
                return candidate_url
        if candidate_list:
            return candidate_list[0]
    return ''


def _fetch_slide_media_links_via_apps_script(presentation_id, slide_id):
    if not presentation_id or not slide_id:
        return {}

    try:
        linked_media_rows = _run_apps_script_function(
            'getSlideLinkedMediaUrls',
            [presentation_id, slide_id],
        )
    except Exception:
        logger.exception(
            "Could not fetch linked slide media URLs via Apps Script for %s slide %s",
            presentation_id,
            slide_id,
        )
        return {}

    linked_media_map = {}
    for row in linked_media_rows or []:
        if not isinstance(row, dict):
            continue
        element_id = str(row.get('element_id') or '').strip()
        linked_url = str(row.get('linked_url') or '').strip()
        if not element_id or not linked_url:
            continue
        linked_media_map[element_id] = {
            'linked_url': linked_url,
            'linked_kind': _normalize_media_kind(row.get('linked_kind') or ''),
        }
    return linked_media_map


def _apply_apps_script_media_links(media_items, linked_media_map):
    enriched_items = []
    for media_item in media_items or []:
        enriched_item = dict(media_item)
        linked_media = linked_media_map.get(str(media_item.get('element_id') or '').strip(), {})
        linked_url = str(linked_media.get('linked_url') or '').strip()
        linked_kind = _normalize_media_kind(linked_media.get('linked_kind') or '')
        if linked_url and not _is_placeholder_media_url(linked_url, expected_kind=linked_kind or media_item.get('kind')):
            enriched_item['playable_url'] = linked_url
            if enriched_item.get('kind') in {'audio', 'video'} or enriched_item.get('likely_audio_control'):
                enriched_item['url'] = linked_url
            if linked_kind in {'audio', 'video'}:
                enriched_item['kind'] = linked_kind
        enriched_items.append(enriched_item)
    return enriched_items


def _is_placeholder_media_url(url, *, expected_kind=''):
    normalized_url = str(url or '').strip()
    if not normalized_url:
        return True

    classified_kind = _classify_media_asset_kind(normalized_url)
    normalized_expected_kind = str(expected_kind or '').strip().lower()
    if normalized_expected_kind in {'audio', 'video'} and classified_kind == 'image':
        return True

    return _looks_like_google_image_asset(normalized_url)


def _export_presentation_as_pptx_bytes(presentation_id, credentials=None):
    if not presentation_id:
        return b''

    credentials = credentials or _load_google_credentials()
    drive_service = build('drive', 'v3', credentials=credentials, cache_discovery=False)
    request = drive_service.files().export_media(
        fileId=presentation_id,
        mimeType=PPTX_EXPORT_MIME_TYPE,
    )
    buffer = BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buffer.getvalue()


def _extract_embedded_slide_media_assets(pptx_bytes, slide_number):
    if not pptx_bytes or not slide_number:
        return []

    relationship_path = f"ppt/slides/_rels/slide{slide_number}.xml.rels"
    assets = []
    with zipfile.ZipFile(BytesIO(pptx_bytes)) as archive:
        if relationship_path not in archive.namelist():
            return []

        relationship_xml = archive.read(relationship_path)
        root = ElementTree.fromstring(relationship_xml)
        namespace = {'rel': 'http://schemas.openxmlformats.org/package/2006/relationships'}
        for relationship in root.findall('rel:Relationship', namespace):
            target = str(relationship.attrib.get('Target') or '').strip()
            if not target:
                continue

            resolved_path = posixpath.normpath(posixpath.join('ppt/slides', target))
            if not resolved_path.startswith('ppt/media/'):
                continue
            if resolved_path not in archive.namelist():
                continue

            relationship_type = relationship.attrib.get('Type') or ''
            asset_kind = _classify_media_asset_kind(resolved_path, relationship_type)
            content_type = mimetypes.guess_type(resolved_path)[0] or 'application/octet-stream'
            assets.append(
                {
                    'kind': asset_kind,
                    'filename': Path(resolved_path).name,
                    'content_type': content_type,
                    'content': archive.read(resolved_path),
                }
            )

    kind_priority = {'audio': 0, 'video': 1, 'image': 2, 'media': 3}
    assets.sort(key=lambda asset: (kind_priority.get(asset['kind'], 9), asset['filename']))
    return assets


def _extract_presentation_id_for_analysis_round(round_obj, run=None):
    if run and getattr(run, 'source_presentation_id', ''):
        return run.source_presentation_id

    analysis_link = getattr(round_obj, 'source_link', '') or getattr(round_obj, 'link', '')
    if not analysis_link:
        return ''

    from .mail import _extract_presentation_link_parts

    presentation_id, _slide_id = _extract_presentation_link_parts(analysis_link)
    return presentation_id or ''


def get_round_analysis_playable_media_asset(entry):
    if not entry or not entry.source_slide_number:
        return None

    expected_kind = _normalize_media_kind(entry.media_kind)
    if expected_kind not in {'audio', 'video'}:
        return None

    presentation_id = _extract_presentation_id_for_analysis_round(entry.round, entry.run)
    if not presentation_id:
        return None

    pptx_bytes = _export_presentation_as_pptx_bytes(presentation_id)
    embedded_assets = _extract_embedded_slide_media_assets(pptx_bytes, entry.source_slide_number)
    if not embedded_assets:
        return None

    for preferred_kind in [expected_kind, 'audio', 'video']:
        for asset in embedded_assets:
            if asset.get('kind') == preferred_kind:
                return asset
    return embedded_assets[0]


def get_round_analysis_playable_media_url(entry):
    if not entry or not entry.source_slide_number:
        return ''

    expected_kind = _normalize_media_kind(entry.media_kind)
    if expected_kind not in {'audio', 'video'}:
        return ''

    try:
        slide_payload = _build_round_slide_payload(entry.round, include_thumbnails=False)
    except Exception:
        logger.exception(
            "Could not rebuild slide payload to locate linked media for analysis entry %s",
            getattr(entry, 'id', ''),
        )
        return ''

    source_slide = _find_slide_by_number(slide_payload, entry.source_slide_number)
    if not source_slide:
        return ''

    media_items = source_slide.get('media_items') or []
    for preferred_kind in [expected_kind, 'audio', 'video']:
        for media_item in media_items:
            if _normalize_media_kind(media_item.get('kind')) != preferred_kind:
                continue
            playable_url = str(media_item.get('playable_url') or media_item.get('url') or '').strip()
            if playable_url and not _is_placeholder_media_url(playable_url, expected_kind=preferred_kind):
                return playable_url
    return ''


def _extract_slide_media_items(slide):
    media_items = []
    def walk_page_elements(page_elements):
        for element in page_elements or []:
            element_id = element.get('objectId', '')
            transform = element.get('transform') or {}
            size = element.get('size') or {}
            position_x = float(transform.get('translateX') or 0)
            position_y = float(transform.get('translateY') or 0)
            width = _dimension_magnitude(size.get('width'))
            height = _dimension_magnitude(size.get('height'))
            element_title = str(element.get('title') or '').strip()
            element_description = str(element.get('description') or '').strip()

            image = element.get('image')
            if image:
                placeholder_url = image.get('sourceUrl') or image.get('contentUrl') or ''
                likely_audio_control = _likely_audio_control_image(
                    element_title=element_title,
                    element_description=element_description,
                    width=width,
                    height=height,
                    image=image,
                )
                playable_url = _extract_playable_media_url(
                    element,
                    placeholder_urls=[placeholder_url],
                )
                media_items.append(
                    {
                        'kind': 'audio' if likely_audio_control else 'image',
                        'element_id': element_id,
                        'url': playable_url if likely_audio_control else (placeholder_url or playable_url),
                        'download_url': '' if likely_audio_control else (image.get('contentUrl') or image.get('sourceUrl') or ''),
                        'placeholder_url': placeholder_url,
                        'playable_url': playable_url,
                        'description': element_description,
                        'title': element_title,
                        'position_x': position_x,
                        'position_y': position_y,
                        'width': width,
                        'height': height,
                        'likely_audio_control': likely_audio_control,
                    }
                )
                continue

            video = element.get('video')
            if video:
                playable_url = _extract_playable_media_url(element)
                media_items.append(
                    {
                        'kind': 'video',
                        'element_id': element_id,
                        'url': playable_url or video.get('url') or video.get('sourceUrl') or '',
                        'download_url': '',
                        'playable_url': playable_url or video.get('url') or video.get('sourceUrl') or '',
                        'description': element_description or video.get('id') or video.get('source') or '',
                        'title': element_title,
                        'position_x': position_x,
                        'position_y': position_y,
                        'width': width,
                        'height': height,
                        'likely_audio_control': False,
                    }
                )
                continue

            audio = element.get('audio')
            if audio:
                playable_url = _extract_playable_media_url(element)
                media_items.append(
                    {
                        'kind': 'audio',
                        'element_id': element_id,
                        'url': playable_url or audio.get('url') or audio.get('sourceUrl') or '',
                        'download_url': '',
                        'playable_url': playable_url or audio.get('url') or audio.get('sourceUrl') or '',
                        'description': element_description or audio.get('id') or '',
                        'title': element_title,
                        'position_x': position_x,
                        'position_y': position_y,
                        'width': width,
                        'height': height,
                        'likely_audio_control': False,
                    }
                )
                continue

            element_group = element.get('elementGroup') or {}
            if element_group:
                walk_page_elements(element_group.get('children', []))

    walk_page_elements(slide.get('pageElements', []))

    media_items.sort(
        key=lambda item: (
            round(item.get('position_y') or 0, -4),
            item.get('position_x') or 0,
            item.get('element_id') or '',
        )
    )
    for index, item in enumerate(media_items, start=1):
        item['media_index'] = index

    return media_items


def _extract_slide_line_items(slide):
    line_items = []

    def walk_page_elements(page_elements):
        for element in page_elements or []:
            element_id = element.get('objectId', '')
            transform = element.get('transform') or {}
            size = element.get('size') or {}
            position_x = float(transform.get('translateX') or 0)
            position_y = float(transform.get('translateY') or 0)
            width = _dimension_magnitude(size.get('width'))
            height = _dimension_magnitude(size.get('height'))
            line = element.get('line') or {}
            if line:
                start_x = position_x
                start_y = position_y
                end_x = position_x + width
                end_y = position_y + height
                line_items.append(
                    {
                        'element_id': element_id,
                        'line_category': str(line.get('lineCategory') or '').strip(),
                        'position_x': position_x,
                        'position_y': position_y,
                        'width': width,
                        'height': height,
                        'start_x': start_x,
                        'start_y': start_y,
                        'end_x': end_x,
                        'end_y': end_y,
                    }
                )

            element_group = element.get('elementGroup') or {}
            if element_group:
                walk_page_elements(element_group.get('children', []))

    walk_page_elements(slide.get('pageElements', []))

    line_items.sort(
        key=lambda item: (
            round(min(item.get('start_y') or 0, item.get('end_y') or 0), -4),
            min(item.get('start_x') or 0, item.get('end_x') or 0),
            item.get('element_id') or '',
        )
    )
    return line_items


def _fetch_slide_thumbnail_data_url(slides_service, credentials, presentation_id, slide_id):
    if not presentation_id or not slide_id:
        return ''

    thumbnail_response = slides_service.presentations().pages().getThumbnail(
        presentationId=presentation_id,
        pageObjectId=slide_id,
        thumbnailProperties_mimeType='PNG',
        thumbnailProperties_thumbnailSize=ROUND_ANALYSIS_THUMBNAIL_SIZE,
    ).execute()
    content_url = thumbnail_response.get('contentUrl')
    if not content_url:
        return ''

    request_headers = {}
    try:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        if credentials:
            credentials.apply(request_headers)
    except Exception:
        logger.exception("Could not refresh Google credentials for slide thumbnail fetch.")

    response = requests.get(content_url, headers=request_headers, timeout=30)
    response.raise_for_status()
    mime_type = (response.headers.get('Content-Type') or 'image/png').split(';')[0].strip() or 'image/png'
    encoded_bytes = base64.b64encode(response.content).decode('ascii')
    return f"data:{mime_type};base64,{encoded_bytes}"


def _build_round_slide_payload(round_obj, *, include_thumbnails=True):
    from .mail import (
        ROUND_SOURCE_MERGED_DECK,
        ROUND_SOURCE_UNKNOWN,
        _classify_round_source_link,
        _extract_speaker_notes_text,
        _extract_slide_text,
        _find_slide_index_for_round_title,
        _infer_historical_round_slide_range,
    )

    analysis_link = round_obj.source_link or round_obj.link
    source_meta = _classify_round_source_link(analysis_link)
    source_type = source_meta.get('source_type')
    presentation_id = source_meta.get('presentation_id')
    slide_id = source_meta.get('slide_id')

    if source_type == ROUND_SOURCE_UNKNOWN or not presentation_id:
        raise RuntimeError(f"Could not determine a presentation source for round {round_obj.id}.")

    credentials = _load_google_credentials()
    slides_service = build('slides', 'v1', credentials=credentials, cache_discovery=False)
    presentation = slides_service.presentations().get(presentationId=presentation_id).execute()
    slides = presentation.get('slides', [])
    if not slides:
        raise RuntimeError(f"No slides found in presentation {presentation_id}.")

    if source_type == ROUND_SOURCE_MERGED_DECK and slide_id:
        sibling_links = list(
            GPTriviaRound.objects.filter(
                date=round_obj.date,
                link__icontains=f'/presentation/d/{presentation_id}',
            ).values_list('link', flat=True)
        )
        next_round_title = (
            GPTriviaRound.objects.filter(date=round_obj.date, round_number__gt=round_obj.round_number)
            .order_by('round_number', 'id')
            .values_list('title', flat=True)
            .first()
        )
        try:
            start_index, end_index = _infer_historical_round_slide_range(
                slides,
                slide_id,
                sibling_links,
                next_round_title=next_round_title,
            )
        except Exception:
            start_index = _find_slide_index_for_round_title(slides, round_obj.title) or 0
            end_index = start_index
    else:
        start_index = 0
        end_index = len(slides) - 1

    selected_slides = slides[start_index:end_index + 1]
    slide_text_rows = []
    for offset, slide in enumerate(selected_slides, start=start_index + 1):
        slide_text = re.sub(r'\s+', ' ', _extract_slide_text(slide)).strip()
        text_items = _extract_slide_text_items(slide)
        media_items = _extract_slide_media_items(slide)
        line_items = _extract_slide_line_items(slide)
        slide_id = slide.get('objectId', '')
        if media_items and any(
            (media_item.get('kind') in {'audio', 'video'} or media_item.get('likely_audio_control'))
            and not media_item.get('playable_url')
            for media_item in media_items
        ):
            media_items = _apply_apps_script_media_links(
                media_items,
                _fetch_slide_media_links_via_apps_script(presentation_id, slide_id),
            )
        if not slide_text and not media_items and not line_items:
            continue
        slide_text_rows.append(
            {
                'slide_number': offset,
                'slide_id': slide_id,
                'slide_url': _google_slide_url(presentation_id, slide_id),
                'text': slide_text,
                'text_items': text_items,
                'line_items': line_items,
                'speaker_notes': re.sub(r'\s+', ' ', _extract_speaker_notes_text(slide)).strip(),
                'media_items': media_items,
                'thumbnail_data_url': (
                    _fetch_slide_thumbnail_data_url(
                        slides_service,
                        credentials,
                        presentation_id,
                        slide_id,
                    )
                    if include_thumbnails else ''
                ),
            }
        )

    if not slide_text_rows:
        raise RuntimeError(f"No extractable slide text found for round {round_obj.id}.")

    return {
        'presentation_id': presentation_id,
        'slide_range_label': f"{start_index + 1}-{end_index + 1}",
        'analysis_link': analysis_link,
        'slides': slide_text_rows,
    }


def _collect_category_options():
    round_queryset = GPTriviaRound.objects.all()
    major_categories = sorted({
        category
        for category in round_queryset.order_by().values_list('major_category', flat=True)
        if category
    })
    minor_categories = sorted({
        category
        for category in chain(
            round_queryset.order_by().values_list('minor_category1', flat=True),
            round_queryset.order_by().values_list('minor_category2', flat=True),
            major_categories,
        )
        if category
    })
    return major_categories, minor_categories


def _empty_player_correctness_map():
    player_fields = get_all_player_fields(
        GPTriviaRound.objects.all().only('creator', 'extra_scores'),
        MergedPresentation.objects.only('player_list', 'creator_list'),
    )
    return {
        display_name_for_player_field(field): ''
        for field in player_fields
        if display_name_for_player_field(field)
    }


def _analyze_round_slides(round_obj, slide_payload):
    classification = _classify_round_structure(round_obj, slide_payload)
    if classification.get('strategy') == 'picture_grid_layout':
        deterministic_payload = _extract_picture_grid_questions_by_layout(round_obj, slide_payload, classification)
        if deterministic_payload:
            return deterministic_payload

    return _analyze_round_slides_with_gpt(round_obj, slide_payload, classification=classification)


def _analyze_round_slides_with_gpt(round_obj, slide_payload, *, classification=None):
    from .views import _create_openai_text_response, _get_openai_client

    major_categories, minor_categories = _collect_category_options()
    serialized_slides = [
        {
            key: value
            for key, value in slide_data.items()
            if key != 'thumbnail_data_url'
        }
        for slide_data in slide_payload['slides']
    ]
    input_payload = {
        'round_title': round_obj.title,
        'round_creator': round_obj.creator,
        'presentation_id': slide_payload['presentation_id'],
        'slide_range': slide_payload['slide_range_label'],
        'classification': classification or {},
        'slides': serialized_slides,
        'allowed_major_categories': major_categories,
        'allowed_minor_categories': minor_categories,
    }
    instructions = (
        "You analyze a trivia round from a Google Slides deck. "
        "A first-pass classifier has already identified the round structure. "
        "Use that classification as the default unless the slide evidence clearly contradicts it, and then extract the question/answer pairs from the slide text and any media metadata. "
        "Return strict JSON only with this schema: "
        "{\"round_type\": string, \"notes\": string, \"questions\": ["
        "{\"question_number\": integer, \"source_slide_number\": integer, "
        "\"question_text\": string, \"instruction_text\": string, \"answer_text\": string, "
        "\"media_kind\": string, \"media_index\": integer, "
        "\"major_category\": string, \"minor_category1\": string, \"minor_category2\": string}"
        "]}. "
        "Use short round types like picture, matching, multiple choice, short answer, music, video, audio, puzzle, or mixed. "
        "Pair question slides with answer slides when possible. Preserve wording from the slides instead of paraphrasing heavily. "
        "Rendered slide thumbnails are also provided and should be treated as the full slide view with all visible page elements available for inspection. "
        "Text items in the payload come directly from slide page elements, including text that may only appear after clicks or animations, so do not ignore answers just because they are not visible in the initial static thumbnail. "
        "Use thumbnails only for layout and media context, not as the sole source of visible text. "
        "If the round is multimedia, use the round title, answer text, nearby slide text, and media metadata to infer what the player is supposed to identify or do. "
        "For example, infer prompts like identify the person, identify the place, name the song and artist, identify the movie, or explain the matching rule. "
        "Some Google Slides audio clips appear in pageElements as tiny clickable image placeholders rather than true audio objects. "
        "If media metadata marks an item as likely_audio_control or the rendered slide clearly indicates music/audio, do not classify the round as a picture round just because an image placeholder exists. "
        "For matching rounds, if the slide clearly shows one overall question number for the entire board, keep it as a single question object instead of splitting it into one object per row. "
        "If the slide does not show one overall board-level question number and the left-side clues are numbered row-by-row, return one question object per left-side clue or numbered row. "
        "For split matching entries, question_text should be that single left-side clue, and answer_text should be the matched right-side option text when visible. "
        "For single-board matching entries, answer_text may be the explicit ordered mapping or ordered option sequence, such as 1-C, 2-A, 3-B or CAB, if that is the clearest recoverable answer form. "
        "If only the matched option position is recoverable, answer_text may use the option letter/number. "
        "If the question slide contains line_items that visibly connect the left side to the right side, use those drawn line connections as the primary matching signal. "
        "Only ignore those line connections if the answer slide clearly reorders the right-side options or explicitly shows a different pairing structure that overrides the question-slide layout. "
        "For multiple choice rounds, answer_text should be the correct option text when visible, not only the stem. "
        "If a single slide contains multiple separate question images or other media items, return one question per item. "
        "Use media_index to point to the matching media item on that slide. media_index is 1-based and follows the media_items order already provided in the slide payload, "
        "which is sorted top-to-bottom and then left-to-right. "
        "instruction_text should be the short task description for the player. "
        "question_text should be the full displayed prompt if visible, otherwise a concise inferred prompt. "
        "source_slide_number should usually point to the main question slide, not the answer reveal slide. "
        "media_kind should be image, video, audio, text, or blank. "
        "If a category does not fit, leave that category blank. "
        "major_category must be chosen from the allowed major categories when possible. "
        "minor categories should be chosen from the allowed minor categories when possible. "
        "Do not repeat the major category in either minor category slot. "
        "If no useful minor category fits, leave the minor category blank. "
        "Do not duplicate the same minor category twice. "
        "Do not invent missing answers; leave answer_text blank if it is not recoverable."
    )
    client = _get_openai_client()
    response_text = _create_openai_text_response(
        client,
        instructions=instructions,
        input_items=[
            {
                'role': 'user',
                'content': (
                    [
                        {
                            'type': 'input_text',
                            'text': json.dumps(input_payload, ensure_ascii=True),
                        }
                    ]
                    + [
                        {
                            'type': 'input_image',
                            'image_url': slide_data['thumbnail_data_url'],
                        }
                        for slide_data in slide_payload['slides']
                        if slide_data.get('thumbnail_data_url')
                    ]
                ),
            }
        ],
        max_output_tokens=4000,
        reasoning_effort="medium",
    )
    return _parse_analysis_response_json(response_text)


def _parse_analysis_response_json(response_text):
    parsed_payload = _parse_openai_json_response(response_text)
    if not isinstance(parsed_payload, dict):
        raise RuntimeError(f"GPT did not return valid JSON: {response_text}")
    return parsed_payload


def _normalize_media_kind(value):
    media_kind = str(value or '').strip().lower()
    if media_kind in {'picture', 'photo'}:
        return 'image'
    if media_kind in {'music'}:
        return 'audio'
    if media_kind in {'video clip'}:
        return 'video'
    if media_kind in {'text', 'image', 'video', 'audio'}:
        return media_kind
    return media_kind


def _normalize_analysis_categories(entry):
    major_category = str(entry.get('major_category') or '').strip()
    minor_category1 = str(entry.get('minor_category1') or '').strip()
    minor_category2 = str(entry.get('minor_category2') or '').strip()

    used_normalized = {
        major_category.casefold()
        for major_category in [major_category]
        if major_category
    }
    cleaned_minors = []
    for minor_value in [minor_category1, minor_category2]:
        normalized_minor = minor_value.casefold()
        if not minor_value or normalized_minor in used_normalized:
            cleaned_minors.append('')
            continue
        used_normalized.add(normalized_minor)
        cleaned_minors.append(minor_value)

    return major_category, cleaned_minors[0], cleaned_minors[1]


def _normalize_possible_answer_variant(value):
    normalized = str(value or '').strip()
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized.strip(" \t\r\n.;:!?\"'")


_PERSON_NAME_PARTICLES = {
    'da', 'de', 'del', 'della', 'der', 'di', 'du', 'la', 'le', 'st', 'st.', 'van', 'von',
}

_GIVEN_NAME_VARIANTS = {
    'alex': ('alex', 'alexander'),
    'alexander': ('alexander', 'alex'),
    'abraham': ('abraham', 'abe'),
    'andy': ('andy', 'andrew'),
    'ben': ('ben', 'benjamin'),
    'benjamin': ('benjamin', 'ben'),
    'bill': ('bill', 'william'),
    'bob': ('bob', 'robert'),
    'charlie': ('charlie', 'charles'),
    'chris': ('chris', 'christopher'),
    'dan': ('dan', 'daniel'),
    'dave': ('dave', 'david'),
    'ed': ('ed', 'edward'),
    'frank': ('frank', 'francis'),
    'george': ('george',),
    'jim': ('jim', 'james'),
    'james': ('james', 'jim'),
    'joe': ('joe', 'joseph'),
    'john': ('john', 'jack'),
    'liz': ('liz', 'elizabeth'),
    'matt': ('matt', 'matthew'),
    'mike': ('mike', 'michael'),
    'rob': ('rob', 'robert'),
    'sam': ('sam', 'samuel'),
    'thomas': ('thomas', 'tom'),
    'tom': ('tom', 'thomas'),
    'will': ('will', 'william'),
    'william': ('william', 'bill', 'will'),
}


def _question_suggests_person_answer(question_text):
    normalized_question = str(question_text or '').casefold()
    if not normalized_question:
        return False
    return any(
        keyword in normalized_question
        for keyword in [
            'who',
            'person',
            'president',
            'founding father',
            'founder',
            'scientist',
            'inventor',
            'author',
            'poet',
            'philosopher',
            'actor',
            'actress',
            'artist',
            'celebrity',
            'politician',
            'leader',
            'composer',
            'singer',
            'musician',
            'historian',
            'general',
            'king',
            'queen',
            'prime minister',
        ]
    )


def _looks_like_person_name_phrase(phrase):
    cleaned_phrase = _normalize_possible_answer_variant(phrase)
    if not cleaned_phrase:
        return False
    if any(character.isdigit() for character in cleaned_phrase):
        return False
    if any(marker in cleaned_phrase for marker in [':', '/', '&', '(', ')']):
        return False

    tokens = cleaned_phrase.split()
    if len(tokens) < 2 or len(tokens) > 5:
        return False

    name_token_pattern = re.compile(r"^[A-Za-z][A-Za-z'.-]*$")
    initial_token_pattern = re.compile(r"^[A-Za-z]\.?$")
    if not name_token_pattern.match(tokens[0]) or not name_token_pattern.match(tokens[-1]):
        return False

    for token in tokens[1:-1]:
        normalized_token = token.casefold()
        if normalized_token in _PERSON_NAME_PARTICLES:
            continue
        if name_token_pattern.match(token) or initial_token_pattern.match(token):
            continue
        return False
    return True


def _given_name_aliases(first_name):
    cleaned_first_name = _normalize_possible_answer_variant(first_name)
    if not cleaned_first_name:
        return []
    normalized_first_name = cleaned_first_name.casefold()
    raw_aliases = _GIVEN_NAME_VARIANTS.get(normalized_first_name, (normalized_first_name,))
    aliases = []
    seen_aliases = set()
    for alias in raw_aliases:
        normalized_alias = _normalize_possible_answer_variant(alias)
        if not normalized_alias:
            continue
        alias_key = normalized_alias.casefold()
        if alias_key in seen_aliases:
            continue
        seen_aliases.add(alias_key)
        aliases.append(normalized_alias.title())
    return aliases


def _expand_person_name_alias_bases(phrase, question_text=''):
    cleaned_phrase = _normalize_possible_answer_variant(phrase)
    if not _looks_like_person_name_phrase(cleaned_phrase):
        return []

    tokens = cleaned_phrase.split()
    if len(tokens) < 2:
        return []

    first_name = tokens[0]
    middle_tokens = tokens[1:-1]
    last_name = tokens[-1]
    if (
        not _question_suggests_person_answer(question_text)
        and first_name.casefold() not in _GIVEN_NAME_VARIANTS
        and not re.match(r"^[A-Za-z]\.?$", first_name)
    ):
        return []

    alias_candidates = [cleaned_phrase, last_name]
    for given_name_alias in _given_name_aliases(first_name):
        if middle_tokens:
            alias_candidates.append(' '.join([given_name_alias] + middle_tokens + [last_name]))
        alias_candidates.append(f"{given_name_alias} {last_name}")

    deduped_alias_candidates = []
    seen_alias_candidates = set()
    for candidate in alias_candidates:
        normalized_candidate = _normalize_possible_answer_variant(candidate)
        candidate_key = normalized_candidate.casefold()
        if not normalized_candidate or candidate_key in seen_alias_candidates:
            continue
        seen_alias_candidates.add(candidate_key)
        deduped_alias_candidates.append(normalized_candidate)
    return deduped_alias_candidates


def _possible_answer_case_forms(value):
    cleaned_value = _normalize_possible_answer_variant(value)
    if not cleaned_value:
        return []

    variants = [cleaned_value]
    lowered_value = cleaned_value.casefold()
    if lowered_value != cleaned_value:
        variants.append(lowered_value)
    sentence_value = lowered_value[:1].upper() + lowered_value[1:] if lowered_value else ''
    if sentence_value and sentence_value not in variants:
        variants.append(sentence_value)
    title_value = ' '.join(word[:1].upper() + word[1:] for word in lowered_value.split(' '))
    if title_value and title_value not in variants:
        variants.append(title_value)
    return variants


def _split_possible_answer_segments(answer_text):
    cleaned_answer = _normalize_possible_answer_variant(answer_text)
    if not cleaned_answer:
        return []

    segments = [cleaned_answer]
    colon_segments = [_normalize_possible_answer_variant(segment) for segment in re.split(r'\s*:\s*', cleaned_answer)]
    if len([segment for segment in colon_segments if segment]) > 1:
        segments.extend(segment for segment in colon_segments if segment)

    slash_segments = [_normalize_possible_answer_variant(segment) for segment in re.split(r'\s*/\s*', cleaned_answer)]
    if len([segment for segment in slash_segments if segment]) > 1:
        segments.extend(segment for segment in slash_segments if segment)
        segments.append(_normalize_possible_answer_variant(' or '.join(segment for segment in slash_segments if segment)))

    normalized_or_answer = re.sub(r'\s+\bor\b\s+', ' or ', cleaned_answer, flags=re.IGNORECASE)
    or_segments = [_normalize_possible_answer_variant(segment) for segment in re.split(r'\s+\bor\b\s+', normalized_or_answer, flags=re.IGNORECASE)]
    if len([segment for segment in or_segments if segment]) > 1:
        segments.extend(segment for segment in or_segments if segment)
        segments.append(_normalize_possible_answer_variant(' or '.join(segment for segment in or_segments if segment)))

    deduped_segments = []
    seen_segments = set()
    for segment in segments:
        normalized_segment = _normalize_possible_answer_variant(segment)
        normalized_key = normalized_segment.casefold()
        if not normalized_segment or normalized_key in seen_segments:
            continue
        seen_segments.add(normalized_key)
        deduped_segments.append(normalized_segment)
    return deduped_segments


def _possible_answer_initialisms(value):
    normalized_value = _normalize_possible_answer_variant(value)
    if not normalized_value:
        return []

    token_groups = [normalized_value.split()]
    punctuation_stripped_tokens = [
        token for token in re.sub(r"[^0-9A-Za-z\s-]", '', normalized_value).replace('-', ' ').split()
        if token
    ]
    if punctuation_stripped_tokens:
        token_groups.append(punctuation_stripped_tokens)

    initialisms = []
    seen_initialisms = set()
    for token_group in token_groups:
        significant_tokens = [
            token for token in token_group
            if token and token.casefold() not in {'a', 'an', 'the', 'of', 'and'}
        ]
        if len(significant_tokens) < 2:
            continue
        initialism = ''.join(token[0] for token in significant_tokens if token)
        if len(initialism) < 2 or len(initialism) > 5:
            continue
        normalized_initialism = _normalize_possible_answer_variant(initialism)
        initialism_key = normalized_initialism.casefold()
        if not normalized_initialism or initialism_key in seen_initialisms:
            continue
        seen_initialisms.add(initialism_key)
        initialisms.append(normalized_initialism.upper())
    return initialisms


_POSITION_ORDINAL_WORDS = {
    1: 'first',
    2: 'second',
    3: 'third',
    4: 'fourth',
    5: 'fifth',
    6: 'sixth',
    7: 'seventh',
    8: 'eighth',
    9: 'ninth',
    10: 'tenth',
}

_POSITION_WORD_TO_INDEX = {
    'first': 1,
    'second': 2,
    'third': 3,
    'fourth': 4,
    'fifth': 5,
    'sixth': 6,
    'seventh': 7,
    'eighth': 8,
    'ninth': 9,
    'tenth': 10,
}


def _split_analysis_text_lines(value):
    return [
        _normalize_possible_answer_variant(line)
        for line in re.split(r'[\r\n]+', str(value or ''))
        if _normalize_possible_answer_variant(line)
    ]


def _extract_alpha_prefix(value):
    match = re.match(r'^\s*([A-Za-z])[\)\].:\-]*\s*(.+?)\s*$', str(value or ''))
    if not match:
        return None, _normalize_text_content(value)
    return match.group(1).upper(), _normalize_text_content(match.group(2))


def _extract_numbered_analysis_items(value):
    items = []
    for line in _split_analysis_text_lines(value):
        label_number, cleaned_text = _extract_numeric_prefix(line)
        if label_number is None or not cleaned_text:
            continue
        items.append({
            'label': label_number,
            'text': cleaned_text,
        })
    return items


def _extract_lettered_analysis_items(value):
    items = []
    for line in _split_analysis_text_lines(value):
        label_letter, cleaned_text = _extract_alpha_prefix(line)
        if not label_letter or not cleaned_text:
            continue
        items.append({
            'label': label_letter,
            'index': ord(label_letter) - 64,
            'text': cleaned_text,
        })
    return items


def _position_index_to_letter(index):
    try:
        parsed_index = int(index)
    except (TypeError, ValueError):
        return ''
    if parsed_index <= 0 or parsed_index > 26:
        return ''
    return chr(64 + parsed_index)


def _position_token_to_index(token, total_count=0):
    normalized_token = _normalize_possible_answer_variant(token).casefold()
    if not normalized_token:
        return None
    if re.fullmatch(r'\d+', normalized_token):
        parsed_index = int(normalized_token)
        return parsed_index if parsed_index > 0 else None
    if re.fullmatch(r'[a-z]', normalized_token):
        return ord(normalized_token.upper()) - 64
    if normalized_token in _POSITION_WORD_TO_INDEX:
        return _POSITION_WORD_TO_INDEX[normalized_token]
    if normalized_token == 'last' and total_count > 0:
        return total_count
    if normalized_token == 'middle' and total_count > 0:
        return (total_count + 1) // 2
    return None


def _position_aliases(index, total_count=0):
    try:
        parsed_index = int(index)
    except (TypeError, ValueError):
        return []
    if parsed_index <= 0:
        return []

    aliases = [str(parsed_index)]
    letter = _position_index_to_letter(parsed_index)
    if letter:
        aliases.extend([letter, letter.casefold()])
    ordinal = _POSITION_ORDINAL_WORDS.get(parsed_index)
    if ordinal:
        aliases.append(ordinal)
    if total_count > 0 and parsed_index == total_count:
        aliases.append('last')
    if total_count > 0 and parsed_index == ((total_count + 1) // 2):
        aliases.append('middle')

    deduped_aliases = []
    seen_aliases = set()
    for alias in aliases:
        normalized_alias = _normalize_possible_answer_variant(alias)
        alias_key = normalized_alias.casefold()
        if not normalized_alias or alias_key in seen_aliases:
            continue
        seen_aliases.add(alias_key)
        deduped_aliases.append(normalized_alias)
    return deduped_aliases


def _normalize_choice_comparison_value(value):
    normalized_value = _normalize_possible_answer_variant(value).casefold()
    normalized_value = re.sub(r'^(?:a|an|the)\s+', '', normalized_value)
    normalized_value = re.sub(r"[^0-9a-z\s]", '', normalized_value)
    normalized_value = re.sub(r'\s+', ' ', normalized_value).strip()
    return normalized_value


def _choice_text_matches_answer(choice_text, answer_text):
    normalized_choice = _normalize_choice_comparison_value(choice_text)
    normalized_answer = _normalize_choice_comparison_value(answer_text)
    if not normalized_choice or not normalized_answer:
        return False
    return normalized_choice == normalized_answer


def _extract_matching_answer_map(answer_text, *, option_count=0):
    mapping = {}
    normalized_answer_text = str(answer_text or '')
    mapping_pattern = re.compile(
        r'(\d+)\s*(?:matches?(?:\s+to)?|->|=>|=|[-:])?\s*'
        r'([A-Za-z]|\d+|first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|middle|last)\b',
        flags=re.IGNORECASE,
    )
    for match in mapping_pattern.finditer(normalized_answer_text):
        left_index = int(match.group(1))
        right_index = _position_token_to_index(match.group(2), total_count=option_count)
        if left_index > 0 and right_index and right_index > 0:
            mapping[left_index] = right_index

    if mapping:
        return mapping

    sequential_lines = _split_analysis_text_lines(answer_text)
    for line_index, line_text in enumerate(sequential_lines, start=1):
        right_index = _position_token_to_index(line_text, total_count=option_count)
        if right_index and right_index > 0:
            mapping[line_index] = right_index
    return mapping


def _extract_matching_left_items(question_text):
    left_items = []
    for line in _split_analysis_text_lines(question_text):
        numeric_match = re.match(r'^\s*(\d+)[\)\].:\-]+\s*(.+?)\s*$', line)
        if not numeric_match:
            continue
        left_items.append(
            {
                'label': int(numeric_match.group(1)),
                'text': _normalize_text_content(numeric_match.group(2)),
            }
        )

    if len(left_items) >= 2 and _question_suggests_matching_prompt(left_items[0].get('text') or ''):
        return left_items[1:]
    return left_items


def _extract_matching_standalone_question_number(question_text):
    for line in _split_analysis_text_lines(question_text):
        question_match = re.match(r'^\s*(?:question\s*)?(\d+)[\)\].:\-]*\s*$', line, flags=re.IGNORECASE)
        if question_match:
            return int(question_match.group(1))
    return None


def _build_matching_sequence_aliases(answer_map, left_items):
    ordered_indices = []
    for left_item in left_items or []:
        left_label = int(left_item.get('label') or 0)
        matched_index = answer_map.get(left_label)
        if not matched_index:
            return []
        ordered_indices.append(int(matched_index))

    if len(ordered_indices) < 2:
        return []

    aliases = []
    letter_tokens = []
    for index in ordered_indices:
        letter = _position_index_to_letter(index)
        if not letter:
            letter_tokens = []
            break
        letter_tokens.append(letter)
    if letter_tokens:
        aliases.extend(
            [
                ''.join(letter_tokens),
                ' '.join(letter_tokens),
                '-'.join(letter_tokens),
                ','.join(letter_tokens),
            ]
        )

    number_tokens = [str(index) for index in ordered_indices]
    if all(len(token) == 1 for token in number_tokens):
        aliases.append(''.join(number_tokens))
    aliases.extend(
        [
            ' '.join(number_tokens),
            '-'.join(number_tokens),
            ','.join(number_tokens),
        ]
    )

    deduped_aliases = []
    seen_aliases = set()
    for alias in aliases:
        normalized_alias = _normalize_possible_answer_variant(alias)
        alias_key = normalized_alias.casefold()
        if not normalized_alias or alias_key in seen_aliases:
            continue
        seen_aliases.add(alias_key)
        deduped_aliases.append(normalized_alias)
    return deduped_aliases


def _expand_matching_question_entry(entry):
    combined_question_text = '\n'.join(
        text
        for text in [
            str(entry.get('question_text') or '').strip(),
            str(entry.get('instruction_text') or '').strip(),
        ]
        if text
    )
    left_items = _extract_matching_left_items(combined_question_text)
    right_items = _extract_lettered_analysis_items(combined_question_text)
    answer_map = _extract_matching_answer_map(
        entry.get('answer_text'),
        option_count=len(right_items),
    )

    if _extract_matching_standalone_question_number(combined_question_text) is not None:
        return []

    if len(left_items) < 2 or not answer_map:
        return []

    right_items_by_index = {
        item['index']: item
        for item in right_items
        if item.get('index')
    }
    inferred_option_count = max(
        len(right_items_by_index),
        max(answer_map.values(), default=0),
    )

    expanded_entries = []
    for left_item in left_items:
        left_label = int(left_item.get('label') or 0)
        matched_index = answer_map.get(left_label)
        if not matched_index:
            continue
        matched_option = right_items_by_index.get(matched_index)
        answer_text = str((matched_option or {}).get('text') or '').strip() or _position_index_to_letter(matched_index) or str(matched_index)
        expanded_entries.append(
            {
                **entry,
                'question_text': str(left_item.get('text') or '').strip() or f"Match {left_label}",
                'answer_text': answer_text,
                'additional_possible_answers': _position_aliases(matched_index, total_count=inferred_option_count),
            }
        )

    return expanded_entries


def _derive_matching_position_aliases(entry):
    combined_question_text = '\n'.join(
        text
        for text in [
            str(entry.get('question_text') or '').strip(),
            str(entry.get('instruction_text') or '').strip(),
        ]
        if text
    )
    option_items = []
    for line in _split_analysis_text_lines(combined_question_text):
        alpha_match = re.match(r'^\s*([A-Za-z])[\)\].:\-]+\s*(.+?)\s*$', line)
        if not alpha_match:
            continue
        option_items.append(
            {
                'index': ord(alpha_match.group(1).upper()) - 64,
                'text': _normalize_text_content(alpha_match.group(2)),
            }
        )
    if not option_items:
        for line in _split_analysis_text_lines(combined_question_text):
            numeric_match = re.match(r'^\s*(\d+)[\)\].:\-]+\s*(.+?)\s*$', line)
            if not numeric_match:
                continue
            option_items.append(
                {
                    'index': int(numeric_match.group(1)),
                    'text': _normalize_text_content(numeric_match.group(2)),
                }
            )

    if len(option_items) < 2:
        return []

    answer_text = str(entry.get('answer_text') or '').strip()
    if not answer_text:
        return []

    total_count = len(option_items)
    matched_index = _position_token_to_index(answer_text, total_count=total_count)

    strict_alpha_match = re.match(r'^\s*([A-Za-z])[\)\].:\-]+\s*(.+?)\s*$', answer_text)
    cleaned_alpha_answer = _normalize_text_content(strict_alpha_match.group(2)) if strict_alpha_match else ''
    if not matched_index and strict_alpha_match:
        matched_index = ord(strict_alpha_match.group(1).upper()) - 64

    strict_numeric_match = re.match(r'^\s*(\d+)[\)\].:\-]+\s*(.+?)\s*$', answer_text)
    cleaned_numeric_answer = _normalize_text_content(strict_numeric_match.group(2)) if strict_numeric_match else ''
    if not matched_index and strict_numeric_match:
        matched_index = int(strict_numeric_match.group(1))

    answer_candidates = [answer_text]
    if cleaned_alpha_answer and cleaned_alpha_answer.casefold() != answer_text.casefold():
        answer_candidates.append(cleaned_alpha_answer)
    if cleaned_numeric_answer and cleaned_numeric_answer.casefold() != answer_text.casefold():
        answer_candidates.append(cleaned_numeric_answer)
    answer_candidates.extend(
        _extract_matching_right_side_alias_bases(
            answer_text,
            question_text=str(entry.get('question_text') or '').strip() or combined_question_text,
        )
    )

    if not matched_index:
        for option_item in option_items:
            option_text = str(option_item.get('text') or '').strip()
            if any(_choice_text_matches_answer(option_text, candidate) for candidate in answer_candidates):
                matched_index = int(option_item.get('index') or 0)
                break

    if not matched_index:
        return []
    return _position_aliases(matched_index, total_count=total_count)


def _derive_matching_board_sequence_aliases(entry):
    combined_question_text = '\n'.join(
        text
        for text in [
            str(entry.get('question_text') or '').strip(),
            str(entry.get('instruction_text') or '').strip(),
        ]
        if text
    )
    if _extract_matching_standalone_question_number(combined_question_text) is None:
        return []

    left_items = _extract_matching_left_items(combined_question_text)
    if len(left_items) < 2:
        return []

    right_items = _extract_lettered_analysis_items(combined_question_text)
    answer_map = _extract_matching_answer_map(
        entry.get('answer_text'),
        option_count=len(right_items),
    )
    if not answer_map:
        return []

    return _build_matching_sequence_aliases(answer_map, left_items)


def _derive_multiple_choice_position_aliases(entry):
    combined_question_text = '\n'.join(
        text
        for text in [
            str(entry.get('question_text') or '').strip(),
            str(entry.get('instruction_text') or '').strip(),
        ]
        if text
    )
    option_items = _extract_lettered_analysis_items(combined_question_text)
    if not option_items:
        option_items = [
            {
                'index': item['label'],
                'text': item['text'],
            }
            for item in _extract_numbered_analysis_items(combined_question_text)
        ]

    if len(option_items) < 2:
        return []

    answer_text = str(entry.get('answer_text') or '').strip()
    matched_index = _position_token_to_index(answer_text, total_count=len(option_items))
    if not matched_index:
        for option_item in option_items:
            if _choice_text_matches_answer(option_item.get('text'), answer_text):
                matched_index = int(option_item.get('index') or 0)
                break
    if not matched_index:
        return []
    return _position_aliases(matched_index, total_count=len(option_items))


def _normalize_analysis_questions(analysis_payload):
    normalized_round_type = str(analysis_payload.get('round_type') or '').strip().lower()
    original_questions = list(analysis_payload.get('questions') or [])
    normalized_questions = []

    for index, question_entry in enumerate(original_questions, start=1):
        normalized_entry = dict(question_entry or {})
        if normalized_round_type == 'matching':
            expanded_entries = _expand_matching_question_entry(normalized_entry)
            if expanded_entries:
                normalized_questions.extend(expanded_entries)
                continue
            additional_aliases = [
                *_derive_matching_position_aliases(normalized_entry),
                *_derive_matching_board_sequence_aliases(normalized_entry),
            ]
            if additional_aliases:
                existing_aliases = list(normalized_entry.get('additional_possible_answers') or [])
                normalized_entry['additional_possible_answers'] = [
                    alias
                    for alias in [*existing_aliases, *additional_aliases]
                    if alias
                ]
        if normalized_round_type == 'multiple choice':
            additional_aliases = _derive_multiple_choice_position_aliases(normalized_entry)
            if additional_aliases:
                existing_aliases = list(normalized_entry.get('additional_possible_answers') or [])
                normalized_entry['additional_possible_answers'] = [
                    alias
                    for alias in [*existing_aliases, *additional_aliases]
                    if alias
                ]
        normalized_questions.append(normalized_entry)

    for question_number, question_entry in enumerate(normalized_questions, start=1):
        question_entry['question_number'] = question_number

    return {
        **analysis_payload,
        'questions': normalized_questions,
    }


def _question_suggests_matching_prompt(question_text):
    normalized_question = str(question_text or '').casefold()
    if not normalized_question:
        return False
    return any(
        keyword in normalized_question
        for keyword in ['match', 'matching', 'pair', 'pairs', 'paired', 'connect']
    )


def _extract_matching_right_side_alias_bases(phrase, question_text=''):
    cleaned_phrase = _normalize_possible_answer_variant(phrase)
    if not cleaned_phrase:
        return []

    split_match = re.split(r'\s(?:-|–|—|:|->|=>)\s', cleaned_phrase, maxsplit=1)
    if len(split_match) != 2:
        return []

    left_side = _normalize_possible_answer_variant(split_match[0])
    right_side = _normalize_possible_answer_variant(split_match[1])
    if not left_side or not right_side:
        return []

    normalized_question = _normalize_possible_answer_variant(question_text)
    left_matches_question = bool(
        normalized_question
        and (
            left_side.casefold() == normalized_question.casefold()
            or normalized_question.casefold() == left_side.casefold()
        )
    )
    if not left_matches_question and not _question_suggests_matching_prompt(question_text):
        return []

    alias_candidates = [right_side]

    label_number, cleaned_numeric_right = _extract_numeric_prefix(right_side)
    if cleaned_numeric_right and cleaned_numeric_right.casefold() != right_side.casefold():
        alias_candidates.append(cleaned_numeric_right)
    if label_number is not None:
        alias_candidates.extend(_position_aliases(label_number))

    label_letter, cleaned_alpha_right = _extract_alpha_prefix(right_side)
    if cleaned_alpha_right and cleaned_alpha_right.casefold() != right_side.casefold():
        alias_candidates.append(cleaned_alpha_right)
    if label_letter:
        alias_candidates.extend(_position_aliases(ord(label_letter) - 64))

    deduped_aliases = []
    seen_aliases = set()
    for alias in alias_candidates:
        normalized_alias = _normalize_possible_answer_variant(alias)
        alias_key = normalized_alias.casefold()
        if not normalized_alias or alias_key in seen_aliases:
            continue
        seen_aliases.add(alias_key)
        deduped_aliases.append(normalized_alias)
    return deduped_aliases


def _expand_simple_phrase_forms(phrase, question_text=''):
    cleaned_phrase = _normalize_possible_answer_variant(phrase)
    if not cleaned_phrase:
        return []

    variants = []
    base_variants = [cleaned_phrase]
    lowercase_phrase = cleaned_phrase.casefold()
    if lowercase_phrase in {'all of those', 'all those', 'all of the above'}:
        base_variants.extend(['all', 'all of those', 'all those', 'all of the above'])

    article_match = re.match(r'^(a|an|the)\s+(.+)$', cleaned_phrase, flags=re.IGNORECASE)
    if article_match:
        article = article_match.group(1).lower()
        remainder = _normalize_possible_answer_variant(article_match.group(2))
        base_variants.append(remainder)
        if article in {'a', 'an'} and remainder and ' ' not in remainder and not remainder.endswith('s'):
            base_variants.append(f"{remainder}s")

    base_variants.extend(_expand_person_name_alias_bases(cleaned_phrase, question_text=question_text))
    base_variants.extend(_extract_matching_right_side_alias_bases(cleaned_phrase, question_text=question_text))

    for base_value in list(base_variants):
        normalized_base_value = _normalize_possible_answer_variant(base_value)
        if not normalized_base_value:
            continue
        variants.extend(_possible_answer_case_forms(normalized_base_value))

        punctuationless_value = _normalize_possible_answer_variant(
            re.sub(r"[^0-9A-Za-z\s-]", '', normalized_base_value)
        )
        if punctuationless_value and punctuationless_value != normalized_base_value:
            variants.extend(_possible_answer_case_forms(punctuationless_value))

        words = normalized_base_value.split()
        if len(words) > 1:
            variants.extend(_possible_answer_case_forms('-'.join(words)))
            variants.extend(_possible_answer_case_forms(''.join(words)))
        elif '-' in normalized_base_value:
            hyphenless = normalized_base_value.replace('-', '')
            spaced = normalized_base_value.replace('-', ' ')
            variants.extend(_possible_answer_case_forms(hyphenless))
            variants.extend(_possible_answer_case_forms(spaced))
        elif len(normalized_base_value) >= 8:
            if normalized_base_value.lower().endswith('style'):
                variants.extend(_possible_answer_case_forms(normalized_base_value[:-5] + ' style'))
            if normalized_base_value.lower().endswith('crawl'):
                variants.extend(_possible_answer_case_forms(normalized_base_value[:-5] + ' crawl'))

        for initialism in _possible_answer_initialisms(normalized_base_value):
            variants.extend(_possible_answer_case_forms(initialism))

    deduped_variants = []
    seen_variants = set()
    for variant in variants:
        normalized_variant = _normalize_possible_answer_variant(variant)
        if not normalized_variant or normalized_variant in seen_variants:
            continue
        seen_variants.add(normalized_variant)
        deduped_variants.append(normalized_variant)
    return deduped_variants


def _build_possible_answers(answer_text, *, question_text=''):
    return _build_possible_answers_with_aliases(answer_text, [], question_text=question_text)


def _build_possible_answers_with_aliases(answer_text, additional_candidates, *, question_text=''):
    segments = _split_possible_answer_segments(answer_text)
    for candidate in additional_candidates or []:
        segments.extend(_split_possible_answer_segments(candidate))
    possible_answers = []
    seen_variants = set()

    for segment in segments:
        for variant in _expand_simple_phrase_forms(segment, question_text=question_text):
            if variant in seen_variants:
                continue
            seen_variants.add(variant)
            possible_answers.append(variant)

    return possible_answers


def _parse_openai_json_response(response_text):
    candidate = (response_text or '').strip()
    if candidate.startswith('```'):
        candidate = re.sub(r'^```(?:json)?\s*', '', candidate)
        candidate = re.sub(r'\s*```$', '', candidate)

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        for pattern in (r'(\{.*\})', r'(\[.*\])'):
            match = re.search(pattern, candidate, re.DOTALL)
            if not match:
                continue
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
        raise RuntimeError(f"GPT did not return valid JSON: {response_text}")


def _generate_additional_possible_answer_aliases(round_obj, question_entries, *, round_type=''):
    from .views import _create_openai_text_response, _get_openai_client

    api_key = str(os.getenv('OPENAI_API_KEY') or '').strip()
    if not api_key or api_key == 'sk-test':
        return {}

    batched_questions = []
    for question_entry in question_entries or []:
        answer_text = str((question_entry or {}).get('answer_text') or '').strip()
        if not answer_text:
            continue
        question_number = int((question_entry or {}).get('question_number') or 0)
        if question_number <= 0:
            continue
        batched_questions.append(
            {
                'question_number': question_number,
                'question_text': str((question_entry or {}).get('question_text') or '').strip(),
                'answer_text': answer_text,
            }
        )

    if not batched_questions:
        return {}

    instructions = (
        "You generate plausible accepted-answer aliases for trivia grading. "
        "For each question, return up to 10 additional answers that should count as correct for the same fact. "
        "Include concise aliases like dropped franchise prefixes, subtitle-only references, well-known abbreviations, "
        "episode numbering variants, and common alternate phrasings when they are clearly equivalent. "
        "For person-name answers, always include surname-only answers plus short-name/full-name surname variants whenever the clue refers to one specific person. "
        "For example, George Washington should accept Washington, and Benjamin Franklin should accept Franklin and Ben Franklin; Franklin should also accept Benjamin Franklin when the clue clearly means that person. "
        "For multiple choice rounds, include option-position aliases when the option order is recoverable, such as A/B/C, 1/2/3, and first/second/third. "
        "For matching rounds, include positional aliases when the option order is recoverable, such as A/B/C, 1/2/3, first/second/third, first/middle/last, and similar equivalents. "
        "If a matching answer combines the left clue with the right answer, like Alex - Defender, also include right-side-only aliases like Defender in addition to any positional aliases. "
        "For long matching-statement answers, also include a very short one- or two-word gist answer when it would obviously identify the correct option, such as church for a long statement about the Church of England. "
        "Do not include simple capitalization, punctuation, spacing, or hyphen variants; those are already handled elsewhere. "
        "Do not include vague near-misses, broader categories, partial guesses, or anything that changes the meaning. "
        "Return strict JSON as an array of objects with keys question_number and aliases."
    )
    input_payload = {
        'round_title': str(getattr(round_obj, 'title', '') or '').strip(),
        'round_type': str(round_type or '').strip(),
        'questions': batched_questions,
    }
    client = _get_openai_client()
    response_text = _create_openai_text_response(
        client,
        instructions=instructions,
        input_items=[
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'input_text',
                        'text': json.dumps(input_payload, ensure_ascii=True),
                    }
                ],
            }
        ],
        max_output_tokens=1200,
        reasoning_effort="low",
    )
    parsed_payload = _parse_openai_json_response(response_text)
    if not isinstance(parsed_payload, list):
        raise RuntimeError(f"GPT did not return an alias list: {response_text}")

    alias_map = {}
    for item in parsed_payload:
        if not isinstance(item, dict):
            continue
        try:
            question_number = int(item.get('question_number') or 0)
        except (TypeError, ValueError):
            continue
        if question_number <= 0:
            continue
        aliases = []
        seen_aliases = set()
        for raw_alias in item.get('aliases') or []:
            normalized_alias = _normalize_possible_answer_variant(raw_alias)
            alias_key = normalized_alias.casefold()
            if not normalized_alias or alias_key in seen_aliases:
                continue
            seen_aliases.add(alias_key)
            aliases.append(normalized_alias)
            if len(aliases) >= 10:
                break
        if aliases:
            alias_map[question_number] = aliases
    return alias_map


def _find_slide_by_number(slide_payload, slide_number):
    for slide_data in slide_payload.get('slides', []):
        if slide_data.get('slide_number') == slide_number:
            return slide_data
    return None


def _parse_optional_positive_int(value):
    try:
        parsed_value = int(value)
    except (TypeError, ValueError):
        return None
    return parsed_value if parsed_value > 0 else None


def _normalize_text_content(text):
    return re.sub(r'\s+', ' ', str(text or '')).strip()


def _text_center(text_item):
    return (
        float(text_item.get('position_x') or 0) + (float(text_item.get('width') or 0) / 2.0),
        float(text_item.get('position_y') or 0) + (float(text_item.get('height') or 0) / 2.0),
    )


def _media_center(media_item):
    return (
        float(media_item.get('position_x') or 0) + (float(media_item.get('width') or 0) / 2.0),
        float(media_item.get('position_y') or 0) + (float(media_item.get('height') or 0) / 2.0),
    )


def _distance_between_points(point_a, point_b):
    return ((point_a[0] - point_b[0]) ** 2 + (point_a[1] - point_b[1]) ** 2) ** 0.5


def _extract_numeric_prefix(value):
    match = re.match(r'^\s*(\d+)[\)\].:\-]*\s*(.+?)\s*$', str(value or ''))
    if not match:
        return None, _normalize_text_content(value)
    return int(match.group(1)), _normalize_text_content(match.group(2))


def _extract_shape_text_content(shape):
    return ''.join(
        _extract_text_elements_content(
            (shape.get('text') or {}).get('textElements', [])
        )
    )


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


def _extract_slide_text_items(slide):
    text_items = []

    def walk_page_elements(page_elements):
        for element in page_elements or []:
            transform = element.get('transform') or {}
            size = element.get('size') or {}
            position_x = float(transform.get('translateX') or 0)
            position_y = float(transform.get('translateY') or 0)
            width = _dimension_magnitude(size.get('width'))
            height = _dimension_magnitude(size.get('height'))
            element_id = element.get('objectId', '')

            candidate_texts = []
            shape = element.get('shape') or {}
            if shape:
                candidate_texts.append(_extract_shape_text_content(shape))

            table = element.get('table') or {}
            if table:
                candidate_texts.append(' '.join(_extract_table_text_chunks(table)))

            word_art = element.get('wordArt') or {}
            if word_art.get('renderedText'):
                candidate_texts.append(word_art['renderedText'])

            element_title = str(element.get('title') or '').strip()
            element_description = str(element.get('description') or '').strip()
            if element_title:
                candidate_texts.append(element_title)
            if element_description:
                candidate_texts.append(element_description)

            for raw_text in candidate_texts:
                normalized_text = _normalize_text_content(raw_text)
                if not normalized_text:
                    continue
                text_items.append(
                    {
                        'element_id': element_id,
                        'text': normalized_text,
                        'position_x': position_x,
                        'position_y': position_y,
                        'width': width,
                        'height': height,
                    }
                )

            element_group = element.get('elementGroup') or {}
            if element_group:
                walk_page_elements(element_group.get('children', []))

    walk_page_elements(slide.get('pageElements', []))
    return text_items


def _expand_text_items_to_answer_candidates(text_items):
    answer_candidates = []
    for text_item in text_items or []:
        raw_lines = [
            _normalize_text_content(line)
            for line in re.split(r'[\r\n]+', str(text_item.get('text') or ''))
        ]
        lines = [line for line in raw_lines if line]
        if not lines:
            continue

        line_height = (float(text_item.get('height') or 0) / max(len(lines), 1)) if len(lines) > 1 else float(text_item.get('height') or 0)
        for line_index, line_text in enumerate(lines):
            label_number, cleaned_text = _extract_numeric_prefix(line_text)
            if not cleaned_text and label_number is None:
                continue
            answer_candidates.append(
                {
                    'text': cleaned_text or _normalize_text_content(line_text),
                    'label_number': label_number,
                    'position_x': float(text_item.get('position_x') or 0),
                    'position_y': float(text_item.get('position_y') or 0) + (line_height * line_index),
                    'width': float(text_item.get('width') or 0),
                    'height': line_height or float(text_item.get('height') or 0),
                }
            )
    return answer_candidates


def _find_nearest_numeric_label_for_media(media_item, text_items):
    media_midpoint = _media_center(media_item)
    candidate_labels = []
    for text_item in text_items or []:
        label_number, cleaned_text = _extract_numeric_prefix(text_item.get('text'))
        if label_number is None:
            normalized_text = _normalize_text_content(text_item.get('text'))
            if re.fullmatch(r'\d+', normalized_text):
                label_number = int(normalized_text)
                cleaned_text = normalized_text
        if label_number is None:
            continue
        candidate_labels.append(
            (
                _distance_between_points(media_midpoint, _text_center(text_item)),
                label_number,
            )
        )
    if not candidate_labels:
        return None
    candidate_labels.sort(key=lambda item: item[0])
    return candidate_labels[0][1]


def _infer_picture_instruction(round_obj, slide_text):
    normalized_context = f"{round_obj.title} {slide_text}".casefold()
    if any(keyword in normalized_context for keyword in ['where', 'location', 'place', 'landmark', 'map']):
        return "Identify the pictured place."
    if any(keyword in normalized_context for keyword in ['who', 'actor', 'celebrity', 'person', 'president']):
        return "Identify the pictured person."
    if any(keyword in normalized_context for keyword in ['movie', 'film', 'show', 'character']):
        return "Identify the pictured entertainment clue."
    return "Identify the pictured item."


def _classify_round_structure(round_obj, slide_payload):
    slides = slide_payload.get('slides', [])
    max_image_count = max(
        (
            len([media_item for media_item in slide.get('media_items', []) if media_item.get('kind') == 'image'])
            for slide in slides
        ),
        default=0,
    )
    has_audio_or_video = any(
        media_item.get('kind') in {'audio', 'video'}
        for slide in slides
        for media_item in slide.get('media_items', [])
    )

    if has_audio_or_video:
        normalized_title = f"{round_obj.title} {round_obj.major_category}".casefold()
        return {
            'round_type': 'music' if 'music' in normalized_title or str(round_obj.major_category or '').casefold() == 'music' else 'video',
            'strategy': 'gpt_multimedia',
            'notes': 'Classified from embedded audio/video media.',
        }

    if max_image_count >= 2:
        return {
            'round_type': 'picture',
            'strategy': 'picture_grid_layout',
            'notes': 'Classified as a multi-image picture round from slide layout.',
        }

    if max_image_count == 1:
        return {
            'round_type': 'picture',
            'strategy': 'gpt_picture',
            'notes': 'Classified as a picture round with one image per question slide.',
        }

    return {
        'round_type': 'short answer',
        'strategy': 'gpt_text',
        'notes': 'Classified as a text-first round from slide layout.',
    }


def _extract_picture_grid_questions_by_layout(round_obj, slide_payload, classification):
    slides = slide_payload.get('slides', [])
    for slide_index, question_slide in enumerate(slides[:-1]):
        image_items = [
            media_item
            for media_item in question_slide.get('media_items', [])
            if media_item.get('kind') == 'image'
        ]
        if len(image_items) < 2:
            continue

        answer_slide = slides[slide_index + 1]
        answer_candidates = _expand_text_items_to_answer_candidates(answer_slide.get('text_items', []))
        if len(answer_candidates) < len(image_items):
            continue

        question_text_items = question_slide.get('text_items', [])
        label_to_answer = {
            candidate['label_number']: candidate
            for candidate in answer_candidates
            if candidate.get('label_number') is not None and candidate.get('text')
        }

        extracted_questions = []
        used_answer_indexes = set()
        for media_item in image_items:
            label_number = _find_nearest_numeric_label_for_media(media_item, question_text_items)
            answer_candidate = label_to_answer.get(label_number) if label_number is not None else None

            if answer_candidate is None:
                media_midpoint = _media_center(media_item)
                remaining_candidates = [
                    (candidate_index, candidate)
                    for candidate_index, candidate in enumerate(answer_candidates)
                    if candidate_index not in used_answer_indexes and candidate.get('text')
                ]
                if not remaining_candidates:
                    continue
                candidate_index, answer_candidate = min(
                    remaining_candidates,
                    key=lambda item: _distance_between_points(media_midpoint, _text_center(item[1])),
                )
                used_answer_indexes.add(candidate_index)
            else:
                for candidate_index, candidate in enumerate(answer_candidates):
                    if candidate is answer_candidate:
                        used_answer_indexes.add(candidate_index)
                        break

            question_number = len(extracted_questions) + 1
            label_suffix = f" {label_number}" if label_number is not None else f" {question_number}"
            extracted_questions.append(
                {
                    'question_number': question_number,
                    'source_slide_number': question_slide.get('slide_number'),
                    'question_text': f"Picture{label_suffix}",
                    'instruction_text': _infer_picture_instruction(round_obj, question_slide.get('text') or ''),
                    'answer_text': answer_candidate.get('text') or '',
                    'media_kind': 'image',
                    'media_index': media_item.get('media_index'),
                    'major_category': round_obj.major_category or '',
                    'minor_category1': round_obj.minor_category1 or '',
                    'minor_category2': round_obj.minor_category2 or '',
                }
            )

        if len(extracted_questions) >= 2:
            return {
                'round_type': classification.get('round_type') or 'picture',
                'notes': classification.get('notes') or 'Extracted from answer-slide layout.',
                'questions': extracted_questions,
            }
    return None


def _choose_media_candidates_for_entry(slide_payload, entry):
    source_slide_number = entry.get('source_slide_number')
    try:
        source_slide_number = int(source_slide_number) if source_slide_number is not None else None
    except (TypeError, ValueError):
        source_slide_number = None

    candidate_slides = []
    if source_slide_number is not None:
        chosen_slide = _find_slide_by_number(slide_payload, source_slide_number)
        if chosen_slide:
            candidate_slides.append(chosen_slide)
    candidate_slides.extend(
        slide_data for slide_data in slide_payload.get('slides', [])
        if slide_data not in candidate_slides
    )

    normalized_kind = _normalize_media_kind(entry.get('media_kind'))
    for slide_data in candidate_slides:
        media_items = slide_data.get('media_items') or []
        if normalized_kind:
            matching_items = [item for item in media_items if item.get('kind') == normalized_kind]
            if matching_items:
                return slide_data, matching_items
        if media_items:
            return slide_data, media_items
    return (
        _find_slide_by_number(slide_payload, source_slide_number) if source_slide_number is not None else None
    ), []


def _assign_media_to_question_entries(slide_payload, questions):
    contexts = []
    for index, entry in enumerate(questions, start=1):
        question_number = entry.get('question_number') or index
        try:
            question_number = int(question_number)
        except (TypeError, ValueError):
            question_number = index

        chosen_slide, candidate_media_items = _choose_media_candidates_for_entry(slide_payload, entry)
        normalized_kind = _normalize_media_kind(
            entry.get('media_kind') or (candidate_media_items[0].get('kind') if candidate_media_items else '')
        )
        source_slide_number = chosen_slide.get('slide_number') if chosen_slide else entry.get('source_slide_number')
        try:
            source_slide_number = int(source_slide_number) if source_slide_number is not None else None
        except (TypeError, ValueError):
            source_slide_number = None

        contexts.append(
            {
                'entry': entry,
                'index': index,
                'question_number': question_number,
                'chosen_slide': chosen_slide,
                'candidate_media_items': list(candidate_media_items or []),
                'media_kind': normalized_kind,
                'source_slide_number': source_slide_number,
                'chosen_media': None,
            }
        )

    grouped_contexts = {}
    for context in contexts:
        group_key = (
            context['source_slide_number'],
            context['media_kind'] or '',
        )
        grouped_contexts.setdefault(group_key, []).append(context)

    for group in grouped_contexts.values():
        media_items = group[0]['candidate_media_items'] if group else []
        if not media_items:
            continue

        ordered_group = sorted(group, key=lambda item: (item['question_number'], item['index']))
        used_media_indexes = set()
        unassigned_contexts = []

        for context in ordered_group:
            preferred_index = _parse_optional_positive_int(context['entry'].get('media_index'))
            if preferred_index and preferred_index <= len(media_items) and preferred_index not in used_media_indexes:
                context['chosen_media'] = media_items[preferred_index - 1]
                used_media_indexes.add(preferred_index)
            else:
                unassigned_contexts.append(context)

        next_media_index = 1
        for context in unassigned_contexts:
            if len(media_items) == 1:
                context['chosen_media'] = media_items[0]
                continue

            while next_media_index in used_media_indexes and next_media_index <= len(media_items):
                next_media_index += 1

            if next_media_index <= len(media_items):
                context['chosen_media'] = media_items[next_media_index - 1]
                used_media_indexes.add(next_media_index)
                next_media_index += 1
            else:
                context['chosen_media'] = media_items[-1]

    return contexts


def _guess_media_filename(round_obj, question_number, media_item, response):
    content_type = (response.headers.get('Content-Type') or '').split(';')[0].strip().lower()
    extension = mimetypes.guess_extension(content_type) or ''
    if not extension:
        source_url = media_item.get('download_url') or media_item.get('url') or ''
        path_extension = Path(urlparse(source_url).path).suffix
        extension = path_extension if path_extension else '.bin'
    round_stub = re.sub(r'[^a-z0-9]+', '-', round_obj.title.lower()).strip('-')[:50] or f'round-{round_obj.id}'
    return f"{round_stub}-q{question_number}{extension}"


def _optimize_analysis_image_content(raw_content):
    try:
        with Image.open(BytesIO(raw_content)) as source_image:
            source_image = ImageOps.exif_transpose(source_image)
            if max(source_image.size) > ROUND_ANALYSIS_IMAGE_MAX_DIMENSION:
                source_image.thumbnail(
                    (ROUND_ANALYSIS_IMAGE_MAX_DIMENSION, ROUND_ANALYSIS_IMAGE_MAX_DIMENSION),
                    Image.LANCZOS,
                )

            has_alpha = 'A' in source_image.getbands()
            output_buffer = BytesIO()
            if has_alpha:
                source_image.save(output_buffer, format='PNG', optimize=True)
                extension = '.png'
            else:
                source_image = source_image.convert('RGB')
                source_image.save(
                    output_buffer,
                    format='JPEG',
                    quality=ROUND_ANALYSIS_IMAGE_JPEG_QUALITY,
                    optimize=True,
                    progressive=True,
                )
                extension = '.jpg'
            output_buffer.seek(0)
            return output_buffer.getvalue(), extension
    except Exception:
        logger.exception("Could not optimize round analysis image content.")
        return None, ''


def _download_media_file(round_obj, question_number, media_item):
    if not media_item or media_item.get('kind') != 'image':
        return None

    download_url = media_item.get('download_url') or media_item.get('url') or ''
    if not download_url:
        return None

    response = requests.get(download_url, timeout=30)
    response.raise_for_status()
    optimized_content, optimized_extension = _optimize_analysis_image_content(response.content)
    if not optimized_content:
        return None

    filename = _guess_media_filename(round_obj, question_number, media_item, response)
    if optimized_extension:
        filename = f"{Path(filename).stem}{optimized_extension}"
    return filename, ContentFile(optimized_content)


def _store_round_analysis(run, slide_payload, analysis_payload):
    normalized_analysis_payload = _normalize_analysis_questions(analysis_payload)
    questions = normalized_analysis_payload.get('questions') or []
    empty_correctness = _empty_player_correctness_map()
    RoundQuestionAnalysisEntry.objects.filter(run=run).delete()
    question_contexts = _assign_media_to_question_entries(slide_payload, questions)

    normalized_round_type = str(normalized_analysis_payload.get('round_type') or '').strip()
    normalized_notes = str(normalized_analysis_payload.get('notes') or '').strip()
    additional_possible_answers_by_question = {
        int(context['question_number']): [
            _normalize_possible_answer_variant(alias)
            for alias in list((context['entry'] or {}).get('additional_possible_answers') or [])
            if _normalize_possible_answer_variant(alias)
        ]
        for context in question_contexts
    }
    try:
        generated_alias_map = _generate_additional_possible_answer_aliases(
            run.round,
            [
                {
                    'question_number': context['question_number'],
                    'question_text': str((context['entry'] or {}).get('question_text') or '').strip(),
                    'answer_text': str((context['entry'] or {}).get('answer_text') or '').strip(),
                }
                for context in question_contexts
            ],
            round_type=normalized_round_type,
        )
        for question_number, aliases in generated_alias_map.items():
            merged_aliases = []
            seen_aliases = set()
            for alias in [
                *additional_possible_answers_by_question.get(question_number, []),
                *(aliases or []),
            ]:
                normalized_alias = _normalize_possible_answer_variant(alias)
                alias_key = normalized_alias.casefold()
                if not normalized_alias or alias_key in seen_aliases:
                    continue
                seen_aliases.add(alias_key)
                merged_aliases.append(normalized_alias)
            additional_possible_answers_by_question[question_number] = merged_aliases
    except Exception:
        logger.exception("Could not generate additional possible answers for round %s", run.round_id)

    for context in question_contexts:
        entry = context['entry']
        question_number = context['question_number']
        chosen_slide = context['chosen_slide']
        chosen_media = context['chosen_media']
        source_slide_number = context['source_slide_number']

        media_kind = _normalize_media_kind(entry.get('media_kind') or (chosen_media or {}).get('kind'))
        if chosen_media and chosen_media.get('likely_audio_control') and media_kind == 'image':
            media_kind = 'audio'
        media_url = (
            (chosen_media or {}).get('playable_url')
            or (chosen_media or {}).get('url')
            or ''
        )
        if chosen_media and chosen_media.get('likely_audio_control') and not (chosen_media or {}).get('playable_url'):
            media_url = ''
        if _is_placeholder_media_url(media_url, expected_kind=media_kind):
            media_url = ''
        source_slide_url = (chosen_slide or {}).get('slide_url') or ''
        major_category, minor_category1, minor_category2 = _normalize_analysis_categories(entry)
        answer_text = str(entry.get('answer_text') or '').strip()

        analysis_entry = RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=run.round,
            round_name=run.round.title,
            round_date=run.round.date,
            question_number=question_number,
            question_text=str(entry.get('question_text') or '').strip(),
            instruction_text=str(entry.get('instruction_text') or '').strip(),
            answer_text=answer_text,
            possible_answers=_build_possible_answers_with_aliases(
                answer_text,
                additional_possible_answers_by_question.get(question_number, []),
                question_text=str(entry.get('question_text') or '').strip(),
            ),
            round_type=normalized_round_type,
            media_kind=media_kind,
            media_url=media_url,
            source_slide_number=source_slide_number,
            source_slide_url=source_slide_url,
            notes=normalized_notes,
            major_category=major_category,
            minor_category1=minor_category1,
            minor_category2=minor_category2,
            player_correctness=dict(empty_correctness),
        )
        try:
            downloaded_media = _download_media_file(run.round, question_number, chosen_media)
            if downloaded_media:
                filename, content_file = downloaded_media
                analysis_entry.media_file.save(filename, content_file, save=True)
        except Exception:
            logger.exception(
                "Could not save analysis media for round %s question %s",
                run.round_id,
                question_number,
            )

    run.status = RoundQuestionAnalysisRun.STATUS_COMPLETED
    run.completed_at = timezone.now()
    run.round_type = normalized_round_type
    run.notes = normalized_notes
    run.source_presentation_id = slide_payload.get('presentation_id', '')
    run.source_slide_range = slide_payload.get('slide_range_label', '')
    run.error_message = ''
    run.save(
        update_fields=[
            'status',
            'completed_at',
            'round_type',
            'notes',
            'source_presentation_id',
            'source_slide_range',
            'error_message',
            'updated_at',
        ]
    )
    RoundQuestionAnalysisRun.objects.filter(round=run.round).exclude(id=run.id).delete()


def _notify_alex_round_analysis_finished(runs, *, batch_label='', success_count=0, failed_count=0):
    if not runs:
        return

    label = batch_label or (runs[0].round.title if len(runs) == 1 else f"{len(runs)} rounds")
    if failed_count:
        failure_summaries = []
        for run in runs:
            if run.status != RoundQuestionAnalysisRun.STATUS_FAILED:
                continue
            error_message = str(run.error_message or '').strip()
            if not error_message:
                continue
            for line in error_message.splitlines():
                normalized_line = str(line or '').strip()
                if normalized_line:
                    failure_summaries.append(normalized_line)
                    break
        title = "Round Analysis Finished"
        body = f"Finished analyzing {label} with {success_count} complete and {failed_count} failed."
        if len(runs) == 1 and failure_summaries:
            body = f"Finished analyzing {label}: {failure_summaries[0]}"
        elif failure_summaries:
            body = f"{body} First failure: {failure_summaries[0]}"
    else:
        title = "Round Analysis Finished"
        body = f"Finished analyzing {label}."
    _send_push_to_username(ANALYSIS_NOTIFICATION_USERNAME, title, body)


def _send_push_to_username(username, title, body):
    from .views import _send_push_to_subscription

    subscriptions = PushSubscription.objects.filter(user__username__iexact=username).select_related('user')
    for subscription in subscriptions:
        _send_push_to_subscription(subscription, title, body)


def latest_analysis_run_map(round_ids):
    latest_map = {}
    for run in (
        RoundQuestionAnalysisRun.objects.filter(round_id__in=round_ids)
        .select_related('round')
        .order_by('round_id', '-created_at', '-id')
    ):
        latest_map.setdefault(run.round_id, run)
    return latest_map


def latest_completed_runs_with_entries(*, round_id=None):
    runs = list(
        RoundQuestionAnalysisRun.objects.filter(status=RoundQuestionAnalysisRun.STATUS_COMPLETED)
        .select_related('round')
        .prefetch_related('entries')
        .order_by('round_id', '-created_at', '-id')
    )
    latest_runs = []
    seen_round_ids = set()
    for run in runs:
        if run.round_id in seen_round_ids:
            continue
        seen_round_ids.add(run.round_id)
        if round_id is not None and run.round_id != round_id:
            continue
        latest_runs.append(run)
    return latest_runs
