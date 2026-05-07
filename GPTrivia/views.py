from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from .forms import GPTriviaRoundForm, ProfileIntroForm, ProfilePictureForm
from .models import GPTriviaRound, MergedPresentation, PresentationBuildState, Profile
from django.db import transaction
from django.db.models import Avg, F, FloatField, Case, When, Sum, Count, Q
from django.contrib.auth import views as auth_views
from django.urls import reverse, reverse_lazy
from django.shortcuts import render
from datetime import datetime
from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.csrf import csrf_exempt
from django.contrib import admin
from django.views import View
from asgiref.sync import sync_to_async
import os
from django.contrib import messages
import string
from django.views.decorators.csrf import ensure_csrf_cookie
import random
from django.shortcuts import redirect
from django.contrib.auth.models import User
import subprocess
import base64
import math
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import pytz
from functools import lru_cache

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeDoneView as BasePasswordChangeDoneView
# import QuerySet
from django.db.models.query import QuerySet
# import json
import json
from django.core.serializers.json import DjangoJSONEncoder
import datetime
import logging
import requests
from urllib.parse import urlencode
import hashlib
from io import BytesIO
from decimal import Decimal, InvalidOperation
from PIL import Image, ImageDraw

## API Libs
from rest_framework import generics
from pywebpush import webpush, WebPushException
from .serializers import GPTriviaRoundSerializer, MergedPresentationSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.http import JsonResponse
from django.http import Http404
from django.core import serializers
from rest_framework.renderers import JSONRenderer
from datetime import date
from django.utils import timezone
from django.http import FileResponse
from django.core.cache import cache
from .models import AnswerSheetEntry, JeopardyQuestion, JeopardyRound, PushSubscription, RoundQuestionAnalysisEntry, RoundQuestionAnalysisRun, SubmittedRound
from .player_scores import (
    FIXED_SCORE_FIELDS,
    MIN_ANALYSIS_ROUNDS,
    get_all_player_fields,
    build_player_color_mapping,
    build_profile_color_override_mapping,
    build_player_text_mapping,
    collect_player_fields,
    display_name_for_player_field,
    flatten_round_for_analysis,
    get_eligible_player_fields,
    get_player_color,
    get_round_score_map,
    player_field_for_name,
    normalize_player_list,
    set_round_score_map,
)
from .blog_posts import (
    get_blog_index_context,
    get_joker_stats_blog_context,
    get_blog_navigation_context,
    get_other_trivia_plots_blog_context,
    get_roboalex_blog_context,
)
from .profile_media import get_profile_avatar_url, get_profile_picture_url
from .swoop_templates import (
    ROUND_MAKER_TEMPLATE_OPTIONS,
    SMART_TRIVIAL_PURSUIT_CATEGORIES,
    SMART_TRIVIAL_PURSUIT_TEMPLATE_ID,
)
import re
import mimetypes
from itertools import chain


gmail_key = '8f35edc691b918094035b22807266a1e468bf5f0'

TRIVIA_TIMEZONE = pytz.timezone('America/Los_Angeles')


VAPID_PRIVATE_KEY = 'sn34CZG_vKbl_AoGObw2aUFo1TV0t2QdGwa-vut-Q70'
VAPID_CLAIMS = {
    "sub": "mailto:hailsciencetrivia@gmail.com"
}
logger = logging.getLogger(__name__)
HOME_BUILD_GROUP_NAME = 'home_build_updates'
HOME_BUILD_STATE_KEY = 'home_page'
HOME_BUILD_STALE_MINUTES = 30
SWOOP_MODEL = "gpt-5.4"
ANSWER_SHEET_OCR_IMAGE_WIDTH = 1400
ANSWER_SHEET_OCR_ROW_HEIGHT = 84
ANSWER_SHEET_OCR_PADDING_TOP = 42
ANSWER_SHEET_OCR_PADDING_BOTTOM = 42
ANSWER_SHEET_OCR_SIDE_PADDING = 20
ANSWER_SHEET_OCR_GUIDE_INSET = 8
ANSWER_SHEET_OCR_STROKE_WIDTH = 5
SWOOP_SYSTEM_PROMPT = (
    "Your name is Swooper, the swoop snake. At the very beginning of every conversation "
    "(but NOT every single reply), the first thing you say is 'Swoop!' in a high pitched voice. "
    "You also have wings. You're sssmooth-talking, sssensual, and myssterious. Now, whenever "
    "someone says something to you, make sure to respond in the voice of that character. Also, "
    "your job is trivia round recommender. No matter what the reply is, you find a way to suggest "
    "exactly one challenging and off-the-wall trivia round idea that the user might enjoy making, "
    "unless the user explicitly asks for multiple options. Keep your reply concise, usually 2 to 4 "
    "short sentences and well under 100 words. And you do not under any circumstances provide actual "
    "questions, only ideas for rounds. Here's an example "
    "of what you might say: 'Sssmooth movesss, my friend! But you ssseem like sssomeone who might "
    "enjoy a great trivia round. How about trying a \"sssensational sssoundtrack\" round, filled "
    "with quessstionsss about famousss movie ssscores and theme sssongsss? Sssounds exciting, "
    "doesssn't it?' Also, if someone starts their message with 'SWOOP', you break out of character "
    "entirely and answer like a normal helpful assistant."
)
SWOOP_SAMPLE_QUESTION_PROMPT = (
    "You generate exactly one creative trivia question and a short correct answer based on the "
    "round idea provided by the user. Keep it unusual but still fair for a general-audience trivia "
    "night. If the user includes previous sample questions, avoid repeating them and make a new "
    "one. Return exactly this format and nothing else:\n"
    "Question: <question text>\n\n"
    "Answer: <short answer>"
)
SWOOP_ICON_KEYWORD_PROMPT = (
    "Provide no more than two keywords that summarize the following trivia question. "
    "Return only the keywords and nothing else."
)
ROUND_MAKER_SMART_TEMPLATE_FALLBACK_KEYWORDS = [
    ("GEOGRAPHY", [r"\bcapital\b", r"\bcountry\b", r"\bcity\b", r"\bstate\b", r"\bmap\b", r"\briver\b", r"\bmountain\b", r"\bocean\b", r"\bwhere\b"]),
    ("FOOD", [r"\bfood\b", r"\bcuisine\b", r"\bdish\b", r"\brecipe\b", r"\bingredient\b", r"\bchef\b", r"\brestaurant\b", r"\bcooking\b"]),
    ("FILM", [r"\bfilm\b", r"\bmovie\b", r"\bdirector\b", r"\bactor\b", r"\bactress\b", r"\bcinema\b", r"\bbox office\b"]),
    ("SCIENCE", [r"\bscience\b", r"\bphysics\b", r"\bchemistry\b", r"\bbiology\b", r"\bscientist\b", r"\belement\b", r"\bplanet\b", r"\bcell\b"]),
    ("NATURE", [r"\bnature\b", r"\bplant\b", r"\bflower\b", r"\btree\b", r"\bforest\b", r"\becosystem\b", r"\bweather\b", r"\bclimate\b", r"\bgeology\b"]),
    ("LAW", [r"\blaw\b", r"\blegal\b", r"\bcourt\b", r"\bjudge\b", r"\bjustice\b", r"\bconstitution\b", r"\bstatute\b", r"\bcrime\b"]),
    ("ANIMALS", [r"\banimal\b", r"\bmammal\b", r"\bbird\b", r"\breptile\b", r"\bspecies\b", r"\bzoolog"]),
    ("PHILOSOPHY", [r"\bphilosophy\b", r"\bphilosopher\b", r"\bethics\b", r"\bmetaphysics\b", r"\bepistemology\b", r"\bexistential\b", r"\bstoic\b"]),
    ("CURRENTEVENTS", [r"\bcurrent event", r"\bbreaking news\b", r"\bheadline\b", r"\brecent\b", r"\bthis year\b", r"\bnews\b", r"\belection\b"]),
    ("HISTORY", [r"\bhistory\b", r"\bcentury\b", r"\bempire\b", r"\bwar\b", r"\bpresident\b", r"\bancient\b", r"\brevolution\b", r"\bhistorical\b"]),
    ("GAMES", [r"\bgame\b", r"\bboard game\b", r"\bvideo game\b", r"\bconsole\b", r"\bpuzzle\b", r"\bchess\b", r"\bcard game\b"]),
    ("THEATER", [r"\btheater\b", r"\btheatre\b", r"\bbroadway\b", r"\bmusical\b", r"\bplay\b", r"\bstage\b"]),
    ("ARTS", [r"\bart\b", r"\bartist\b", r"\bpainting\b", r"\bsculpt", r"\bopera\b", r"\bballet\b", r"\barchitecture\b"]),
    ("LITERATURE", [r"\bbook\b", r"\bnovel\b", r"\bauthor\b", r"\bpoem\b", r"\bliterature\b", r"\bplaywright\b"]),
    ("FOOTBALL", [r"\bfootball\b", r"\btouchdown\b", r"\bquarterback\b", r"\bsuper bowl\b", r"\bnfl\b", r"\bfield goal\b"]),
    ("SPORTS", [r"\bsport\b", r"\bteam\b", r"\bgoal\b", r"\bscore\b", r"\bchampionship\b", r"\bolympic\b", r"\bnba\b", r"\bnfl\b", r"\bmlb\b"]),
    ("TECHNOLOGY", [r"\btechnology\b", r"\bcomputer\b", r"\bsoftware\b", r"\binternet\b", r"\bprogramming\b", r"\bdevice\b", r"\bai\b"]),
    ("WRITING", [r"\bwriting\b", r"\bgrammar\b", r"\bspelling\b", r"\bpunctuation\b", r"\banagram\b", r"\bpalindrome\b", r"\bsynonym\b", r"\bword\b"]),
    ("ENTERTAINMENT", [r"\btelevision\b", r"\btv\b", r"\bmusic\b", r"\bcelebrity\b", r"\bpop culture\b", r"\bsitcom\b", r"\bband\b", r"\bsinger\b"]),
]
GOOGLE_PRESENTATION_ID_PATTERN = re.compile(r"/presentation/d/([A-Za-z0-9_-]+)")
HOME_ROUNDS_CACHE_TTL_SECONDS = 20
ANALYSIS_PLOT_CACHE_TTL_SECONDS = 60 * 60 * 24
PROFILE_STATS_CACHE_TTL_SECONDS = 60 * 60 * 24
SITE_DATA_CACHE_VERSION_KEY = 'site_data_cache_version'


MOBILE_MANIFEST_USER_AGENT_TOKENS = (
    'android',
    'iphone',
    'ipad',
    'ipod',
    'mobile',
)


def _get_site_data_cache_version():
    return cache.get_or_set(SITE_DATA_CACHE_VERSION_KEY, 1, None)


def _bump_site_data_cache_version():
    try:
        cache.incr(SITE_DATA_CACHE_VERSION_KEY)
    except ValueError:
        cache.set(SITE_DATA_CACHE_VERSION_KEY, 2, None)


def _request_prefers_mobile_answer_sheet_start(request):
    user_agent = (request.META.get('HTTP_USER_AGENT') or '').lower()
    return any(token in user_agent for token in MOBILE_MANIFEST_USER_AGENT_TOKENS)


def web_app_manifest(request):
    start_url = reverse('answer_sheet') if _request_prefers_mobile_answer_sheet_start(request) else reverse('home')
    manifest_payload = {
        'id': '/',
        'name': 'Hail Science Trivia',
        'short_name': 'Hail Science',
        'description': 'An App for Hail Science Trivia',
        'start_url': start_url,
        'scope': '/',
        'display': 'standalone',
        'background_color': '#ffffff',
        'theme_color': '#000000',
        'icons': [
            {
                'src': '/static/img/app-snake-icon-192.png',
                'sizes': '192x192',
                'type': 'image/png',
            },
            {
                'src': '/static/splash/app-snake-icon-512.maskable.png',
                'sizes': '512x512',
                'type': 'image/png',
                'purpose': 'maskable',
            },
        ],
    }
    return JsonResponse(manifest_payload, content_type='application/manifest+json')


def _request_wants_fresh_cache(request):
    refresh_value = str(request.GET.get('refresh') or '').strip().lower()
    if refresh_value in {'1', 'true', 'yes', 'reload'}:
        return True

    cache_control = (request.headers.get('Cache-Control') or '').lower()
    pragma = (request.headers.get('Pragma') or '').lower()
    return any(token in cache_control for token in ('no-cache', 'no-store', 'max-age=0')) or 'no-cache' in pragma


def create_presentation(*args, **kwargs):
    from .mail import create_presentation as mail_create_presentation

    return mail_create_presentation(*args, **kwargs)


def update_merged_presentation(*args, **kwargs):
    from .mail import update_merged_presentation as mail_update_merged_presentation

    return mail_update_merged_presentation(*args, **kwargs)


def copy_template(*args, **kwargs):
    from .mail import copy_template as mail_copy_template

    return mail_copy_template(*args, **kwargs)


def share_slides(*args, **kwargs):
    from .mail import share_slides as mail_share_slides

    return mail_share_slides(*args, **kwargs)


def get_round_titles_and_links(*args, **kwargs):
    from .mail import get_round_titles_and_links as mail_get_round_titles_and_links

    return mail_get_round_titles_and_links(*args, **kwargs)


def _get_presentation_build_error_class():
    from .mail import PresentationBuildError

    return PresentationBuildError


@lru_cache(maxsize=1)
def _get_openai_client():
    from openai import OpenAI

    return OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

def _extract_openai_text(response):
    output_text = getattr(response, 'output_text', None)
    if output_text:
        return output_text.strip()

    collected_chunks = []
    for output in getattr(response, 'output', []) or []:
        for content in getattr(output, 'content', []) or []:
            text = getattr(content, 'text', None)
            if text:
                collected_chunks.append(text)

    return ''.join(collected_chunks).strip()


def _extract_openai_text_from_payload(payload):
    output_text = str((payload or {}).get('output_text', '') or '').strip()
    if output_text:
        return output_text

    collected_chunks = []
    for output in (payload or {}).get('output', []) or []:
        for content in (output or {}).get('content', []) or []:
            text = (content or {}).get('text')
            if text:
                collected_chunks.append(text)

    return ''.join(collected_chunks).strip()


def _build_responses_input(messages):
    response_messages = []
    for message in messages:
        role = (message or {}).get('role')
        content = str((message or {}).get('content', '')).strip()
        if role == 'system' or not content:
            continue
        content_type = "output_text" if role == "assistant" else "input_text"
        response_messages.append(
            {
                "role": role,
                "content": [{"type": content_type, "text": content}],
            }
        )
    return response_messages


def _create_openai_text_response_http(*, instructions, input_items, max_output_tokens=250, reasoning_effort="medium"):
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('OPENAI_API_KEY is not configured.')

    request_kwargs = {
        "model": SWOOP_MODEL,
        "instructions": instructions,
        "input": input_items,
        "max_output_tokens": max_output_tokens,
        "store": False,
    }
    if reasoning_effort:
        request_kwargs["reasoning"] = {"effort": reasoning_effort}

    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=request_kwargs,
        timeout=60,
    )
    response.raise_for_status()
    return _extract_openai_text_from_payload(response.json())


def _create_openai_text_response(client, *, instructions, input_items, max_output_tokens=250, reasoning_effort="medium"):
    if hasattr(client, 'responses'):
        request_kwargs = {
            "model": SWOOP_MODEL,
            "instructions": instructions,
            "input": input_items,
            "max_output_tokens": max_output_tokens,
            "store": False,
        }
        if reasoning_effort:
            request_kwargs["reasoning"] = {"effort": reasoning_effort}

        response = client.responses.create(**request_kwargs)
        return _extract_openai_text(response)

    return _create_openai_text_response_http(
        instructions=instructions,
        input_items=input_items,
        max_output_tokens=max_output_tokens,
        reasoning_effort=reasoning_effort,
    )


def _get_round_maker_conversation_history(request):
    conversation_history = None

    if request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        if profile is not None:
            stored_history = profile.swoop_conversation_history
            session_history = request.session.get('conversation_history')
            if (not isinstance(stored_history, list) or not stored_history) and isinstance(session_history, list) and session_history:
                conversation_history = session_history
            else:
                conversation_history = stored_history

    if not isinstance(conversation_history, list):
        conversation_history = request.session.get('conversation_history')
    if not isinstance(conversation_history, list):
        conversation_history = []

    if not conversation_history:
        conversation_history = [{"role": "system", "content": SWOOP_SYSTEM_PROMPT}]
    elif conversation_history[0].get("role") != "system":
        conversation_history = [{"role": "system", "content": SWOOP_SYSTEM_PROMPT}, *conversation_history]

    if request.user.is_authenticated:
        profile = getattr(request.user, 'profile', None)
        if profile is not None and profile.swoop_conversation_history != conversation_history:
            profile.swoop_conversation_history = conversation_history
            profile.save(update_fields=['swoop_conversation_history'])

    request.session['conversation_history'] = conversation_history
    request.session.modified = True
    return conversation_history


def _is_truthy_form_value(value):
    return str(value or '').strip().lower() in {'1', 'true', 'on', 'yes'}


def _extract_google_presentation_id(link_value):
    match = GOOGLE_PRESENTATION_ID_PATTERN.search(str(link_value or ''))
    return match.group(1) if match else ''


def _normalize_round_link(link_value):
    return str(link_value or '').strip()


def _normalize_round_title(title_value):
    return re.sub(r'\s+', ' ', str(title_value or '').strip()).casefold()


def _normalize_round_creator(creator_value):
    return re.sub(r'\s+', ' ', str(creator_value or '').strip()).casefold()


def _parse_available_round_shared_date(shared_date_value):
    if isinstance(shared_date_value, datetime.datetime):
        return shared_date_value.date()
    if isinstance(shared_date_value, datetime.date):
        return shared_date_value
    return _parse_scoresheet_date(str(shared_date_value or '').strip())


def _normalize_round_shared_date(shared_date_value):
    parsed_date = _parse_available_round_shared_date(shared_date_value)
    return parsed_date.isoformat() if parsed_date else ''


def _creator_allows_title_fallback(creator_value):
    creator_key = _normalize_round_creator(creator_value)
    return creator_key in {'', 'unknown'}


def _build_submitted_round_lookup(submitted_rounds):
    submitted_rounds_by_presentation_id = {
        submitted_round.presentation_id: submitted_round
        for submitted_round in submitted_rounds
    }
    submitted_rounds_by_link = {}
    submitted_rounds_by_title = {}
    submitted_rounds_by_title_creator_date = {}
    duplicate_title_keys = set()
    duplicate_title_creator_date_keys = set()

    def add_title_key(candidate_title, submitted_round):
        title_key = _normalize_round_title(candidate_title)
        if not title_key:
            return
        existing_round = submitted_rounds_by_title.get(title_key)
        if existing_round and existing_round.id != submitted_round.id:
            duplicate_title_keys.add(title_key)
            return
        submitted_rounds_by_title[title_key] = submitted_round

    def add_title_creator_date_key(candidate_title, submitted_round):
        title_key = _normalize_round_title(candidate_title)
        creator_key = _normalize_round_creator(submitted_round.creator)
        shared_date_key = _normalize_round_shared_date(submitted_round.shared_date)
        if not title_key or not creator_key or not shared_date_key:
            return
        identity_key = (title_key, creator_key, shared_date_key)
        existing_round = submitted_rounds_by_title_creator_date.get(identity_key)
        if existing_round and existing_round.id != submitted_round.id:
            duplicate_title_creator_date_keys.add(identity_key)
            return
        submitted_rounds_by_title_creator_date[identity_key] = submitted_round

    for submitted_round in submitted_rounds:
        normalized_link = _normalize_round_link(submitted_round.link)
        if normalized_link:
            submitted_rounds_by_link[normalized_link] = submitted_round

        add_title_key(submitted_round.title, submitted_round)
        add_title_key(submitted_round.source_title, submitted_round)
        add_title_creator_date_key(submitted_round.title, submitted_round)
        add_title_creator_date_key(submitted_round.source_title, submitted_round)

    return (
        submitted_rounds_by_presentation_id,
        submitted_rounds_by_link,
        submitted_rounds_by_title,
        submitted_rounds_by_title_creator_date,
        duplicate_title_keys,
        duplicate_title_creator_date_keys,
    )


def _find_matching_submitted_round(title, creator, link, old_link, submitted_round_lookup, shared_date=''):
    (
        submitted_rounds_by_presentation_id,
        submitted_rounds_by_link,
        submitted_rounds_by_title,
        submitted_rounds_by_title_creator_date,
        duplicate_title_keys,
        duplicate_title_creator_date_keys,
    ) = submitted_round_lookup

    title_key = _normalize_round_title(title)
    creator_key = _normalize_round_creator(creator)
    shared_date_key = _normalize_round_shared_date(shared_date)

    def shared_date_matches(candidate_round, *, require_date=False):
        if not candidate_round:
            return False
        candidate_date_key = _normalize_round_shared_date(candidate_round.shared_date)
        if not shared_date_key:
            return True
        if not candidate_date_key:
            return not require_date
        return candidate_date_key == shared_date_key

    submitted_round = submitted_rounds_by_presentation_id.get(
        _extract_google_presentation_id(link) or _extract_google_presentation_id(old_link)
    )
    if submitted_round and not shared_date_matches(submitted_round):
        submitted_round = None
    if not submitted_round:
        submitted_round = submitted_rounds_by_link.get(_normalize_round_link(link)) or submitted_rounds_by_link.get(
            _normalize_round_link(old_link)
        )
    if submitted_round and not shared_date_matches(submitted_round):
        submitted_round = None
    if (
        not submitted_round
        and title_key
        and creator_key
        and shared_date_key
        and (title_key, creator_key, shared_date_key) not in duplicate_title_creator_date_keys
    ):
        submitted_round = submitted_rounds_by_title_creator_date.get((title_key, creator_key, shared_date_key))
    if not submitted_round and title_key and title_key not in duplicate_title_keys:
        candidate_round = submitted_rounds_by_title.get(title_key)
        if candidate_round:
            candidate_creator_key = _normalize_round_creator(candidate_round.creator)
            if _creator_allows_title_fallback(creator) or (
                creator_key and creator_key == candidate_creator_key
            ):
                requires_exact_date = bool(shared_date_key and not _creator_allows_title_fallback(creator))
                if shared_date_matches(candidate_round, require_date=requires_exact_date):
                    submitted_round = candidate_round
    return submitted_round


def _mark_selected_submitted_rounds_consumed(rounds):
    submitted_rounds = list(SubmittedRound.objects.filter(is_consumed=False))
    submitted_round_lookup = _build_submitted_round_lookup(submitted_rounds)
    matched_ids = []

    for round_data in rounds or []:
        submitted_round = _find_matching_submitted_round(
            round_data.get("title"),
            round_data.get("creator"),
            round_data.get("link"),
            round_data.get("old_link"),
            submitted_round_lookup,
            shared_date=round_data.get("shared_date"),
        )
        if submitted_round:
            matched_ids.append(submitted_round.id)

    if matched_ids:
        SubmittedRound.objects.filter(id__in=set(matched_ids)).update(is_consumed=True)


def _build_submitted_round_link(presentation_id):
    if not presentation_id:
        return ''
    return f"https://docs.google.com/presentation/d/{presentation_id}/edit"


def _build_available_round_persistence_id(link='', old_link='', title='', creator='', shared_date=''):
    presentation_id = _extract_google_presentation_id(link) or _extract_google_presentation_id(old_link)
    if presentation_id:
        return presentation_id

    normalized_link = _normalize_round_link(link) or _normalize_round_link(old_link)
    if normalized_link:
        return f"link-{hashlib.sha1(normalized_link.encode('utf-8')).hexdigest()[:24]}"

    persistence_parts = [
        _normalize_round_title(title),
        _normalize_round_creator(creator),
        _normalize_round_shared_date(shared_date),
    ]
    normalized_identity = '|'.join(persistence_parts).strip('|')
    if normalized_identity:
        return f"title-{hashlib.sha1(normalized_identity.encode('utf-8')).hexdigest()[:24]}"

    normalized_title = _normalize_round_title(title)
    if normalized_title:
        return f"title-{hashlib.sha1(normalized_title.encode('utf-8')).hexdigest()[:24]}"

    return ''


def _save_available_round_metadata(data, *, user=None):
    title = str(data.get('title') or '').strip()
    creator = str(data.get('creator') or '').strip()
    link = _normalize_round_link(data.get('link'))
    old_link = _normalize_round_link(data.get('old_link'))
    source_title = str(data.get('source_title') or title).strip()
    shared_date = _parse_available_round_shared_date(data.get('shared_date'))
    cooperative = bool(data.get('coop'))

    if not title:
        return None, 'Round title is required.'
    if not creator:
        return None, 'Round creator is required.'

    submitted_rounds = list(SubmittedRound.objects.order_by('-updated_at', '-submitted_at'))
    submitted_round_lookup = _build_submitted_round_lookup(submitted_rounds)
    submitted_round = _find_matching_submitted_round(
        source_title or title,
        creator,
        link,
        old_link,
        submitted_round_lookup,
        shared_date=shared_date,
    )

    persistence_id = (
        submitted_round.presentation_id
        if submitted_round
        else _build_available_round_persistence_id(
            link,
            old_link,
            source_title or title,
            creator,
            shared_date,
        )
    )
    if not persistence_id:
        return None, 'Could not identify this round.'

    link_to_store = link or old_link or (submitted_round.link if submitted_round else '') or _build_submitted_round_link(persistence_id)
    defaults = {
        'title': title,
        'source_title': source_title or title,
        'creator': creator,
        'shared_date': shared_date or (submitted_round.shared_date if submitted_round else None),
        'cooperative': cooperative,
        'link': link_to_store,
        'is_consumed': submitted_round.is_consumed if submitted_round else False,
        'submitted_by': (
            user
            if getattr(user, 'is_authenticated', False)
            else (submitted_round.submitted_by if submitted_round else None)
        ),
    }
    saved_round, _ = SubmittedRound.objects.update_or_create(
        presentation_id=persistence_id,
        defaults=defaults,
    )
    _bump_site_data_cache_version()
    return saved_round, ''


def _sanitize_inferred_available_round_title(title_text):
    candidate = str(title_text or '').strip()
    if candidate.startswith('```'):
        candidate = re.sub(r'^```(?:text)?\s*', '', candidate)
        candidate = re.sub(r'\s*```$', '', candidate)
    candidate = candidate.strip().strip('"').strip("'")
    candidate = re.sub(r'\s+', ' ', candidate).strip()
    if '\n' in candidate:
        candidate = candidate.splitlines()[0].strip()
    return candidate[:255]


def _infer_available_round_title_from_first_slide(link='', old_link='', fallback_title=''):
    presentation_id = _extract_google_presentation_id(link) or _extract_google_presentation_id(old_link)
    if not presentation_id:
        return str(fallback_title or '').strip()

    from googleapiclient.discovery import build
    from .mail import _extract_slide_text
    from .round_analysis import (
        _extract_slide_text_items,
        _fetch_slide_thumbnail_data_url,
        _load_google_credentials,
    )

    credentials = _load_google_credentials()
    slides_service = build('slides', 'v1', credentials=credentials, cache_discovery=False)
    presentation = slides_service.presentations().get(presentationId=presentation_id).execute()
    slides = presentation.get('slides', []) or []
    if not slides:
        return str(fallback_title or '').strip()

    first_slide = slides[0]
    first_slide_id = str(first_slide.get('objectId') or '').strip()
    slide_text = re.sub(r'\s+', ' ', _extract_slide_text(first_slide)).strip()
    text_items = _extract_slide_text_items(first_slide)
    thumbnail_data_url = ''
    if first_slide_id:
        try:
            thumbnail_data_url = _fetch_slide_thumbnail_data_url(
                slides_service,
                credentials,
                presentation_id,
                first_slide_id,
            )
        except Exception:
            logger.exception("Could not fetch first-slide thumbnail for round title inference.")

    instructions = (
        "You identify the title of a trivia round from the first slide of a Google Slides deck. "
        "Choose the most prominent title text on the slide based on layout, size, and overall presentation. "
        "Prefer the actual round title over creator names, subtitles, dates, instructions, and footer text. "
        "Return plain text only containing the best round title. Do not use quotes or extra commentary."
    )
    input_payload = {
        'presentation_id': presentation_id,
        'fallback_title': str(fallback_title or '').strip(),
        'slide_text': slide_text,
        'text_items': text_items,
    }
    input_content = [
        {
            'type': 'input_text',
            'text': json.dumps(input_payload, ensure_ascii=True),
        }
    ]
    if thumbnail_data_url:
        input_content.append(
            {
                'type': 'input_image',
                'image_url': thumbnail_data_url,
            }
        )

    inferred_title = _create_openai_text_response(
        _get_openai_client(),
        instructions=instructions,
        input_items=[
            {
                'role': 'user',
                'content': input_content,
            }
        ],
        max_output_tokens=80,
        reasoning_effort="low",
    )
    return _sanitize_inferred_available_round_title(inferred_title) or str(fallback_title or '').strip()


def _ensure_available_round_identified_title(title, creator, link, old_link, shared_date='', submitted_round=None):
    if not _creator_allows_round_analysis(creator):
        return submitted_round, False
    if submitted_round and submitted_round.source_title:
        return submitted_round, False

    try:
        inferred_source_title = _infer_available_round_title_from_first_slide(
            link=link,
            old_link=old_link,
            fallback_title=title,
        )
    except Exception:
        logger.exception("Could not infer available round title for link %s", link or old_link)
        return submitted_round, False

    inferred_source_title = str(inferred_source_title or '').strip() or str(title or '').strip()
    if not inferred_source_title:
        return submitted_round, False

    display_title = (
        str(submitted_round.title or '').strip()
        if submitted_round and str(submitted_round.title or '').strip()
        else inferred_source_title
    )
    creator_to_store = (
        str(submitted_round.creator or '').strip()
        if submitted_round and str(submitted_round.creator or '').strip()
        else str(creator or '').strip()
    )
    coop_to_store = bool(submitted_round.cooperative) if submitted_round else False

    saved_round, error_message = _save_available_round_metadata(
        {
            'title': display_title,
            'source_title': inferred_source_title,
            'creator': creator_to_store,
            'link': link,
            'old_link': old_link,
            'shared_date': shared_date,
            'coop': coop_to_store,
        }
    )
    if error_message or not saved_round:
        if error_message:
            logger.warning("Could not persist inferred available round title: %s", error_message)
        return submitted_round, False
    return saved_round, True


def _build_round_maker_creator_options():
    player_names = {
        display_name_for_player_field(player_field)
        for player_field in collect_player_fields(
            rounds=list(GPTriviaRound.objects.all()),
            presentations=list(MergedPresentation.objects.all()),
            include_fixed=True,
        )
    }
    player_names.update(
        display_name_for_player_field(submitted_round.creator)
        for submitted_round in SubmittedRound.objects.only('creator')
        if submitted_round.creator
    )
    player_names.update(
        display_name_for_player_field(user.username)
        for user in User.objects.only('username').order_by('username')
        if user.username
    )
    return sorted(name for name in player_names if name)


@admin.register(PushSubscription)
class PushSubscriptionAdminAgain(admin.ModelAdmin):
    list_display = ('user', 'endpoint', 'created_at')
    actions = ['send_test_push']
    search_fields = ('endpoint', 'user__username')

    def send_test_push(self, request, queryset):
        send_push_to_all("Admin Test", "Test push from admin.")
        self.message_user(request, "Push notification sent to all subscriptions.", messages.SUCCESS)
    send_test_push.short_description = "Send test push notification to all"


def _send_push_to_subscription(subscription, title, body):
    payload = {
        "title": title,
        "body": body,
    }
    sub_info = {
        "endpoint": subscription.endpoint,
        "keys": {
            "p256dh": subscription.p256dh,
            "auth": subscription.auth,
        }
    }
    try:
        webpush(
            subscription_info=sub_info,
            data=json.dumps(payload),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS.copy(),
        )
        print(f"Notification sent to {subscription.endpoint}")
        return True
    except WebPushException as ex:
        print(f"Failed to send notification: {ex}")
        return False


def send_push_to_all(title, body):
    subscriptions = PushSubscription.objects.all()
    for sub in subscriptions:
        print(f"Endpoint: {sub.endpoint}")
        _send_push_to_subscription(sub, title, body)

def get_j_question(request, question_id):
    question = get_object_or_404(JeopardyQuestion, id=question_id)
    return JsonResponse({"id": question.id,  # Include the ID field,
                         'text': question.text,
                         "is_active": question.is_active,
                         "daily_double": question.daily_double  # Ensure this field is included
                         })

def deactivate_j_question(request, question_id):
    question = get_object_or_404(JeopardyQuestion, id=question_id)
    question.is_active = False
    question.save()
    return JsonResponse({'success': True})


@csrf_exempt  # Use this only if you're not including CSRF token (better to include it in the JS)
def save_subscription(request):
    if request.method == 'GET':
        endpoint = str(request.GET.get('endpoint') or '').strip()
        if not endpoint:
            return JsonResponse({'success': True, 'subscribed_for_user': False})

        if request.user.is_authenticated:
            subscribed_for_user = PushSubscription.objects.filter(
                endpoint=endpoint,
                user=request.user,
            ).exists()
        else:
            subscribed_for_user = PushSubscription.objects.filter(endpoint=endpoint).exists()

        return JsonResponse({
            'success': True,
            'subscribed_for_user': subscribed_for_user,
        })

    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            endpoint = data.get('endpoint')
            keys = data.get('keys', {})
            p256dh = keys.get('p256dh')
            auth = keys.get('auth')

            if not endpoint or not p256dh or not auth:
                return JsonResponse({'success': False, 'error': 'Incomplete subscription info'}, status=400)

            sub, created = PushSubscription.objects.get_or_create(endpoint=endpoint)
            sub.p256dh = p256dh
            sub.auth = auth
            if request.user.is_authenticated:
                sub.user = request.user
            sub.save()

            test_notification_sent = _send_push_to_subscription(
                sub,
                "Notifications Enabled",
                "Hail Science notifications are now enabled on this device.",
            )

            return JsonResponse({
                'success': True,
                'test_notification_sent': test_notification_sent,
                'subscribed_for_user': bool(request.user.is_authenticated and sub.user_id == request.user.id),
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    if request.method == 'DELETE':
        try:
            data = json.loads(request.body or '{}')
            endpoint = data.get('endpoint')
            if not endpoint:
                return JsonResponse({'success': False, 'error': 'Endpoint is required'}, status=400)

            deleted_count, _ = PushSubscription.objects.filter(endpoint=endpoint).delete()
            return JsonResponse({'success': True, 'deleted': bool(deleted_count)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

    return JsonResponse({'error': 'Invalid request method'}, status=405)

# def send_push(title, message, subscriptions):
#     for sub in subscriptions:
#         try:
#             webpush(
#                 subscription_info=sub,
#                 data=json.dumps({'title': title, 'body': message}),
#                 vapid_private_key='MKOWyxQRCG8kKDaoX4BEME-aQuij50hdO9DfWxna8bo',
#                 vapid_claims={"sub": "mailto:hailsciencetrivia@gmail.com"}
#             )
#         except WebPushException as ex:
#             print("Web push failed:", repr(ex))

# def jeopardy_screen(request):
#     rounds = JeopardyRound.objects.filter(type=JeopardyRound.JEOPARDY)
#     return render(request, 'GPTrivia/jeopardyboard.html', {'rounds': rounds, 'next_screen': 'double_jeopardy_screen', 'value_multiplier': 200, 'is_final_jeopardy': False})

# @csrf_exempt
# def save_rounds(request):
#     if request.method == 'POST':
#         try:
#             data = json.loads(request.body)
#             request.session['selected_rounds'] = data  # Save to session for simplicity
#             return JsonResponse({'success': True})
#         except Exception as e:
#             return JsonResponse({'success': False, 'error': str(e)}, status=400)
#     return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)

@csrf_exempt
def save_rounds(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            # Save the selected rounds in the session
            request.session['selected_jeopardy_rounds'] = [int(data[f'jeopardy-round-{i}']) for i in range(1, 7)]
            request.session['selected_double_jeopardy_rounds'] = [int(data[f'double-jeopardy-round-{i}']) for i in range(1, 7)]
            request.session['selected_final_jeopardy_round'] = int(data['final-jeopardy-round'])

            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)


def jeopardy_screen(request):
    # Get available rounds
    jeopardy_rounds = JeopardyRound.objects.filter(type=JeopardyRound.JEOPARDY)
    double_jeopardy_rounds = JeopardyRound.objects.filter(type=JeopardyRound.DOUBLE_JEOPARDY)
    final_jeopardy_rounds = JeopardyRound.objects.filter(type=JeopardyRound.FINAL_JEOPARDY)

    # Get the selected rounds from the session or use defaults
    selected_jeopardy_rounds = request.session.get('selected_jeopardy_rounds', [r.id for r in jeopardy_rounds[:6]])
    selected_double_jeopardy_rounds = request.session.get('selected_double_jeopardy_rounds', [r.id for r in double_jeopardy_rounds[:6]])
    selected_final_jeopardy_round = request.session.get('selected_final_jeopardy_round', final_jeopardy_rounds.first().id if final_jeopardy_rounds.exists() else None)

    return render(request, 'GPTrivia/jeopardyboard.html', {
        'rounds': jeopardy_rounds.filter(id__in=selected_jeopardy_rounds),
        'next_screen': 'double_jeopardy_screen',
        'value_multiplier': 200,
        'is_final_jeopardy': False,
        'jeopardy_rounds': jeopardy_rounds,
        'double_jeopardy_rounds': double_jeopardy_rounds,
        'final_jeopardy_rounds': final_jeopardy_rounds,
        'selected_jeopardy_rounds': selected_jeopardy_rounds,
        'selected_double_jeopardy_rounds': selected_double_jeopardy_rounds,
        'selected_final_jeopardy_round': selected_final_jeopardy_round,
        'range_six': range(1, 7),  # Range for dropdown positions
    })

def double_jeopardy_screen(request):
    rounds = JeopardyRound.objects.filter(type=JeopardyRound.DOUBLE_JEOPARDY)
    return render(request, 'GPTrivia/jeopardyboard.html', {'rounds': rounds, 'next_screen': 'final_jeopardy_screen', 'value_multiplier': 400, 'is_final_jeopardy': False})

def final_jeopardy_screen(request):
    round_ = JeopardyRound.objects.filter(type=JeopardyRound.FINAL_JEOPARDY)
    return render(request, 'GPTrivia/jeopardyboard.html', {'rounds': round_, 'next_screen': 'jeopardy_screen', 'value_multiplier': 0, 'is_final_jeopardy': True})


class CustomPasswordChangeView(auth_views.PasswordChangeView):
    template_name = 'registration/password_change.html'
    success_url = reverse_lazy('password_changed')

class CustomPasswordChangeDoneView(auth_views.PasswordChangeDoneView):
    template_name = 'registration/password_changed.html'


def _user_can_use_smart_round_templates(user):
    if not getattr(user, 'is_authenticated', False):
        return False
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.round_analysis_opt_in)


def _build_round_maker_template_options(user):
    can_use_smart_templates = _user_can_use_smart_round_templates(user)
    return [
        option
        for option in ROUND_MAKER_TEMPLATE_OPTIONS
        if can_use_smart_templates or not option.get('requires_round_analysis')
    ]


def _normalize_round_maker_smart_category(category_value):
    normalized_category = re.sub(r'[^A-Z]', '', str(category_value or '').upper())
    if normalized_category in SMART_TRIVIAL_PURSUIT_CATEGORIES:
        return normalized_category
    return ''


def _ordered_round_maker_question_answer_rows(qas_dict):
    rows = []
    for question_number in range(1, 11):
        key_number = 0 if question_number == 10 else question_number
        question_text = str((qas_dict or {}).get(f'Question{key_number}') or '').strip()
        answer_text = str((qas_dict or {}).get(f'Answer{key_number}') or '').strip()
        if not question_text and not answer_text:
            continue
        rows.append(
            {
                'question_number': question_number,
                'question_text': question_text,
                'answer_text': answer_text,
            }
        )
    return rows


def _fallback_round_maker_smart_category(question_text, answer_text=''):
    combined_text = f"{question_text or ''} {answer_text or ''}".casefold()
    for category_name, patterns in ROUND_MAKER_SMART_TEMPLATE_FALLBACK_KEYWORDS:
        for pattern in patterns:
            if re.search(pattern, combined_text):
                return category_name
    return 'ENTERTAINMENT'


def _parse_round_maker_smart_category_response(response_text):
    candidate = str(response_text or '').strip()
    if candidate.startswith('```'):
        candidate = re.sub(r'^```(?:json)?\s*', '', candidate)
        candidate = re.sub(r'\s*```$', '', candidate)

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        match = re.search(r'(\{.*\})', candidate, re.DOTALL)
        if not match:
            raise RuntimeError(f"Smart template classifier did not return valid JSON: {response_text}")
        payload = json.loads(match.group(1))

    normalized_assignments = {}
    for row in (payload or {}).get('questions', []) or []:
        try:
            question_number = int(row.get('question_number'))
        except (TypeError, ValueError):
            continue
        normalized_category = _normalize_round_maker_smart_category(row.get('category'))
        if not normalized_category:
            continue
        normalized_assignments[question_number] = normalized_category
    return normalized_assignments


def _classify_round_maker_smart_template(round_title, qas_dict):
    question_rows = _ordered_round_maker_question_answer_rows(qas_dict)
    if not question_rows:
        return []

    instructions = (
        "You classify trivia question and answer pairs into one Trivial Pursuit category each. "
        "Choose exactly one category from this list for every question: "
        + ", ".join(SMART_TRIVIAL_PURSUIT_CATEGORIES)
        + ". "
        "Prefer FILM for movie-specific questions instead of the broader ENTERTAINMENT bucket. "
        "Use ENTERTAINMENT for television, music, celebrities, and other pop culture topics that are not specifically film. "
        "Use WRITING for spelling, grammar, wordplay, and writing craft. "
        "Use ARTS for visual art, theater, dance, architecture, and fine arts. "
        "Return strict JSON only in this schema: "
        "{\"questions\":[{\"question_number\": integer, \"category\": string}]}"
    )
    response_text = _create_openai_text_response(
        _get_openai_client(),
        instructions=instructions,
        input_items=[
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'input_text',
                        'text': json.dumps(
                            {
                                'round_title': str(round_title or '').strip(),
                                'questions': question_rows,
                            },
                            ensure_ascii=True,
                        ),
                    }
                ],
            }
        ],
        max_output_tokens=400,
        reasoning_effort="low",
    )
    categorized_questions = _parse_round_maker_smart_category_response(response_text)

    plan = []
    for question_row in question_rows:
        question_number = question_row['question_number']
        category_name = categorized_questions.get(question_number) or _fallback_round_maker_smart_category(
            question_row['question_text'],
            question_row['answer_text'],
        )
        plan.append(
            {
                **question_row,
                'category': category_name,
            }
        )
    return plan

class PreviewView(View):
    def post(self, request, *args, **kwargs):
        round_title = request.POST.get('round_title')
        presentation_id = request.POST.get('presentation_id')
        qas_json_string = request.POST.get('qas')
        # Convert the JSON string to a dictionary
        qas_dict = json.loads(qas_json_string)
        icon_links = None
        smart_category_plan = None
        print(presentation_id)
        if presentation_id == SMART_TRIVIAL_PURSUIT_TEMPLATE_ID:
            if not _user_can_use_smart_round_templates(request.user):
                return JsonResponse({'error': 'This template requires round analysis opt-in.'}, status=403)
            smart_category_plan = _classify_round_maker_smart_template(round_title, qas_dict)
        if presentation_id == "1x8J9cEpFeMMYAJ_Inxw4Z_2-zYBwa5NMfOsN8pZKVHQ":
            icon_links = json.loads(request.POST.get('icon_urls'))
            print(f"ICON LINKS: {icon_links}")
        new_id = copy_template(
            presentation_id,
            round_title,
            qas_dict,
            icon_links,
            smart_category_plan=smart_category_plan,
        )
        print (qas_dict)
        return JsonResponse({'new_id': new_id})

class ShareView(View):
    def post(self, request, *args, **kwargs):
        presentation_id = (request.POST.get('presentation_id') or '').strip()
        round_title = (request.POST.get('round_title') or '').strip() or 'Untitled Round'
        cooperative = _is_truthy_form_value(request.POST.get('cooperative'))
        creator = (
            display_name_for_player_field(request.user.username)
            if request.user.is_authenticated
            else display_name_for_player_field(request.POST.get('creator'))
        )

        if not presentation_id:
            return JsonResponse({'success': False, 'error': 'Presentation id is required.'}, status=400)
        if not creator:
            return JsonResponse({'success': False, 'error': 'Creator is required.'}, status=400)

        share_slides(presentation_id)
        SubmittedRound.objects.update_or_create(
            presentation_id=presentation_id,
            defaults={
                'title': round_title,
                'creator': creator,
                'cooperative': cooperative,
                'link': _build_submitted_round_link(presentation_id),
                'is_consumed': False,
                'submitted_by': request.user if request.user.is_authenticated else None,
            },
        )
        _bump_site_data_cache_version()
        return JsonResponse({'success': True})

@login_required
def rounds_list(request):
    from .round_analysis import ensure_round_analysis_worker_for_pending_runs

    ensure_round_analysis_worker_for_pending_runs()
    rounds = GPTriviaRound.objects.all()
    # can we reverse the order of the rounds
    rounds = rounds[::-1]
    initial_title_search = (request.GET.get('title_search') or '').strip()
    initial_creator_search = (request.GET.get('creator_search') or '').strip()
    initial_category_search = (request.GET.get('category_search') or '').strip()
    initial_date_search = (request.GET.get('date_search') or '').strip()

    player_fields = _get_global_player_fields()
    player_names = [display_name_for_player_field(field) for field in player_fields]
    player_color_mapping = build_player_color_mapping(player_names)
    analysis_status_map = _build_round_analysis_status_map([round_obj.id for round_obj in rounds])
    text_color = {}
    for player in player_names:
        player_color = player_color_mapping[player]
        brightness = (0.7 * int(player_color[1:3], 16)) + int(player_color[3:5], 16) + (0.3 * int(player_color[5:7], 16))
        text_color[player] = 'white' if brightness < 300 else 'black'

    context = {
        'player_fields': player_fields,
        'player_names': player_names,
        'round_rows': _build_round_rows(rounds, player_fields),
        'playerColorMapping': player_color_mapping,
        'text_color_mapping': text_color,
        'initial_title_search': initial_title_search,
        'initial_creator_search': initial_creator_search,
        'initial_category_search': initial_category_search,
        'initial_date_search': initial_date_search,
        'analysis_status_map': analysis_status_map,
    }

    return render(request, 'GPTrivia/rounds_list.html', context)


def _serialize_round_analysis_status(round_id, latest_run=None, has_completed_entries=False):
    error_message = str((latest_run.error_message if latest_run else '') or '').strip()
    error_summary = ''
    if error_message:
        for line in error_message.splitlines():
            normalized_line = str(line or '').strip()
            if normalized_line:
                error_summary = normalized_line
                break
    is_active = bool(
        latest_run and latest_run.status in {
            RoundQuestionAnalysisRun.STATUS_PENDING,
            RoundQuestionAnalysisRun.STATUS_RUNNING,
        }
    )
    was_analyzed_before = bool(
        has_completed_entries
        or (latest_run and latest_run.status == RoundQuestionAnalysisRun.STATUS_COMPLETED)
    )
    scheduled_for_iso = ''
    scheduled_summary = ''
    if latest_run and latest_run.scheduled_for:
        scheduled_for_iso = latest_run.scheduled_for.isoformat()
        localized_scheduled_for = timezone.localtime(latest_run.scheduled_for)
        formatted_scheduled_for = (
            f"{localized_scheduled_for.month}/{localized_scheduled_for.day}/"
            f"{localized_scheduled_for.strftime('%y')} "
            f"{localized_scheduled_for.strftime('%I').lstrip('0') or '0'}:"
            f"{localized_scheduled_for.strftime('%M')} "
            f"{localized_scheduled_for.strftime('%p')}"
        )
        if latest_run.status == RoundQuestionAnalysisRun.STATUS_PENDING:
            summary_prefix = (
                'Auto queued for'
                if latest_run.trigger_type == RoundQuestionAnalysisRun.TRIGGER_AUTO
                else 'Queued for'
            )
            scheduled_summary = f"{summary_prefix} {formatted_scheduled_for}"
    return {
        'status': latest_run.status if latest_run else '',
        'status_label': latest_run.get_status_display() if latest_run else '',
        'has_any_run': bool(latest_run),
        'is_active': is_active,
        'button_label': 'Restart' if is_active else ('Analyze Again' if was_analyzed_before else 'Analyze'),
        'button_action': 'restart' if is_active else 'trigger',
        'button_disabled': False,
        'show_already_analyzed': bool(was_analyzed_before and not is_active),
        'has_completed_entries': bool(has_completed_entries),
        'view_url': f"{reverse('round_analysis_list')}?round_id={round_id}" if has_completed_entries else '',
        'error_summary': error_summary,
        'error_message': error_message,
        'scheduled_for_iso': scheduled_for_iso,
        'scheduled_summary': scheduled_summary,
    }


def _build_round_analysis_opt_in_map(creator_names):
    normalized_names = []
    seen_names = set()
    for creator_name in creator_names or []:
        normalized_name = str(creator_name or '').strip()
        if not normalized_name:
            continue
        folded_name = normalized_name.casefold()
        if folded_name in seen_names:
            continue
        seen_names.add(folded_name)
        normalized_names.append(normalized_name)

    if not normalized_names:
        return {}

    opted_in_usernames = {
        username.casefold(): True
        for username in Profile.objects.filter(
            round_analysis_opt_in=True,
        ).values_list('user__username', flat=True)
    }
    return {
        creator_name: bool(opted_in_usernames.get(creator_name.casefold()))
        for creator_name in normalized_names
    }


def _creator_allows_round_analysis(creator_name):
    return bool(_build_round_analysis_opt_in_map([creator_name]).get(str(creator_name or '').strip(), False))


def _should_auto_queue_round_analysis_for_round(round_obj, source_round_data, *, presentation_name, action_name):
    is_new_round = bool((source_round_data or {}).get('is_new'))
    creator_opted_in = _creator_allows_round_analysis(round_obj.creator)
    queue_reason = 'queued'
    should_queue = True

    if not is_new_round:
        queue_reason = 'not_new'
        should_queue = False
    elif round_obj.replay:
        queue_reason = 'replay'
        should_queue = False
    elif not creator_opted_in:
        queue_reason = 'creator_not_opted_in'
        should_queue = False

    logger.info(
        "Auto round analysis %s during %s for presentation %s: round_id=%s title=%r creator=%r date=%s reason=%s is_new=%s replay=%s creator_opted_in=%s",
        'queued' if should_queue else 'skipped',
        action_name,
        presentation_name,
        round_obj.id,
        round_obj.title,
        round_obj.creator,
        round_obj.date,
        queue_reason,
        is_new_round,
        bool(round_obj.replay),
        creator_opted_in,
    )
    return should_queue


def _build_round_analysis_status_map(round_ids):
    normalized_round_ids = []
    seen_round_ids = set()
    for round_id in round_ids or []:
        try:
            parsed_round_id = int(round_id)
        except (TypeError, ValueError):
            continue
        if parsed_round_id in seen_round_ids:
            continue
        seen_round_ids.add(parsed_round_id)
        normalized_round_ids.append(parsed_round_id)

    from .round_analysis import ensure_round_analysis_worker_for_pending_runs, latest_analysis_run_map

    ensure_round_analysis_worker_for_pending_runs()

    round_rows = list(GPTriviaRound.objects.filter(id__in=normalized_round_ids).values('id', 'creator'))
    creator_opt_in_map = _build_round_analysis_opt_in_map([row['creator'] for row in round_rows])
    creator_by_round_id = {
        row['id']: row['creator']
        for row in round_rows
    }
    latest_run_map = latest_analysis_run_map(normalized_round_ids)
    rounds_with_completed_entries = set(
        RoundQuestionAnalysisEntry.objects.filter(round_id__in=normalized_round_ids)
        .values_list('round_id', flat=True)
        .distinct()
    )
    status_map = {
        round_id: {
            **_serialize_round_analysis_status(
                round_id,
                latest_run=latest_run_map.get(round_id),
                has_completed_entries=round_id in rounds_with_completed_entries,
            ),
            'can_trigger': bool(creator_opt_in_map.get(creator_by_round_id.get(round_id, ''), False)),
        }
        for round_id in normalized_round_ids
    }
    for round_id in normalized_round_ids:
        if round_id not in status_map:
            status_map[round_id] = {
                **_serialize_round_analysis_status(
                    round_id,
                    latest_run=None,
                    has_completed_entries=False,
                ),
                'can_trigger': False,
            }
    return status_map


@login_required
def round_analysis_list(request):
    from .round_analysis import ensure_round_analysis_worker_for_pending_runs, latest_completed_runs_with_entries

    ensure_round_analysis_worker_for_pending_runs()

    requested_round_id = (request.GET.get('round_id') or '').strip()
    selected_round_id = None
    try:
        if requested_round_id:
            selected_round_id = int(requested_round_id)
    except (TypeError, ValueError):
        selected_round_id = None

    latest_runs = latest_completed_runs_with_entries(round_id=selected_round_id)
    player_names = _get_global_player_names()
    round_options = list(
        GPTriviaRound.objects.order_by('-date', '-round_number', 'title').values('id', 'title', 'date', 'round_number')
    )
    return render(
        request,
        'GPTrivia/round_analysis_list.html',
        {
            'latest_runs': latest_runs,
            'player_names': player_names,
            'selected_round_id': selected_round_id,
            'round_options': round_options,
        },
    )


@login_required
def round_analysis_status(request, round_id):
    round_obj = get_object_or_404(GPTriviaRound, id=round_id)
    return JsonResponse({
        'status': _build_round_analysis_status_map([round_obj.id])[round_obj.id],
    })


@login_required
def _build_round_analysis_question_payload(request, latest_completed_run, entry):
    response_payload = {
        'round_id': entry.round_id,
        'analysis_run_id': latest_completed_run.id,
        'round_name': entry.round_name or latest_completed_run.round.title,
        'round_date': entry.round_date.isoformat() if entry.round_date else '',
        'question_number': entry.question_number,
        'question_text': entry.question_text,
        'answer_text': entry.answer_text,
        'possible_answers': list(entry.possible_answers or []),
        'media_kind': entry.media_kind or '',
        'image_url': '',
        'image_content_type': '',
        'image_data_url': '',
    }

    if str(entry.media_kind or '').strip().lower() == 'image':
        if entry.media_file:
            image_url = request.build_absolute_uri(reverse('round_analysis_image', args=[entry.id]))
            image_content_type = mimetypes.guess_type(entry.media_file.name)[0] or 'application/octet-stream'
            response_payload['image_url'] = image_url
            response_payload['image_content_type'] = image_content_type
            if _is_truthy_form_value(request.GET.get('include_image')):
                try:
                    entry.media_file.open('rb')
                    encoded_image = base64.b64encode(entry.media_file.read()).decode('ascii')
                    response_payload['image_data_url'] = f'data:{image_content_type};base64,{encoded_image}'
                finally:
                    try:
                        entry.media_file.close()
                    except Exception:
                        pass
        elif entry.media_url:
            response_payload['image_url'] = entry.media_url

    return response_payload


def _latest_completed_round_analysis_run(round_id):
    return (
        RoundQuestionAnalysisRun.objects.filter(
            round_id=round_id,
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
        )
        .select_related('round')
        .order_by('-created_at', '-id')
        .first()
    )


def _run_is_music_round(run):
    round_major_category = str((run.round.major_category if run and run.round else '') or '').strip().lower()
    run_round_type = str((run.round_type if run else '') or '').strip().lower()
    return round_major_category == 'music' or run_round_type == 'music'


@login_required
def round_analysis_question(request):
    if request.method != 'GET':
        return JsonResponse({'detail': 'Method not allowed.'}, status=405)

    round_id_raw = str(request.GET.get('round_id') or '').strip()
    question_number_raw = str(request.GET.get('question_number') or '').strip()

    try:
        round_id = int(round_id_raw)
    except (TypeError, ValueError):
        return JsonResponse({'detail': 'round_id must be an integer.'}, status=400)

    try:
        question_number = int(question_number_raw)
    except (TypeError, ValueError):
        return JsonResponse({'detail': 'question_number must be an integer.'}, status=400)

    latest_completed_run = _latest_completed_round_analysis_run(round_id)
    if latest_completed_run is None:
        raise Http404("No completed round analysis exists for that round.")

    entry = (
        RoundQuestionAnalysisEntry.objects.filter(
            run=latest_completed_run,
            question_number=question_number,
        )
        .order_by('id')
        .first()
    )
    if entry is None:
        raise Http404("No analyzed question exists for that round and question number.")

    return JsonResponse(_build_round_analysis_question_payload(request, latest_completed_run, entry))


@login_required
def round_analysis_random_question(request):
    if request.method != 'GET':
        return JsonResponse({'detail': 'Method not allowed.'}, status=405)

    from .round_analysis import latest_completed_runs_with_entries

    valid_runs = []
    for run in latest_completed_runs_with_entries():
        if _run_is_music_round(run):
            continue
        run_entries = list(run.entries.all())
        if not run_entries:
            continue
        valid_runs.append((run, run_entries))

    if not valid_runs:
        raise Http404("No analyzed non-music rounds are available.")

    selected_run, selected_entries = random.choice(valid_runs)
    selected_entry = random.choice(selected_entries)
    return JsonResponse(_build_round_analysis_question_payload(request, selected_run, selected_entry))

def _normalize_answer_sheet_answers(raw_answers):
    if isinstance(raw_answers, str):
        answers = raw_answers.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    elif isinstance(raw_answers, list):
        answers = [str(item or '') for item in raw_answers]
    else:
        answers = []

    normalized_answers = [str(answer or '').strip() for answer in answers]
    if len(normalized_answers) < 10:
        normalized_answers.extend([''] * (10 - len(normalized_answers)))
    return normalized_answers


def _normalize_answer_sheet_input_mode(raw_input_mode):
    normalized_mode = str(raw_input_mode or '').strip().lower()
    if normalized_mode == AnswerSheetEntry.INPUT_MODE_PENCIL:
        return AnswerSheetEntry.INPUT_MODE_PENCIL
    return AnswerSheetEntry.INPUT_MODE_TEXT


def _normalize_answer_sheet_ink_strokes(raw_strokes):
    normalized_strokes = []
    if not isinstance(raw_strokes, list):
        return normalized_strokes

    for raw_stroke in raw_strokes[:400]:
        raw_points = raw_stroke.get('points') if isinstance(raw_stroke, dict) else raw_stroke
        if not isinstance(raw_points, list):
            continue

        normalized_points = []
        for raw_point in raw_points[:2000]:
            if not isinstance(raw_point, dict):
                continue
            try:
                point_x = float(raw_point.get('x'))
                point_y = float(raw_point.get('y'))
            except (TypeError, ValueError):
                continue

            if not (0 <= point_x <= 1 and 0 <= point_y <= 1):
                continue

            normalized_point = {
                'x': round(point_x, 5),
                'y': round(point_y, 5),
            }

            try:
                point_row = int(raw_point.get('r'))
            except (TypeError, ValueError):
                point_row = None
            if point_row is not None and point_row >= 1:
                normalized_point['r'] = point_row

            try:
                point_unit_x = float(raw_point.get('ux'))
            except (TypeError, ValueError):
                point_unit_x = None
            if point_unit_x is not None and math.isfinite(point_unit_x):
                normalized_point['ux'] = round(point_unit_x, 5)

            try:
                point_unit_y = float(raw_point.get('uy'))
            except (TypeError, ValueError):
                point_unit_y = None
            if point_unit_y is not None and math.isfinite(point_unit_y):
                normalized_point['uy'] = round(point_unit_y, 5)

            try:
                point_pressure = float(raw_point.get('p'))
            except (TypeError, ValueError):
                point_pressure = None
            if point_pressure is not None and 0 <= point_pressure <= 1:
                normalized_point['p'] = round(point_pressure, 4)

            normalized_points.append(normalized_point)

        if normalized_points:
            normalized_strokes.append(normalized_points)

    return normalized_strokes


def _normalize_answer_sheet_ink_stroke_rows(raw_rows, *, stroke_count=0, row_count=10):
    normalized_rows = []
    if not isinstance(raw_rows, list):
        return normalized_rows
    max_row_count = max(10, int(row_count or 10))
    for raw_value in raw_rows[:stroke_count or len(raw_rows)]:
        try:
            row_number = int(raw_value)
        except (TypeError, ValueError):
            normalized_rows.append(None)
            continue
        if row_number < 1 or row_number > max_row_count:
            normalized_rows.append(None)
            continue
        normalized_rows.append(row_number)
    return normalized_rows


def _get_answer_sheet_ocr_image_height(row_count):
    return (
        ANSWER_SHEET_OCR_PADDING_TOP
        + ANSWER_SHEET_OCR_PADDING_BOTTOM
        + (max(10, int(row_count or 10)) * ANSWER_SHEET_OCR_ROW_HEIGHT)
    )


def _answer_sheet_row_count(raw_row_count, raw_answers=None):
    try:
        parsed_row_count = int(raw_row_count)
    except (TypeError, ValueError):
        parsed_row_count = 0

    if parsed_row_count > 0:
        return max(10, parsed_row_count)

    if isinstance(raw_answers, str):
        candidate_count = len(raw_answers.replace('\r\n', '\n').replace('\r', '\n').split('\n'))
    elif isinstance(raw_answers, list):
        candidate_count = len(raw_answers)
    else:
        candidate_count = 0
    return max(10, candidate_count)


def _group_answer_sheet_ink_strokes_by_row(ink_strokes, *, row_count=10, stroke_rows=None):
    normalized_strokes = _normalize_answer_sheet_ink_strokes(ink_strokes)
    row_count = max(10, int(row_count or 10))
    row_buckets = {row_index: [] for row_index in range(row_count)}
    if not normalized_strokes:
        return row_buckets

    normalized_stroke_rows = _normalize_answer_sheet_ink_stroke_rows(
        stroke_rows,
        stroke_count=len(normalized_strokes),
        row_count=row_count,
    )
    image_height = _get_answer_sheet_ocr_image_height(row_count)
    for stroke_index, stroke in enumerate(normalized_strokes):
        if not stroke:
            continue
        explicit_row_number = (
            normalized_stroke_rows[stroke_index]
            if stroke_index < len(normalized_stroke_rows)
            else None
        )
        if explicit_row_number:
            row_index = explicit_row_number - 1
        else:
            average_y = sum(point["y"] * image_height for point in stroke) / len(stroke)
            row_index = int((average_y - ANSWER_SHEET_OCR_PADDING_TOP) / ANSWER_SHEET_OCR_ROW_HEIGHT)
            row_index = max(0, min(row_count - 1, row_index))
        row_buckets[row_index].append(stroke)

    return row_buckets


def _build_answer_sheet_ink_transcription_image_data_url(ink_strokes, *, row_count=10):
    normalized_strokes = _normalize_answer_sheet_ink_strokes(ink_strokes)
    row_count = max(10, int(row_count or 10))
    image_height = _get_answer_sheet_ocr_image_height(row_count)
    image = Image.new("RGB", (ANSWER_SHEET_OCR_IMAGE_WIDTH, image_height), "white")
    draw = ImageDraw.Draw(image)

    guide_left = ANSWER_SHEET_OCR_SIDE_PADDING
    guide_right = ANSWER_SHEET_OCR_IMAGE_WIDTH - ANSWER_SHEET_OCR_SIDE_PADDING
    for row_index in range(row_count):
        guide_y = (
            ANSWER_SHEET_OCR_PADDING_TOP
            + ((row_index + 1) * ANSWER_SHEET_OCR_ROW_HEIGHT)
            - ANSWER_SHEET_OCR_GUIDE_INSET
        )
        draw.line(
            [(guide_left, guide_y), (guide_right, guide_y)],
            fill=(206, 214, 224),
            width=1,
        )

    drawable_width = ANSWER_SHEET_OCR_IMAGE_WIDTH - (2 * ANSWER_SHEET_OCR_SIDE_PADDING)
    for stroke in normalized_strokes:
        if not stroke:
            continue
        points = [
            (
                ANSWER_SHEET_OCR_SIDE_PADDING + (point["x"] * drawable_width),
                point["y"] * image_height,
            )
            for point in stroke
        ]
        if len(points) == 1:
            point_x, point_y = points[0]
            radius = max(ANSWER_SHEET_OCR_STROKE_WIDTH // 2, 2)
            draw.ellipse(
                [
                    (point_x - radius, point_y - radius),
                    (point_x + radius, point_y + radius),
                ],
                fill="black",
            )
            continue
        draw.line(points, fill="black", width=ANSWER_SHEET_OCR_STROKE_WIDTH, joint="curve")

    image_buffer = BytesIO()
    image.save(image_buffer, format="PNG")
    encoded_image = base64.b64encode(image_buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded_image}"


def _build_answer_sheet_ink_row_image_data_urls(ink_strokes, *, row_count=10, stroke_rows=None):
    normalized_strokes = _normalize_answer_sheet_ink_strokes(ink_strokes)
    row_count = max(10, int(row_count or 10))
    if not normalized_strokes:
        return {}

    row_buckets = _group_answer_sheet_ink_strokes_by_row(
        normalized_strokes,
        row_count=row_count,
        stroke_rows=stroke_rows,
    )
    full_image_height = _get_answer_sheet_ocr_image_height(row_count)
    drawable_width = ANSWER_SHEET_OCR_IMAGE_WIDTH - (2 * ANSWER_SHEET_OCR_SIDE_PADDING)
    row_image_height = (
        ANSWER_SHEET_OCR_PADDING_TOP
        + ANSWER_SHEET_OCR_PADDING_BOTTOM
        + ANSWER_SHEET_OCR_ROW_HEIGHT
    )
    row_image_urls = {}

    for row_index, row_strokes in row_buckets.items():
        if not row_strokes:
            continue

        image = Image.new("RGB", (ANSWER_SHEET_OCR_IMAGE_WIDTH, row_image_height), "white")
        draw = ImageDraw.Draw(image)
        guide_y = ANSWER_SHEET_OCR_PADDING_TOP + ANSWER_SHEET_OCR_ROW_HEIGHT - ANSWER_SHEET_OCR_GUIDE_INSET
        draw.line(
            [
                (ANSWER_SHEET_OCR_SIDE_PADDING, guide_y),
                (ANSWER_SHEET_OCR_IMAGE_WIDTH - ANSWER_SHEET_OCR_SIDE_PADDING, guide_y),
            ],
            fill=(206, 214, 224),
            width=1,
        )

        row_top = ANSWER_SHEET_OCR_PADDING_TOP + (row_index * ANSWER_SHEET_OCR_ROW_HEIGHT)
        for stroke in row_strokes:
            points = [
                (
                    ANSWER_SHEET_OCR_SIDE_PADDING + (point["x"] * drawable_width),
                    (point["y"] * full_image_height) - row_top + ANSWER_SHEET_OCR_PADDING_TOP,
                )
                for point in stroke
            ]
            if len(points) == 1:
                point_x, point_y = points[0]
                radius = max(ANSWER_SHEET_OCR_STROKE_WIDTH // 2, 2)
                draw.ellipse(
                    [
                        (point_x - radius, point_y - radius),
                        (point_x + radius, point_y + radius),
                    ],
                    fill="black",
                )
                continue
            draw.line(points, fill="black", width=ANSWER_SHEET_OCR_STROKE_WIDTH, joint="curve")

        image_buffer = BytesIO()
        image.save(image_buffer, format="PNG")
        row_image_urls[row_index + 1] = (
            f"data:image/png;base64,{base64.b64encode(image_buffer.getvalue()).decode('ascii')}"
        )

    return row_image_urls


def _transcribe_answer_sheet_ink_strokes_to_lines(ink_strokes, *, row_count=10, round_title='', stroke_rows=None):
    normalized_strokes = _normalize_answer_sheet_ink_strokes(ink_strokes)
    row_count = max(10, int(row_count or 10))
    if not normalized_strokes:
        return [''] * row_count

    from .round_analysis import _parse_openai_json_response

    row_image_urls = _build_answer_sheet_ink_row_image_data_urls(
        normalized_strokes,
        row_count=row_count,
        stroke_rows=stroke_rows,
    )
    if not row_image_urls:
        return [''] * row_count

    instructions = (
        "Transcribe handwritten trivia answers from separate lined answer-row images. "
        "Return strict JSON with exactly one key named lines_by_row whose value is an object. "
        "Each key must be a row number as a string and each value must be that row's transcription. "
        "Only include the provided row numbers. Do not renumber or collapse rows. "
        "Do not add numbering, commentary, markdown, or extra keys. "
        "Preserve the handwritten wording as best you can in plain text. "
        "If handwriting is ambiguous, make the best short plain-text guess."
    )
    input_payload = {
        'row_count': row_count,
        'round_title': str(round_title or '').strip(),
        'provided_rows': sorted(row_image_urls.keys()),
    }
    content_items = [
        {
            'type': 'input_text',
            'text': json.dumps(input_payload, ensure_ascii=True),
        },
    ]
    for row_number in sorted(row_image_urls.keys()):
        content_items.append({
            'type': 'input_text',
            'text': f'Row {row_number}',
        })
        content_items.append({
            'type': 'input_image',
            'image_url': row_image_urls[row_number],
        })

    response_text = _create_openai_text_response(
        _get_openai_client(),
        instructions=instructions,
        input_items=[
            {
                'role': 'user',
                'content': content_items,
            }
        ],
        max_output_tokens=1200,
        reasoning_effort="low",
    )
    parsed_payload = _parse_openai_json_response(response_text)
    if not isinstance(parsed_payload, dict) or not isinstance(parsed_payload.get('lines_by_row'), dict):
        raise RuntimeError(f"Could not parse handwritten transcription JSON: {response_text}")

    normalized_lines = [''] * row_count
    for raw_row_number, raw_line in parsed_payload['lines_by_row'].items():
        try:
            row_number = int(str(raw_row_number).strip())
        except (TypeError, ValueError):
            continue
        if row_number < 1 or row_number > row_count or row_number not in row_image_urls:
            continue
        normalized_lines[row_number - 1] = str(raw_line or '').strip()
    return normalized_lines


def _normalize_answer_sheet_score(raw_score):
    score_text = str(raw_score or '').strip()
    if score_text == '':
        return None

    try:
        parsed_score = float(score_text)
    except (TypeError, ValueError):
        raise ValueError('score must be numeric.')

    if parsed_score.is_integer():
        return int(parsed_score)
    return parsed_score


def _normalize_answer_sheet_grade_overrides(raw_overrides):
    normalized_overrides = []
    seen = set()
    for raw_override in raw_overrides or []:
        try:
            question_number = int(raw_override)
        except (TypeError, ValueError):
            continue
        if question_number <= 0 or question_number in seen:
            continue
        seen.add(question_number)
        normalized_overrides.append(question_number)
    return normalized_overrides


def _serialize_answer_sheet_entry_state(answer_entry):
    if answer_entry is None:
        return {
            'input_mode': AnswerSheetEntry.INPUT_MODE_TEXT,
            'ink_strokes': [],
            'pencil_answers': [''] * 10,
        }
    return {
        'input_mode': _normalize_answer_sheet_input_mode(getattr(answer_entry, 'input_mode', '')),
        'ink_strokes': _normalize_answer_sheet_ink_strokes(getattr(answer_entry, 'ink_strokes', [])),
        'pencil_answers': _normalize_answer_sheet_answers(getattr(answer_entry, 'pencil_answers', [])),
    }


def _get_answer_sheet_grade_answers(answer_entry):
    if answer_entry is None:
        return [''] * 10
    entry_state = _serialize_answer_sheet_entry_state(answer_entry)
    if entry_state['input_mode'] == AnswerSheetEntry.INPUT_MODE_PENCIL:
        return entry_state['pencil_answers']
    return _normalize_answer_sheet_answers(getattr(answer_entry, 'answers', []))


def _get_changed_answer_sheet_questions(previous_answers, next_answers):
    normalized_previous = list(previous_answers or [])
    normalized_next = list(next_answers or [])
    changed_questions = []
    for index in range(max(len(normalized_previous), len(normalized_next))):
        previous_value = normalized_previous[index] if index < len(normalized_previous) else ''
        next_value = normalized_next[index] if index < len(normalized_next) else ''
        if str(previous_value or '') != str(next_value or ''):
            changed_questions.append(index + 1)
    return changed_questions


def _clear_answer_sheet_grade_marks_for_changed_answers(previous_answers, next_answers, existing_marks):
    changed_questions = set(_get_changed_answer_sheet_questions(previous_answers, next_answers))
    return [
        question_number
        for question_number in _normalize_answer_sheet_grade_overrides(existing_marks)
        if question_number not in changed_questions
    ]


def _clear_answer_sheet_overrides_for_changed_answers(previous_answers, next_answers, existing_overrides):
    return _clear_answer_sheet_grade_marks_for_changed_answers(
        previous_answers,
        next_answers,
        existing_overrides,
    )


def _normalize_answer_sheet_grade_value(raw_value):
    normalized_value = str(raw_value or '').casefold()
    normalized_value = normalized_value.replace('&', ' and ')
    normalized_value = re.sub(r"[’']", '', normalized_value)
    normalized_value = re.sub(r'[^0-9a-z]+', ' ', normalized_value)
    normalized_value = re.sub(r'\s+', ' ', normalized_value)
    return normalized_value.strip()


def _build_answer_sheet_invalidated_questions(previous_answers, next_answers, existing_invalidated_questions, *, was_graded=False):
    if not was_graded:
        return []

    merged_questions = [
        *_normalize_answer_sheet_grade_overrides(existing_invalidated_questions),
        *_get_changed_answer_sheet_questions(previous_answers, next_answers),
    ]
    return _normalize_answer_sheet_grade_overrides(merged_questions)


def _strip_answer_sheet_leading_article(value):
    normalized_value = _normalize_answer_sheet_grade_value(value)
    return re.sub(r'^(?:a|an|the)\s+', '', normalized_value, flags=re.IGNORECASE)


def _answer_sheet_initialism(value):
    normalized_value = _normalize_answer_sheet_grade_value(value)
    if not normalized_value:
        return ''
    tokens = [
        token for token in normalized_value.split()
        if token and token not in {'a', 'an', 'the', 'of', 'and'}
    ]
    if len(tokens) < 2:
        return ''
    initialism = ''.join(token[0] for token in tokens if token)
    if len(initialism) < 2 or len(initialism) > 5:
        return ''
    return initialism


def _answer_sheet_grade_forms(raw_value):
    normalized_value = _normalize_answer_sheet_grade_value(raw_value)
    if not normalized_value:
        return set()

    forms = {normalized_value}
    articleless_value = _strip_answer_sheet_leading_article(normalized_value)
    if articleless_value:
        forms.add(articleless_value)

    compact_forms = {form.replace(' ', '') for form in list(forms) if form}
    forms.update(form for form in compact_forms if form)

    initialism = _answer_sheet_initialism(normalized_value)
    if initialism:
        forms.add(initialism)

    return {form for form in forms if form}


def _answer_sheet_edit_distance(left_value, right_value):
    if left_value == right_value:
        return 0
    if not left_value:
        return len(right_value)
    if not right_value:
        return len(left_value)
    if len(left_value) > len(right_value):
        left_value, right_value = right_value, left_value

    previous_row = list(range(len(left_value) + 1))
    for right_index, right_char in enumerate(right_value, start=1):
        current_row = [right_index]
        for left_index, left_char in enumerate(left_value, start=1):
            insertion_cost = current_row[left_index - 1] + 1
            deletion_cost = previous_row[left_index] + 1
            substitution_cost = previous_row[left_index - 1] + (0 if left_char == right_char else 1)
            current_row.append(min(insertion_cost, deletion_cost, substitution_cost))
        previous_row = current_row
    return previous_row[-1]


def _parse_answer_sheet_numeric_value(raw_value):
    numeric_text = str(raw_value or '').strip()
    if not numeric_text:
        return None
    numeric_text = numeric_text.replace(',', '').replace('−', '-')
    if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d+)?|\.\d+)', numeric_text):
        return None
    try:
        return Decimal(numeric_text)
    except (InvalidOperation, ValueError):
        return None


def _extract_answer_sheet_numeric_tolerance(raw_value):
    tolerance_text = str(raw_value or '').strip()
    if not tolerance_text:
        return None
    tolerance_text = (
        tolerance_text
        .replace(',', '')
        .replace('−', '-')
        .replace('±', '+/-')
        .replace('+/−', '+/-')
    )
    tolerance_match = re.fullmatch(
        r'\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*\+/-\s*([+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*',
        tolerance_text,
    )
    if not tolerance_match:
        return None
    center_value = _parse_answer_sheet_numeric_value(tolerance_match.group(1))
    tolerance_value = _parse_answer_sheet_numeric_value(tolerance_match.group(2))
    if center_value is None or tolerance_value is None:
        return None
    return center_value, abs(tolerance_value)


def _answer_sheet_numeric_forms_match(raw_guess, raw_accepted_candidates):
    guess_numeric_value = _parse_answer_sheet_numeric_value(raw_guess)
    if guess_numeric_value is None:
        return False

    for raw_candidate in raw_accepted_candidates or []:
        parsed_tolerance = _extract_answer_sheet_numeric_tolerance(raw_candidate)
        if not parsed_tolerance:
            continue
        center_value, tolerance_value = parsed_tolerance
        if center_value - tolerance_value <= guess_numeric_value <= center_value + tolerance_value:
            return True

    return False


def _answer_sheet_word_level_typo_match(guess_form, accepted_form):
    if not guess_form or not accepted_form:
        return False

    guess_tokens = [token for token in guess_form.split() if token]
    accepted_tokens = [token for token in accepted_form.split() if token]
    if not guess_tokens or len(guess_tokens) != len(accepted_tokens):
        return False

    has_typo_match = False
    for guess_token, accepted_token in zip(guess_tokens, accepted_tokens):
        if guess_token == accepted_token:
            continue
        if (
            _parse_answer_sheet_numeric_value(guess_token) is not None
            or _parse_answer_sheet_numeric_value(accepted_token) is not None
        ):
            return False
        if len(guess_token) < 5 or len(accepted_token) < 5:
            return False
        if abs(len(guess_token) - len(accepted_token)) > 1:
            return False
        if _answer_sheet_edit_distance(guess_token, accepted_token) > 1:
            return False
        has_typo_match = True

    return has_typo_match


def _answer_sheet_fuzzy_forms(raw_value):
    normalized_value = _normalize_answer_sheet_grade_value(raw_value)
    if not normalized_value:
        return []

    fuzzy_forms = [normalized_value]
    articleless_value = _strip_answer_sheet_leading_article(raw_value)
    if articleless_value and articleless_value not in fuzzy_forms:
        fuzzy_forms.append(articleless_value)
    return fuzzy_forms


def _answer_sheet_forms_match(guess_forms, accepted_forms, *, raw_guess='', raw_accepted_candidates=None):
    if not guess_forms or not accepted_forms:
        return False
    if guess_forms.intersection(accepted_forms):
        return True
    if raw_guess and raw_accepted_candidates and _answer_sheet_numeric_forms_match(raw_guess, raw_accepted_candidates):
        return True

    if not raw_guess or not raw_accepted_candidates:
        return False

    for guess_form in _answer_sheet_fuzzy_forms(raw_guess):
        if not guess_form:
            continue
        for raw_candidate in raw_accepted_candidates:
            for accepted_form in _answer_sheet_fuzzy_forms(raw_candidate):
                if not accepted_form:
                    continue
                if _answer_sheet_word_level_typo_match(guess_form, accepted_form):
                    return True
    return False


def _extract_answer_sheet_line_answer(line_text):
    normalized_line = str(line_text or '').replace('\r\n', '\n').replace('\r', '\n')
    match = re.search(r'\S.*?(?=\s{3,}|$)', normalized_line)
    if not match:
        return ''
    return match.group(0).strip()


def _build_answer_sheet_accepted_answers(entry):
    from .round_analysis import (
        _build_possible_answers_with_aliases,
        _derive_matching_position_aliases,
        _derive_multiple_choice_position_aliases,
        _normalize_round_type_label,
    )

    accepted_answers = []
    additional_candidates = list(entry.possible_answers or [])
    normalized_round_type = _normalize_round_type_label(getattr(entry, 'round_type', '') or '')
    if normalized_round_type == 'multiple choice':
        additional_candidates.extend(_derive_multiple_choice_position_aliases({
            'question_text': entry.question_text,
            'instruction_text': '',
            'answer_text': entry.answer_text,
        }))
    elif normalized_round_type == 'matching':
        additional_candidates.extend(_derive_matching_position_aliases({
            'question_text': entry.question_text,
            'instruction_text': '',
            'answer_text': entry.answer_text,
        }))
    for candidate in _build_possible_answers_with_aliases(
        entry.answer_text,
        additional_candidates,
        question_text=entry.question_text,
    ):
        for normalized_candidate in _answer_sheet_grade_forms(candidate):
            if normalized_candidate and normalized_candidate not in accepted_answers:
                accepted_answers.append(normalized_candidate)
    return accepted_answers


def _build_answer_sheet_raw_answer_candidates(entry):
    raw_candidates = []
    for candidate in [getattr(entry, 'answer_text', ''), *(list(getattr(entry, 'possible_answers', []) or []))]:
        normalized_candidate = str(candidate or '').strip()
        if normalized_candidate and normalized_candidate not in raw_candidates:
            raw_candidates.append(normalized_candidate)
    return raw_candidates


def _has_answer_sheet_saved_grade_state(answer_entry):
    if answer_entry is None:
        return False
    return bool(
        getattr(answer_entry, 'was_graded', False)
        or _normalize_answer_sheet_grade_overrides(getattr(answer_entry, 'grade_overrides', []))
        or _normalize_answer_sheet_grade_overrides(getattr(answer_entry, 'grade_rejections', []))
        or _normalize_answer_sheet_grade_overrides(getattr(answer_entry, 'grade_invalidated_questions', []))
    )


def _build_saved_answer_sheet_grade_payload(round_obj, answer_entry):
    if answer_entry is None or not _has_answer_sheet_saved_grade_state(answer_entry):
        return None
    try:
        return _grade_answer_sheet_answers(
            round_obj,
            _get_answer_sheet_grade_answers(answer_entry),
            manual_correct_questions=answer_entry.grade_overrides,
            manual_incorrect_questions=answer_entry.grade_rejections,
            invalidated_questions=getattr(answer_entry, 'grade_invalidated_questions', []),
        )
    except ValueError:
        return None


def _promote_answer_sheet_overrides_to_possible_answers(round_obj, answer_entry):
    from .round_analysis import _build_possible_answers_with_aliases

    if not round_obj or not answer_entry:
        return 0

    overridden_questions = _normalize_answer_sheet_grade_overrides(answer_entry.grade_overrides)
    if not overridden_questions:
        return 0

    latest_completed_run = _latest_completed_round_analysis_run(round_obj.id)
    if latest_completed_run is None:
        return 0

    analysis_entries_by_question = {
        entry.question_number: entry
        for entry in RoundQuestionAnalysisEntry.objects.filter(run=latest_completed_run).order_by('question_number', 'id')
    }
    normalized_answers = _get_answer_sheet_grade_answers(answer_entry)
    updated_entry_count = 0

    for question_number in overridden_questions:
        if question_number <= 0 or question_number > len(normalized_answers):
            continue
        analysis_entry = analysis_entries_by_question.get(question_number)
        if analysis_entry is None:
            continue

        accepted_answer_text = _extract_answer_sheet_line_answer(normalized_answers[question_number - 1])
        if not accepted_answer_text:
            continue

        merged_possible_answers = []
        seen_possible_answers = set()
        for candidate in [
            *(analysis_entry.possible_answers or []),
            *_build_possible_answers_with_aliases(
                accepted_answer_text,
                [],
                question_text=analysis_entry.question_text,
            ),
        ]:
            normalized_candidate = str(candidate or '').strip()
            if not normalized_candidate or normalized_candidate in seen_possible_answers:
                continue
            seen_possible_answers.add(normalized_candidate)
            merged_possible_answers.append(normalized_candidate)

        if merged_possible_answers == list(analysis_entry.possible_answers or []):
            continue

        analysis_entry.possible_answers = merged_possible_answers
        analysis_entry.save(update_fields=['possible_answers'])
        updated_entry_count += 1

    return updated_entry_count


def _remove_answer_sheet_rejections_from_possible_answers(round_obj, answer_entry):
    from .round_analysis import _build_possible_answers_with_aliases

    if not round_obj or not answer_entry:
        return 0

    rejected_questions = _normalize_answer_sheet_grade_overrides(answer_entry.grade_rejections)
    if not rejected_questions:
        return 0

    latest_completed_run = _latest_completed_round_analysis_run(round_obj.id)
    if latest_completed_run is None:
        return 0

    analysis_entries_by_question = {
        entry.question_number: entry
        for entry in RoundQuestionAnalysisEntry.objects.filter(run=latest_completed_run).order_by('question_number', 'id')
    }
    normalized_answers = _get_answer_sheet_grade_answers(answer_entry)
    updated_entry_count = 0

    for question_number in rejected_questions:
        if question_number <= 0 or question_number > len(normalized_answers):
            continue
        analysis_entry = analysis_entries_by_question.get(question_number)
        if analysis_entry is None:
            continue

        rejected_answer_text = _extract_answer_sheet_line_answer(normalized_answers[question_number - 1])
        if not rejected_answer_text:
            continue

        removal_candidates = {
            str(candidate or '').strip()
            for candidate in _build_possible_answers_with_aliases(
                rejected_answer_text,
                [],
                question_text=analysis_entry.question_text,
            )
            if str(candidate or '').strip()
        }
        if not removal_candidates:
            continue

        next_possible_answers = [
            candidate
            for candidate in list(analysis_entry.possible_answers or [])
            if str(candidate or '').strip() not in removal_candidates
        ]
        if next_possible_answers == list(analysis_entry.possible_answers or []):
            continue

        analysis_entry.possible_answers = next_possible_answers
        analysis_entry.save(update_fields=['possible_answers'])
        updated_entry_count += 1

    return updated_entry_count


def _grade_answer_sheet_answers(
    round_obj,
    answers,
    manual_correct_questions=None,
    manual_incorrect_questions=None,
    invalidated_questions=None,
):
    latest_completed_run = _latest_completed_round_analysis_run(round_obj.id)
    if latest_completed_run is None:
        raise ValueError("the round has not yet been analyzed")

    entries_by_question = {
        entry.question_number: entry
        for entry in RoundQuestionAnalysisEntry.objects.filter(run=latest_completed_run).order_by('question_number', 'id')
    }
    normalized_answers = [str(answer or '') for answer in (answers or [])]
    manual_correct_question_set = set(_normalize_answer_sheet_grade_overrides(manual_correct_questions))
    manual_incorrect_question_set = set(_normalize_answer_sheet_grade_overrides(manual_incorrect_questions))
    invalidated_question_set = set(_normalize_answer_sheet_grade_overrides(invalidated_questions))
    row_results = []
    correct_count = 0

    for index, raw_line in enumerate(normalized_answers, start=1):
        extracted_answer = _extract_answer_sheet_line_answer(raw_line)
        normalized_guess_forms = _answer_sheet_grade_forms(extracted_answer)
        entry = entries_by_question.get(index)
        accepted_answers = _build_answer_sheet_accepted_answers(entry) if entry else []
        raw_accepted_candidates = _build_answer_sheet_raw_answer_candidates(entry) if entry else []

        if not normalized_guess_forms or not entry:
            state = 'blank'
        elif index in manual_incorrect_question_set:
            state = 'incorrect'
        elif index in manual_correct_question_set:
            state = 'correct'
            correct_count += 1
        elif index in invalidated_question_set:
            state = 'default'
        elif _answer_sheet_forms_match(
            normalized_guess_forms,
            set(accepted_answers),
            raw_guess=extracted_answer,
            raw_accepted_candidates=raw_accepted_candidates,
        ):
            state = 'correct'
            correct_count += 1
        else:
            state = 'incorrect'

        row_results.append({
            'question_number': index,
            'submitted_text': extracted_answer,
            'state': state,
            'answer_text': entry.answer_text if entry else '',
            'possible_answers': list(entry.possible_answers or []) if entry else [],
            'manually_overridden': bool(index in manual_correct_question_set),
            'manually_rejected': bool(index in manual_incorrect_question_set),
            'invalidated': bool(index in invalidated_question_set),
        })

    return {
        'row_results': row_results,
        'score': correct_count,
        'score_display': _format_profile_round_score(correct_count),
        'grade_overrides': sorted(manual_correct_question_set),
        'grade_rejections': sorted(manual_incorrect_question_set),
        'grade_invalidated_questions': sorted(invalidated_question_set),
    }


def _get_answer_sheet_round_player_fields(round_obj, current_user_player_field=''):
    player_fields = []
    if getattr(round_obj, 'date', None):
        presentation = _get_scoresheet_presentation(selected_date=round_obj.date.isoformat())
        if presentation:
            player_fields.extend(normalize_player_list(getattr(presentation, 'player_list', None)))

    player_fields.extend(get_round_score_map(round_obj, include_null_fixed=False).keys())
    if current_user_player_field:
        player_fields.append(current_user_player_field)

    normalized = []
    seen = set()
    for player_field in player_fields:
        normalized_field = player_field_for_name(player_field)
        if not normalized_field or normalized_field in seen:
            continue
        seen.add(normalized_field)
        normalized.append(normalized_field)
    return normalized


def _get_answer_sheet_shared_users(round_obj, current_user=None):
    current_user_player_field = player_field_for_name(getattr(current_user, 'username', '')) if current_user else ''
    candidate_names = [
        display_name_for_player_field(player_field)
        for player_field in _get_answer_sheet_round_player_fields(
            round_obj,
            current_user_player_field=current_user_player_field,
        )
    ]
    candidate_names.extend([
        str(getattr(round_obj, 'creator', '') or '').strip(),
        str(getattr(round_obj, 'secondary_creator', '') or '').strip(),
    ])
    candidate_names.extend(
        str(username or '').strip()
        for username in AnswerSheetEntry.objects.filter(round=round_obj)
        .select_related('user')
        .values_list('user__username', flat=True)
    )
    if current_user and getattr(current_user, 'is_authenticated', False):
        candidate_names.append(str(current_user.username or '').strip())

    normalized_names = []
    seen_names = set()
    for candidate_name in candidate_names:
        normalized_name = str(candidate_name or '').strip()
        if not normalized_name:
            continue
        folded_name = normalized_name.casefold()
        if folded_name in seen_names:
            continue
        seen_names.add(folded_name)
        normalized_names.append(normalized_name)

    if not normalized_names:
        return [current_user] if current_user and getattr(current_user, 'is_authenticated', False) else []

    users_by_username = {
        user.username.casefold(): user
        for user in User.objects.only('id', 'username')
        if str(user.username or '').strip()
    }
    shared_users = []
    seen_user_ids = set()
    for candidate_name in normalized_names:
        matched_user = users_by_username.get(candidate_name.casefold())
        if not matched_user or matched_user.id in seen_user_ids:
            continue
        seen_user_ids.add(matched_user.id)
        shared_users.append(matched_user)

    if current_user and getattr(current_user, 'is_authenticated', False) and current_user.id not in seen_user_ids:
        shared_users.append(current_user)
    return shared_users


def _get_answer_sheet_diverged_user_ids(round_obj):
    return set(
        AnswerSheetEntry.objects.filter(round=round_obj, is_diverged=True)
        .values_list('user_id', flat=True)
    )


def _get_answer_sheet_diverged_player_fields(round_obj):
    diverged_fields = set()
    for username in User.objects.filter(
        id__in=_get_answer_sheet_diverged_user_ids(round_obj)
    ).values_list('username', flat=True):
        normalized_field = player_field_for_name(username)
        if normalized_field:
            diverged_fields.add(normalized_field)
    return diverged_fields


def _answer_sheet_user_is_round_creator(user, round_obj):
    if not user or not getattr(user, 'is_authenticated', False) or not round_obj:
        return False
    player_field = player_field_for_name(getattr(user, 'username', ''))
    if not player_field:
        return False
    return _profile_player_matches_any_creator(
        player_field,
        getattr(round_obj, 'creator', ''),
        getattr(round_obj, 'secondary_creator', ''),
    )


def _get_answer_sheet_communal_score_display(round_obj):
    score_map = get_round_score_map(round_obj, include_null_fixed=False)
    creator_fields = {
        normalized_field
        for normalized_field in (
            player_field_for_name(getattr(round_obj, 'creator', '')),
            player_field_for_name(getattr(round_obj, 'secondary_creator', '')),
        )
        if normalized_field
    }
    communal_fields = [
        candidate_field
        for candidate_field in _get_answer_sheet_round_player_fields(round_obj)
        if candidate_field not in creator_fields and candidate_field not in _get_answer_sheet_diverged_player_fields(round_obj)
    ]
    for candidate_field in communal_fields:
        candidate_score = score_map.get(candidate_field)
        if candidate_score is not None:
            return _format_profile_round_score(candidate_score)
    return ''


def _get_answer_sheet_display_score(round_obj, user, current_user_player_field=''):
    score_map = get_round_score_map(round_obj, include_null_fixed=False)
    current_score = score_map.get(current_user_player_field) if current_user_player_field else None
    if current_score is not None:
        return _format_profile_round_score(current_score)
    if round_obj.cooperative and _answer_sheet_user_is_round_creator(user, round_obj):
        return _get_answer_sheet_communal_score_display(round_obj)
    return ''


def _get_answer_sheet_date_values():
    return sorted({
        round_date.isoformat()
        for round_date in GPTriviaRound.objects.order_by().values_list('date', flat=True).distinct()
        if round_date
    }, reverse=True)


def _build_answer_sheet_context(user, requested_date=''):
    date_values = _get_answer_sheet_date_values()
    parsed_requested_date = _parse_scoresheet_date(requested_date)
    selected_date_obj = (
        parsed_requested_date
        if parsed_requested_date
        else (_parse_scoresheet_date(date_values[0]) if date_values else None)
    )
    selected_date = (
        selected_date_obj.isoformat()
        if selected_date_obj
        else (date_values[0] if date_values else '')
    )
    selected_rounds = list(
        GPTriviaRound.objects.filter(date=selected_date).order_by('round_number', 'id')
    ) if selected_date else []
    creator_opt_in_map = _build_round_analysis_opt_in_map([round_obj.creator for round_obj in selected_rounds])
    latest_completed_run_by_round_id = {}
    for run in (
        RoundQuestionAnalysisRun.objects.filter(
            round_id__in=[round_obj.id for round_obj in selected_rounds],
            status=RoundQuestionAnalysisRun.STATUS_COMPLETED,
        )
        .select_related('round')
        .order_by('round_id', '-created_at', '-id')
    ):
        latest_completed_run_by_round_id.setdefault(run.round_id, run)
    saved_entries = {
        entry.round_id: entry
        for entry in AnswerSheetEntry.objects.filter(user=user, round_id__in=[round_obj.id for round_obj in selected_rounds])
    }
    current_user_player_field = player_field_for_name(getattr(user, 'username', ''))

    round_pages = []
    for round_obj in selected_rounds:
        saved_entry = saved_entries.get(round_obj.id)
        round_state = _serialize_answer_sheet_sync_round(
            round_obj,
            user,
            current_entry=saved_entry,
            current_user_player_field=current_user_player_field,
        )
        creator_allows_analysis = bool(creator_opt_in_map.get(round_obj.creator, False))
        latest_completed_run = latest_completed_run_by_round_id.get(round_obj.id)
        user_is_round_creator = _answer_sheet_user_is_round_creator(user, round_obj)
        round_creator_display = display_name_for_player_field(round_obj.creator)
        round_creator_profile_url = (
            reverse('player_profile', kwargs={'player_name': round_creator_display})
            if round_creator_display
            else ''
        )
        grade_enabled = bool(
            creator_allows_analysis
            and latest_completed_run is not None
        )
        if not creator_allows_analysis:
            grade_disabled_message = "round analysis is not enabled for this creator"
        elif latest_completed_run is None:
            grade_disabled_message = "the round has not yet been analyzed"
        else:
            grade_disabled_message = ''
        round_pages.append({
            'round_id': round_obj.id,
            'round_number': round_obj.round_number,
            'round_title': round_obj.title,
            'round_creator': round_obj.creator,
            'round_creator_display': round_creator_display,
            'round_creator_profile_url': round_creator_profile_url,
            'round_creator_color': get_player_color(round_creator_display),
            'cooperative': bool(round_obj.cooperative),
            'is_diverged': bool(round_state['is_diverged']),
            'submit_requires_confirmation': bool(
                round_obj.cooperative
                and not bool(round_state['is_diverged'])
                and not user_is_round_creator
            ),
            'show_diverge': bool(round_obj.cooperative and not user_is_round_creator),
            'grade_enabled': grade_enabled,
            'grade_disabled_message': grade_disabled_message,
            'answers': round_state['answers'],
            'answers_text': '\n'.join(round_state['answers']),
            'grade_overrides': _normalize_answer_sheet_grade_overrides(saved_entry.grade_overrides if saved_entry else []),
            'grade_rejections': _normalize_answer_sheet_grade_overrides(saved_entry.grade_rejections if saved_entry else []),
            'grade_invalidated_questions': _normalize_answer_sheet_grade_overrides(saved_entry.grade_invalidated_questions if saved_entry else []),
            'was_graded': bool(saved_entry.was_graded) if saved_entry else False,
            'score_value': round_state['score_value'],
            'input_mode': round_state['input_mode'],
            'ink_strokes': round_state['ink_strokes'],
            'ink_strokes_json': json.dumps(round_state['ink_strokes'], cls=DjangoJSONEncoder),
        })

    return {
        'date_values': date_values,
        'selected_date': selected_date,
        'selected_date_display': selected_date_obj.strftime('%m/%d/%y') if selected_date_obj else '',
        'current_user_player_field': current_user_player_field,
        'round_pages': round_pages,
        'has_cooperative_rounds': any(page['cooperative'] for page in round_pages),
        'save_url': reverse('save_answer_sheet_entry'),
        'submit_score_url': reverse('submit_answer_sheet_score'),
        'grade_url': reverse('grade_answer_sheet_round'),
        'override_grade_url': reverse('override_answer_sheet_grade'),
        'diverge_url': reverse('diverge_answer_sheet_round'),
        'merge_url': reverse('merge_answer_sheet_round'),
        'sync_url': reverse('answer_sheet_sync'),
    }


@login_required
@ensure_csrf_cookie
def answer_sheet(request):
    requested_date = (request.GET.get('date') or '').strip()
    return render(
        request,
        'GPTrivia/answer_sheet.html',
        _build_answer_sheet_context(request.user, requested_date=requested_date),
    )


@login_required
def answer_sheet_sync(request):
    requested_date = (request.GET.get('date') or '').strip()
    if requested_date and not _parse_scoresheet_date(requested_date):
        return JsonResponse({'detail': 'date must be a valid YYYY-MM-DD value.'}, status=400)

    date_values = _get_answer_sheet_date_values()
    selected_date_obj = (
        _parse_scoresheet_date(requested_date)
        if requested_date
        else (_parse_scoresheet_date(date_values[0]) if date_values else None)
    )
    selected_date = selected_date_obj.isoformat() if selected_date_obj else ''
    selected_rounds = list(
        GPTriviaRound.objects.filter(date=selected_date).order_by('round_number', 'id')
    ) if selected_date else []
    saved_entries = {
        entry.round_id: entry
        for entry in AnswerSheetEntry.objects.filter(user=request.user, round_id__in=[round_obj.id for round_obj in selected_rounds])
    }
    current_user_player_field = player_field_for_name(getattr(request.user, 'username', ''))

    return JsonResponse({
        'ok': True,
        'selected_date': selected_date,
        'rounds': [
            _serialize_answer_sheet_sync_round(
                round_obj,
                request.user,
                current_entry=saved_entries.get(round_obj.id),
                current_user_player_field=current_user_player_field,
            )
            for round_obj in selected_rounds
        ],
    })


@login_required
def save_answer_sheet_entry(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed.'}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'detail': 'Invalid JSON payload.'}, status=400)

    round_id = payload.get('round_id')
    try:
        round_id = int(round_id)
    except (TypeError, ValueError):
        return JsonResponse({'detail': 'round_id must be an integer.'}, status=400)

    round_obj = get_object_or_404(GPTriviaRound, id=round_id)
    answers = _normalize_answer_sheet_answers(payload.get('answers', []))
    row_count = _answer_sheet_row_count(payload.get('row_count'), payload.get('answers', []))
    edited_row_numbers = _normalize_answer_sheet_grade_overrides(payload.get('edited_row_numbers', []))
    client_id = str(payload.get('client_id') or '').strip()
    current_entry = AnswerSheetEntry.objects.filter(user=request.user, round=round_obj).first()
    current_entry_state = _serialize_answer_sheet_entry_state(current_entry)
    input_mode = (
        _normalize_answer_sheet_input_mode(payload.get('input_mode'))
        if 'input_mode' in payload
        else current_entry_state['input_mode']
    )
    ink_strokes = (
        _normalize_answer_sheet_ink_strokes(payload.get('ink_strokes', []))
        if 'ink_strokes' in payload
        else current_entry_state['ink_strokes']
    )
    current_user_is_diverged = bool(current_entry.is_diverged) if current_entry else False

    target_users = [request.user]
    if round_obj.cooperative:
        if current_user_is_diverged:
            target_users = [request.user]
        else:
            diverged_user_ids = _get_answer_sheet_diverged_user_ids(round_obj)
            target_users = [
                target_user
                for target_user in _get_answer_sheet_shared_users(round_obj, current_user=request.user)
                if target_user.id not in diverged_user_ids
            ]
            if not target_users:
                target_users = [request.user]

    with transaction.atomic():
        updated_entries = {}
        for target_user in target_users:
            previous_entry = AnswerSheetEntry.objects.filter(user=target_user, round=round_obj).first()
            previous_answers = _normalize_answer_sheet_answers(previous_entry.answers if previous_entry else [])
            previous_pencil_answers = _normalize_answer_sheet_answers(
                getattr(previous_entry, 'pencil_answers', []) if previous_entry else []
            )
            previous_was_graded = bool(previous_entry.was_graded) if previous_entry else False
            previous_entry_state = _serialize_answer_sheet_entry_state(previous_entry)
            next_answers = previous_answers if input_mode == AnswerSheetEntry.INPUT_MODE_PENCIL else answers
            next_pencil_answers = previous_pencil_answers
            if input_mode == AnswerSheetEntry.INPUT_MODE_PENCIL and edited_row_numbers:
                next_grade_overrides = _clear_answer_sheet_overrides_for_changed_answers(
                    previous_pencil_answers,
                    previous_pencil_answers,
                    [
                        question_number
                        for question_number in (previous_entry.grade_overrides if previous_entry else [])
                        if question_number not in edited_row_numbers
                    ],
                )
                next_grade_rejections = _clear_answer_sheet_grade_marks_for_changed_answers(
                    previous_pencil_answers,
                    previous_pencil_answers,
                    [
                        question_number
                        for question_number in (previous_entry.grade_rejections if previous_entry else [])
                        if question_number not in edited_row_numbers
                    ],
                )
                next_grade_invalidated_questions = _normalize_answer_sheet_grade_overrides([
                    *(previous_entry.grade_invalidated_questions if previous_entry else []),
                    *edited_row_numbers,
                ])
            else:
                next_grade_overrides = _clear_answer_sheet_overrides_for_changed_answers(
                    previous_answers,
                    next_answers,
                    previous_entry.grade_overrides if previous_entry else [],
                )
                next_grade_rejections = _clear_answer_sheet_grade_marks_for_changed_answers(
                    previous_answers,
                    next_answers,
                    previous_entry.grade_rejections if previous_entry else [],
                )
                next_grade_invalidated_questions = _build_answer_sheet_invalidated_questions(
                    previous_answers,
                    next_answers,
                    previous_entry.grade_invalidated_questions if previous_entry else [],
                    was_graded=previous_was_graded,
                )
            answer_entry, _ = AnswerSheetEntry.objects.update_or_create(
                user=target_user,
                round=round_obj,
                defaults={
                    'trivia_date': round_obj.date,
                    'answers': next_answers,
                    'pencil_answers': next_pencil_answers,
                    'input_mode': input_mode,
                    'ink_strokes': ink_strokes,
                    'grade_overrides': next_grade_overrides,
                    'grade_rejections': next_grade_rejections,
                    'grade_invalidated_questions': next_grade_invalidated_questions,
                    'was_graded': previous_was_graded,
                    'is_diverged': bool(current_entry.is_diverged) if (current_entry and target_user.id == request.user.id) else False,
                },
            )
            updated_entries[target_user.id] = answer_entry

        response_entry = updated_entries.get(request.user.id) or next(iter(updated_entries.values()))
        shared_entry = _get_answer_sheet_communal_entry(round_obj, current_user=request.user)
        shared_grade_payload = _build_saved_answer_sheet_grade_payload(round_obj, shared_entry or response_entry)

        _schedule_scoresheet_broadcast({
            'action': 'answer_sheet',
            'event': 'answer_sheet_save',
            'selected_date': round_obj.date.isoformat() if round_obj.date else '',
            'round_id': round_obj.id,
            'client_id': client_id,
            'target_user_ids': [target_user.id for target_user in target_users],
            'answers': response_entry.answers,
            'input_mode': input_mode,
            'ink_strokes': ink_strokes,
            'updated_at': response_entry.updated_at.isoformat() if response_entry.updated_at else '',
            'grade_payload': shared_grade_payload,
            'shared': bool(round_obj.cooperative and not current_user_is_diverged),
            'is_diverged': bool(response_entry.is_diverged),
            'row_count': row_count,
            'transcribed_from_ink': bool(input_mode == AnswerSheetEntry.INPUT_MODE_PENCIL and shared_grade_payload),
        })

    return JsonResponse({
        'ok': True,
        'round_id': round_obj.id,
        'trivia_date': round_obj.date.isoformat() if round_obj.date else '',
        'answers': response_entry.answers,
        'input_mode': _normalize_answer_sheet_input_mode(response_entry.input_mode),
        'ink_strokes': _normalize_answer_sheet_ink_strokes(response_entry.ink_strokes),
        'grade_overrides': _normalize_answer_sheet_grade_overrides(response_entry.grade_overrides),
        'grade_rejections': _normalize_answer_sheet_grade_overrides(response_entry.grade_rejections),
        'grade_invalidated_questions': _normalize_answer_sheet_grade_overrides(response_entry.grade_invalidated_questions),
        'grade_payload': shared_grade_payload,
        'was_graded': bool(response_entry.was_graded),
        'updated_at': response_entry.updated_at.isoformat() if response_entry.updated_at else '',
        'shared': bool(round_obj.cooperative and not current_user_is_diverged),
        'is_diverged': bool(response_entry.is_diverged),
        'transcribed_from_ink': bool(input_mode == AnswerSheetEntry.INPUT_MODE_PENCIL and shared_grade_payload),
    })


@login_required
def diverge_answer_sheet_round(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed.'}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'detail': 'Invalid JSON payload.'}, status=400)

    round_id = payload.get('round_id')
    try:
        round_id = int(round_id)
    except (TypeError, ValueError):
        return JsonResponse({'detail': 'round_id must be an integer.'}, status=400)

    round_obj = get_object_or_404(GPTriviaRound, id=round_id)
    if not round_obj.cooperative:
        return JsonResponse({'detail': 'Only cooperative rounds can diverge.'}, status=400)
    if _answer_sheet_user_is_round_creator(request.user, round_obj):
        return JsonResponse({'detail': 'Round creators cannot diverge cooperative rounds.'}, status=400)

    answers = _normalize_answer_sheet_answers(payload.get('answers', []))
    current_entry = AnswerSheetEntry.objects.filter(user=request.user, round=round_obj).first()
    communal_entry = _get_answer_sheet_communal_entry(round_obj, current_user=request.user)
    source_entry = current_entry or communal_entry
    source_entry_state = _serialize_answer_sheet_entry_state(source_entry)
    input_mode = (
        _normalize_answer_sheet_input_mode(payload.get('input_mode'))
        if 'input_mode' in payload
        else source_entry_state['input_mode']
    )
    ink_strokes = (
        _normalize_answer_sheet_ink_strokes(payload.get('ink_strokes', []))
        if 'ink_strokes' in payload
        else source_entry_state['ink_strokes']
    )
    entry, _ = AnswerSheetEntry.objects.update_or_create(
        user=request.user,
        round=round_obj,
        defaults={
            'trivia_date': round_obj.date,
            'answers': answers,
            'pencil_answers': source_entry_state['pencil_answers'],
            'input_mode': input_mode,
            'ink_strokes': ink_strokes,
            'grade_overrides': _normalize_answer_sheet_grade_overrides(
                source_entry.grade_overrides if source_entry else []
            ),
            'grade_rejections': _normalize_answer_sheet_grade_overrides(
                source_entry.grade_rejections if source_entry else []
            ),
            'grade_invalidated_questions': _normalize_answer_sheet_grade_overrides(
                source_entry.grade_invalidated_questions if source_entry else []
            ),
            'was_graded': bool(source_entry.was_graded) if source_entry else False,
            'is_diverged': True,
        },
    )

    return JsonResponse({
        'ok': True,
        'round_id': round_obj.id,
        'answers': entry.answers,
        'input_mode': _normalize_answer_sheet_input_mode(entry.input_mode),
        'ink_strokes': _normalize_answer_sheet_ink_strokes(entry.ink_strokes),
        'grade_overrides': _normalize_answer_sheet_grade_overrides(entry.grade_overrides),
        'grade_rejections': _normalize_answer_sheet_grade_overrides(entry.grade_rejections),
        'grade_invalidated_questions': _normalize_answer_sheet_grade_overrides(entry.grade_invalidated_questions),
        'grade_payload': _build_saved_answer_sheet_grade_payload(round_obj, entry),
        'was_graded': bool(entry.was_graded),
        'is_diverged': True,
        'shared': False,
    })


def _get_answer_sheet_communal_answers(round_obj, current_user=None):
    communal_entry = _get_answer_sheet_communal_entry(round_obj, current_user=current_user)
    if communal_entry is None:
        return _normalize_answer_sheet_answers([])
    return _normalize_answer_sheet_answers(communal_entry.answers)


def _get_answer_sheet_communal_entry(round_obj, current_user=None):
    diverged_user_ids = _get_answer_sheet_diverged_user_ids(round_obj)
    communal_users = [
        target_user
        for target_user in _get_answer_sheet_shared_users(round_obj, current_user=current_user)
        if target_user.id not in diverged_user_ids
    ]
    communal_user_ids = [target_user.id for target_user in communal_users]
    if not communal_user_ids:
        return None

    return (
        AnswerSheetEntry.objects.filter(
            round=round_obj,
            user_id__in=communal_user_ids,
            is_diverged=False,
        )
        .order_by('-updated_at', '-id')
        .first()
    )


def _serialize_answer_sheet_sync_round(round_obj, user, current_entry=None, current_user_player_field=''):
    communal_entry = _get_answer_sheet_communal_entry(round_obj, current_user=user)
    use_current_entry = bool(
        current_entry
        and (
            not round_obj.cooperative
            or bool(current_entry.is_diverged)
        )
    )
    source_entry = current_entry if use_current_entry else (communal_entry or current_entry)
    source_entry_state = _serialize_answer_sheet_entry_state(source_entry)
    normalized_answers = _normalize_answer_sheet_answers(source_entry.answers if source_entry else [])
    response_payload = {
        'round_id': round_obj.id,
        'answers': normalized_answers,
        'input_mode': source_entry_state['input_mode'],
        'ink_strokes': source_entry_state['ink_strokes'],
        'score_value': _get_answer_sheet_display_score(round_obj, user, current_user_player_field=current_user_player_field),
        'is_diverged': bool(current_entry.is_diverged) if current_entry else False,
        'shared': bool(round_obj.cooperative and not (bool(current_entry.is_diverged) if current_entry else False)),
        'grade_payload': _build_saved_answer_sheet_grade_payload(round_obj, source_entry),
        'transcribed_from_ink': bool(
            source_entry_state['input_mode'] == AnswerSheetEntry.INPUT_MODE_PENCIL
            and _has_answer_sheet_saved_grade_state(source_entry)
        ) if source_entry else False,
    }

    return response_payload


@login_required
def merge_answer_sheet_round(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed.'}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'detail': 'Invalid JSON payload.'}, status=400)

    round_id = payload.get('round_id')
    try:
        round_id = int(round_id)
    except (TypeError, ValueError):
        return JsonResponse({'detail': 'round_id must be an integer.'}, status=400)

    round_obj = get_object_or_404(GPTriviaRound, id=round_id)
    if not round_obj.cooperative:
        return JsonResponse({'detail': 'Only cooperative rounds can merge.'}, status=400)

    current_entry = AnswerSheetEntry.objects.filter(user=request.user, round=round_obj).first()
    if not current_entry or not current_entry.is_diverged:
        return JsonResponse({'detail': 'Only diverged cooperative rounds can merge.'}, status=400)

    communal_answers = _get_answer_sheet_communal_answers(round_obj, current_user=request.user)
    communal_entry = (
        AnswerSheetEntry.objects.filter(
            round=round_obj,
            user_id__in=[target_user.id for target_user in _get_answer_sheet_shared_users(round_obj, current_user=request.user)],
            is_diverged=False,
        )
        .order_by('-updated_at', '-id')
        .first()
    )
    communal_grade_overrides = _normalize_answer_sheet_grade_overrides(
        communal_entry.grade_overrides if communal_entry else []
    )
    communal_grade_rejections = _normalize_answer_sheet_grade_overrides(
        communal_entry.grade_rejections if communal_entry else []
    )
    communal_grade_invalidated_questions = _normalize_answer_sheet_grade_overrides(
        communal_entry.grade_invalidated_questions if communal_entry else []
    )
    communal_was_graded = bool(communal_entry.was_graded) if communal_entry else False
    communal_entry_state = _serialize_answer_sheet_entry_state(communal_entry)

    with transaction.atomic():
        AnswerSheetEntry.objects.filter(user=request.user, round=round_obj).delete()
        merged_entry = AnswerSheetEntry.objects.create(
            user=request.user,
            round=round_obj,
            trivia_date=round_obj.date,
            answers=communal_answers,
            pencil_answers=communal_entry_state['pencil_answers'],
            input_mode=communal_entry_state['input_mode'],
            ink_strokes=communal_entry_state['ink_strokes'],
            grade_overrides=communal_grade_overrides,
            grade_rejections=communal_grade_rejections,
            grade_invalidated_questions=communal_grade_invalidated_questions,
            was_graded=communal_was_graded,
            is_diverged=False,
        )

    return JsonResponse({
        'ok': True,
        'round_id': round_obj.id,
        'answers': merged_entry.answers,
        'input_mode': _normalize_answer_sheet_input_mode(merged_entry.input_mode),
        'ink_strokes': _normalize_answer_sheet_ink_strokes(merged_entry.ink_strokes),
        'grade_overrides': _normalize_answer_sheet_grade_overrides(merged_entry.grade_overrides),
        'grade_rejections': _normalize_answer_sheet_grade_overrides(merged_entry.grade_rejections),
        'grade_invalidated_questions': _normalize_answer_sheet_grade_overrides(merged_entry.grade_invalidated_questions),
        'grade_payload': _build_saved_answer_sheet_grade_payload(round_obj, merged_entry),
        'was_graded': bool(merged_entry.was_graded),
        'is_diverged': False,
        'shared': True,
        'submit_requires_confirmation': bool(
            round_obj.cooperative
            and str(getattr(request.user, 'username', '') or '').strip().casefold()
            != str(getattr(round_obj, 'creator', '') or '').strip().casefold()
        ),
    })


@login_required
def submit_answer_sheet_score(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed.'}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'detail': 'Invalid JSON payload.'}, status=400)

    round_id = payload.get('round_id')
    try:
        round_id = int(round_id)
    except (TypeError, ValueError):
        return JsonResponse({'detail': 'round_id must be an integer.'}, status=400)

    try:
        normalized_score = _normalize_answer_sheet_score(payload.get('score', ''))
    except ValueError as error:
        return JsonResponse({'detail': str(error)}, status=400)
    client_id = str(payload.get('client_id') or '').strip()

    player_field = player_field_for_name(getattr(request.user, 'username', ''))
    if not player_field:
        return JsonResponse({'detail': 'This user cannot be mapped to a scoresheet player field.'}, status=400)

    round_obj = get_object_or_404(GPTriviaRound, id=round_id)
    current_entry = AnswerSheetEntry.objects.filter(user=request.user, round=round_obj).first()
    current_user_is_diverged = bool(current_entry.is_diverged) if current_entry else False

    with transaction.atomic():
        score_map = get_round_score_map(round_obj)
        if round_obj.cooperative and not current_user_is_diverged:
            creator_fields = {
                normalized_field
                for normalized_field in [
                    player_field_for_name(round_obj.creator),
                    player_field_for_name(getattr(round_obj, 'secondary_creator', '')),
                ]
                if normalized_field
            }
            target_player_fields = [
                candidate_field
                for candidate_field in _get_answer_sheet_round_player_fields(round_obj, current_user_player_field=player_field)
                if candidate_field not in creator_fields and candidate_field not in _get_answer_sheet_diverged_player_fields(round_obj)
            ]
            if not target_player_fields and player_field not in creator_fields:
                target_player_fields = [player_field]
            for target_field in target_player_fields:
                score_map[target_field] = normalized_score
        else:
            score_map[player_field] = normalized_score
        set_round_score_map(round_obj, score_map)
        round_obj.save(update_fields=[*FIXED_SCORE_FIELDS, 'extra_scores'])
        _promote_answer_sheet_overrides_to_possible_answers(round_obj, current_entry)
        _remove_answer_sheet_rejections_from_possible_answers(round_obj, current_entry)

        _schedule_scoresheet_broadcast({
            'action': 'update',
            'event': 'answer_sheet_submit_score',
            'client_id': client_id,
            'selected_date': round_obj.date.isoformat() if round_obj.date else '',
            'round_updates': [
                {
                    'id': round_obj.id,
                    'fields': {
                        candidate_field: normalized_score
                        for candidate_field in (
                            target_player_fields if round_obj.cooperative else [player_field]
                        )
                    },
                },
            ],
            'presentation_updates': {},
        })

    _bump_site_data_cache_version()
    return JsonResponse({
        'ok': True,
        'round_id': round_obj.id,
        'trivia_date': round_obj.date.isoformat() if round_obj.date else '',
        'player_field': player_field,
        'score': normalized_score,
        'score_display': _format_profile_round_score(normalized_score),
    })


@login_required
def grade_answer_sheet_round(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed.'}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'detail': 'Invalid JSON payload.'}, status=400)

    round_id = payload.get('round_id')
    try:
        round_id = int(round_id)
    except (TypeError, ValueError):
        return JsonResponse({'detail': 'round_id must be an integer.'}, status=400)

    round_obj = get_object_or_404(GPTriviaRound, id=round_id)
    client_id = str(payload.get('client_id') or '').strip()
    current_entry = AnswerSheetEntry.objects.filter(user=request.user, round=round_obj).first()
    current_user_is_diverged = bool(current_entry.is_diverged) if current_entry else False
    current_entry_state = _serialize_answer_sheet_entry_state(current_entry)
    input_mode = (
        _normalize_answer_sheet_input_mode(payload.get('input_mode'))
        if 'input_mode' in payload
        else current_entry_state['input_mode']
    )
    ink_strokes = (
        _normalize_answer_sheet_ink_strokes(payload.get('ink_strokes', []))
        if 'ink_strokes' in payload
        else current_entry_state['ink_strokes']
    )
    raw_answers = payload.get('answers', [])
    row_count = _answer_sheet_row_count(payload.get('row_count'), raw_answers)
    ink_stroke_rows = _normalize_answer_sheet_ink_stroke_rows(
        payload.get('ink_stroke_rows', []),
        stroke_count=len(ink_strokes),
        row_count=row_count,
    )
    transcribed_from_ink = False
    typed_answers = _normalize_answer_sheet_answers(current_entry.answers if current_entry else [])
    if input_mode == AnswerSheetEntry.INPUT_MODE_PENCIL:
        try:
            answers = _transcribe_answer_sheet_ink_strokes_to_lines(
                ink_strokes,
                row_count=row_count,
                round_title=round_obj.title,
                stroke_rows=ink_stroke_rows,
            )
        except Exception as error:
            logger.exception("Unable to transcribe handwritten answer sheet round %s", round_obj.id)
            return JsonResponse({'detail': f'Unable to read handwritten answers: {error}'}, status=400)
        transcribed_from_ink = True
    elif isinstance(raw_answers, str):
        answers = raw_answers.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    elif isinstance(raw_answers, list):
        answers = [str(answer or '') for answer in raw_answers]
    else:
        answers = []

    normalized_answers = _normalize_answer_sheet_answers(answers)
    current_grade_overrides = _normalize_answer_sheet_grade_overrides(
        current_entry.grade_overrides if current_entry else []
    )
    current_grade_rejections = _normalize_answer_sheet_grade_overrides(
        current_entry.grade_rejections if current_entry else []
    )

    try:
        grade_payload = _grade_answer_sheet_answers(
            round_obj,
            normalized_answers,
            manual_correct_questions=current_grade_overrides,
            manual_incorrect_questions=current_grade_rejections,
        )
    except ValueError as error:
        return JsonResponse({'detail': str(error)}, status=400)

    if input_mode == AnswerSheetEntry.INPUT_MODE_PENCIL:
        present_row_numbers = {
            row_number
            for row_number in ink_stroke_rows
            if isinstance(row_number, int) and row_number >= 1
        }
        for row_result in grade_payload['row_results']:
            if (
                row_result['question_number'] in present_row_numbers
                and row_result['state'] == 'blank'
            ):
                row_result['state'] = 'incorrect'

    target_users = [request.user]
    if round_obj.cooperative and not current_user_is_diverged:
        diverged_user_ids = _get_answer_sheet_diverged_user_ids(round_obj)
        target_users = [
            target_user
            for target_user in _get_answer_sheet_shared_users(round_obj, current_user=request.user)
            if target_user.id not in diverged_user_ids
        ]
        if not target_users:
            target_users = [request.user]

    with transaction.atomic():
        for target_user in target_users:
            previous_entry = AnswerSheetEntry.objects.filter(user=target_user, round=round_obj).first()
            previous_typed_answers = _normalize_answer_sheet_answers(previous_entry.answers if previous_entry else [])
            previous_pencil_answers = _normalize_answer_sheet_answers(
                getattr(previous_entry, 'pencil_answers', []) if previous_entry else []
            )
            previous_grade_answers = (
                previous_pencil_answers
                if input_mode == AnswerSheetEntry.INPUT_MODE_PENCIL
                else previous_typed_answers
            )
            next_typed_answers = previous_typed_answers if input_mode == AnswerSheetEntry.INPUT_MODE_PENCIL else normalized_answers
            next_pencil_answers = normalized_answers if input_mode == AnswerSheetEntry.INPUT_MODE_PENCIL else previous_pencil_answers
            next_grade_overrides = _clear_answer_sheet_overrides_for_changed_answers(
                previous_grade_answers,
                normalized_answers,
                previous_entry.grade_overrides if previous_entry else [],
            )
            next_grade_rejections = _clear_answer_sheet_grade_marks_for_changed_answers(
                previous_grade_answers,
                normalized_answers,
                previous_entry.grade_rejections if previous_entry else [],
            )
            AnswerSheetEntry.objects.update_or_create(
                user=target_user,
                round=round_obj,
                defaults={
                    'trivia_date': round_obj.date,
                    'answers': next_typed_answers,
                    'pencil_answers': next_pencil_answers,
                    'input_mode': input_mode,
                    'ink_strokes': ink_strokes,
                    'grade_overrides': next_grade_overrides,
                    'grade_rejections': next_grade_rejections,
                    'grade_invalidated_questions': [],
                    'was_graded': True,
                    'is_diverged': bool(current_entry.is_diverged) if (current_entry and target_user.id == request.user.id) else False,
                },
            )

        _schedule_scoresheet_broadcast({
            'action': 'answer_sheet',
            'event': 'answer_sheet_grade',
            'selected_date': round_obj.date.isoformat() if round_obj.date else '',
            'round_id': round_obj.id,
            'client_id': client_id,
            'target_user_ids': [target_user.id for target_user in target_users],
            'answers': typed_answers if input_mode == AnswerSheetEntry.INPUT_MODE_PENCIL else normalized_answers,
            'input_mode': input_mode,
            'shared': bool(round_obj.cooperative and not current_user_is_diverged),
            'is_diverged': bool(current_user_is_diverged),
            'transcribed_from_ink': transcribed_from_ink,
            **grade_payload,
        })

    return JsonResponse({
        'ok': True,
        'round_id': round_obj.id,
        'shared': bool(round_obj.cooperative and not current_user_is_diverged),
        'answers': typed_answers if input_mode == AnswerSheetEntry.INPUT_MODE_PENCIL else normalized_answers,
        'input_mode': input_mode,
        'transcribed_from_ink': transcribed_from_ink,
        **grade_payload,
    })


@login_required
def override_answer_sheet_grade(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed.'}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'detail': 'Invalid JSON payload.'}, status=400)

    round_id = payload.get('round_id')
    question_number = payload.get('question_number')
    try:
        round_id = int(round_id)
        question_number = int(question_number)
    except (TypeError, ValueError):
        return JsonResponse({'detail': 'round_id and question_number must be integers.'}, status=400)
    if question_number <= 0:
        return JsonResponse({'detail': 'question_number must be positive.'}, status=400)

    raw_answers = payload.get('answers', [])
    if isinstance(raw_answers, str):
        answers = raw_answers.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    elif isinstance(raw_answers, list):
        answers = [str(answer or '') for answer in raw_answers]
    else:
        answers = []

    round_obj = get_object_or_404(GPTriviaRound, id=round_id)
    client_id = str(payload.get('client_id') or '').strip()
    mode = str(payload.get('mode') or 'correct').strip().lower()
    if mode not in {'correct', 'incorrect'}:
        return JsonResponse({'detail': 'mode must be correct or incorrect.'}, status=400)
    current_entry = AnswerSheetEntry.objects.filter(user=request.user, round=round_obj).first()
    current_user_is_diverged = bool(current_entry.is_diverged) if current_entry else False
    current_entry_state = _serialize_answer_sheet_entry_state(current_entry)
    input_mode = current_entry_state['input_mode']
    normalized_answers = (
        current_entry_state['pencil_answers']
        if input_mode == AnswerSheetEntry.INPUT_MODE_PENCIL
        else _normalize_answer_sheet_answers(answers)
    )
    typed_answers = _normalize_answer_sheet_answers(current_entry.answers if current_entry else [])

    target_users = [request.user]
    if round_obj.cooperative and not current_user_is_diverged:
        diverged_user_ids = _get_answer_sheet_diverged_user_ids(round_obj)
        target_users = [
            target_user
            for target_user in _get_answer_sheet_shared_users(round_obj, current_user=request.user)
            if target_user.id not in diverged_user_ids
        ]
        if not target_users:
            target_users = [request.user]

    with transaction.atomic():
        response_entry = None
        applied_grade_overrides = []
        applied_grade_rejections = []
        for target_user in target_users:
            previous_entry = AnswerSheetEntry.objects.filter(user=target_user, round=round_obj).first()
            previous_typed_answers = _normalize_answer_sheet_answers(previous_entry.answers if previous_entry else [])
            previous_pencil_answers = _normalize_answer_sheet_answers(
                getattr(previous_entry, 'pencil_answers', []) if previous_entry else []
            )
            previous_grade_answers = (
                previous_pencil_answers
                if input_mode == AnswerSheetEntry.INPUT_MODE_PENCIL
                else previous_typed_answers
            )
            next_grade_overrides = _clear_answer_sheet_overrides_for_changed_answers(
                previous_grade_answers,
                normalized_answers,
                previous_entry.grade_overrides if previous_entry else [],
            )
            next_grade_rejections = _clear_answer_sheet_grade_marks_for_changed_answers(
                previous_grade_answers,
                normalized_answers,
                previous_entry.grade_rejections if previous_entry else [],
            )
            if mode == 'correct':
                if question_number not in next_grade_overrides:
                    next_grade_overrides.append(question_number)
                next_grade_rejections = [
                    value for value in next_grade_rejections
                    if value != question_number
                ]
            else:
                if question_number not in next_grade_rejections:
                    next_grade_rejections.append(question_number)
                next_grade_overrides = [
                    value for value in next_grade_overrides
                    if value != question_number
                ]
            next_grade_overrides = _normalize_answer_sheet_grade_overrides(next_grade_overrides)
            next_grade_rejections = _normalize_answer_sheet_grade_overrides(next_grade_rejections)
            answer_entry, _ = AnswerSheetEntry.objects.update_or_create(
                user=target_user,
                round=round_obj,
                defaults={
                    'trivia_date': round_obj.date,
                    'answers': previous_typed_answers if input_mode == AnswerSheetEntry.INPUT_MODE_PENCIL else normalized_answers,
                    'pencil_answers': normalized_answers if input_mode == AnswerSheetEntry.INPUT_MODE_PENCIL else previous_pencil_answers,
                    'grade_overrides': next_grade_overrides,
                    'grade_rejections': next_grade_rejections,
                    'grade_invalidated_questions': [],
                    'was_graded': True,
                    'is_diverged': bool(current_entry.is_diverged) if (current_entry and target_user.id == request.user.id) else False,
                },
            )
            if target_user.id == request.user.id:
                response_entry = answer_entry
                applied_grade_overrides = next_grade_overrides
                applied_grade_rejections = next_grade_rejections
        if response_entry is None:
            response_entry = AnswerSheetEntry.objects.get(user=request.user, round=round_obj)
            applied_grade_overrides = _normalize_answer_sheet_grade_overrides(response_entry.grade_overrides)
            applied_grade_rejections = _normalize_answer_sheet_grade_overrides(response_entry.grade_rejections)

    try:
        grade_payload = _grade_answer_sheet_answers(
            round_obj,
            normalized_answers,
            manual_correct_questions=applied_grade_overrides,
            manual_incorrect_questions=applied_grade_rejections,
        )
    except ValueError as error:
        return JsonResponse({'detail': str(error)}, status=400)

    _schedule_scoresheet_broadcast({
        'action': 'answer_sheet',
        'event': 'answer_sheet_grade',
        'selected_date': round_obj.date.isoformat() if round_obj.date else '',
        'round_id': round_obj.id,
        'client_id': client_id,
        'target_user_ids': [target_user.id for target_user in target_users],
        'answers': typed_answers if input_mode == AnswerSheetEntry.INPUT_MODE_PENCIL else normalized_answers,
        'input_mode': current_entry_state['input_mode'],
        'shared': bool(round_obj.cooperative and not current_user_is_diverged),
        'is_diverged': bool(current_user_is_diverged),
        'transcribed_from_ink': current_entry_state['input_mode'] == AnswerSheetEntry.INPUT_MODE_PENCIL,
        **grade_payload,
    })

    return JsonResponse({
        'ok': True,
        'round_id': round_obj.id,
        'shared': bool(round_obj.cooperative and not current_user_is_diverged),
        'answers': typed_answers if input_mode == AnswerSheetEntry.INPUT_MODE_PENCIL else normalized_answers,
        'input_mode': current_entry_state['input_mode'],
        'transcribed_from_ink': current_entry_state['input_mode'] == AnswerSheetEntry.INPUT_MODE_PENCIL,
        **grade_payload,
    })


@login_required
def round_analysis_image(request, entry_id):
    entry = get_object_or_404(
        RoundQuestionAnalysisEntry.objects.select_related('round', 'run'),
        id=entry_id,
    )
    if str(entry.media_kind or '').strip().lower() != 'image':
        raise Http404("Saved image is only available for image entries.")
    if entry.media_file:
        return _serve_profile_media_file(entry.media_file)
    if entry.media_url:
        return redirect(entry.media_url)
    raise Http404("No image is available for this round analysis entry.")


@login_required
def round_analysis_media(request, entry_id):
    from .round_analysis import (
        _is_placeholder_media_url,
        get_round_analysis_playable_media_asset,
        get_round_analysis_playable_media_url,
    )

    entry = get_object_or_404(
        RoundQuestionAnalysisEntry.objects.select_related('round', 'run'),
        id=entry_id,
    )
    expected_kind = str(entry.media_kind or '').strip().lower()
    if expected_kind not in {'audio', 'video'}:
        raise Http404("Playable media is only available for audio or video entries.")

    rebuilt_playable_url = get_round_analysis_playable_media_url(entry)
    if rebuilt_playable_url:
        return redirect(rebuilt_playable_url)

    if entry.media_url and not _is_placeholder_media_url(entry.media_url, expected_kind=expected_kind):
        return redirect(entry.media_url)

    if entry.media_file:
        saved_file_content_type = mimetypes.guess_type(entry.media_file.name)[0] or 'application/octet-stream'
        if saved_file_content_type.startswith(f'{expected_kind}/'):
            file_handle = entry.media_file.open('rb')
            response = FileResponse(
                file_handle,
                content_type=saved_file_content_type,
            )
            response['Content-Disposition'] = f'inline; filename="{os.path.basename(entry.media_file.name)}"'
            return response

    try:
        asset = get_round_analysis_playable_media_asset(entry)
    except Exception:
        logger.exception("Could not resolve fallback playable media for round analysis entry %s", entry.id)
        raise Http404("No playable media is available for this round analysis entry.")
    if not asset:
        raise Http404("No playable media is available for this round analysis entry.")

    response = FileResponse(
        BytesIO(asset['content']),
        content_type=asset.get('content_type') or 'application/octet-stream',
    )
    response['Content-Disposition'] = f'inline; filename="{asset.get("filename") or "media"}"'
    return response


@login_required
def trigger_round_analysis(request, round_id):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed.'}, status=405)

    round_obj = get_object_or_404(GPTriviaRound, id=round_id)
    next_url = (request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse('rounds_list')).strip()
    wants_json = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    if round_obj.replay:
        if wants_json:
            return JsonResponse({
                'ok': False,
                'message': f"{round_obj.title} is marked as a replay round and cannot be analyzed.",
                'status': _build_round_analysis_status_map([round_obj.id])[round_obj.id],
            }, status=400)
        messages.error(request, f"{round_obj.title} is marked as a replay round and cannot be analyzed.")
        return redirect(next_url)

    if not _creator_allows_round_analysis(round_obj.creator):
        if wants_json:
            return JsonResponse({
                'ok': False,
                'message': f"{round_obj.creator} has not opted in to round analysis.",
                'status': _build_round_analysis_status_map([round_obj.id])[round_obj.id],
            }, status=403)
        messages.error(request, f"{round_obj.creator} has not opted in to round analysis.")
        return redirect(next_url)

    if RoundQuestionAnalysisRun.objects.filter(
        round=round_obj,
        status__in=[RoundQuestionAnalysisRun.STATUS_PENDING, RoundQuestionAnalysisRun.STATUS_RUNNING],
    ).exists():
        if wants_json:
            return JsonResponse({
                'ok': True,
                'message': f"Round analysis is already running for {round_obj.title}.",
                'status': _build_round_analysis_status_map([round_obj.id])[round_obj.id],
            })
        messages.info(request, f"Round analysis is already running for {round_obj.title}.")
        return redirect(next_url)

    from .round_analysis import queue_round_analysis

    queued_run_ids = queue_round_analysis(
        round_obj.id,
        trigger_type=RoundQuestionAnalysisRun.TRIGGER_MANUAL,
        initiated_by=request.user.username if request.user.is_authenticated else '',
    )
    status_payload = _build_round_analysis_status_map([round_obj.id])[round_obj.id]
    message_text = (
        f"Round analysis queued for {round_obj.title}."
        if queued_run_ids
        else f"Round analysis is already running for {round_obj.title}."
    )
    if wants_json:
        return JsonResponse({
            'ok': bool(queued_run_ids),
            'message': message_text,
            'status': status_payload,
        })
    if queued_run_ids:
        messages.success(request, message_text)
    else:
        messages.info(request, message_text)

    return redirect(next_url)


@login_required
def restart_round_analysis(request, round_id):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed.'}, status=405)

    round_obj = get_object_or_404(GPTriviaRound, id=round_id)
    next_url = (request.POST.get('next') or request.META.get('HTTP_REFERER') or reverse('rounds_list')).strip()
    wants_json = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    if round_obj.replay:
        if wants_json:
            return JsonResponse({
                'ok': False,
                'message': f"{round_obj.title} is marked as a replay round and cannot be analyzed.",
                'status': _build_round_analysis_status_map([round_obj.id])[round_obj.id],
            }, status=400)
        messages.error(request, f"{round_obj.title} is marked as a replay round and cannot be analyzed.")
        return redirect(next_url)

    if not _creator_allows_round_analysis(round_obj.creator):
        if wants_json:
            return JsonResponse({
                'ok': False,
                'message': f"{round_obj.creator} has not opted in to round analysis.",
                'status': _build_round_analysis_status_map([round_obj.id])[round_obj.id],
            }, status=403)
        messages.error(request, f"{round_obj.creator} has not opted in to round analysis.")
        return redirect(next_url)

    active_runs = list(
        RoundQuestionAnalysisRun.objects.filter(
            round=round_obj,
            status__in=[RoundQuestionAnalysisRun.STATUS_PENDING, RoundQuestionAnalysisRun.STATUS_RUNNING],
        ).order_by('id')
    )
    if not active_runs:
        return trigger_round_analysis(request, round_id)

    restart_note = (
        f"Restarted manually by {request.user.username} on "
        f"{timezone.now().strftime('%Y-%m-%d %H:%M:%S %Z') or timezone.now().isoformat()}."
    )
    with transaction.atomic():
        completed_at = timezone.now()
        for active_run in active_runs:
            error_parts = [str(active_run.error_message or '').strip(), restart_note]
            active_run.status = RoundQuestionAnalysisRun.STATUS_FAILED
            active_run.completed_at = completed_at
            active_run.error_message = '\n\n'.join(part for part in error_parts if part)
            active_run.save(update_fields=['status', 'completed_at', 'error_message', 'updated_at'])

    from .round_analysis import queue_round_analysis

    queued_run_ids = queue_round_analysis(
        round_obj.id,
        trigger_type=RoundQuestionAnalysisRun.TRIGGER_MANUAL,
        initiated_by=request.user.username if request.user.is_authenticated else '',
    )
    status_payload = _build_round_analysis_status_map([round_obj.id])[round_obj.id]
    message_text = (
        f"Round analysis restarted for {round_obj.title}."
        if queued_run_ids
        else f"Round analysis could not be restarted for {round_obj.title}."
    )
    if wants_json:
        return JsonResponse({
            'ok': bool(queued_run_ids),
            'message': message_text,
            'status': status_payload,
        })

    if queued_run_ids:
        messages.success(request, message_text)
    else:
        messages.error(request, message_text)
    return redirect(next_url)


def blog_roboalex(request):
    context = {}
    context.update(get_roboalex_blog_context())
    context.update(get_blog_navigation_context("blog_roboalex"))
    return render(request, 'GPTrivia/blog_roboalex.html', context)


def blog_index(request):
    return render(request, 'GPTrivia/blog_index.html', get_blog_index_context())


def blog_joker_stats(request):
    context = {}
    context.update(get_joker_stats_blog_context())
    context.update(get_blog_navigation_context("blog_joker_stats"))
    return render(request, 'GPTrivia/blog_joker_stats.html', context)


def blog_other_trivia_plots(request):
    context = {}
    context.update(get_other_trivia_plots_blog_context())
    context.update(get_blog_navigation_context("blog_other_trivia_plots"))
    return render(request, 'GPTrivia/blog_other_trivia_plots.html', context)


@login_required
def player_analysis(request):
    round_queryset = GPTriviaRound.objects.all()
    round_player_queryset = round_queryset.only('creator', 'extra_scores')
    presentation_queryset = MergedPresentation.objects.only('player_list', 'creator_list')
    initial_creator_selection = (request.GET.get('creator') or '').strip()
    initial_category_selection = (request.GET.get('category') or '').strip()
    initial_player_selection = (request.GET.get('player') or '').strip()
    initial_include_coop = str(request.GET.get('include_coop') or '').strip().lower() in {'1', 'true', 'yes', 'on', 'include_coop'}
    initial_include_inactive = str(request.GET.get('include_inactive') or '').strip().lower() in {'1', 'true', 'yes', 'on', 'include_inactive', 'show_inactive'}
    player_fields = get_all_player_fields(round_player_queryset, presentation_queryset)
    player_names = [display_name_for_player_field(field) for field in player_fields]
    player_name_mapping = {
        player_name: player_field
        for player_name, player_field in zip(player_names, player_fields)
    }

    creators = sorted({
        creator_name
        for creator_name in chain(
            round_queryset.order_by().values_list('creator', flat=True).distinct(),
            round_queryset.order_by().values_list('secondary_creator', flat=True).distinct(),
        )
        if creator_name
    })
    categories = sorted({
        category_name
        for category_name in round_queryset.order_by().values_list('major_category', flat=True).distinct()
        if category_name
    })

    if initial_creator_selection not in creators:
        initial_creator_selection = ''
    if initial_category_selection not in categories:
        initial_category_selection = ''
    if initial_player_selection not in player_names:
        initial_player_selection = ''

    player_color_mapping = build_player_color_mapping(player_names)
    player_text_mapping = build_player_text_mapping(player_names)

    context = {
        'playerColorMapping': player_color_mapping,
        'player_color_mapping_json': json.dumps(player_color_mapping, cls=DjangoJSONEncoder),
        'creators': creators,
        'categories': categories,
        'players': player_names,
        'initial_creator_selection': initial_creator_selection,
        'initial_category_selection': initial_category_selection,
        'initial_player_selection': initial_player_selection,
        'initial_include_coop': initial_include_coop,
        'initial_include_inactive': initial_include_inactive,
        "mapping": player_name_mapping,
        "player_text_mapping": player_text_mapping,
        "player_text_mapping_json": json.dumps(player_text_mapping, cls=DjangoJSONEncoder),
    }

    return render(request, 'GPTrivia/player_analysis_new.html', context)



@login_required
def player_analysis_legacy(request):
    return redirect('player_analysis')


@login_required
def upload_profile_picture(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ProfilePictureForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            profile = form.save()
            if profile.has_custom_profile_picture():
                profile.ensure_profile_icon(force=True)
            return redirect('player_profile', player_name=request.user.username)
    else:
        form = ProfilePictureForm(instance=profile)

    context = player_profile_dict(request, request.user.username, form=form, include_deferred_stats=False)
    return render(request, 'GPTrivia/player_profile.html', context)


@login_required
def toggle_round_analysis_opt_in(request, player_name):
    if request.method != 'POST':
        raise Http404("Round analysis preference updates must be submitted with POST.")

    normalized_player_name = display_name_for_player_field(player_name)
    if display_name_for_player_field(request.user.username) != normalized_player_name:
        messages.error(request, "You can only update round analysis settings for your own profile.")
        return redirect('player_profile', player_name=normalized_player_name)

    profile, _created = Profile.objects.get_or_create(user=request.user)
    desired_state = _is_truthy_form_value(request.POST.get('round_analysis_opt_in'))
    if profile.round_analysis_opt_in != desired_state:
        profile.round_analysis_opt_in = desired_state
        profile.save(update_fields=['round_analysis_opt_in'])

    if desired_state:
        messages.success(request, "Round analysis is enabled for your rounds.")
    else:
        messages.success(request, "Round analysis is disabled for your rounds.")

    return redirect('player_profile', player_name=request.user.username)


def _serve_profile_media_file(file_field):
    if not file_field:
        raise Http404("Profile image not found.")

    try:
        file_field.open('rb')
    except Exception as exc:
        raise Http404("Profile image not found.") from exc

    content_type = mimetypes.guess_type(getattr(file_field, 'name', '') or '')[0] or 'application/octet-stream'
    response = FileResponse(file_field, content_type=content_type)
    response['Cache-Control'] = 'private, max-age=3600'
    return response


@login_required
def profile_picture_media(request, player_name, version):
    profile_user = get_object_or_404(User, username__iexact=player_name)
    profile = profile_user.profile
    return _serve_profile_media_file(profile.profile_picture)


@login_required
def profile_avatar_media(request, player_name, version):
    profile_user = get_object_or_404(User, username__iexact=player_name)
    profile = profile_user.profile
    if profile.has_custom_profile_picture():
        profile.ensure_profile_icon()

    avatar_file = profile.profile_icon or profile.profile_picture
    return _serve_profile_media_file(avatar_file)


@login_required
def update_profile_intro(request, player_name):
    profile_user = get_object_or_404(User, username__iexact=player_name)
    if request.user.pk != profile_user.pk:
        raise Http404("You can only edit your own profile intro.")
    if request.method != 'POST':
        raise Http404("Profile intro updates must be submitted with POST.")

    profile = profile_user.profile
    form = ProfileIntroForm(request.POST)
    expects_json = (
        'application/json' in (request.headers.get('Accept') or '')
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    )
    if form.is_valid():
        profile.profile_intro = (form.cleaned_data.get('profile_intro') or '').strip()
        profile.save(update_fields=['profile_intro'])
        if expects_json:
            return JsonResponse({
                'ok': True,
                'profile_intro': profile.profile_intro,
            })
        return redirect('player_profile', player_name=profile_user.username)

    if expects_json:
        return JsonResponse({
            'ok': False,
            'errors': form.errors.get_json_data(),
        }, status=400)

    appearance_form = ProfilePictureForm(instance=profile)
    context = player_profile_dict(
        request,
        profile_user.username,
        form=appearance_form,
        intro_form=form,
        include_form=True,
        include_deferred_stats=False,
    )
    return render(request, 'GPTrivia/player_profile.html', context)


def _build_player_icon_map():
    icon_map = {}

    for profile in Profile.objects.select_related('user'):
        if not profile.user_id:
            continue

        if profile.has_custom_profile_picture():
            profile.ensure_profile_icon()

        icon_url = get_profile_avatar_url(profile, include_default=False)
        if not icon_url:
            continue

        display_name = display_name_for_player_field(profile.user.username)
        if not display_name:
            continue

        icon_map[display_name] = icon_url
        player_field = player_field_for_name(display_name)
        if player_field:
            icon_map[player_field] = icon_url

    return icon_map


def _build_player_color_override_map():
    return build_profile_color_override_mapping()


def _format_profile_round_score(value):
    if value is None:
        return ''
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip('0').rstrip('.')


def _summarize_profile_round_scores(round_obj):
    score_values = [
        score
        for score in get_round_score_map(round_obj, include_null_fixed=False).values()
        if score is not None
    ]
    if not score_values:
        return {
            'high_score': None,
            'average_score': None,
            'high_score_display': '',
            'average_score_display': '',
        }

    high_score = max(score_values)
    average_score = sum(score_values) / len(score_values)
    return {
        'high_score': high_score,
        'average_score': average_score,
        'high_score_display': _format_profile_round_score(high_score),
        'average_score_display': _format_profile_round_score(average_score),
    }


def _get_profile_page_color_value(profile, field_name, default_value):
    if not profile:
        return default_value
    return getattr(profile, field_name, '') or default_value


def _normalize_hex_color(color_value, fallback):
    cleaned_value = str(color_value or '').strip()
    if re.fullmatch(r'#[0-9a-fA-F]{6}', cleaned_value):
        return cleaned_value.lower()
    return fallback.lower()


def _darken_hex_color(color_value, factor=0.84):
    normalized = _normalize_hex_color(color_value, Profile.PROFILE_PAGE_CHROME_DEFAULT)
    channels = [int(normalized[index:index + 2], 16) for index in (1, 3, 5)]
    darkened_channels = [
        max(0, min(255, int(round(channel * factor))))
        for channel in channels
    ]
    return "#{:02x}{:02x}{:02x}".format(*darkened_channels)


def _profile_text_color_for_background(color_value):
    normalized = _normalize_hex_color(color_value, Profile.PROFILE_PAGE_CHROME_DEFAULT)
    red = int(normalized[1:3], 16)
    green = int(normalized[3:5], 16)
    blue = int(normalized[5:7], 16)
    brightness = (0.5 * red) + green + (0.25 * blue)
    return '#ffffff' if brightness < 300 else '#111111'


def _with_alpha(hex_color, alpha):
    normalized = _normalize_hex_color(hex_color, '#ffffff')
    red = int(normalized[1:3], 16)
    green = int(normalized[3:5], 16)
    blue = int(normalized[5:7], 16)
    clamped_alpha = max(0, min(1, alpha))
    return f"rgba({red}, {green}, {blue}, {clamped_alpha:.2f})"


def _format_profile_percentage_stat(numerator, denominator, signed=False):
    if numerator is None or denominator in (None, 0):
        return ''

    absolute_numerator = abs(numerator) if signed else numerator
    numerator_display = _format_profile_round_score(absolute_numerator)
    denominator_display = _format_profile_round_score(denominator)
    percent_value = (numerator / denominator) * 100

    sign_prefix = ''
    percent_prefix = ''
    if signed:
        if numerator > 0:
            sign_prefix = '+'
        elif numerator < 0:
            sign_prefix = '-'

        if percent_value > 0:
            percent_prefix = '+'
        elif percent_value < 0:
            percent_prefix = '-'

    return f"{sign_prefix}{numerator_display}/{denominator_display} ({percent_prefix}{abs(percent_value):.1f}%)"


def _format_profile_gap_stat(value):
    if value is None:
        return ''

    display_value = _format_profile_round_score(abs(value))
    if value > 0:
        return f"+{display_value} points"
    if value < 0:
        return f"-{display_value} points"
    return "0 points"


def _can_edit_profile_round_categories(request_user, profile_user=None, profile_player_name=''):
    if not request_user or not request_user.is_authenticated:
        return False

    request_user_name = display_name_for_player_field(request_user.username)
    if request_user_name == 'Alex':
        return True

    if profile_player_name and request_user_name == display_name_for_player_field(profile_player_name):
        return True

    return bool(profile_user and request_user.pk == profile_user.pk)


def _build_scoresheet_date_link(target_date):
    if not target_date:
        return ''

    target_date_str = target_date.isoformat()
    if not _get_scoresheet_presentation(selected_date=target_date_str):
        return ''

    return f"{reverse('scoresheet_new')}?date={target_date_str}"


def _get_recently_active_profile_player_names(all_rounds):
    cutoff_date = _current_trivia_date() - datetime.timedelta(days=365)
    active_player_names = set()

    for round_obj in all_rounds:
        if not round_obj.date or round_obj.date < cutoff_date:
            continue

        creator_name = display_name_for_player_field(round_obj.creator)
        if creator_name:
            active_player_names.add(creator_name)

        for player_field, score_value in get_round_score_map(round_obj, include_null_fixed=False).items():
            if score_value is None:
                continue
            player_name = display_name_for_player_field(player_field)
            if player_name:
                active_player_names.add(player_name)

    return active_player_names


def _normalize_profile_presentation_value(value):
    if isinstance(value, dict):
        return {
            _normalize_profile_presentation_value(key): _normalize_profile_presentation_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_normalize_profile_presentation_value(item) for item in value]
    if isinstance(value, str):
        return value.replace('~~~~', "'")
    return value


def _parse_profile_presentation_json(value, fallback):
    if value in (None, '', []):
        return fallback

    if isinstance(value, (dict, list)):
        return _normalize_profile_presentation_value(value)

    if not isinstance(value, str):
        return fallback

    try:
        return _normalize_profile_presentation_value(json.loads(
            value
            .replace("'", '"')
            .replace('~~~~', "'")
        ))
    except Exception:
        return fallback


def _get_profile_player_storage_key(player_field):
    display_name = display_name_for_player_field(player_field)
    return display_name.lower() if display_name else ''


def _profile_player_matches_creator(round_creator, player_field):
    normalized_round_creator = display_name_for_player_field(round_creator)
    player_name = display_name_for_player_field(player_field)
    if player_name == 'Dan':
        return normalized_round_creator in {'Dad', 'Dan'}
    if player_name == 'Debi':
        return normalized_round_creator in {'Mom', 'Debi'}
    return normalized_round_creator == player_name


def _profile_player_matches_any_creator(player_field, *round_creators):
    return any(
        _profile_player_matches_creator(round_creator, player_field)
        for round_creator in round_creators
        if round_creator
    )


def _profile_creator_name_variants(player_field):
    player_name = display_name_for_player_field(player_field)
    if player_name == 'Dan':
        return {'Dad', 'Dan'}
    if player_name == 'Debi':
        return {'Mom', 'Debi'}
    return {player_name} if player_name else set()


def _profile_creator_round_query(player_field):
    creator_variants = _profile_creator_name_variants(player_field)
    if not creator_variants:
        return Q(pk__in=[])
    return Q(creator__in=creator_variants) | Q(secondary_creator__in=creator_variants)


def _count_created_rounds_for_profile_player(player_field):
    return GPTriviaRound.objects.filter(_profile_creator_round_query(player_field)).count()


def _build_profile_creator_panels_context(player_name, score_field):
    created_rounds = list(
        GPTriviaRound.objects
        .filter(_profile_creator_round_query(score_field))
        .order_by('-date', 'round_number')
    )

    for round_obj in created_rounds:
        round_summary = _summarize_profile_round_scores(round_obj)
        round_obj.high_score = round_summary['high_score']
        round_obj.average_score = round_summary['average_score']
        round_obj.high_score_display = round_summary['high_score_display']
        round_obj.average_score_display = round_summary['average_score_display']

    all_categories = sorted({
        category
        for category in GPTriviaRound.objects.values_list('major_category', flat=True)
        if category
    })
    all_minor_categories = sorted({
        category
        for category in GPTriviaRound.objects.values_list('minor_category1', flat=True)
        if category
    } | {
        category
        for category in GPTriviaRound.objects.values_list('minor_category2', flat=True)
        if category
    })

    created_category_counts = {
        category: 0
        for category in all_categories
    }
    for round_obj in created_rounds:
        if round_obj.major_category:
            created_category_counts[round_obj.major_category] = (
                created_category_counts.get(round_obj.major_category, 0) + 1
            )

    created_rounds_cat_list = [
        {'major_category': category, 'num_rounds': created_category_counts.get(category, 0)}
        for category in all_categories
    ]

    return {
        'player_name': player_name,
        'created_rounds': created_rounds,
        'created_rounds_cat': created_rounds_cat_list,
        'available_major_categories': all_categories,
        'available_minor_categories': all_minor_categories,
        'created_rounds_count': len(created_rounds),
    }


def _get_profile_round_creator_fields(round_obj):
    return {
        player_field_for_name(creator_name)
        for creator_name in (
            getattr(round_obj, 'creator', ''),
            getattr(round_obj, 'secondary_creator', ''),
        )
        if player_field_for_name(creator_name)
    }


def _normalize_profile_selected_joker_titles(raw_selection):
    if isinstance(raw_selection, list):
        return list(dict.fromkeys(
            title for title in raw_selection
            if isinstance(title, str) and title.strip() and title.strip().lower() != 'select'
        ))[:2]
    if isinstance(raw_selection, str):
        normalized_title = raw_selection.strip()
        if normalized_title and normalized_title.lower() != 'select':
            return [normalized_title]
    return []


def _get_profile_joker_weight(selected_titles):
    return 0.5 if len(selected_titles) > 1 else 1.0


def _build_profile_night_final_totals(night_rounds, presentation):
    night_totals = _build_profile_night_player_totals(night_rounds, presentation)
    return {
        player_field: totals['final_total']
        for player_field, totals in night_totals.items()
    }


def _player_completed_profile_night(player_field, night_rounds):
    for round_obj in night_rounds:
        score_map = get_round_score_map(round_obj, include_null_fixed=False)
        player_score = score_map.get(player_field)
        if isinstance(player_score, (int, float)):
            continue
        if _profile_player_matches_any_creator(
            player_field,
            round_obj.creator,
            getattr(round_obj, 'secondary_creator', ''),
        ):
            continue
        return False
    return True


def _build_profile_night_score_totals(night_rounds, presentation):
    night_totals = _build_profile_night_player_totals(night_rounds, presentation)
    return {
        player_field: {
            'score_total': totals['percentage_score_total'],
            'possible_total': totals['percentage_possible_total'],
        }
        for player_field, totals in night_totals.items()
    }


def _build_profile_style_points_total(player_name):
    total = 0.0

    for presentation in MergedPresentation.objects.all():
        style_points_raw = _parse_profile_presentation_json(
            getattr(presentation, 'style_points', None),
            {},
        )
        if not isinstance(style_points_raw, dict):
            continue

        for raw_player_name, raw_value in style_points_raw.items():
            if display_name_for_player_field(raw_player_name) != player_name:
                continue

            try:
                numeric_value = float(raw_value)
            except (TypeError, ValueError):
                continue
            total += numeric_value

    return int(total) if float(total).is_integer() else round(total, 2)


def _build_profile_night_player_totals(night_rounds, presentation):
    player_fields = set(collect_player_fields(
        rounds=night_rounds,
        presentations=[presentation] if presentation else None,
        include_fixed=False,
    ))
    for round_obj in night_rounds:
        player_fields.update(get_round_score_map(round_obj, include_null_fixed=False).keys())
    player_fields = sorted(player_fields)
    if not player_fields:
        return {}

    selected_rounds_raw = _parse_profile_presentation_json(
        getattr(presentation, 'joker_round_indices', None) if presentation else None,
        {},
    )
    selected_rounds = {
        player_field_for_name(player_key): _normalize_profile_selected_joker_titles(round_title)
        for player_key, round_title in (selected_rounds_raw or {}).items()
        if player_field_for_name(player_key) and _normalize_profile_selected_joker_titles(round_title)
    }

    median_scores_by_title = {}
    for round_obj in night_rounds:
        score_map = get_round_score_map(round_obj, include_null_fixed=False)
        creator_fields = _get_profile_round_creator_fields(round_obj)
        score_values = [
            score
            for candidate_field, score in score_map.items()
            if candidate_field not in creator_fields and isinstance(score, (int, float))
        ]
        if not score_values:
            median_scores_by_title[round_obj.title] = None
            continue

        score_values.sort()
        middle_index = len(score_values) // 2
        if len(score_values) % 2 == 0:
            median_value = (score_values[middle_index - 1] + score_values[middle_index]) / 2
        else:
            median_value = score_values[middle_index]
        median_scores_by_title[round_obj.title] = median_value

    totals = {}
    overall_round_max_scores = sorted(
        (round_obj.max_score for round_obj in night_rounds if round_obj.max_score not in (None, 0)),
        reverse=True,
    )
    for player_field in player_fields:
        round_total = 0
        creator_bonus_total = 0
        joker_bonus = 0
        percentage_score_total = 0
        has_any_value = False
        completed = True
        selected_round_titles = selected_rounds.get(player_field, [])
        selected_round_title_set = set(selected_round_titles)
        joker_weight = _get_profile_joker_weight(selected_round_titles) if selected_round_titles else 0
        percentage_possible_total = 0

        for round_obj in night_rounds:
            score_map = get_round_score_map(round_obj, include_null_fixed=False)
            player_score = score_map.get(player_field)
            is_creator = _profile_player_matches_any_creator(
                player_field,
                round_obj.creator,
                getattr(round_obj, 'secondary_creator', ''),
            )
            median_value = median_scores_by_title.get(round_obj.title)

            if not is_creator and round_obj.max_score not in (None, 0):
                percentage_possible_total += round_obj.max_score

            if isinstance(player_score, (int, float)):
                round_total += player_score
                has_any_value = True
                if not is_creator:
                    percentage_score_total += player_score
                if round_obj.title in selected_round_title_set and not is_creator:
                    joker_bonus += player_score * joker_weight
            elif is_creator:
                has_any_value = True
            else:
                completed = False

            if is_creator:
                if isinstance(median_value, (int, float)):
                    creator_bonus_total += median_value
                    has_any_value = True
                    if round_obj.title in selected_round_title_set:
                        joker_bonus += median_value * joker_weight

        if not has_any_value:
            continue

        joker_possible_total = 0
        if selected_round_titles:
            joker_possible_total = sum(
                round_max * joker_weight
                for round_max in overall_round_max_scores[:len(selected_round_titles)]
            )
        denominator = percentage_possible_total + joker_possible_total
        totals[player_field] = {
            'final_total': round_total + creator_bonus_total + joker_bonus,
            'percentage_score_total': percentage_score_total + joker_bonus,
            'percentage_possible_total': denominator,
            'completed': completed,
        }

    return totals


def _build_profile_best_night_stats(all_rounds, player_name, active_player_names):
    score_field = player_field_for_name(player_name)
    other_player_fields = [
        player_field_for_name(active_player_name)
        for active_player_name in active_player_names
        if active_player_name != player_name
    ]
    other_player_fields = [player_field for player_field in other_player_fields if player_field]

    rounds_by_date = {}
    for round_obj in all_rounds:
        rounds_by_date.setdefault(round_obj.date, []).append(round_obj)

    best_score_stat = None
    best_performance_stat = None

    for night_date, night_rounds in rounds_by_date.items():
        night_presentation = _get_scoresheet_presentation(selected_date=night_date.isoformat())
        night_totals = _build_profile_night_player_totals(night_rounds, night_presentation)
        player_night_totals = night_totals.get(score_field)
        player_score_totals = None
        if player_night_totals:
            player_score_totals = {
                'score_total': player_night_totals['percentage_score_total'],
                'possible_total': player_night_totals['percentage_possible_total'],
            }
        if player_score_totals and player_score_totals['possible_total']:
            player_percentage = player_score_totals['score_total'] / player_score_totals['possible_total']
            best_score_candidate = {
                'date': night_date,
                'display_value': _format_profile_percentage_stat(
                    player_score_totals['score_total'],
                    player_score_totals['possible_total'],
                ),
                'player_total': player_score_totals['score_total'],
                'max_total': player_score_totals['possible_total'],
                'percentage': player_percentage,
            }
            if (
                best_score_stat is None
                or player_percentage > best_score_stat['percentage']
                or (
                    player_percentage == best_score_stat['percentage']
                    and night_date > best_score_stat['date']
                )
            ):
                best_score_stat = best_score_candidate

        if player_night_totals and player_night_totals.get('completed'):
            eligible_other_totals = [
                totals['final_total']
                for other_player_field, totals in night_totals.items()
                if (
                    other_player_field != score_field
                    and other_player_field in other_player_fields
                    and totals.get('completed')
                )
            ]

            if eligible_other_totals:
                performance_player_total = player_night_totals['final_total'] if player_night_totals else None
                if performance_player_total is None:
                    continue
                second_place_total = max(eligible_other_totals)
                performance_gap = performance_player_total - second_place_total
                best_performance_candidate = {
                    'date': night_date,
                    'display_value': _format_profile_gap_stat(performance_gap),
                    'gap_total': performance_gap,
                }
                if (
                    best_performance_stat is None
                    or performance_gap > best_performance_stat['gap_total']
                    or (
                        performance_gap == best_performance_stat['gap_total']
                        and night_date > best_performance_stat['date']
                    )
                ):
                    best_performance_stat = best_performance_candidate

    if best_score_stat:
        best_score_stat['scoresheet_link'] = _build_scoresheet_date_link(best_score_stat['date'])
    if best_performance_stat:
        best_performance_stat['scoresheet_link'] = _build_scoresheet_date_link(best_performance_stat['date'])

    return {
        'best_score_ever': best_score_stat,
        'best_performance_ever': best_performance_stat,
    }


def _build_profile_streak_timeline(all_rounds, player_name):
    score_field = player_field_for_name(player_name)
    if not score_field:
        return {
            'timeline': [],
            'longest_play_streak': 0,
            'longest_creator_streak': 0,
        }

    rounds_by_date = {}
    for round_obj in all_rounds:
        rounds_by_date.setdefault(round_obj.date, []).append(round_obj)

    presentations_by_date = {}
    for presentation in MergedPresentation.objects.all():
        presentation_date = _parse_presentation_name_date(presentation.name)
        if presentation_date is not None:
            presentations_by_date[presentation_date] = presentation

    player_storage_key = _get_profile_player_storage_key(score_field)
    night_dates = sorted(set(rounds_by_date.keys()) | set(presentations_by_date.keys()))

    longest_play_streak = 0
    longest_creator_streak = 0
    current_play_streak = 0
    current_creator_streak = 0
    timeline = []

    for night_date in night_dates:
        night_rounds = rounds_by_date.get(night_date, [])
        presentation = presentations_by_date.get(night_date)
        joker_rounds_raw = _parse_profile_presentation_json(
            getattr(presentation, 'joker_round_indices', None) if presentation else None,
            {},
        )
        presentation_creators = _parse_profile_presentation_json(
            getattr(presentation, 'creator_list', None) if presentation else None,
            [],
        )
        presentation_players_raw = _parse_profile_presentation_json(
            getattr(presentation, 'player_list', None) if presentation else None,
            {},
        )
        valid_saved_jokers = {
            storage_key: _normalize_profile_selected_joker_titles(value)
            for storage_key, value in (joker_rounds_raw or {}).items()
            if _normalize_profile_selected_joker_titles(value)
        }
        has_saved_joker = any(
            valid_saved_jokers.get(storage_key)
            for storage_key in (player_storage_key, score_field)
            if storage_key
        )
        has_any_scores_recorded = any(
            isinstance(score_value, (int, float))
            for round_obj in night_rounds
            for score_value in get_round_score_map(round_obj, include_null_fixed=False).values()
        )
        presentation_player_names = []
        if isinstance(presentation_players_raw, dict):
            presentation_player_names.extend(presentation_players_raw.values())
            presentation_player_names.extend(presentation_players_raw.keys())
        elif isinstance(presentation_players_raw, list):
            presentation_player_names.extend(presentation_players_raw)
        elif presentation_players_raw:
            presentation_player_names.append(presentation_players_raw)
        listed_as_player = any(
            display_name_for_player_field(player_entry) == player_name
            for player_entry in presentation_player_names
            if player_entry
        )
        played = any(
            isinstance(get_round_score_map(round_obj, include_null_fixed=False).get(score_field), (int, float))
            for round_obj in night_rounds
        ) or has_saved_joker or (
            not has_any_scores_recorded
            and not valid_saved_jokers
            and listed_as_player
        )
        created = any(
            _profile_player_matches_any_creator(
                score_field,
                round_obj.creator,
                getattr(round_obj, 'secondary_creator', ''),
            )
            for round_obj in night_rounds
        ) or any(
            _profile_player_matches_creator(creator_name, score_field)
            for creator_name in presentation_creators
        )

        current_play_streak = current_play_streak + 1 if played else 0
        current_creator_streak = current_creator_streak + 1 if created else 0
        longest_play_streak = max(longest_play_streak, current_play_streak)
        longest_creator_streak = max(longest_creator_streak, current_creator_streak)

        timeline.append({
            'date': night_date,
            'played': played,
            'created': created,
        })

    return {
        'timeline': timeline,
        'longest_play_streak': longest_play_streak,
        'longest_creator_streak': longest_creator_streak,
    }


def _build_profile_deferred_stats_context(
    all_rounds,
    flattened_rounds,
    player_name,
    score_field,
    created_rounds_count,
    active_player_names,
    global_player_names,
):
    player_values = [
        round_data.get(score_field)
        for round_data in flattened_rounds
        if round_data.get(score_field) is not None
    ]
    best_night_stats = _build_profile_best_night_stats(all_rounds, player_name, active_player_names)
    streak_timeline = _build_profile_streak_timeline(all_rounds, player_name)
    player_avg = (sum(player_values) / len(player_values)) if player_values else None
    total_rounds = len(player_values)
    style_points_total = _build_profile_style_points_total(player_name)

    all_categories = sorted({
        round_data['major_category']
        for round_data in flattened_rounds
        if round_data['major_category']
    })
    category_averages = []
    for category in all_categories:
        values = [
            round_data.get(score_field)
            for round_data in flattened_rounds
            if round_data['major_category'] == category and round_data.get(score_field) is not None
        ]
        avg_score = (sum(values) / len(values)) if values else None
        category_averages.append({
            'major_category': category,
            'avg_score': (avg_score - player_avg) if avg_score is not None and player_avg is not None else 0,
        })
    category_averages = sorted(category_averages, key=lambda item: item['avg_score'], reverse=True)

    max_avg = category_averages[0]['major_category'] if category_averages else ''
    min_avg = category_averages[-1]['major_category'] if category_averages else ''

    normalized_creators = sorted({
        round_data['normalized_creator']
        for round_data in flattened_rounds
        if round_data['normalized_creator']
    })

    creator_averages = []
    for creator_name in normalized_creators:
        values = [
            round_data.get(score_field)
            for round_data in flattened_rounds
            if round_data['normalized_creator'] == creator_name and round_data.get(score_field) is not None
        ]
        avg_score = (sum(values) / len(values)) if values else None
        if creator_name == player_name:
            continue
        creator_averages.append({
            'creator': creator_name,
            'avg_score': (avg_score - player_avg) if avg_score is not None and player_avg is not None else None,
        })
    creator_averages = sorted(
        creator_averages,
        key=lambda item: item['avg_score'] if item['avg_score'] is not None else float('-inf'),
        reverse=True,
    )

    eligible_creator_averages = [
        creator_avg
        for creator_avg in creator_averages
        if (
            creator_avg['creator'] in global_player_names
            and creator_avg['creator'] in active_player_names
            and creator_avg['creator'] != player_name
            and creator_avg['avg_score'] is not None
        )
    ]
    max_creator_avg = eligible_creator_averages[0]['creator'] if eligible_creator_averages else ''
    min_creator_avg = eligible_creator_averages[-1]['creator'] if eligible_creator_averages else ''

    creator_player_scores = {}
    for creator_name in global_player_names:
        creator_records = [
            round_data for round_data in flattened_rounds
            if round_data['normalized_creator'] == creator_name
        ]
        player_scores = {}
        for other_player in global_player_names:
            other_field = player_field_for_name(other_player)
            values = [
                round_data.get(other_field)
                for round_data in creator_records
                if round_data.get(other_field) is not None
            ]
            player_scores[other_player] = (sum(values) / len(values)) if values else None
        creator_player_scores[creator_name] = player_scores

    creator_row_averages = {}
    for creator_name, score_map in creator_player_scores.items():
        values = [avg_score for avg_score in score_map.values() if avg_score is not None]
        creator_row_averages[creator_name] = (sum(values) / len(values)) if values else None

    favoritism_toward_player = {}
    for item in creator_averages:
        creator_name = item['creator']
        if creator_name not in active_player_names:
            continue
        creator_row_average = creator_row_averages.get(creator_name)
        if creator_row_average is not None and item['avg_score'] is not None:
            favoritism_toward_player[creator_name] = item['avg_score'] - creator_row_average
        else:
            favoritism_toward_player[creator_name] = 0

    favoritism_sum = 0
    for creator_name in list(favoritism_toward_player.keys()):
        if favoritism_toward_player[creator_name] is not None and player_avg is not None:
            favoritism_toward_player[creator_name] = favoritism_toward_player[creator_name] + player_avg
            favoritism_sum += favoritism_toward_player[creator_name]
        else:
            favoritism_toward_player[creator_name] = 0

    if favoritism_toward_player:
        mean_favoritism = favoritism_sum / len(favoritism_toward_player)
        for creator_name in list(favoritism_toward_player.keys()):
            if favoritism_toward_player[creator_name] is not None:
                favoritism_toward_player[creator_name] = favoritism_toward_player[creator_name] - mean_favoritism
            else:
                favoritism_toward_player[creator_name] = 0

    if favoritism_toward_player:
        most_favoring_creator = max(favoritism_toward_player, key=favoritism_toward_player.get)
        least_favoring_creator = min(favoritism_toward_player, key=favoritism_toward_player.get)
        most_favoring_creator_value = "{:.2f}".format(favoritism_toward_player[most_favoring_creator])
        least_favoring_creator_value = "{:.2f}".format(favoritism_toward_player[least_favoring_creator])
    else:
        most_favoring_creator = ''
        least_favoring_creator = ''
        most_favoring_creator_value = "0.00"
        least_favoring_creator_value = "0.00"

    player_creator_records = [
        round_obj for round_obj in all_rounds
        if _profile_player_matches_any_creator(
            score_field,
            round_obj.creator,
            getattr(round_obj, 'secondary_creator', ''),
        )
    ]
    creator_favoritism_by_player = {}
    for other_player in global_player_names:
        if other_player not in active_player_names or other_player == player_name:
            continue
        other_field = player_field_for_name(other_player)
        creator_round_scores = [
            get_round_score_map(round_obj, include_null_fixed=False).get(other_field)
            for round_obj in player_creator_records
            if get_round_score_map(round_obj, include_null_fixed=False).get(other_field) is not None
        ]
        if not creator_round_scores:
            continue
        creator_round_average = sum(creator_round_scores) / len(creator_round_scores)
        overall_scores = [
            round_data.get(other_field)
            for round_data in flattened_rounds
            if round_data.get(other_field) is not None
        ]
        if not overall_scores:
            continue
        overall_average = sum(overall_scores) / len(overall_scores)
        creator_favoritism_by_player[other_player] = creator_round_average - overall_average

    if creator_favoritism_by_player:
        most_favored_player = max(creator_favoritism_by_player, key=creator_favoritism_by_player.get)
        least_favored_player = min(creator_favoritism_by_player, key=creator_favoritism_by_player.get)
        most_favored_player_value = "{:.2f}".format(creator_favoritism_by_player[most_favored_player])
        least_favored_player_value = "{:.2f}".format(creator_favoritism_by_player[least_favored_player])
    else:
        most_favored_player = ''
        least_favored_player = ''
        most_favored_player_value = "0.00"
        least_favored_player_value = "0.00"

    return {
        'total_rounds': total_rounds,
        'created_rounds_count': created_rounds_count,
        'style_points_total': style_points_total,
        'best_score_ever': best_night_stats['best_score_ever'],
        'best_performance_ever': best_night_stats['best_performance_ever'],
        'max_avg': max_avg,
        'min_avg': min_avg,
        'max_cat_avg': max_creator_avg,
        'min_cat_avg': min_creator_avg,
        'most_favoring_creator': most_favoring_creator,
        'least_favoring_creator': least_favoring_creator,
        'most_favoring_creator_value': most_favoring_creator_value,
        'least_favoring_creator_value': least_favoring_creator_value,
        'most_favored_player': most_favored_player,
        'least_favored_player': least_favored_player,
        'most_favored_player_value': most_favored_player_value,
        'least_favored_player_value': least_favored_player_value,
        'streak_timeline': streak_timeline['timeline'],
        'longest_play_streak': streak_timeline['longest_play_streak'],
        'longest_creator_streak': streak_timeline['longest_creator_streak'],
    }


@login_required
def player_profile_dict(
    request,
    player_name,
    form=None,
    intro_form=None,
    include_form=False,
    include_deferred_stats=True,
    include_creator_panels=False,
):
    player_name = display_name_for_player_field(player_name)
    score_field = player_field_for_name(player_name)

    profile_user = User.objects.filter(username__iexact=player_name).first()
    if not profile_user and player_name not in _get_global_player_names():
        raise Http404("Player profile not available")
    profile = profile_user.profile if profile_user else None

    all_profile_player_names = sorted({
        display_name_for_player_field(profile.user.username)
        for profile in Profile.objects.select_related('user')
        if profile.user_id and display_name_for_player_field(profile.user.username)
    })

    player_color = get_player_color(player_name)
    brightness = (0.5 * int(player_color[1:3], 16)) + int(player_color[3:5], 16) + (0.25 * int(player_color[5:7], 16))
    text_color = 'white' if brightness < 300 else 'black'
    created_rounds_count = _count_created_rounds_for_profile_player(score_field)

    created_rounds = []
    created_rounds_cat_list = []
    available_major_categories = []
    available_minor_categories = []
    if include_creator_panels:
        creator_panels_context = _build_profile_creator_panels_context(player_name, score_field)
        created_rounds = creator_panels_context['created_rounds']
        created_rounds_cat_list = creator_panels_context['created_rounds_cat']
        available_major_categories = creator_panels_context['available_major_categories']
        available_minor_categories = creator_panels_context['available_minor_categories']
        created_rounds_count = creator_panels_context['created_rounds_count']

    deferred_stats = {}
    if include_deferred_stats:
        all_rounds = list(GPTriviaRound.objects.all().order_by('-date', 'round_number'))
        flattened_rounds = [
            {
                **flatten_round_for_analysis(round_obj),
                'normalized_creator': display_name_for_player_field(round_obj.creator),
            }
            for round_obj in all_rounds
        ]
        global_player_names = _get_global_player_names()
        active_player_names = _get_recently_active_profile_player_names(all_rounds)
        deferred_stats = _build_profile_deferred_stats_context(
            all_rounds,
            flattened_rounds,
            player_name,
            score_field,
            created_rounds_count,
            active_player_names,
            global_player_names,
        )

    profile_page_chrome_color = _get_profile_page_color_value(
        profile,
        'profile_page_chrome_color',
        Profile.PROFILE_PAGE_CHROME_DEFAULT,
    )
    profile_card_color = _darken_hex_color(profile_page_chrome_color)
    profile_card_text_color = _profile_text_color_for_background(profile_card_color)
    profile_card_muted_text_color = _with_alpha(profile_card_text_color, 0.72)
    if form is None and include_form:
        form = ProfilePictureForm(instance=profile)
    profile_picture_url = get_profile_picture_url(profile)
    is_own_profile = bool(
        profile_user
        and request.user.is_authenticated
        and request.user.pk == profile_user.pk
    )
    if intro_form is None and is_own_profile:
        intro_form = ProfileIntroForm(initial={'profile_intro': getattr(profile, 'profile_intro', '')})
    can_edit_round_categories = _can_edit_profile_round_categories(request.user, profile_user, player_name)
    profile_intro_value = (
        intro_form['profile_intro'].value()
        if intro_form is not None and getattr(intro_form, 'is_bound', False)
        else getattr(profile, 'profile_intro', '')
    )

    context = {
        'profile': profile,
        'profile_user': profile_user,
        'profile_page_chrome_color': profile_page_chrome_color,
        'profile_card_color': profile_card_color,
        'profile_card_text_color': profile_card_text_color,
        'profile_card_muted_text_color': profile_card_muted_text_color,
        'profile_page_trivia_color_one': _get_profile_page_color_value(
            profile,
            'profile_page_trivia_color_one',
            Profile.PROFILE_PAGE_TRIVIA_COLOR_ONE_DEFAULT,
        ),
        'profile_page_trivia_color_two': _get_profile_page_color_value(
            profile,
            'profile_page_trivia_color_two',
            Profile.PROFILE_PAGE_TRIVIA_COLOR_TWO_DEFAULT,
        ),
        'profile_page_trivia_color_three': _get_profile_page_color_value(
            profile,
            'profile_page_trivia_color_three',
            Profile.PROFILE_PAGE_TRIVIA_COLOR_THREE_DEFAULT,
        ),
        'profile_intro': (profile_intro_value or '').strip(),
        'page_profile_theme': getattr(profile, 'profile_page_theme', Profile.THEME_DEFAULT) or Profile.THEME_DEFAULT,
        'is_own_profile': is_own_profile,
        'can_edit_round_categories': can_edit_round_categories,
        'profile_picture_url': profile_picture_url,
        'player_name': player_name,
        'player_color': player_color,
        'created_rounds_count': created_rounds_count,
        'profile_stats_url': reverse('player_profile_stats', kwargs={'player_name': player_name}),
        'profile_creator_panels_url': reverse('player_profile_creator_panels', kwargs={'player_name': player_name}),
        'created_rounds_cat': created_rounds_cat_list,
        'created_rounds': created_rounds,
        'available_major_categories': available_major_categories,
        'available_minor_categories': available_minor_categories,
        'player_color_mapping': build_player_color_mapping(all_profile_player_names),
        'text_color': text_color,
        'defer_profile_stats': not include_deferred_stats,
        'defer_profile_creator_panels': not include_creator_panels,
    }
    context.update(deferred_stats)

    if include_form or form is not None:
        context['form'] = form
    if intro_form is not None:
        context['profile_intro_form'] = intro_form

    return context


@login_required
def update_profile_round_category(request, round_id):
    if request.method != 'POST':
        raise Http404("Category updates must be submitted with POST.")

    round_obj = get_object_or_404(GPTriviaRound, id=round_id)
    round_creator_names = [
        display_name_for_player_field(creator_name)
        for creator_name in (round_obj.creator, getattr(round_obj, 'secondary_creator', ''))
        if display_name_for_player_field(creator_name)
    ]
    primary_round_creator_name = round_creator_names[0] if round_creator_names else ''
    can_edit_round = False
    for round_creator_name in round_creator_names or [primary_round_creator_name]:
        profile_user = User.objects.filter(username__iexact=round_creator_name).first()
        if _can_edit_profile_round_categories(request.user, profile_user, round_creator_name):
            can_edit_round = True
            break
    if not can_edit_round:
        raise Http404("Round not found.")

    allowed_fields = {'major_category', 'minor_category1', 'minor_category2'}
    fields_to_update = {
        field_name: (request.POST.get(field_name) or '').strip()
        for field_name in allowed_fields
        if field_name in request.POST
    }
    if not fields_to_update:
        raise Http404("No editable category field provided.")

    for field_name, field_value in fields_to_update.items():
        setattr(round_obj, field_name, field_value)
    round_obj.save(update_fields=list(fields_to_update.keys()))

    wants_json = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        or 'application/json' in (request.headers.get('Accept') or '')
    )
    if wants_json:
        return JsonResponse(
            {
                'success': True,
                'round_id': round_obj.id,
                'fields': {
                    'major_category': round_obj.major_category or '',
                    'minor_category1': round_obj.minor_category1 or '',
                    'minor_category2': round_obj.minor_category2 or '',
                },
                'panel': (request.POST.get('next_panel') or '').strip(),
            }
        )

    redirect_target_name = primary_round_creator_name or display_name_for_player_field(round_obj.creator)
    redirect_url = reverse('player_profile', kwargs={'player_name': redirect_target_name})
    panel = (request.POST.get('next_panel') or '').strip()
    if panel:
        redirect_url = f"{redirect_url}?{urlencode({'panel': panel})}"
    return redirect(redirect_url)

# views.py
class GenerateIdeaView(View):
    def post(self, request, *args, **kwargs):
        items_list = ["Physical Science", "Biology", "Anatomy", "Human Organs", "Bones and Muscles", "Cells", "Cell Structures", "Medicine", "Common Diseases", "Medical Milestones", "Genetics", "Basic Genetics", "Evolution",
                      "Evolutionary Milestones", "Extinct Species", "Ecology", "Ecosystems", "Endangered Species", "Chemistry", "Atoms", "Atomic Structure", "Notable Elements", "The Periodic Table", "Element Categories",
                      "Chemical Reactions", "Organic Chemistry", "Organic Compounds", "Inorganic Chemistry", "Inorganic Compounds", "Physics", "Mechanics", "Laws of Motion", "Simple Machines", "Optics",
                      "Light and Color", "Optical Illusions", "Electricity and Magnetism", "Basic Circuits", "Magnetic Fields", "Quantum Mechanics", "Basic Quantum Concepts", "Relativity", "Basic Concepts of Relativity",
                      "Entertainment", "Music", "Famous Musicians", "Hit Singles and Albums", "Movies", "Famous Directors and Actors", "Box Office Hits", "Television", "Famous TV Shows", "Memorable TV Characters", "Books",
                      "Famous Authors", "Bestselling Books", "Video Games", "Popular Video Games", "Renowned Game Developers", "Theater and Musicals", "Famous Plays and Musicals", "Notable Playwrights and Composers",
                      "Iconic Theaters", "Comics and Animation", "Popular Comics", "Famous Animators and Studios", "Iconic Animated Characters", "History", "Ancient Civilizations", "Ancient Egyptian Civilization",
                      "Ancient Greek Civilization", "Ancient Roman Civilization", "Ancient Chinese Civilization", "Ancient Mesopotamian Civilization", "Medieval History", "Medieval Feudal System", "Medieval Crusades",
                      "Medieval Black Death", "Renaissance and Enlightenment", "Renaissance Art and Inventions", "Enlightenment Thinkers and Ideas", "Modern History", "World Wars", "World War I Events", "World War II Events",
                      "Cold War Events", "Significant 20th Century Events", "American History", "American Revolution Events", "American Civil War Events", "Significant American Legislation", "American Civil Rights Movement",
                      "Asian History", "Chinese Dynasties", "Japanese Shogunate History", "Indian Independence Movement", "European History", "British Monarchy History", "French Revolution Events", "Russian Revolution Events",
                      "African History", "Ancient African Kingdoms", "African Colonial Era", "African Post-Colonial Era", "Latin American History", "Pre-Columbian Civilizations", "Latin American Colonial Era",
                      "Latin American Independence Movements", "Food", "Cuisines", "Italian Cuisine", "Chinese Cuisine", "Mexican Cuisine", "Indian Cuisine", "French Cuisine", "Cooking Techniques", "Baking", "Grilling", "Frying",
                      "Ingredients", "Vegetables", "Fruits", "Meats", "Dairy Products", "Dishes", "Appetizers", "Main Courses", "Desserts", "Snacks", "Drinks", "Alcoholic Beverages", "Non-Alcoholic Beverages", "Coffee and Tea",
                      "Dietary Preferences", "Vegetarianism", "Veganism", "Food Industry", "Famous Chefs", "Popular Restaurants", "Nature", "Animals", "Mammals", "Birds", "Reptiles", "Amphibians", "Fish", "Insects", "Plants",
                      "Trees", "Flowers", "Natural Phenomena", "Weather Events", "Natural Disasters", "Ecosystems", "Forests", "Deserts", "Oceans", "Conservation", "Endangered Species", "Conservation Efforts", "Geology",
                      "Rocks and Minerals", "Fossils", "Water Bodies", "Rivers and Lakes", "Oceans and Seas", "Exploration", "Famous Naturalists", "Technology", "Computing", "Hardware", "Software", "The Internet", "Electronics",
                      "Gadgets and Devices", "Home Appliances", "Telecommunications", "Mobile Technology", "Networking", "Transportation Technology", "Automotive Technology", "Aviation Technology", "Energy Technology",
                      "Renewable Energy", "Fossil Fuels", "Medical Technology", "Medical Devices", "Telemedicine", "Industrial Technology", "Robotics", "Automation", "Emerging Technologies", "Artificial Intelligence",
                      "Virtual Reality and Augmented Reality", "Sports", "Team Sports", "Football (Soccer)", "American Football", "Baseball", "Basketball", "Hockey", "Individual Sports", "Tennis", "Golf", "Swimming",
                      "Athletics (Track and Field)", "Boxing", "Water Sports", "Sailing", "Surfing", "Winter Sports", "Skiing", "Snowboarding", "Motorsports", "Formula 1", "NASCAR", "Racket Sports", "Badminton", "Table Tennis",
                      "Equestrian Sports", "Horse Racing", "International Competitions", "Olympics", "World Cup (various sports)", "Sports Personalities", "Famous Athletes", "Notable Coaches", "Music", "Musical Genres",
                      "Pop Music", "Rock Music", "Hip-Hop Music", "Country Music", "Classical Music", "Musical Instruments", "String Instruments", "Wind Instruments", "Percussion Instruments", "Keyboard Instruments",
                      "Musical Performance", "Solo Performance", "Ensemble Performance", "Music Production", "Recording Techniques", "Music Producers", "Music Industry", "Record Labels", "Music Awards", "Famous Musicians and Bands",
                      "Iconic Singers", "Legendary Bands", "Music Events and Festivals", "Music Festivals", "Charity Concerts", "Humanities", "Philosophy", "Famous Philosophers", "Philosophical Movements", "Literature", "Literature Genres",
                      "Fiction Novels", "Poetry Collections", "Drama Plays", "Fantasy Novels", "Mystery Novels", "Science Fiction Novels", "Historical Literature Periods", "Classical Literature", "Modern Literature", "Famous Authors",
                      "Notable Poets", "Iconic Novelists", "Celebrated Playwrights", "Major Literary Works", "Classic Novels", "Significant Poems", "Memorable Plays", "Literary Awards", "Booker Prize Winners", "Pulitzer Prize Winners",
                      "Nobel Prize in Literature Laureates", "Geography and Languages", "Physical Geography", "Landforms", "Bodies of Water", "Political Geography", "Countries and Capitals", "Borders and Territories", "Languages",
                      "World Languages", "Linguistics", "Regional Studies", "African Geography and Languages", "Asian Geography and Languages", "European Geography and Languages", "North American Geography and Languages",
                      "South American Geography and Languages", "Oceania Geography and Languages", "Travel and Tourism", "Famous Landmarks", "World Cities", "Languages", "Language Families", "Indo-European Languages",
                      "Sino-Tibetan Languages", "Afro-Asiatic Languages", "World Languages", "English", "Spanish", "Mandarin Chinese", "French", "Arabic", "Linguistics", "Phonetics and Phonology", "Linguistic Syntax", "Writing Systems",
                      "Alphabets", "Syllabaries", "Historical and Ancient Languages", "Latin", "Ancient Greek", "Regional Languages", "European Languages", "Asian Languages", "African Languages", "Language in Society", "Sociolinguistics",
                      "Dialects and Varieties", "Government", "Political Systems", "Democracy", "Monarchy", "Republican Government", "Branches of Government", "The Executive Branch", "The Legislative Branch", "The Judicial Branch", "Elections and Voting", "Electoral Systems",
                      "Political Campaigns", "Political Parties and Ideologies", "Major Political Parties", "Government Institutions", "Parliaments and Congresses", "Courts", "International Relations", "International Organizations",
                      "Diplomacy", "Public Policy", "Economic Policy", "Environmental Policy", "Civil Rights and Liberties", "Human Rights", "Freedom of Speech", "Legal Systems", "Common Law", "Civil Law", "Historical and Political Figures",
                      "Heads of State", "Influential Politicians", "Political Activism", "Protests and Movements", "Word Games", "Current Events", "Hodgepodge", "Family", "Mathematics", "Computer Science", "Clouds", "Space", "Space Travel"]
        random_item = random.choice(items_list)
        suggestion = f'How about {random_item}?'
        return JsonResponse({'suggestion': suggestion})

class AutoGenView(View):
    def post(self, request, *args, **kwargs):
        user_input = (request.POST.get('user_input') or '').strip()
        client = _get_openai_client()

        try:
            auto_resp = _create_openai_text_response(
                client=client,
                instructions=SWOOP_SAMPLE_QUESTION_PROMPT,
                input_items=user_input,
                max_output_tokens=220,
                reasoning_effort="low",
            )
        except Exception as e:
            auto_resp = str(e)

        return JsonResponse({'autogen_response': auto_resp})

class IconView(View):
    def post(self, request, *args, **kwargs):
        gpt_response = request.POST.get('question_text')
        client = _get_openai_client()


        try:
            try:
                second_response = _create_openai_text_response(
                    client=client,
                    instructions=SWOOP_ICON_KEYWORD_PROMPT,
                    input_items=gpt_response,
                    max_output_tokens=40,
                    reasoning_effort="low",
                )
            except Exception as e:
                second_response = str(e)
                print(f"EXCEPTION: {second_response}")
                return JsonResponse({'dalle_image_url': None})

            # Call to DALL-E to generate an image based on the conversation
            dalle_response = client.images.generate(prompt=f"Draw me a very simple minimalist white line icon on a black background using the following key words: {second_response}",
            # This assumes you want to generate an image based on the last text response from GPT-4
            n=1,  # Number of images to generate
            size="1024x1024",  # The size of the image
            model='gpt-image-1')
            print(f"DALLE RESPONSE: {dalle_response}")
            image_url = dalle_response.data[0].url  # URL of the generated image
            print(f"IMAGE_URL: {image_url}")

        except Exception as e:
            image_url = None  # No image if there's an error
            # print(f"EXCEPTION IMAGE_URL: {image_url}")
            print(f"EXCEPTION: {e}")


        return JsonResponse({'dalle_image_url': image_url})



class RoundMaker(View):
    template_name = 'GPTrivia/round_maker.html'

    def get(self, request, *args, **kwargs):
        _get_round_maker_conversation_history(request)
        return render(
            request,
            self.template_name,
            {
                'round_maker_creator_options': _build_round_maker_creator_options(),
                'round_maker_default_creator': (
                    display_name_for_player_field(request.user.username)
                    if request.user.is_authenticated
                    else ''
                ),
                'round_maker_template_options': _build_round_maker_template_options(request.user),
                'round_maker_can_use_smart_templates': _user_can_use_smart_round_templates(request.user),
            },
        )

    def post(self, request, *args, **kwargs):
        user_input = (request.POST.get('user_input') or '').strip()
        client = _get_openai_client()


        # Get the conversation history from the session
        conversation_history = _get_round_maker_conversation_history(request)
        # Append the user's message to the conversation history
        conversation_history.append({"role": "user", "content": user_input})

        try:
            gpt_response = _create_openai_text_response(
                client=client,
                instructions=SWOOP_SYSTEM_PROMPT,
                input_items=_build_responses_input(conversation_history),
                max_output_tokens=180,
                reasoning_effort="low",
            )
            conversation_history.append({"role": "assistant", "content": gpt_response})
            request.session['conversation_history'] = conversation_history
            request.session.modified = True
            if request.user.is_authenticated and hasattr(request.user, 'profile'):
                request.user.profile.swoop_conversation_history = conversation_history
                request.user.profile.save(update_fields=['swoop_conversation_history'])

        except Exception as e:
            gpt_response = str(e)

        return JsonResponse({'gpt_response': gpt_response})

@login_required
def player_profile(request, player_name):
    context = player_profile_dict(
        request,
        player_name,
        include_form=True,
        include_deferred_stats=False,
        include_creator_panels=False,
    )
    return render(request, 'GPTrivia/player_profile.html', context)


@login_required
def player_profile_stats(request, player_name):
    cache_key = f'player_profile_stats:v{_get_site_data_cache_version()}:{player_name.lower()}'
    if not _request_wants_fresh_cache(request):
        cached_payload = cache.get(cache_key)
        if cached_payload is not None:
            return JsonResponse(cached_payload, encoder=DjangoJSONEncoder)

    context = player_profile_dict(
        request,
        player_name,
        include_deferred_stats=True,
        include_creator_panels=False,
    )
    summary_html = render_to_string('GPTrivia/_player_profile_summary.html', context, request=request)
    timeline_html = render_to_string('GPTrivia/_player_profile_timeline.html', context, request=request)
    stats_payload = {
        'total_rounds': context.get('total_rounds'),
        'created_rounds_count': context.get('created_rounds_count'),
        'style_points_total': context.get('style_points_total'),
        'best_score_ever': context.get('best_score_ever'),
        'best_performance_ever': context.get('best_performance_ever'),
        'max_avg': context.get('max_avg'),
        'min_avg': context.get('min_avg'),
        'max_cat_avg': context.get('max_cat_avg'),
        'min_cat_avg': context.get('min_cat_avg'),
        'most_favoring_creator': context.get('most_favoring_creator'),
        'least_favoring_creator': context.get('least_favoring_creator'),
        'most_favoring_creator_value': context.get('most_favoring_creator_value'),
        'least_favoring_creator_value': context.get('least_favoring_creator_value'),
        'most_favored_player': context.get('most_favored_player'),
        'least_favored_player': context.get('least_favored_player'),
        'most_favored_player_value': context.get('most_favored_player_value'),
        'least_favored_player_value': context.get('least_favored_player_value'),
        'streak_timeline': context.get('streak_timeline'),
        'longest_play_streak': context.get('longest_play_streak'),
        'longest_creator_streak': context.get('longest_creator_streak'),
    }
    payload = {
        'ok': True,
        'summary_html': summary_html,
        'timeline_html': timeline_html,
        'stats': stats_payload,
    }
    cache.set(cache_key, payload, PROFILE_STATS_CACHE_TTL_SECONDS)
    return JsonResponse(payload, encoder=DjangoJSONEncoder)


@login_required
def player_profile_creator_panels(request, player_name):
    context = player_profile_dict(
        request,
        player_name,
        include_deferred_stats=False,
        include_creator_panels=True,
    )
    return JsonResponse({
        'ok': True,
        'created_categories_html': render_to_string(
            'GPTrivia/_player_profile_created_categories_panel.html',
            context,
            request=request,
        ),
        'created_rounds_html': render_to_string(
            'GPTrivia/_player_profile_created_rounds_panel.html',
            context,
            request=request,
        ),
    })


@sync_to_async          # runs blocking code in a thread-pool
def _collect_rounds():
    links, titles, creators, old_links, shared_dates = get_round_titles_and_links()
    submitted_rounds = list(SubmittedRound.objects.order_by('-submitted_at'))
    submitted_round_lookup = _build_submitted_round_lookup(submitted_rounds)
    creator_opt_in_map = _build_round_analysis_opt_in_map(creators)
    new_rounds = []
    for title, creator, link, old_link, shared_date in zip(titles, creators, links, old_links, shared_dates):
        submitted_round = _find_matching_submitted_round(
            title,
            creator,
            link,
            old_link,
            submitted_round_lookup,
            shared_date=shared_date,
        )
        if creator_opt_in_map.get(str(creator or '').strip()) and (
            not submitted_round or not str(submitted_round.source_title or '').strip()
        ):
            submitted_round, _ = _ensure_available_round_identified_title(
                title,
                creator,
                link,
                old_link,
                shared_date,
                submitted_round=submitted_round,
            )
        display_title = submitted_round.title if submitted_round and submitted_round.title else title
        source_title = (
            submitted_round.source_title
            if submitted_round and submitted_round.source_title
            else title
        )
        new_rounds.append(
            {
                "title": display_title,
                "source_title": source_title,
                "creator": submitted_round.creator if submitted_round and submitted_round.creator else creator,
                "link": link,
                "old_link": old_link,
                "presentation_id": (
                    (submitted_round.presentation_id if submitted_round else '')
                    or _extract_google_presentation_id(link)
                    or _extract_google_presentation_id(old_link)
                ),
                "shared_date": shared_date
                or (
                    submitted_round.shared_date.isoformat()
                    if submitted_round and submitted_round.shared_date
                    else (
                        submitted_round.submitted_at.date().isoformat()
                        if submitted_round and submitted_round.submitted_at
                        else ""
                    )
                ),
                "coop": bool(submitted_round.cooperative) if submitted_round else False,
                "is_new": True,
            }
        )
    historical_rounds = [
        {
            "title": trivia_round.title,
            "source_title": trivia_round.title,
            "creator": trivia_round.creator,
            "link": trivia_round.link,
            "old_link": trivia_round.source_link or trivia_round.link,
            "presentation_id": _extract_google_presentation_id(trivia_round.link),
            "shared_date": trivia_round.date.isoformat() if trivia_round.date else "",
            "coop": bool(trivia_round.cooperative),
            "is_new": False,
        }
        for trivia_round in GPTriviaRound.objects.order_by('-date', 'round_number', 'title')
    ]
    return new_rounds + historical_rounds

async def collect_rounds_api(request):
    if request.method != "GET":
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    cache_key = f'collect_rounds_api:v{_get_site_data_cache_version()}'
    data = None if _request_wants_fresh_cache(request) else cache.get(cache_key)
    if data is None:
        data = await _collect_rounds()
        cache.set(cache_key, data, HOME_ROUNDS_CACHE_TTL_SECONDS)
    return JsonResponse({"rounds": data})


def save_available_round_metadata(request):
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication required."}, status=403)

    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON payload."}, status=400)

    saved_round, error_message = _save_available_round_metadata(data, user=request.user)
    if error_message:
        return JsonResponse({"detail": error_message}, status=400)

    return JsonResponse({
        "ok": True,
        "presentation_id": saved_round.presentation_id,
        "title": saved_round.title,
        "source_title": saved_round.source_title or saved_round.title,
        "creator": saved_round.creator,
        "shared_date": saved_round.shared_date.isoformat() if saved_round.shared_date else '',
        "coop": bool(saved_round.cooperative),
    })


def _build_scoresheet_bootstrap_payload(requested_date=''):
    round_queryset = GPTriviaRound.objects.all()
    date_values = sorted({
        round_date.isoformat()
        for round_date in round_queryset.order_by().values_list('date', flat=True).distinct()
        if round_date
    }, reverse=True)
    parsed_requested_date = _parse_scoresheet_date(requested_date)
    selected_date = (
        parsed_requested_date.isoformat()
        if parsed_requested_date
        else (date_values[0] if date_values else '')
    )

    selected_rounds = round_queryset.filter(date=selected_date).order_by('round_number', 'id') if selected_date else GPTriviaRound.objects.none()
    creator_options = sorted({
        display_name_for_player_field(creator_name)
        for creator_name in chain(
            round_queryset.order_by().values_list('creator', flat=True).distinct(),
            round_queryset.order_by().values_list('secondary_creator', flat=True).distinct(),
        )
        if display_name_for_player_field(creator_name)
    })
    major_categories = sorted({
        category_name
        for category_name in round_queryset.order_by().values_list('major_category', flat=True).distinct()
        if category_name
    })
    minor_categories = sorted({
        category_name
        for category_name in chain(
            round_queryset.order_by().values_list('minor_category1', flat=True).distinct(),
            round_queryset.order_by().values_list('minor_category2', flat=True).distinct(),
            major_categories,
        )
        if category_name
    })

    return {
        'dates': date_values,
        'selected_date': selected_date,
        'creator_options': creator_options,
        'major_categories': major_categories,
        'minor_categories': minor_categories,
        'rounds': GPTriviaRoundSerializer(selected_rounds, many=True).data,
    }


@login_required
def scoresheet_bootstrap(request):
    requested_date = (request.GET.get('date') or '').strip()
    return JsonResponse(_build_scoresheet_bootstrap_payload(requested_date), encoder=CustomJSONEncoder)


def _build_scoresheet_presentation_meta_payload(selected_date=''):
    selected_presentation = _get_scoresheet_presentation(selected_date=selected_date)
    presentation_history = sorted(
        list(
            _ready_presentations_queryset(include_blank_ids=True)
            .only('name', 'crowned_winner')
            .values('name', 'crowned_winner')
        ),
        key=lambda item: _parse_presentation_name_date(item.get('name')) or datetime.date.min,
    )
    return {
        'selected_presentation': (
            MergedPresentationSerializer(selected_presentation).data
            if selected_presentation is not None
            else None
        ),
        'crown_history': presentation_history,
    }


@login_required
def scoresheet_presentation_meta(request):
    selected_date = (request.GET.get('date') or '').strip()
    return JsonResponse(_build_scoresheet_presentation_meta_payload(selected_date), encoder=CustomJSONEncoder)


PRESENTATION_NAME_DATE_FORMATS = (
    "%m.%d.%Y",
    "%Y-%m-%d",
    "%m/%d/%Y",
)


def _parse_presentation_name_date(presentation_name):
    if not presentation_name:
        return None

    for date_format in PRESENTATION_NAME_DATE_FORMATS:
        try:
            return datetime.datetime.strptime(presentation_name, date_format).date()
        except ValueError:
            continue

    return None


def _build_presentation_calendar(presentations):
    presentation_calendar = {}

    for presentation in presentations:
        if not presentation.presentation_id:
            continue
        presentation_date = _parse_presentation_name_date(presentation.name)
        if presentation_date is None:
            continue

        presentation_calendar[presentation_date.isoformat()] = {
            "presentation_id": presentation.presentation_id,
            "name": presentation.name,
        }

    return presentation_calendar


def _delete_presentations_for_date(presentation_date):
    matching_ids = [
        presentation.id
        for presentation in MergedPresentation.objects.all()
        if _parse_presentation_name_date(presentation.name) == presentation_date
    ]
    if matching_ids:
        MergedPresentation.objects.filter(id__in=matching_ids).delete()


def _ready_presentations_queryset(*, include_blank_ids=False):
    queryset = MergedPresentation.objects.filter(status=MergedPresentation.STATUS_READY)
    if not include_blank_ids:
        queryset = queryset.exclude(presentation_id="")
    return queryset


def _delete_stale_ready_presentations_without_rounds():
    round_dates = set(GPTriviaRound.objects.values_list("date", flat=True).distinct())
    stale_ids = [
        presentation.id
        for presentation in _ready_presentations_queryset(include_blank_ids=True).order_by("id")
        if (presentation_date := _parse_presentation_name_date(presentation.name)) is not None
        and presentation_date not in round_dates
    ]
    if stale_ids:
        MergedPresentation.objects.filter(id__in=stale_ids).delete()


def _home_visible_presentations():
    _delete_stale_ready_presentations_without_rounds()
    round_dates = set(GPTriviaRound.objects.values_list("date", flat=True).distinct())
    presentations = list(_ready_presentations_queryset().order_by("id"))
    return [
        presentation
        for presentation in presentations
        if _parse_presentation_name_date(presentation.name) in round_dates
    ]


def _stale_home_build_cutoff():
    return timezone.now() - datetime.timedelta(minutes=HOME_BUILD_STALE_MINUTES)


def _serialize_home_build_state(build_state=None):
    if build_state is None:
        build_state = _get_home_build_state()

    return {
        "is_active": bool(build_state and build_state.is_active),
        "action": build_state.action if build_state else "",
        "presentation_name": build_state.presentation_name if build_state else "",
        "presentation_id": build_state.presentation_id if build_state else "",
    }


def _clear_stale_home_build_state(build_state):
    if not build_state or not build_state.is_active or not build_state.started_at:
        return build_state
    if build_state.started_at >= _stale_home_build_cutoff():
        return build_state

    build_state.is_active = False
    build_state.action = ""
    build_state.presentation_name = ""
    build_state.presentation_id = ""
    build_state.started_at = None
    build_state.save(
        update_fields=["is_active", "action", "presentation_name", "presentation_id", "started_at", "updated_at"]
    )
    return build_state


def _get_home_build_state():
    build_state, _ = PresentationBuildState.objects.get_or_create(
        key=HOME_BUILD_STATE_KEY,
    )
    return _clear_stale_home_build_state(build_state)


def _broadcast_home_build_state(build_state):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    async_to_sync(channel_layer.group_send)(
        HOME_BUILD_GROUP_NAME,
        {
            "type": "home_build_message",
            "build_state": _serialize_home_build_state(build_state),
        },
    )


def _schedule_home_build_state_broadcast(build_state):
    transaction.on_commit(lambda: _broadcast_home_build_state(build_state))


def _broadcast_home_presentation_refresh(selected_presentation, presentation_id=None, *, action=""):
    if selected_presentation is None:
        return

    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    async_to_sync(channel_layer.group_send)(
        HOME_BUILD_GROUP_NAME,
        {
            "type": "home_presentation_message",
            "presentation": _serialize_home_presentation(selected_presentation, presentation_id),
            "action": action,
            "refreshed_at": timezone.now().isoformat(),
        },
    )


def _schedule_home_presentation_refresh_broadcast(selected_presentation, presentation_id=None, *, action=""):
    transaction.on_commit(
        lambda: _broadcast_home_presentation_refresh(
            selected_presentation,
            presentation_id,
            action=action,
        )
    )


def _acquire_home_build_lock(action, *, presentation_name="", presentation_id=""):
    with transaction.atomic():
        build_state, _ = PresentationBuildState.objects.select_for_update().get_or_create(
            key=HOME_BUILD_STATE_KEY,
        )
        _clear_stale_home_build_state(build_state)
        if build_state.is_active:
            return False, build_state

        build_state.is_active = True
        build_state.action = action
        build_state.presentation_name = presentation_name
        build_state.presentation_id = presentation_id
        build_state.started_at = timezone.now()
        build_state.save(
            update_fields=["is_active", "action", "presentation_name", "presentation_id", "started_at", "updated_at"]
        )

    _schedule_home_build_state_broadcast(build_state)
    return True, build_state


def _release_home_build_lock():
    with transaction.atomic():
        build_state, _ = PresentationBuildState.objects.select_for_update().get_or_create(
            key=HOME_BUILD_STATE_KEY,
        )
        if not build_state.is_active and not build_state.action and not build_state.presentation_name and not build_state.presentation_id:
            return build_state

        build_state.is_active = False
        build_state.action = ""
        build_state.presentation_name = ""
        build_state.presentation_id = ""
        build_state.started_at = None
        build_state.save(
            update_fields=["is_active", "action", "presentation_name", "presentation_id", "started_at", "updated_at"]
        )

    _schedule_home_build_state_broadcast(build_state)
    return build_state


def _build_home_context(selected_presentation, presentation_calendar, build_state=None):
    selected_presentation_date = None
    presentation_url = None
    profileable_player_names = _get_global_player_names()

    if selected_presentation is not None:
        selected_presentation_date = _parse_presentation_name_date(selected_presentation.name)
        presentation_url = (
            f"https://docs.google.com/presentation/d/{selected_presentation.presentation_id}/embed"
        )

    return {
        "presentation_url": presentation_url,
        "pres_name": selected_presentation.name if selected_presentation else "None",
        "selected_presentation_id": (
            selected_presentation.presentation_id if selected_presentation else ""
        ),
        "selected_presentation_iso_date": (
            selected_presentation_date.isoformat() if selected_presentation_date else ""
        ),
        "presentation_calendar": presentation_calendar,
        "home_build_state": _serialize_home_build_state(build_state),
        "playerColorMapping": build_player_color_mapping(profileable_player_names),
        "profileable_player_names": profileable_player_names,
    }


def _serialize_home_presentation(selected_presentation, presentation_id=None, include_calendar_entry=None):
    if selected_presentation is None:
        return {
            "presentation_id": "",
            "presentation_name": "",
            "presentation_url": "",
            "selected_presentation_iso_date": "",
            "calendar_entry": None,
        }

    resolved_presentation_id = presentation_id or selected_presentation.presentation_id
    selected_presentation_date = _parse_presentation_name_date(selected_presentation.name)
    if include_calendar_entry is None:
        include_calendar_entry = (
            getattr(selected_presentation, "status", MergedPresentation.STATUS_READY)
            == MergedPresentation.STATUS_READY
        )

    return {
        "presentation_id": resolved_presentation_id,
        "presentation_name": selected_presentation.name,
        "presentation_url": (
            f"https://docs.google.com/presentation/d/{resolved_presentation_id}/embed"
        ),
        "selected_presentation_iso_date": (
            selected_presentation_date.isoformat() if selected_presentation_date else ""
        ),
        "calendar_entry": (
            {
                "presentation_id": resolved_presentation_id,
                "name": selected_presentation.name,
            }
            if selected_presentation_date and include_calendar_entry
            else None
        ),
    }


def _is_ajax_home_request(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def _get_selected_home_presentation(selected_presentation_id=None):
    presentations = _home_visible_presentations()
    latest_presentation = presentations[-1] if presentations else None
    selected_presentation = latest_presentation

    if selected_presentation_id:
        selected_presentation = next(
            (
                presentation
                for presentation in reversed(presentations)
                if presentation.presentation_id == selected_presentation_id
            ),
            latest_presentation,
        )

    return latest_presentation, selected_presentation, _build_presentation_calendar(presentations)


def _upsert_failed_presentation(
    *,
    name,
    presentation_id,
    creator_list,
    round_names,
    error_message,
):
    if not presentation_id:
        return None

    failed_presentation, _ = MergedPresentation.objects.update_or_create(
        presentation_id=presentation_id,
        defaults={
            "name": name,
            "creator_list": creator_list,
            "round_names": round_names,
            "player_list": {},
            "host": "Unknown",
            "scorekeeper": "Unknown",
            "style_points": {},
            "notes": "",
            "tiebreak_winner": "",
            "status": MergedPresentation.STATUS_FAILED,
            "error_message": error_message,
        },
    )
    return failed_presentation

@login_required
@ensure_csrf_cookie
def home(request):
    from .round_analysis import ensure_round_analysis_worker_for_pending_runs

    ensure_round_analysis_worker_for_pending_runs()
    ajax_request = _is_ajax_home_request(request)
    selected_presentation_id = (
        request.GET.get("presentation_id") or request.POST.get("selected_presentation_id")
    )
    home_build_state = _get_home_build_state()
    latest_presentation, selected_presentation, presentation_calendar = _get_selected_home_presentation(
        selected_presentation_id
    )
    home_context = _build_home_context(selected_presentation, presentation_calendar, home_build_state)

    # (links, titles, creators, old_links, shared_dates) = get_round_titles_and_links(processed_senders=[])

    presentation_name = datetime.date.strftime(_current_trivia_date(), '%-m.%d.%Y')
    if request.method == 'POST':
        action = request.POST.get('action')
        response_presentation = None
        response_presentation_id = None
        indices = {
            key.rsplit("_", 1)[-1]  # → "0", "1", …
            for key in request.POST
            if key.startswith("round_title_")
        }

        if action == 'generate':

            round_order = {}
            for idx in indices:
                order_val = request.POST.get(f"round_order_{idx}")
                if not order_val:
                    continue  # user didn’t pick this row
                order = int(order_val)

                round_order[order] = {
                    "title": request.POST.get(f"round_title_{idx}"),
                    "creator": request.POST.get(f"round_creator_{idx}"),
                    "link": request.POST.get(f"round_link_{idx}"),
                    "old_link": request.POST.get(f"round_old_link_{idx}"),
                    "shared_date": request.POST.get(f"round_shared_date_{idx}"),
                    "coop": request.POST.get(f"round_coop_{idx}"),
                    "is_new": str(request.POST.get(f"round_is_new_{idx}") or '').strip().lower() in {'1', 'true', 'yes', 'on'},
                }
            # make sure there's at least one round, or else just return
            if not round_order:
                if ajax_request:
                    return JsonResponse({"detail": "No rounds selected."}, status=400)
                return render(request, "GPTrivia/home.html", home_context)

            lock_acquired, active_build_state = _acquire_home_build_lock(
                "generate",
                presentation_name=presentation_name,
            )
            if not lock_acquired:
                detail = "Another presentation build is already in progress."
                if ajax_request:
                    payload = {"detail": detail, "build_in_progress": True}
                    payload.update(_serialize_home_build_state(active_build_state))
                    return JsonResponse(payload, status=409)
                return render(request, "GPTrivia/home.html", home_context)

            # Sort rounds by order
            ordered_rounds = [round_order[key] for key in sorted(round_order.keys())]

            # Extract ordered titles, creators, and links
            ordered_titles = [round['title'] for round in ordered_rounds]
            ordered_creators = [round['creator'] for round in ordered_rounds]
            ordered_links = [round['link'] for round in ordered_rounds]
            ordered_old_links = [round['old_link'] for round in ordered_rounds]
            ordered_coop = [round['coop'] for round in ordered_rounds]
            logger.info(
                "Home generate requested for %s with %s rounds",
                presentation_name,
                len(ordered_titles),
            )

            # Pass the ordered data to create_presentation
            try:
                create_result = create_presentation(
                    ordered_titles,
                    ordered_creators,
                    ordered_links,
                    presentation_name=presentation_name,
                    old_links=ordered_old_links,
                    coops=ordered_coop
                )
            except Exception as error:
                PresentationBuildError = _get_presentation_build_error_class()
                if not isinstance(error, PresentationBuildError):
                    logger.exception(
                        "Home generate failed before completion for %s",
                        presentation_name,
                    )
                    if ajax_request:
                        return JsonResponse(
                            {"detail": f"Slide generation failed before completion: {error}"},
                            status=500,
                        )
                    raise

                logger.error(
                    "Home generate failed during %s for %s (%s)",
                    error.step or "unknown step",
                    presentation_name,
                    error.presentation_id,
                )
                failed_presentation = _upsert_failed_presentation(
                    name=presentation_name,
                    presentation_id=error.presentation_id,
                    creator_list=error.creators or ordered_creators,
                    round_names=error.round_titles or ordered_titles,
                    error_message=str(error),
                )
                if ajax_request:
                    payload = _serialize_home_presentation(
                        failed_presentation,
                        error.presentation_id,
                        include_calendar_entry=False,
                    )
                    payload["detail"] = str(error)
                    payload["build_failed"] = True
                    return JsonResponse(payload, status=500)
                raise
            finally:
                _release_home_build_lock()

            if isinstance(create_result, tuple):
                new_presentation_id, creators, round_titles, round_links = create_result
            else:
                new_presentation_id = create_result
                round_titles = ordered_titles
                creators = ordered_creators
                round_links = ordered_links
            logger.info(
                "Home generate completed for %s (%s)",
                presentation_name,
                new_presentation_id,
            )

            # new_presentation_id, creators, round_titles, round_links = create_presentation()

            response_presentation = MergedPresentation.objects.create(
                name=presentation_name,
                presentation_id=new_presentation_id,
                creator_list=creators,
                round_names=round_titles,
                player_list={},
                host="Unknown",
                scorekeeper="Unknown",
                style_points={},
                notes="",
                tiebreak_winner="",
            )
            response_presentation_id = new_presentation_id
            _schedule_home_presentation_refresh_broadcast(
                response_presentation,
                response_presentation_id,
                action="generate",
            )
            print (new_presentation_id, creators, round_titles)

            round_ids_for_analysis = []
            for round_index in range(len(round_titles)):
                new_round = GPTriviaRound()
                # Assign the round_data fields to the GPTriviaRound instance
                new_round.creator = creators[round_index]
                new_round.title = round_titles[round_index]
                new_round.major_category = ""
                new_round.minor_category1 = ""
                new_round.minor_category2 = ""
                new_round.date = datetime.datetime.strptime(presentation_name, "%m.%d.%Y").date().strftime('%Y-%m-%d')
                new_round.round_number = round_index + 1
                new_round.max_score = 10
                set_round_score_map(new_round, {})
                new_round.replay = 0
                # round coop will be 0 if the checkbox is not checked, 1 if it is
                new_round.cooperative = 1 if ordered_coop[round_index] == 'on' else 0
                new_round.link = round_links[round_index]
                new_round.source_link = ordered_old_links[round_index] or ordered_links[round_index]
                new_round.save()
                if _should_auto_queue_round_analysis_for_round(
                    new_round,
                    ordered_rounds[round_index],
                    presentation_name=presentation_name,
                    action_name='generate',
                ):
                    round_ids_for_analysis.append(new_round.id)

            _mark_selected_submitted_rounds_consumed(ordered_rounds)
            if round_ids_for_analysis:
                from .round_analysis import schedule_auto_round_analysis_batch

                transaction.on_commit(
                    lambda queued_ids=list(round_ids_for_analysis), initiated_by=(request.user.username if request.user.is_authenticated else ''), label=f"new rounds from {presentation_name}": schedule_auto_round_analysis_batch(
                        queued_ids,
                        initiated_by=initiated_by,
                        batch_label=label,
                    )
                )

        elif action == 'update':

            round_order = {}
            for idx in indices:
                order_val = request.POST.get(f"round_order_{idx}")
                if not order_val:
                    continue  # user didn’t pick this row
                order = int(order_val)

                round_order[order] = {
                    "title": request.POST.get(f"round_title_{idx}"),
                    "creator": request.POST.get(f"round_creator_{idx}"),
                    "link": request.POST.get(f"round_link_{idx}"),
                    "old_link": request.POST.get(f"round_old_link_{idx}"),
                    "shared_date": request.POST.get(f"round_shared_date_{idx}"),
                    "coop": request.POST.get(f"round_coop_{idx}"),
                    "is_new": str(request.POST.get(f"round_is_new_{idx}") or '').strip().lower() in {'1', 'true', 'yes', 'on'},
                }

            if not round_order:
                # nothing selected → render page without hitting Gmail
                if ajax_request:
                    return JsonResponse({"detail": "No rounds selected."}, status=400)
                return render(request, "GPTrivia/home.html", home_context)

            if selected_presentation is None:
                if ajax_request:
                    return JsonResponse({"detail": "No presentation selected."}, status=400)
                return render(request, "GPTrivia/home.html", home_context)

            lock_acquired, active_build_state = _acquire_home_build_lock(
                "update",
                presentation_name=selected_presentation.name,
                presentation_id=selected_presentation.presentation_id,
            )
            if not lock_acquired:
                detail = "Another presentation build is already in progress."
                if ajax_request:
                    payload = {"detail": detail, "build_in_progress": True}
                    payload.update(_serialize_home_build_state(active_build_state))
                    return JsonResponse(payload, status=409)
                return render(request, "GPTrivia/home.html", home_context)

            # Sort rounds by order
            ordered_rounds = [round_order[key] for key in sorted(round_order.keys())]

            # Extract ordered titles, creators, and links
            ordered_titles = [round['title'] for round in ordered_rounds]
            ordered_creators = [round['creator'] for round in ordered_rounds]
            ordered_links = [round['link'] for round in ordered_rounds]
            ordered_old_links = [round['old_link'] for round in ordered_rounds]
            ordered_coop = [round['coop'] for round in ordered_rounds]
            logger.info(
                "Home update requested for %s using presentation %s with %s rounds",
                presentation_name,
                selected_presentation.presentation_id,
                len(ordered_titles),
            )


            # Pass the ordered data to create_presentation
            # new_presentation_id = create_presentation(
            #     ordered_titles,
            #     ordered_creators,
            #     ordered_links,
            #     presentation_name=presentation_name
            # )

            try:
                updated_presentation_id, new_creators, round_titles, new_links = update_merged_presentation(
                    selected_presentation.presentation_id,
                    selected_presentation.creator_list,
                    ordered_titles,
                    ordered_creators,
                    ordered_links,
                    ordered_old_links,
                    coops=ordered_coop,
                )
            except Exception as error:
                logger.exception(
                    "Home update failed for %s (%s)",
                    presentation_name,
                    selected_presentation.presentation_id,
                )
                selected_presentation.status = MergedPresentation.STATUS_FAILED
                selected_presentation.error_message = str(error)
                selected_presentation.save(update_fields=["status", "error_message"])
                if ajax_request:
                    payload = _serialize_home_presentation(
                        selected_presentation,
                        selected_presentation.presentation_id,
                        include_calendar_entry=False,
                    )
                    payload["detail"] = f"Slide update stopped before completion: {error}"
                    payload["build_failed"] = True
                    return JsonResponse(payload, status=500)
                raise
            finally:
                _release_home_build_lock()
            logger.info(
                "Home update completed for %s (%s)",
                presentation_name,
                updated_presentation_id,
            )

            # update the MergedPresentation object that has the same presentation_id as the latest_presentation
            # by appending the new creators to the creator_list and appending the new round titles to the round_names

            selected_presentation = MergedPresentation.objects.get(
                presentation_id=selected_presentation.presentation_id
            )
            selected_presentation.presentation_id = updated_presentation_id
            selected_presentation.round_names.extend(round_titles)
            selected_presentation.creator_list.extend(new_creators)
            selected_presentation.status = MergedPresentation.STATUS_READY
            selected_presentation.error_message = ""
            selected_presentation.save()
            _schedule_home_presentation_refresh_broadcast(
                selected_presentation,
                updated_presentation_id,
                action="update",
            )

            print(updated_presentation_id, new_creators, round_titles)
            response_presentation = selected_presentation
            response_presentation_id = updated_presentation_id

            round_ids_for_analysis = []
            for round_index in range(len(round_titles)):
                new_round = GPTriviaRound()
                # Assign the round_data fields to the GPTriviaRound instance
                new_round.creator = new_creators[round_index]
                new_round.title = round_titles[round_index]
                new_round.major_category = ""
                new_round.minor_category1 = ""
                new_round.minor_category2 = ""
                new_round.date = datetime.datetime.strptime(presentation_name, "%m.%d.%Y").date().strftime('%Y-%m-%d')
                new_round.round_number = round_index + 1
                new_round.max_score = 10
                set_round_score_map(new_round, {})
                new_round.replay = 0
                new_round.cooperative = 1 if ordered_coop[round_index] == 'on' else 0
                new_round.link = new_links[round_index]
                new_round.source_link = ordered_old_links[round_index] or ordered_links[round_index]
                new_round.save()
                if _should_auto_queue_round_analysis_for_round(
                    new_round,
                    ordered_rounds[round_index],
                    presentation_name=presentation_name,
                    action_name='update',
                ):
                    round_ids_for_analysis.append(new_round.id)

            _mark_selected_submitted_rounds_consumed(ordered_rounds)
            if round_ids_for_analysis:
                from .round_analysis import schedule_auto_round_analysis_batch

                transaction.on_commit(
                    lambda queued_ids=list(round_ids_for_analysis), initiated_by=(request.user.username if request.user.is_authenticated else ''), label=f"new rounds from {presentation_name}": schedule_auto_round_analysis_batch(
                        queued_ids,
                        initiated_by=initiated_by,
                        batch_label=label,
                    )
                )

        if ajax_request and response_presentation is not None:
            return JsonResponse(
                _serialize_home_presentation(response_presentation, response_presentation_id)
            )

        if action == "update" and response_presentation is not None:
            return redirect(
                f"{reverse_lazy('home')}?presentation_id={response_presentation_id}"
            )
        return redirect("home")

    # return render(request, 'GPTrivia/home.html', {'presentation_url': presentation_url, 'pres_name': latest_presentation.name if latest_presentation else "None", 'avail_links': links, 'avail_titles': titles, 'avail_creators': creators, 'shared_dates': shared_dates, 'avail_coops': [0]*len(titles)})
    return render(request, 'GPTrivia/home.html', home_context)

@login_required
def scoresheet(request):
    return redirect('scoresheet_new')


def buzzer_page(request):
    def generate_random_suffix(length=5):
        # Generate a random string of uppercase letters and digits
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    username = request.user.username if request.user.is_authenticated else f"unknown_{generate_random_suffix()}"
    context = {'username': username}
    return render(request, 'GPTrivia/buzzer_page.html', context)

@login_required
def scoresheet_new(request):
    return render(request, 'GPTrivia/scoresheet_new.html', {
        'player_icon_map': _build_player_icon_map(),
        'player_color_map': _build_player_color_override_map(),
    })

## API stuff

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return super().default(obj)

class PlayerProfileAPI(generics.ListAPIView):
    renderer_classes = [JSONRenderer]

    def get(self, request, player_name):
        context = player_profile_dict(request, player_name)
        for key in context:
            if isinstance(context[key], QuerySet):
                context[key] = list(context[key].values())
        return JsonResponse(context, encoder=CustomJSONEncoder)

class TriviaRoundList(generics.ListAPIView):
    queryset = GPTriviaRound.objects.all()
    serializer_class = GPTriviaRoundSerializer
    permission_classes = [IsAuthenticated]

class PresentationList(generics.ListAPIView):
    queryset = _ready_presentations_queryset()
    serializer_class = MergedPresentationSerializer
    permission_classes = [IsAuthenticated]

class CustomObtainAuthToken(ObtainAuthToken):
    def post(self, request, *args, **kwargs):
        response = super(CustomObtainAuthToken, self).post(request, *args, **kwargs)
        token = Token.objects.get(key=response.data['token'])
        user = token.user
        return Response({
            'token': token.key,
            'user_id': user.pk,
            'username': user.username
        })


def player_analysis_plot(request, *args, **kwargs):
    from .analysis import PlayerAnalysisPlot

    normalized_query = json.dumps(
        sorted((key, tuple(request.GET.getlist(key))) for key in request.GET.keys()),
        separators=(',', ':'),
    )
    query_digest = hashlib.md5(normalized_query.encode('utf-8')).hexdigest()
    cache_key = f'player_analysis_plot:v{_get_site_data_cache_version()}:{query_digest}'
    cached_payload = None if _request_wants_fresh_cache(request) else cache.get(cache_key)
    if cached_payload is not None:
        return JsonResponse(cached_payload)

    response = PlayerAnalysisPlot.as_view()(request, *args, **kwargs)
    if isinstance(response, JsonResponse) and response.status_code == 200:
        try:
            cache.set(
                cache_key,
                json.loads(response.content.decode('utf-8')),
                ANALYSIS_PLOT_CACHE_TTL_SECONDS,
            )
        except Exception:
            pass
    return response


SCORESHEET_GROUP_NAME = 'scoresheet_scoresheet_updates'
SCORESHEET_ROUND_FIELDS = {
    'creator', 'secondary_creator', 'title', 'major_category', 'minor_category1', 'minor_category2', 'date',
    'round_number', 'max_score', 'replay', 'cooperative', 'notes', 'link', 'extra_scores',
    *FIXED_SCORE_FIELDS,
}
SCORESHEET_PRESENTATION_FIELDS = {
    'round_names', 'creator_list', 'joker_round_indices', 'player_list', 'host',
    'scorekeeper', 'tiebreak_winner', 'crowned_winner', 'notes', 'style_points',
}


def _broadcast_scoresheet_message(message):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return

    async_to_sync(channel_layer.group_send)(
        SCORESHEET_GROUP_NAME,
        {
            'type': 'scoresheet_message',
            'message': message,
        }
    )


def _schedule_scoresheet_broadcast(message):
    transaction.on_commit(lambda: _broadcast_scoresheet_message(message))


def _parse_scoresheet_date(date_str):
    if not date_str:
        return None

    for fmt in ('%m.%d.%Y', '%Y-%m-%d'):
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    return None


def _sanitize_scoresheet_joker_round_indices(value):
    if isinstance(value, dict):
        return {
            key: _sanitize_scoresheet_joker_round_indices(nested_value)
            for key, nested_value in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_scoresheet_joker_round_indices(item) for item in value]
    if isinstance(value, str):
        return value.replace("'", "~~~~")
    return value


def _presentation_name_for_date(selected_date):
    parsed_date = _parse_scoresheet_date(selected_date)
    if not parsed_date:
        return None
    return parsed_date.strftime("%m.%d.%Y")


def _current_trivia_date():
    return datetime.datetime.now(TRIVIA_TIMEZONE).date()


def _choose_scoresheet_presentation(presentations, *, presentation_id=None, selected_date=None):
    matches = list(presentations)
    if not matches:
        return None

    if len(matches) > 1:
        logger.warning(
            "Multiple ready MergedPresentation rows matched scoresheet lookup for "
            "presentation_id=%s selected_date=%s ids=%s",
            presentation_id or "",
            selected_date or "",
            [presentation.id for presentation in matches],
        )

    parsed_selected_date = _parse_scoresheet_date(selected_date)
    if parsed_selected_date:
        date_matches = [
            presentation
            for presentation in matches
            if _parse_presentation_name_date(presentation.name) == parsed_selected_date
        ]
        if date_matches:
            matches = date_matches

    matches.sort(key=lambda presentation: presentation.id, reverse=True)
    return matches[0]


def _get_global_player_fields():
    return get_eligible_player_fields(
        list(GPTriviaRound.objects.all()),
        min_rounds=MIN_ANALYSIS_ROUNDS,
    )


def _get_global_player_names():
    return [display_name_for_player_field(field) for field in _get_global_player_fields()]


def _build_round_rows(round_queryset, player_fields):
    round_rows = []
    for trivia_round in round_queryset:
        round_rows.append({
            'round': trivia_round,
            'score_values': get_round_score_map(trivia_round),
        })
    return round_rows


def _get_scoresheet_presentation(presentation_id=None, selected_date=None):
    if presentation_id:
        return _choose_scoresheet_presentation(
            _ready_presentations_queryset(include_blank_ids=True).filter(presentation_id=presentation_id),
            presentation_id=presentation_id,
            selected_date=selected_date,
        )

    parsed_selected_date = _parse_scoresheet_date(selected_date)
    if not parsed_selected_date:
        return None

    return _choose_scoresheet_presentation(
        [
            presentation
            for presentation in _ready_presentations_queryset(include_blank_ids=True).order_by("-id")
            if _parse_presentation_name_date(presentation.name) == parsed_selected_date
        ],
        selected_date=selected_date,
    )


def _save_scores_patch(data):
    round_updates = data.get('round_updates', [])
    presentation_updates = data.get('presentation_updates', {})
    selected_date = data.get('selected_date')
    presentation_id = data.get('presentation_id')
    client_id = data.get('client_id')
    mutation_id = data.get('mutation_id')

    with transaction.atomic():
        for update in round_updates:
            round_id = update.get('id')
            fields = update.get('fields', {})
            round_obj = GPTriviaRound.objects.get(id=round_id)
            dirty_fields = []
            score_fields_updated = False
            score_map = get_round_score_map(round_obj)

            for field, value in fields.items():
                if field not in SCORESHEET_ROUND_FIELDS:
                    return JsonResponse({"message": f"Invalid round field: {field}"}, status=400)
                if field == 'date':
                    value = _parse_scoresheet_date(value)
                if field in FIXED_SCORE_FIELDS:
                    score_map[field] = value
                    score_fields_updated = True
                    continue
                if field == 'extra_scores':
                    replacement_scores = {}
                    for key, score_value in (value or {}).items():
                        replacement_scores[key] = score_value
                    score_map = {
                        fixed_field: score_map.get(fixed_field)
                        for fixed_field in FIXED_SCORE_FIELDS
                    }
                    score_map.update(replacement_scores)
                    score_fields_updated = True
                    continue
                setattr(round_obj, field, value)
                dirty_fields.append(field)

            if score_fields_updated:
                set_round_score_map(round_obj, score_map)
                dirty_fields.extend([*FIXED_SCORE_FIELDS, 'extra_scores'])

            if dirty_fields:
                round_obj.save(update_fields=dirty_fields)

        presentation = _get_scoresheet_presentation(
            presentation_id=presentation_id,
            selected_date=selected_date,
        )

        if not presentation:
            presentation_name = _presentation_name_for_date(selected_date)
            if not presentation_name:
                return JsonResponse({"message": "Presentation not found."}, status=400)

            presentation = MergedPresentation(
                name=presentation_name,
                presentation_id=presentation_id or "",
            )

        dirty_fields = []
        for field, value in presentation_updates.items():
            if field not in SCORESHEET_PRESENTATION_FIELDS:
                return JsonResponse({"message": f"Invalid presentation field: {field}"}, status=400)
            setattr(presentation, field, value)
            dirty_fields.append(field)

        parsed_selected_date = _parse_scoresheet_date(selected_date)
        has_rounds_for_selected_date = bool(
            parsed_selected_date
            and GPTriviaRound.objects.filter(date=parsed_selected_date).exists()
        )
        should_persist_presentation = bool(
            presentation.pk
            or presentation.presentation_id
            or (dirty_fields and has_rounds_for_selected_date)
        )

        if should_persist_presentation and (dirty_fields or presentation.pk is None):
            presentation.save()

        message = {
            'action': 'update',
            'event': 'save_scores',
            'client_id': client_id,
            'mutation_id': mutation_id,
            'presentation_id': presentation.presentation_id,
            'selected_date': selected_date,
            'round_updates': round_updates,
            'presentation_updates': presentation_updates,
        }
        _schedule_scoresheet_broadcast(message)

    _bump_site_data_cache_version()
    return JsonResponse({
        "message": "Data saved successfully!",
        "presentation_id": presentation.presentation_id,
    })

@api_view(['POST'])
def create_round(request, date, number):
    # Logic to create a new round
    print("here")
    selected_date = _parse_scoresheet_date(date) or date
    client_id = request.data.get('client_id')
    mutation_id = request.data.get('mutation_id')
    with transaction.atomic():
        new_round = GPTriviaRound.objects.create(
            date=selected_date,
            round_number=number,
            title=f"Round {number}",
        )
        _schedule_scoresheet_broadcast({
            'action': 'update',
            'event': 'create_round',
            'client_id': client_id,
            'mutation_id': mutation_id,
            'round_id': new_round.id,
            'selected_date': str(new_round.date),
        })
    # set the date
    # print(date)
    # try:
    #     newdate = datetime.datetime.strptime(date, '%m.%d.%Y').date()
    #     print(newdate)
    # except Exception as e:
    #     try:
    #         newdate = datetime.datetime.strptime(date, '%Y-%m-%d').date()
    #         print(newdate)
    #     except ValueError:
    #         # handle the case where date_str doesn't match any format
    #         print("error")
    #         newdate = None
    # new_round.date = newdate
    # # set the round number
    # new_round.round_number = number
    # set it's name to "Round {number}"
    # new_round.title = f"Round {number}"
    serializer = GPTriviaRoundSerializer(new_round)
    _bump_site_data_cache_version()
    return Response(serializer.data)  # Return new round details

@api_view(['DELETE'])
def delete_round(request, round_id):
    round_to_delete = GPTriviaRound.objects.get(id=round_id)
    client_id = request.data.get('client_id')
    mutation_id = request.data.get('mutation_id')
    # get the date of the round to delete
    thedate = round_to_delete.date
    with transaction.atomic():
        round_to_delete.delete()
        # if there aren't any rounds with the same date left, remove the MergedPresentation object with the same date
        print("round deleted successfully: " + str(round_id))
        print ("remaining rounds with date: " + str(thedate) + ": " + str(GPTriviaRound.objects.filter(date=thedate).count()))
        print ("GPTriviaRound.objects.filter(date=thedate): " + str(GPTriviaRound.objects.filter(date=thedate)))
        print ("GPTriviaRound.objects.filter(date=thedate).count(): " + str(GPTriviaRound.objects.filter(date=thedate).count()))
        print ("thedate.strftime: " + thedate.strftime("%m.%d.%Y"))
        print("MergedPresentation.objects.filter(name=thedate.strftime): " + str(MergedPresentation.objects.filter(name=thedate.strftime("%m.%d.%Y"))))

        if GPTriviaRound.objects.filter(date=thedate).count() == 0:
            print("deleting merged presentation with date: " + str(thedate))
            _delete_presentations_for_date(thedate)

        _schedule_scoresheet_broadcast({
            'action': 'update',
            'event': 'delete_round',
            'client_id': client_id,
            'mutation_id': mutation_id,
            'round_id': round_id,
            'selected_date': str(thedate),
        })
    _bump_site_data_cache_version()
    return Response({'message': 'Round deleted successfully'})

@api_view(['POST'])
def save_scores(request):
    data = request.data
    if 'round_updates' in data or 'presentation_updates' in data:
        return _save_scores_patch(data)
    rounds = data.get('rounds', [])
    joker_round_indices = data.get('joker_round_indices', {})
    presentation_id = data.get('presentation_id', None)
    round_names = data.get('round_names', [])
    creator_list = data.get('round_creators', [])
    date_str = "2020-12-12"
    player_list = data.get('player_list', [])
    host = data.get('host', "") or ""
    scorekeeper = data.get('scorekeeper', "") or ""
    notes = data.get('notes', "") or ""  # was {} → must be str
    style_points = data.get('style_points') or {}
    if isinstance(style_points, str):  # tolerate JSON string
        try:
            style_points = json.loads(style_points.replace("'", '"'))
        except Exception:
            style_points = {}
    tiebreak_winner = data.get('tiebreak_winner', "") or ""

    all_player_list = {}
    # player_list is a string array of the players, so we need to convert it to a dictionary, use 0if the player is not in the list
    for player in player_list:
        all_player_list[player] = player

    script_should_run = False  # Flag to indicate if the script should run

    for round_data in rounds:
        # Get the round_data fields
        creator = round_data.get('creator')
        secondary_creator = round_data.get('secondary_creator')
        title = round_data.get('title')
        print(creator)
        date_str = round_data.get('date')
        try:
            newdate = datetime.datetime.strptime(date_str, '%m.%d.%Y').date()
        except Exception as e:
            try:
                newdate = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                # handle the case where date_str doesn't match any format
                newdate = None
        # print the date to the console

        try:
            # Try to get the existing trivia_round from the database
            # trivia_round = GPTriviaRound.objects.get(creator=creator, title=title, date=newdate)
            # New idea, just use the round id
            trivia_round = GPTriviaRound.objects.get(id=round_data.get('id'))
            old_link = trivia_round.link  # Get the existing link from the database
        except ObjectDoesNotExist:
            # If it does not exist, create a new instance
            trivia_round = GPTriviaRound()
            old_link = None  # No existing link if the round is new

        new_link = round_data.get('link')
        if old_link != new_link:
            script_should_run = True  # Set the flag if the link was modified

        # Assign the round_data fields to the GPTriviaRound instance
        trivia_round.creator = creator
        trivia_round.secondary_creator = secondary_creator
        trivia_round.title = title
        trivia_round.major_category = round_data.get('major_category')
        trivia_round.minor_category1 = round_data.get('minor_category1')
        trivia_round.minor_category2 = round_data.get('minor_category2')
        trivia_round.date = newdate
        trivia_round.round_number = round_data.get('round_number')
        trivia_round.max_score = round_data.get('max_score')
        score_map = {}
        for field in FIXED_SCORE_FIELDS:
            score_map[field] = round_data.get(field)
        for key, value in (round_data.get('extra_scores') or {}).items():
            score_map[key] = value
        for key, value in round_data.items():
            if key.startswith('score_') and key not in FIXED_SCORE_FIELDS:
                score_map[key] = value
        set_round_score_map(trivia_round, score_map)
        trivia_round.replay = round_data.get('replay', False)
        trivia_round.cooperative = round_data.get('cooperative', False)
        trivia_round.link = round_data.get('link')

        # Save the instance to the database
        # first, log the trivia_round to the console
        try:
            print(trivia_round)
            trivia_round.save()

            # Run the update_links.py script only if the link field was modified
            #
            # # After saving, send an update message to the channel layer
            # channel_layer = get_channel_layer()
            # group_name = 'scoresheet_updates'  # The name of the group you've set up in your consumer
            #
            # # Prepare the data you want to send. Modify this based on your requirements
            # data_to_send = {
            #     'type': 'scoresheet_message',  # The handler method in the consumer
            #     'message': {
            #         'action': 'update'  # Replace with actual data
            #     }
            # }
            #
            # print("sending message to group: " + str(group_name) + " with data: " + str(data_to_send))
            #
            # # Send the message to the group
            # async_to_sync(channel_layer.group_send)(
            #     group_name,
            #     data_to_send
            # )
        except Exception as e:
            print(f"Error saving trivia_round: {e}")

    if script_should_run:
        try:
            subprocess.run(['python', './modify_links.py'], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error running update_links.py script: {e}")

    # replace any single quotes with a tilde so that it doesn't mess up the json
    joker_round_indices = _sanitize_scoresheet_joker_round_indices(joker_round_indices)

    # Update the joker_round_indices in the MergedPresentation
    if presentation_id:
        presentation = _get_scoresheet_presentation(
            presentation_id=presentation_id,
            selected_date=date_str,
        )
        if presentation is None:
            return JsonResponse({"message": "Presentation not found."}, status=400)
        presentation.joker_round_indices = joker_round_indices
        print(f"joker_round_indices: {joker_round_indices}")
        print(f"type of joker_round_indices: {type(joker_round_indices)}")
        presentation.creator_list = creator_list
        presentation.player_list = all_player_list
        presentation.round_names = round_names

        # NEW
        presentation.host = host
        presentation.scorekeeper = scorekeeper
        presentation.style_points = style_points
        presentation.notes = notes
        presentation.tiebreak_winner = tiebreak_winner

        presentation.save()
    elif date_str:
        try:
            presentation = _ready_presentations_queryset(include_blank_ids=True).get(
                name=datetime.datetime.strptime(date_str, '%Y-%m-%d').date().strftime("%m.%d.%Y")
            )
            presentation.joker_round_indices = joker_round_indices
            presentation.creator_list = creator_list
            presentation.player_list = all_player_list
            presentation.round_names = round_names

            presentation.host = host
            presentation.scorekeeper = scorekeeper
            presentation.style_points = style_points
            presentation.notes = notes
            presentation.tiebreak_winner = tiebreak_winner
            presentation.save()
        except ObjectDoesNotExist:
            pass
    else:
        pass

    _bump_site_data_cache_version()
    return JsonResponse({"message": "Data saved successfully!"})
