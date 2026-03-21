import json
import logging
import mimetypes
import os
import pickle
import re
import threading
import traceback
from io import BytesIO
from itertools import chain
from pathlib import Path
from urllib.parse import urlparse

import requests
from django.core.files.base import ContentFile
from django.db import close_old_connections
from django.utils import timezone
from PIL import Image, ImageOps

from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from .models import GPTriviaRound, MergedPresentation, PushSubscription, RoundQuestionAnalysisEntry, RoundQuestionAnalysisRun
from .player_scores import display_name_for_player_field, get_all_player_fields


logger = logging.getLogger(__name__)
ANALYSIS_NOTIFICATION_USERNAME = 'Alex'
ROUND_ANALYSIS_IMAGE_MAX_DIMENSION = 512
ROUND_ANALYSIS_IMAGE_JPEG_QUALITY = 72


def _google_slide_url(presentation_id, slide_id=''):
    if presentation_id and slide_id:
        return f"https://docs.google.com/presentation/d/{presentation_id}/edit#slide=id.{slide_id}"
    if presentation_id:
        return f"https://docs.google.com/presentation/d/{presentation_id}/edit"
    return ''


def queue_round_analysis(round_id, *, trigger_type=RoundQuestionAnalysisRun.TRIGGER_MANUAL, initiated_by=''):
    return queue_round_analysis_batch(
        [round_id],
        trigger_type=trigger_type,
        initiated_by=initiated_by,
    )


def queue_round_analysis_batch(round_ids, *, trigger_type=RoundQuestionAnalysisRun.TRIGGER_AUTO, initiated_by='', batch_label=''):
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

    queued_run_ids = []
    for round_id in normalized_ids:
        if round_id not in queueable_rounds or round_id in active_round_ids:
            continue
        run = RoundQuestionAnalysisRun.objects.create(
            round_id=round_id,
            trigger_type=trigger_type,
            initiated_by=initiated_by or '',
            status=RoundQuestionAnalysisRun.STATUS_PENDING,
        )
        queued_run_ids.append(run.id)

    if not queued_run_ids:
        return []

    worker = threading.Thread(
        target=_run_round_analysis_batch,
        kwargs={
            'run_ids': queued_run_ids,
            'batch_label': batch_label or '',
        },
        daemon=True,
        name=f"round-analysis-{queued_run_ids[0]}",
    )
    worker.start()
    return queued_run_ids


def _run_round_analysis_batch(*, run_ids, batch_label=''):
    close_old_connections()
    try:
        runs = list(
            RoundQuestionAnalysisRun.objects.select_related('round').filter(id__in=run_ids).order_by('id')
        )
        if not runs:
            return

        _notify_alex_round_analysis_started(runs, batch_label=batch_label)

        success_count = 0
        failed_count = 0
        for run in runs:
            try:
                _run_single_round_analysis(run.id)
                success_count += 1
            except Exception:
                failed_count += 1
                logger.exception("Round analysis failed for run %s", run.id)

        _notify_alex_round_analysis_finished(
            runs,
            batch_label=batch_label,
            success_count=success_count,
            failed_count=failed_count,
        )
    finally:
        close_old_connections()


def _run_single_round_analysis(run_id):
    run = RoundQuestionAnalysisRun.objects.select_related('round').get(id=run_id)
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


def _extract_slide_media_items(slide):
    media_items = []
    for element in slide.get('pageElements', []):
        element_id = element.get('objectId', '')
        transform = element.get('transform') or {}
        position_x = float(transform.get('translateX') or 0)
        position_y = float(transform.get('translateY') or 0)
        image = element.get('image')
        if image:
            media_items.append(
                {
                    'kind': 'image',
                    'element_id': element_id,
                    'url': image.get('sourceUrl') or image.get('contentUrl') or '',
                    'download_url': image.get('contentUrl') or image.get('sourceUrl') or '',
                    'description': image.get('title') or image.get('description') or '',
                    'position_x': position_x,
                    'position_y': position_y,
                }
            )
            continue

        video = element.get('video')
        if video:
            media_items.append(
                {
                    'kind': 'video',
                    'element_id': element_id,
                    'url': video.get('url') or video.get('sourceUrl') or '',
                    'download_url': '',
                    'description': video.get('id') or video.get('source') or '',
                    'position_x': position_x,
                    'position_y': position_y,
                }
            )
            continue

        audio = element.get('audio')
        if audio:
            media_items.append(
                {
                    'kind': 'audio',
                    'element_id': element_id,
                    'url': audio.get('url') or audio.get('sourceUrl') or '',
                    'download_url': '',
                    'description': audio.get('id') or '',
                    'position_x': position_x,
                    'position_y': position_y,
                }
            )

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


def _build_round_slide_payload(round_obj):
    from .mail import (
        ROUND_SOURCE_MERGED_DECK,
        ROUND_SOURCE_UNKNOWN,
        _classify_round_source_link,
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
        media_items = _extract_slide_media_items(slide)
        if not slide_text and not media_items:
            continue
        slide_text_rows.append(
            {
                'slide_number': offset,
                'slide_id': slide.get('objectId', ''),
                'slide_url': _google_slide_url(presentation_id, slide.get('objectId', '')),
                'text': slide_text,
                'media_items': media_items,
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
    from .views import _create_openai_text_response, _get_openai_client

    major_categories, minor_categories = _collect_category_options()
    input_payload = {
        'round_title': round_obj.title,
        'round_creator': round_obj.creator,
        'presentation_id': slide_payload['presentation_id'],
        'slide_range': slide_payload['slide_range_label'],
        'slides': slide_payload['slides'],
        'allowed_major_categories': major_categories,
        'allowed_minor_categories': minor_categories,
    }
    instructions = (
        "You analyze a trivia round from a Google Slides deck. "
        "Infer the overall round type and extract the question/answer pairs from the slide text and any media metadata. "
        "Return strict JSON only with this schema: "
        "{\"round_type\": string, \"notes\": string, \"questions\": ["
        "{\"question_number\": integer, \"source_slide_number\": integer, "
        "\"question_text\": string, \"instruction_text\": string, \"answer_text\": string, "
        "\"media_kind\": string, \"media_index\": integer, "
        "\"major_category\": string, \"minor_category1\": string, \"minor_category2\": string}"
        "]}. "
        "Use short round types like picture, matching, multiple choice, short answer, music, video, audio, puzzle, or mixed. "
        "Pair question slides with answer slides when possible. Preserve wording from the slides instead of paraphrasing heavily. "
        "If the round is multimedia, use the round title, answer text, nearby slide text, and media metadata to infer what the player is supposed to identify or do. "
        "For example, infer prompts like identify the person, identify the place, name the song and artist, identify the movie, or explain the matching rule. "
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
                'content': [
                    {
                        'type': 'input_text',
                        'text': json.dumps(input_payload, ensure_ascii=True),
                    }
                ],
            }
        ],
        max_output_tokens=4000,
        reasoning_effort="medium",
    )
    return _parse_analysis_response_json(response_text)


def _parse_analysis_response_json(response_text):
    candidate = (response_text or '').strip()
    if candidate.startswith('```'):
        candidate = re.sub(r'^```(?:json)?\s*', '', candidate)
        candidate = re.sub(r'\s*```$', '', candidate)

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        match = re.search(r'(\{.*\})', candidate, re.DOTALL)
        if not match:
            raise RuntimeError(f"GPT did not return valid JSON: {response_text}")
        return json.loads(match.group(1))


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
    questions = analysis_payload.get('questions') or []
    empty_correctness = _empty_player_correctness_map()
    RoundQuestionAnalysisEntry.objects.filter(run=run).delete()
    question_contexts = _assign_media_to_question_entries(slide_payload, questions)

    normalized_round_type = str(analysis_payload.get('round_type') or '').strip()
    normalized_notes = str(analysis_payload.get('notes') or '').strip()
    for context in question_contexts:
        entry = context['entry']
        question_number = context['question_number']
        chosen_slide = context['chosen_slide']
        chosen_media = context['chosen_media']
        source_slide_number = context['source_slide_number']

        media_kind = _normalize_media_kind(entry.get('media_kind') or (chosen_media or {}).get('kind'))
        media_url = (chosen_media or {}).get('url') or ''
        source_slide_url = (chosen_slide or {}).get('slide_url') or ''
        major_category, minor_category1, minor_category2 = _normalize_analysis_categories(entry)

        analysis_entry = RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=run.round,
            round_name=run.round.title,
            round_date=run.round.date,
            question_number=question_number,
            question_text=str(entry.get('question_text') or '').strip(),
            instruction_text=str(entry.get('instruction_text') or '').strip(),
            answer_text=str(entry.get('answer_text') or '').strip(),
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


def _notify_alex_round_analysis_started(runs, *, batch_label=''):
    if not runs:
        return

    if len(runs) == 1:
        round_obj = runs[0].round
        title = "Round Analysis Started"
        body = f"Started analyzing {round_obj.title} ({round_obj.date:%m/%d/%Y})."
    else:
        title = "Round Analysis Started"
        label = batch_label or f"{len(runs)} rounds"
        body = f"Started analyzing {label}."
    _send_push_to_username(ANALYSIS_NOTIFICATION_USERNAME, title, body)


def _notify_alex_round_analysis_finished(runs, *, batch_label='', success_count=0, failed_count=0):
    if not runs:
        return

    label = batch_label or (runs[0].round.title if len(runs) == 1 else f"{len(runs)} rounds")
    if failed_count:
        title = "Round Analysis Finished"
        body = f"Finished analyzing {label} with {success_count} complete and {failed_count} failed."
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
