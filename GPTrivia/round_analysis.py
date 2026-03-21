import json
import logging
import os
import pickle
import re
import threading
import traceback
from itertools import chain

from django.db import close_old_connections
from django.utils import timezone

from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from .models import GPTriviaRound, MergedPresentation, PushSubscription, RoundQuestionAnalysisEntry, RoundQuestionAnalysisRun
from .player_scores import display_name_for_player_field, get_all_player_fields


logger = logging.getLogger(__name__)
ANALYSIS_NOTIFICATION_USERNAME = 'Alex'


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
            status__in=[RoundQuestionAnalysisRun.STATUS_PENDING, RoundQuestionAnalysisRun.STATUS_RUNNING],
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


def _build_round_slide_payload(round_obj):
    from .mail import (
        ROUND_SOURCE_MERGED_DECK,
        ROUND_SOURCE_UNKNOWN,
        _classify_round_source_link,
        _extract_slide_text,
        _find_slide_index_for_round_title,
        _infer_historical_round_slide_range,
    )

    source_meta = _classify_round_source_link(round_obj.link)
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
        if not slide_text:
            continue
        slide_text_rows.append(
            {
                'slide_number': offset,
                'slide_id': slide.get('objectId', ''),
                'text': slide_text,
            }
        )

    if not slide_text_rows:
        raise RuntimeError(f"No extractable slide text found for round {round_obj.id}.")

    return {
        'presentation_id': presentation_id,
        'slide_range_label': f"{start_index + 1}-{end_index + 1}",
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
        "You analyze a trivia round copied into a Google Slides deck. "
        "Infer the overall round type and extract the question/answer pairs from the slide text. "
        "Return strict JSON only with this schema: "
        "{\"round_type\": string, \"notes\": string, \"questions\": ["
        "{\"question_number\": integer, \"question_text\": string, \"answer_text\": string, "
        "\"major_category\": string, \"minor_category1\": string, \"minor_category2\": string}"
        "]}. "
        "Use short round types like picture, matching, multiple choice, short answer, music, video, audio, puzzle, or mixed. "
        "Pair question slides with answer slides when possible. Preserve wording from the slides instead of paraphrasing heavily. "
        "If a category does not fit, leave that category blank. "
        "major_category must be chosen from the allowed major categories when possible. "
        "minor categories should be chosen from the allowed minor categories when possible. "
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


def _store_round_analysis(run, slide_payload, analysis_payload):
    questions = analysis_payload.get('questions') or []
    empty_correctness = _empty_player_correctness_map()
    RoundQuestionAnalysisEntry.objects.filter(run=run).delete()

    normalized_round_type = str(analysis_payload.get('round_type') or '').strip()
    normalized_notes = str(analysis_payload.get('notes') or '').strip()
    for index, entry in enumerate(questions, start=1):
        question_number = entry.get('question_number') or index
        RoundQuestionAnalysisEntry.objects.create(
            run=run,
            round=run.round,
            round_name=run.round.title,
            round_date=run.round.date,
            question_number=int(question_number),
            question_text=str(entry.get('question_text') or '').strip(),
            answer_text=str(entry.get('answer_text') or '').strip(),
            round_type=normalized_round_type,
            notes=normalized_notes,
            major_category=str(entry.get('major_category') or '').strip(),
            minor_category1=str(entry.get('minor_category1') or '').strip(),
            minor_category2=str(entry.get('minor_category2') or '').strip(),
            player_correctness=dict(empty_correctness),
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
