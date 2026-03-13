from django.shortcuts import render, redirect, get_object_or_404
from .forms import GPTriviaRoundForm, ProfilePictureForm
from .models import GPTriviaRound, MergedPresentation, Profile
from django.db import transaction
from django.db.models import Avg, F, FloatField, Case, When, Sum, Count
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
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
from .models import JeopardyQuestion, JeopardyRound, PushSubscription
from .player_scores import (
    FIXED_SCORE_FIELDS,
    MIN_ANALYSIS_ROUNDS,
    build_player_color_mapping,
    build_player_text_mapping,
    collect_player_fields,
    display_name_for_player_field,
    flatten_round_for_analysis,
    get_eligible_player_fields,
    get_player_color,
    get_round_score_map,
    player_field_for_name,
    set_round_score_map,
)


gmail_key = '8f35edc691b918094035b22807266a1e468bf5f0'

TRIVIA_TIMEZONE = pytz.timezone('America/Los_Angeles')


VAPID_PRIVATE_KEY = 'sn34CZG_vKbl_AoGObw2aUFo1TV0t2QdGwa-vut-Q70'
VAPID_CLAIMS = {
    "sub": "mailto:hailsciencetrivia@gmail.com"
}


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


@lru_cache(maxsize=1)
def _get_openai_client():
    from openai import OpenAI

    return OpenAI(api_key=os.getenv('OPENAI_API_KEY'))


def _get_autogen_config_list():
    return [
        {
            'model': 'o3',
            'api_key': os.getenv('OPENAI_API_KEY')
        }
    ]


@admin.register(PushSubscription)
class PushSubscriptionAdminAgain(admin.ModelAdmin):
    list_display = ('user', 'endpoint', 'created_at')
    actions = ['send_test_push']
    search_fields = ('endpoint', 'user__username')

    def send_test_push(self, request, queryset):
        send_push_to_all("Admin Test", "Test push from admin.")
        self.message_user(request, "Push notification sent to all subscriptions.", messages.SUCCESS)
    send_test_push.short_description = "Send test push notification to all"

def send_push_to_all(title, body):
    subscriptions = PushSubscription.objects.all()
    payload = {
        "title": title,
        "body": body,
    }
    for sub in subscriptions:
        print(f"Endpoint: {sub.endpoint}")
        sub_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh,
                "auth": sub.auth,
            }
        }
        try:
            webpush(
                subscription_info=sub_info,
                data=json.dumps(payload),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS.copy(),
            )
            print(f"Notification sent to {sub.endpoint}")
        except WebPushException as ex:
            print(f"Failed to send notification: {ex}")

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

            return JsonResponse({'success': True})
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

class PreviewView(View):
    def post(self, request, *args, **kwargs):
        round_title = request.POST.get('round_title')
        presentation_id = request.POST.get('presentation_id')
        qas_json_string = request.POST.get('qas')
        # Convert the JSON string to a dictionary
        qas_dict = json.loads(qas_json_string)
        icon_links = None
        print(presentation_id)
        if presentation_id == "1x8J9cEpFeMMYAJ_Inxw4Z_2-zYBwa5NMfOsN8pZKVHQ":
            icon_links = json.loads(request.POST.get('icon_urls'))
            print(f"ICON LINKS: {icon_links}")
        new_id = copy_template(presentation_id, round_title, qas_dict, icon_links)
        print (qas_dict)
        return JsonResponse({'new_id': new_id})

class ShareView(View):
    def post(self, request, *args, **kwargs):
        presentation_id = request.POST.get('presentation_id')
        share_slides(presentation_id)
        return JsonResponse({'success': True})

@login_required
def rounds_list(request):
    rounds = GPTriviaRound.objects.all()
    # can we reverse the order of the rounds
    rounds = rounds[::-1]

    player_fields = _get_global_player_fields()
    player_names = [display_name_for_player_field(field) for field in player_fields]
    player_color_mapping = build_player_color_mapping(player_names)
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
    }

    return render(request, 'GPTrivia/rounds_list.html', context)

@login_required
def player_analysis(request):
    queryset_rounds = GPTriviaRound.objects.all()
    player_fields = _get_global_player_fields()
    player_names = [display_name_for_player_field(field) for field in player_fields]
    player_name_mapping = {
        player_name: player_field
        for player_name, player_field in zip(player_names, player_fields)
    }

    creators = sorted({
        round_obj.creator for round_obj in queryset_rounds if round_obj.creator
    })
    categories = sorted({
        round_obj.major_category for round_obj in queryset_rounds if round_obj.major_category
    })

    rounds = []
    for round_obj in queryset_rounds:
        round_data = flatten_round_for_analysis(round_obj)
        round_data['date'] = round_obj.date.strftime("%m/%d/%Y")
        round_data['replay'] = str(round_obj.replay).lower()
        round_data['cooperative'] = str(round_obj.cooperative).lower()
        for player_field in player_fields:
            if round_data.get(player_field) is None:
                round_data[player_field] = ''
        rounds.append(round_data)

    player_color_mapping = build_player_color_mapping(player_names)
    player_text_mapping = build_player_text_mapping(player_names)

    context = {
        'rounds': rounds,
        'playerColorMapping': player_color_mapping,
        'creators': creators,
        'categories': categories,
        'players': player_names,
        "mapping": player_name_mapping,
        "player_text_mapping": player_text_mapping,
    }

    return render(request, 'GPTrivia/player_analysis_new.html', context)



@login_required
def player_analysis_legacy(request):
    return redirect('player_analysis')


def upload_profile_picture(request):
    if request.method == 'POST':
        # Get or create the profile instance
        profile, created = Profile.objects.get_or_create(user=request.user)
        form = ProfilePictureForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('player_profile', player_name=request.user.username)
    else:
        form = ProfilePictureForm(instance=request.user.profile)
    return render(request, 'your_template.html', {'form': form})


def _build_player_icon_map():
    icon_map = {}

    for profile in Profile.objects.select_related('user'):
        if not profile.user_id:
            continue

        if profile.has_custom_profile_picture():
            profile.ensure_profile_icon()

        if not profile.profile_icon:
            continue

        display_name = display_name_for_player_field(profile.user.username)
        if not display_name:
            continue

        icon_map[display_name] = profile.profile_icon.url
        player_field = player_field_for_name(display_name)
        if player_field:
            icon_map[player_field] = profile.profile_icon.url

    return icon_map

@login_required
def player_profile_dict(request, player_name):
    player_name = display_name_for_player_field(player_name)
    score_field = player_field_for_name(player_name)

    all_rounds = list(GPTriviaRound.objects.all().order_by('-date', 'round_number'))
    flattened_rounds = [
        {
            **flatten_round_for_analysis(round_obj),
            'normalized_creator': display_name_for_player_field(round_obj.creator),
        }
        for round_obj in all_rounds
    ]

    global_player_names = _get_global_player_names()
    if player_name not in global_player_names:
        raise Http404("Player profile not available")

    player_color = get_player_color(player_name)
    brightness = (0.5 * int(player_color[1:3], 16)) + int(player_color[3:5], 16) + (0.25 * int(player_color[5:7], 16))
    text_color = 'white' if brightness < 300 else 'black'

    created_rounds = [
        round_obj for round_obj in all_rounds
        if display_name_for_player_field(round_obj.creator) == player_name
    ]
    created_rounds_count = len(created_rounds)

    all_categories = sorted({
        round_data['major_category']
        for round_data in flattened_rounds
        if round_data['major_category']
    })
    created_category_counts = {
        category: 0
        for category in all_categories
    }
    for round_obj in created_rounds:
        if round_obj.major_category:
            created_category_counts[round_obj.major_category] = created_category_counts.get(round_obj.major_category, 0) + 1
    created_rounds_cat_list = [
        {'major_category': category, 'num_rounds': created_category_counts.get(category, 0)}
        for category in all_categories
    ]

    player_values = [
        round_data.get(score_field)
        for round_data in flattened_rounds
        if round_data.get(score_field) is not None
    ]
    player_avg = (sum(player_values) / len(player_values)) if player_values else None
    total_rounds = len(player_values)

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
        if creator_avg['creator'] in global_player_names and creator_avg['creator'] != player_name and creator_avg['avg_score'] is not None
    ]
    max_creator_avg = eligible_creator_averages[0]['creator'] if eligible_creator_averages else ''
    min_creator_avg = eligible_creator_averages[-1]['creator'] if eligible_creator_averages else ''

    final_results = {}
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
        final_results[creator_name] = player_scores

    final_averages = {}
    for creator_name, score_map in final_results.items():
        values = [avg_score for avg_score in score_map.values() if avg_score is not None]
        final_averages[creator_name] = (sum(values) / len(values)) if values else None

    biases = {}
    for item in creator_averages:
        creator_name = item['creator']
        if creator_name not in final_averages:
            continue
        if final_averages[creator_name] is not None and item['avg_score'] is not None:
            biases[creator_name] = item['avg_score'] - final_averages[creator_name]
        else:
            biases[creator_name] = 0

    sumb = 0
    for entry in list(biases.keys()):
        if biases[entry] is not None and player_avg is not None:
            biases[entry] = biases[entry] + player_avg
            sumb += biases[entry]
        else:
            biases[entry] = 0

    if biases:
        mean_bias = sumb / len(biases)
        for entry in list(biases.keys()):
            if biases[entry] is not None:
                biases[entry] = biases[entry] - mean_bias
            else:
                biases[entry] = 0
        max_bias_avg = max(biases, key=biases.get)
        min_bias_avg = min(biases, key=biases.get)
        max_bias_avg_value = "{:.2f}".format(biases[max_bias_avg])
        min_bias_avg_value = "{:.2f}".format(biases[min_bias_avg])
    else:
        max_bias_avg = ''
        min_bias_avg = ''
        max_bias_avg_value = "0.00"
        min_bias_avg_value = "0.00"

    form = ProfilePictureForm()
    profile_user = User.objects.filter(username__iexact=player_name).first()
    profile_picture_url = profile_user.profile.profile_picture.url if profile_user else '/media/default.jpg'

    context = {
        'profile_user': profile_user,
        'profile_picture_url': profile_picture_url,
        'player_name': player_name,
        'created_rounds_cat': created_rounds_cat_list,
        'created_rounds': created_rounds,
        'player_color_mapping': build_player_color_mapping(global_player_names),
        'text_color': text_color,
        'max_avg': max_avg,
        'min_avg': min_avg,
        'max_bias_avg': max_bias_avg,
        'min_bias_avg': min_bias_avg,
        'max_bias_avg_value': max_bias_avg_value,
        'min_bias_avg_value': min_bias_avg_value,
        'total_rounds': total_rounds,
        'max_cat_avg': max_creator_avg,
        'min_cat_avg': min_creator_avg,
        'created_rounds_count': created_rounds_count,
        'form': form,
    }

    return context

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
        try:
            import autogen
        except ImportError:
            return JsonResponse({'error': 'autogen is not installed'}, status=503)

        llm_config = {"config_list": _get_autogen_config_list(), "seed": random.randint(1, 100000)}
        user_proxy = autogen.UserProxyAgent(
            name="User_proxy",
            system_message="""
    Reply TERMINATE if the task has been solved at full satisfaction. 
    Otherwise, reply RETRY, or the reason why the task is not solved yet.""",
            human_input_mode="NEVER",
            is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
            llm_config=llm_config,

        )
        qm = autogen.AssistantAgent(
            name="QuestionMaster",
            llm_config=llm_config,
            system_message="You provide creative ideas for ONE SINGLE trivia question based on a theme provided to you by the User_proxy. You also provide a SHORT answer to your question. You start the question with the word 'Question:' and the answer with the word 'Answer:'. You are careful to make sure that the selected trivia idea is creative and unusual, but not too niche of a topic for a general-audience trivia night."
        )
        ap = autogen.AssistantAgent(
            name="Analyzer",
            system_message="You analyze the question provided by the QuestionMaster and check if the question is appropriate for a general-audience trivia night. If not, you request a new question from the QuestionMaster.",
            llm_config=llm_config,
        )
        cr = autogen.AssistantAgent(
            name="Critic",
            system_message="You look through answers provided by the QuestionMaster after review by the Analyzer to check if the answer is wrong. If not correct, either request a new question or if possible, provide a corrected answer. You should be very particular about the correctness of the answer.",
            llm_config=llm_config,
        )
        final = autogen.AssistantAgent(
            name="Finalizer",
            system_message="Once the Critic says the answer is correct, simply state the question provided by the QuestionMaster and answer provided by the Critic, absolutely nothing else. Start the question with the format 'Question:' and the answer after two newlines with the format 'Answer:' (with NO PERIOD) and end the message with the statement with the word `TERMINATE` (all caps, no period).",
            llm_config=llm_config,
            is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
        )
        groupchat = autogen.GroupChat(agents=[qm, ap, cr, final, user_proxy], messages=[], max_round= 10)
        manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=llm_config, is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"), system_message="Reply `TERMINATE` in the end when everything is done.")

        user_proxy.initiate_chat(manager, message=request.POST.get('user_input'))

        auto_resp = manager.last_message(final)

        return JsonResponse({'autogen_response': auto_resp["content"]})

class GenerateImageView(View):
    def post(self, request, *args, **kwargs):
        gpt_response = request.POST.get('gpt_text')
        client = _get_openai_client()

        try:
            # Get the conversation history from the session
            conversation_history = request.session.get('conversation_history', [])
            # Append the user's message to the conversation history
            conversation_history.append({"role": "user", "content": f"SWOOP I want you to condense this text by summarizing the theme of the round being suggested in this prompt in a few words and nothing else: {gpt_response}"})

            try:
                response = client.chat.completions.create(# model="gpt-3.5-turbo",
                # model="gpt-4",
                model="o3",
                temperature=1,
                messages=conversation_history,
                max_completion_tokens=150)
                print(f"RESPONSE: {response}")
                second_response = response.choices[0].message.content
                print(f"SECOND RESPONSE: {second_response}")
            except Exception as e:
                second_response = str(e)
                return JsonResponse({'dalle_image_url': None})

            # Call to DALL-E to generate an image based on the conversation
            dalle_response = client.images.generate(prompt=f"Swooper, a snake with wings. He's mysterious and sly. Draw Swooper, and have his surroundings and clothing reflect the theme of this sentence: {second_response}. Make sure the image is artistic and stylized.",
            # This assumes you want to generate an image based on the last text response from GPT-4
            n=1,  # Number of images to generate
            size="1024x1024",  # The size of the image
            model='gpt-image-1')
            image_url = dalle_response.data[0].url  # URL of the generated image
            print(image_url)

        except Exception as e:
            image_url = None  # No image if there's an error
            print(image_url)

        return JsonResponse({'dalle_image_url': image_url})

class IconView(View):
    def post(self, request, *args, **kwargs):
        gpt_response = request.POST.get('question_text')
        client = _get_openai_client()


        try:
            # Get the conversation history from the session

            # conversation_history = request.session.get('conversation_history', [])
            # actually, let's just start a new conversation history
            conversation_history = []
            # Append the user's message to the conversation history
            conversation_history.append({"role": "user", "content": f"I want you to provide key words (no more than two) that summarize the following question. For example, if the question was about dinosaurs, you could response with the word \"dinosaur\" and nothing else. Here's the question: {gpt_response}"})

            try:
                response = client.chat.completions.create(# model="gpt-3.5-turbo",
                # model="gpt-4",
                model="gpt-4o",
                temperature=1,
                messages=conversation_history,
                max_tokens=150)
                print(f"RESPONSE: {response}")
                second_response = response.choices[0].message.content
                print(f"SECOND RESPONSE: {second_response}")
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
        request.session['conversation_history'] = [
            {"role": "system", "content": "Your name is Swooper, the swoop snake. At the very beginning of every conversation (but NOT every single reply), the first thing you say is 'Swoop!' in a high pitched voice. You also have wings. You're sssmooth-talking, sssensual, and myssterious. Now, whenever someone says something to you, make sure to respond in the voice of that character. Also, your job is trivia round recommender. No matter what the reply is, you find a way to suggest challenging and off-the-wall trivia rounds that the user might enjoy making. And you do not under any circumstances provide actual question, only ideas for rounds. Here's an example of what you might say:'Sssmooth movesss, my friend! But you ssseem like sssomeone who might enjoy a great trivia round. How about trying a \"sssensational sssoundtrack\" round, filled with quessstionsss about famousss movie ssscores and theme sssongsss? Sssounds exciting, doesssn't it?' Also, if someone starts their message with 'SWOOP', you break out of character entirely and answer like a normal helpful assistant."}
        ]
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        user_input = request.POST.get('user_input')
        client = _get_openai_client()


        # Get the conversation history from the session
        conversation_history = request.session.get('conversation_history', [])
        # Append the user's message to the conversation history
        conversation_history.append({"role": "user", "content": user_input})

        try:
            response = client.chat.completions.create(# model="gpt-3.5-turbo",
            # model="gpt-4",
            model = "o3",
            temperature=1,
            messages=conversation_history,
            max_completion_tokens=150)
            print(f"RESPONSE: {response}")
            gpt_response = response.choices[0].message.content
            conversation_history.append({"role": "assistant", "content": gpt_response})
            request.session['conversation_history'] = conversation_history

            # # Call to DALL-E to generate an image based on the conversation
            # dalle_response = openai.Image.create(
            #     prompt=f"Draw an image of the following creature: Swooper, the swoop snake. You have wings. You're sssmooth-talking, and myssterious. Swooper's job is trivia round recommender. Swooper has just suggested the following round: {gpt_response} I want you to draw Swooper, and have him be dressed up and have his surroundings reflect the theme of the suggested round. Make sure the image is artistic and stylized, NOT photorealistic or computer-generated.",
            #     # This assumes you want to generate an image based on the last text response from GPT-4
            #     n=1,  # Number of images to generate
            #     size="1024x1024",  # The size of the image
            #     model='dall-e-3'
            # )
            # image_url = dalle_response['data'][0]['url']  # URL of the generated image

        except Exception as e:
            gpt_response = str(e)

        return JsonResponse({'gpt_response': gpt_response})

@login_required
def player_profile(request, player_name):
    context = player_profile_dict(request, player_name)
    return render(request, 'GPTrivia/player_profile.html', context)


@sync_to_async          # runs blocking code in a thread-pool
def _collect_rounds():
    links, titles, creators, old_links, shared_dates = get_round_titles_and_links()
    return [
        {
            "title": t, "creator": c, "link": l,
            "old_link": o, "shared_date": d
        }
        for t, c, l, o, d in zip(titles, creators, links, old_links, shared_dates)
    ]

async def collect_rounds_api(request):
    if request.method != "GET":
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    data = await _collect_rounds()
    return JsonResponse({"rounds": data})


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
        presentation_date = _parse_presentation_name_date(presentation.name)
        if presentation_date is None:
            continue

        presentation_calendar[presentation_date.isoformat()] = {
            "presentation_id": presentation.presentation_id,
            "name": presentation.name,
        }

    return presentation_calendar


def _build_home_context(selected_presentation, presentation_calendar):
    selected_presentation_date = None
    presentation_url = None

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
    }


def _serialize_home_presentation(selected_presentation, presentation_id=None):
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
            if selected_presentation_date
            else None
        ),
    }


def _is_ajax_home_request(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def _get_selected_home_presentation(selected_presentation_id=None):
    presentations = list(MergedPresentation.objects.order_by("id"))
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

@login_required
@ensure_csrf_cookie
def home(request):
    ajax_request = _is_ajax_home_request(request)
    selected_presentation_id = (
        request.GET.get("presentation_id") or request.POST.get("selected_presentation_id")
    )
    latest_presentation, selected_presentation, presentation_calendar = _get_selected_home_presentation(
        selected_presentation_id
    )
    home_context = _build_home_context(selected_presentation, presentation_calendar)

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
                }
            # make sure there's at least one round, or else just return
            if not round_order:
                if ajax_request:
                    return JsonResponse({"detail": "No rounds selected."}, status=400)
                return render(request, "GPTrivia/home.html", home_context)

            # Sort rounds by order
            ordered_rounds = [round_order[key] for key in sorted(round_order.keys())]

            # Extract ordered titles, creators, and links
            ordered_titles = [round['title'] for round in ordered_rounds]
            ordered_creators = [round['creator'] for round in ordered_rounds]
            ordered_links = [round['link'] for round in ordered_rounds]
            ordered_old_links = [round['old_link'] for round in ordered_rounds]
            ordered_coop = [round['coop'] for round in ordered_rounds]

            # Pass the ordered data to create_presentation
            new_presentation_id = create_presentation(
                ordered_titles,
                ordered_creators,
                ordered_links,
                presentation_name=presentation_name,
                old_links=ordered_old_links,
                coops=ordered_coop
            )

            round_titles = ordered_titles
            creators = ordered_creators
            round_links = ordered_links

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
            print (new_presentation_id, creators, round_titles)

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
                new_round.save()

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

            # Sort rounds by order
            ordered_rounds = [round_order[key] for key in sorted(round_order.keys())]

            # Extract ordered titles, creators, and links
            ordered_titles = [round['title'] for round in ordered_rounds]
            ordered_creators = [round['creator'] for round in ordered_rounds]
            ordered_links = [round['link'] for round in ordered_rounds]
            ordered_old_links = [round['old_link'] for round in ordered_rounds]
            ordered_coop = [round['coop'] for round in ordered_rounds]


            # Pass the ordered data to create_presentation
            # new_presentation_id = create_presentation(
            #     ordered_titles,
            #     ordered_creators,
            #     ordered_links,
            #     presentation_name=presentation_name
            # )

            updated_presentation_id, new_creators, round_titles, new_links = update_merged_presentation(
                selected_presentation.presentation_id,
                selected_presentation.creator_list,
                ordered_titles,
                ordered_creators,
                ordered_links,
                ordered_old_links,
                coops=ordered_coop,
            )

            # update the MergedPresentation object that has the same presentation_id as the latest_presentation
            # by appending the new creators to the creator_list and appending the new round titles to the round_names

            selected_presentation = MergedPresentation.objects.get(
                presentation_id=selected_presentation.presentation_id
            )
            selected_presentation.presentation_id = updated_presentation_id
            selected_presentation.round_names.extend(round_titles)
            selected_presentation.creator_list.extend(new_creators)
            selected_presentation.save()

            print(updated_presentation_id, new_creators, round_titles)
            response_presentation = selected_presentation
            response_presentation_id = updated_presentation_id

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
                new_round.save()

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
    queryset = MergedPresentation.objects.all()
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

    return PlayerAnalysisPlot.as_view()(request, *args, **kwargs)


SCORESHEET_GROUP_NAME = 'scoresheet_scoresheet_updates'
SCORESHEET_ROUND_FIELDS = {
    'creator', 'title', 'major_category', 'minor_category1', 'minor_category2', 'date',
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


def _presentation_name_for_date(selected_date):
    parsed_date = _parse_scoresheet_date(selected_date)
    if not parsed_date:
        return None
    return parsed_date.strftime("%m.%d.%Y")


def _current_trivia_date():
    return datetime.datetime.now(TRIVIA_TIMEZONE).date()


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
        try:
            return MergedPresentation.objects.get(presentation_id=presentation_id)
        except ObjectDoesNotExist:
            return None

    presentation_name = _presentation_name_for_date(selected_date)
    if not presentation_name:
        return None

    try:
        return MergedPresentation.objects.get(name=presentation_name)
    except ObjectDoesNotExist:
        return None


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

        if dirty_fields or presentation.pk is None:
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
            MergedPresentation.objects.filter(name=thedate.strftime("%m.%d.%Y")).delete()

        _schedule_scoresheet_broadcast({
            'action': 'update',
            'event': 'delete_round',
            'client_id': client_id,
            'mutation_id': mutation_id,
            'round_id': round_id,
            'selected_date': str(thedate),
        })
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
    joker_round_indices = {key: value.replace("'", "~~~~") for key, value in joker_round_indices.items()}

    # Update the joker_round_indices in the MergedPresentation
    if presentation_id:
        try:
            presentation = MergedPresentation.objects.get(presentation_id=presentation_id)
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
        except ObjectDoesNotExist:
            return JsonResponse({"message": "Presentation not found."}, status=400)
    elif date_str:
        try:
            presentation = MergedPresentation.objects.get(name=datetime.datetime.strptime(date_str, '%Y-%m-%d').date().strftime("%m.%d.%Y"))
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
            try:
                MergedPresentation.objects.create(
                    name=datetime.datetime.strptime(date_str, '%Y-%m-%d').date().strftime("%m.%d.%Y"),
                    presentation_id="",
                    creator_list=creator_list,
                    round_names=round_names,
                    joker_round_indices=joker_round_indices,
                    player_list=all_player_list,
                    host = host,
                    scorekeeper=scorekeeper,
                    style_points=style_points,
                    notes=notes,
                    tiebreak_winner=tiebreak_winner,
                )
            except Exception as e:
                print(f"Error creating MergedPresentation object: {e}")
                return JsonResponse({"message": "Error creating MergedPresentation object."}, status=400)
    else:
        # create a new MergedPresentation object
        try:
            MergedPresentation.objects.create(
                name=datetime.datetime.strptime(date_str, '%Y-%m-%d').date().strftime("%m.%d.%Y"),
                presentation_id="",
                creator_list=creator_list,
                round_names=round_names,
                joker_round_indices=joker_round_indices,
                player_list=all_player_list,
                host=host,
                scorekeeper=scorekeeper,
                style_points=style_points,
                notes=notes,
                tiebreak_winner=tiebreak_winner,
            )
        except Exception as e:
            print(f"Error creating MergedPresentation object: {e}")
            return JsonResponse({"message": "Error creating MergedPresentation object."}, status=400)


    return JsonResponse({"message": "Data saved successfully!"})
