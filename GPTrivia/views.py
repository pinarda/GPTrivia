from django.shortcuts import render, redirect
from .forms import GPTriviaRoundForm
from .models import GPTriviaRound, MergedPresentation
from django.db.models import Avg, F, FloatField, Case, When, Sum, Count
from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from django.shortcuts import render
from .mail import create_presentation, update_merged_presentation, copy_template, share_slides
from datetime import datetime
from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.csrf import csrf_exempt
import openai
from django.views import View
import os
import random




import numpy as np
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
from .serializers import GPTriviaRoundSerializer, MergedPresentationSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.decorators import api_view
from django.http import JsonResponse
from django.core import serializers
from rest_framework.renderers import JSONRenderer
from datetime import date
from django.contrib.postgres.fields import JSONField  # Import this at the top of your file


gmail_key = '8f35edc691b918094035b22807266a1e468bf5f0'

playerColorMapping = {
            'Alex': '#D2042D',
            'Ichigo': '#ff7f0e',
            'Megan': '#8e4585',
            'Zach': '#A020F0',
            'Jenny': '#ffef00',
            'Debi': '#8551ff',
            'Mom': '#8551ff',
            'Dan': '#0000FF',
            'Dad': '#0000FF',
            'Chris': '#005427',
            'Drew': '#8c564b',
            'Jeff': '#333333',
            'Paige': '#333333',
            'Dillon': '#333333',
            'Unknown': '#333333',
        };

players = [
    'score_alex', 'score_ichigo', 'score_megan', 'score_zach', 'score_jenny', 'score_debi',
    'score_dan', 'score_chris', 'score_drew']

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

        new_id = copy_template(presentation_id, round_title, qas_dict)
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
    text_color = {}
    players = ["Alex", "Ichigo", "Megan", "Zach", "Jenny", "Debi", "Dan", "Chris", "Drew", "Dad", "Mom"]
    for player in players:
        # grab the player's hex color from the playerColorMapping dictionary
        player_color = playerColorMapping[player]
        # convert the hex color to a measure of brightness
        brightness = int(player_color[1:3], 16) + int(player_color[3:5], 16) + int(player_color[5:7], 16)
        # if the brightness is less than 384, use white text, otherwise use black text
        if brightness < 480:
            text_color[player] = 'white'
        else:
            text_color[player] = 'black'
    context = {'rounds': rounds,
               'playerColorMapping': playerColorMapping,
               'text_color_mapping': text_color}

    return render(request, 'GPTrivia/rounds_list.html', context)


@login_required
def player_analysis(request):
    queryset_rounds = GPTriviaRound.objects.all()

    players = ["Alex", "Ichigo", "Megan", "Zach", "Jenny", "Debi", "Dan", "Chris", "Drew"]

    # a dicitonary that maps the player name to the string score_playername
    player_name_mapping = {"Alex": "score_alex", "Ichigo": "score_ichigo", "Megan": "score_megan", "Zach": "score_zach",
                            "Jenny": "score_jenny", "Debi": "score_debi", "Dan": "score_dan", "Chris": "score_chris", "Drew": "score_drew"}


    creators = set()
    categories = set()

    for round in queryset_rounds:
        creators.add(round.creator)
        categories.add(round.major_category)

    rounds = [{
        'creator': round.creator,
        'title': round.title,
        'major_category': round.major_category,
        'minor_category1': round.minor_category1,
        'minor_category2': round.minor_category2,
        # convert date to string
        'date': round.date.strftime("%m/%d/%Y"),
        'round_number': round.round_number,
        'max_score': round.max_score,
        # if the player_score is None, replace with empty string
        'score_alex': round.score_alex if round.score_alex is not None else '',
        'score_ichigo': round.score_ichigo if round.score_ichigo is not None else '',
        'score_megan': round.score_megan if round.score_megan is not None else '',
        'score_zach': round.score_zach if round.score_zach is not None else '',
        'score_jenny': round.score_jenny if round.score_jenny is not None else '',
        'score_debi': round.score_debi if round.score_debi is not None else '',
        'score_dan': round.score_dan if round.score_dan is not None else '',
        'score_chris': round.score_chris if round.score_chris is not None else '',
        'score_drew': round.score_drew if round.score_drew is not None else '',
        'replay': str(round.replay).lower(),
        'cooperative': str(round.cooperative).lower(),
    } for round in queryset_rounds]

    context = {
        'rounds': rounds,
        'playerColorMapping': playerColorMapping,
        'creators': list(creators),
        'categories': list(categories),
        'players': players,
        "mapping": player_name_mapping,
    }

    return render(request, 'GPTrivia/player_analysis.html', context)



@login_required
def player_analysis_legacy(request):
    creators = GPTriviaRound.objects.values_list('creator', flat=True).distinct()

    player_averages = []
    player_cat_averages = []
    player_scores = []
    player_cat_scores = []


    #aggregate the average score regardless of creator
    player_aggregates_ind = {
        f"{player}__avg": Avg(
            Case(When(**{f"{player}__isnull": True}, then=None), default=F(player)), output_field=FloatField()
        ) for player in players
    }

    # Calculate player averages
    averages_ind = GPTriviaRound.objects.aggregate(**player_aggregates_ind)
    # filter out None values, replace with 0

    filtered_averages_ind = {k: v or 0 for k, v in averages_ind.items()}

    for creator in creators:
        queryset = GPTriviaRound.objects.filter(creator=creator)

        # Create a dictionary for aggregating player averages
        player_aggregates = {
            f"{player}__avg": Avg(
                Case(When(**{f"{player}__isnull": True}, then=None), default=F(player)), output_field=FloatField()
            ) for player in players
        }

        # Get all scores for each creator and filter out None values
        scores = queryset.values(*players)
        filtered_scores = []
        for score in scores:
            filtered_score = {key: value for key, value in score.items() if value is not None}
            filtered_scores.append(filtered_score)

        # Calculate the mean for each creator
        means = {player: np.mean([score[player] for score in filtered_scores if player in score]) for player in players}

        # Normalize the scores by subtracting the player's average over all rounds
        normalized_scores = []
        for score in filtered_scores:
            normalized_score = {player: value - averages_ind[f"{player}__avg"] for player, value in score.items()}
            normalized_scores.append(normalized_score)

        # convert the creator name to a lowercase string and prepend score_ to the beginning
        # unless the creator is Dad or Mom, in which case call them score_dan and score_debi
        if creator == "Dad":
            creator = "Dan"
        elif creator == "Mom":
            creator = "Debi"

        score_c = f"score_{creator.lower()}"
        # Then check the means dictionary for this score_c key and if it exists, delete it
        if score_c in means:
            del means[score_c]

        player_scores.append({"creator": creator, "scores": normalized_scores, "means": means})

        # Sort player_scores by the mean in descending order
        player_scores.sort(key=lambda x: np.mean(list(x['means'].values())), reverse=True)
        # Calculate player averages
        averages = queryset.aggregate(**player_aggregates)

     # Filter out None values, replace with 0
        filtered_averages = {k: v or 0 for k, v in averages.items()}

        #subtract the average score for each player regardless of creator from the average score for each player for the given creator
        # unless the average score for the given creator is 0, in which case the average score for the given creator is used
        filtered_normalized_averages = {k: v - filtered_averages_ind[k] if v != 0 else v for k, v in filtered_averages.items()}

        # Add creator to the dictionary and append it to the list
        filtered_normalized_averages['creator'] = creator
        player_averages.append(filtered_normalized_averages)


        # Round Category filtering

        categories = GPTriviaRound.objects.values_list('major_category', flat=True).distinct()

    for cat in categories:
        queryset = GPTriviaRound.objects.filter(major_category=cat)

        # Create a dictionary for aggregating player averages
        #
        player_cat_aggregates = {
            f"{player}__avg": Avg(
                Case(When(**{f"{player}__isnull": True}, then=None), default=F(player)), output_field=FloatField()
            ) for player in players
        }

        # Get all scores for each category and filter out None values
        scores = queryset.values(*players)
        filtered_scores = []
        for score in scores:
            filtered_score = {key: value for key, value in score.items() if value is not None}
            filtered_scores.append(filtered_score)

        # Calculate player averages
        averages = queryset.aggregate(**player_cat_aggregates)

        # Calculate the mean for each creator
        means = {player: np.mean([score[player] for score in filtered_scores if player in score]) for player in players}

        # Normalize the scores by subtracting the player's average over all rounds
        normalized_scores = []
        for score in filtered_scores:
            normalized_score = {player: value - averages_ind[f"{player}__avg"] for player, value in score.items()}
            normalized_scores.append(normalized_score)



        # Filter out None values, replace with 0
        filtered_cat_averages = {k: v or 0 for k, v in averages.items()}

        filtered_normalized_cat_averages = {k: v - filtered_averages_ind[k] if v != 0 else v for k, v in
                                        filtered_cat_averages.items()}


        # Add category to the dictionary and append it to the list
        filtered_normalized_cat_averages['category'] = cat
        player_cat_averages.append(filtered_normalized_cat_averages)

        player_cat_scores.append({"category": cat, "scores": normalized_scores, "means": means})



    return render(request, 'GPTrivia/player_analysis_legacy.html', {
        'player_averages': player_averages,
        'player_cat_averages': player_cat_averages,
        'creators': creators,
        'categories': categories,
        'player_scores': player_scores,
        'player_cat_scores': player_cat_scores,
        'player_color_mapping': playerColorMapping,
    })

@login_required
def player_profile_dict(request, player_name):
    # Ensure the player_name is in the correct format (e.g., title case)
    player_name = player_name.title()

    # convert the player name to a lowercase string and prepend score_ to the beginning
    # unless the player is Dad or Mom, in which case call them score_dan and score_debi
    if player_name == "Dad":
        player_name = "Dan"
    elif player_name == "Mom":
        player_name = "Debi"

    # creator name should be equal to the player name
    # unless the player is Dan or Debi, in which case call them Dad and Mom
    if player_name == "Dan":
        creator_name = "Dad"
    elif player_name == "Debi":
        creator_name = "Mom"
    else:
        creator_name = player_name

    score_p = f"score_{player_name.lower()}"

    # Fetch the created round categories for the given player and sum the number of rounds in each category
    # and call it num_rounds and order by the number of rounds in descending order
    created_rounds_cat = (
        GPTriviaRound.objects
        .filter(creator=creator_name)
        .values('major_category')
        .annotate(num_rounds=Count('major_category'))
        .order_by('-num_rounds')
    )

    # Fetch the created round names for the given player, and order by creation date
    created_rounds = (
        GPTriviaRound.objects
        .filter(creator=creator_name)
        .order_by('-date')
    )

    # grab the player's hex color from the playerColorMapping dictionary
    player_color = playerColorMapping[player_name]
    # convert the hex color to a measure of brightness
    brightness = int(player_color[1:3], 16) + int(player_color[3:5], 16) + int(player_color[5:7], 16)
    # if the brightness is less than 384, use white text, otherwise use black text
    if brightness < 480:
        text_color = 'white'
    else:
        text_color = 'black'

    # compute the player's average score over all rounds
    player_avg = GPTriviaRound.objects.aggregate(
        avg_score=Avg(
            Case(When(**{f"{score_p}__isnull": True}, then=None), default=F(score_p)), output_field=FloatField()
        )
    )['avg_score']


    # compute the players average score for each category
    category_averages = GPTriviaRound.objects.values('major_category').annotate(
        avg_score=Avg(
            Case(When(**{f"{score_p}__isnull": True}, then=None), default=F(score_p)), output_field=FloatField()
        )
    ).order_by('-avg_score', 'major_category')

    # subtract the category average from the player's average score
    # this will be used to determine the relative position of the player's average score
    # in the category
    for cat_avg in category_averages:
        if cat_avg['avg_score'] is not None:
            cat_avg['avg_score'] = cat_avg['avg_score'] - player_avg
        else:
            cat_avg['avg_score'] = 0

    # sort the category averages by the average score
    category_averages = sorted(category_averages, key=lambda k: k['avg_score'], reverse=True)


    # save category of the round with the highest and lowest average score for the player
    max_avg = category_averages[0]['major_category']
    min_avg = category_averages[len(category_averages) - 1]['major_category']
    players = ["Alex", "Ichigo", "Megan", "Zach", "Jenny", "Debi", "Dan", "Chris", "Drew", "Dad", "Mom"]

    # count the total number of rounds the player has a score for
    total_rounds = GPTriviaRound.objects.filter(**{f"{score_p}__isnull": False}).count()

    # compute the players average score for each creator
    creator_averages = GPTriviaRound.objects.values('creator').annotate(
        avg_score=Avg(
            Case(When(**{f"{score_p}__isnull": True}, then=None), default=F(score_p)), output_field=FloatField()
        )
    ).order_by('-avg_score', 'creator')

    # remove the player's average score from the list of creator averages
    creator_averages = [creator_avg for creator_avg in creator_averages if creator_avg['creator'] != creator_name]


    # subtract the player's average score from the average score for each creator
    # this will be used to determine the relative position of the player's average score
    # in the creator
    # but make sure we don't try to subtract a None from a float
    for creator_avg in creator_averages:
        if creator_avg['avg_score'] is not None:
            creator_avg['avg_score'] = creator_avg['avg_score'] - player_avg

    # save creator of the round with the highest and lowest average score for the player
    # but make sure the player isn't the creator of the round with the highest or lowest average score
    # max_creator_avg = creator_averages[0]['creator']
    # min_creator_avg = creator_averages[len(creator_averages) - 1]['creator']
    # if max_creator_avg == player_name:
    #     max_creator_avg = creator_averages[1]['creator']
    # if min_creator_avg == player_name:
    #     min_creator_avg = creator_averages[len(creator_averages) - 2]['creator']
    # # if the max_creator_avg or min_creator_avg is an empty string
    # # choose the next highest or lowest average score
    # if max_creator_avg == "":
    #     max_creator_avg = creator_averages[2]['creator']
    # if min_creator_avg == "":
    #     min_creator_avg = creator_averages[len(creator_averages) - 3]['creator']

    # if the max_creator_avg or min_creator_avg is not in the list of players
    # continue until we find a player that is in the list of players and is not the player
    max_creator_avg = creator_averages[0]['creator']
    min_creator_avg = creator_averages[len(creator_averages) - 1]['creator']
    i = 0
    while max_creator_avg not in players or max_creator_avg == player_name:
        i=i+1
        max_creator_avg = creator_averages[i]['creator']
    i = 0
    while min_creator_avg not in players or min_creator_avg == player_name:
        i=i+1
        min_creator_avg = creator_averages[len(creator_averages) - 1 - i]['creator']





    # let's count the number of rounds that the player has created
    created_rounds_count = created_rounds.count()


    context = {
        'player_name': player_name,
        'created_rounds_cat': created_rounds_cat,
        'created_rounds': created_rounds,
        'player_color_mapping': playerColorMapping,
        'text_color': text_color,
        'max_avg': max_avg,
        'min_avg': min_avg,
        'total_rounds': total_rounds,
        'max_cat_avg': max_creator_avg,
        'min_cat_avg': min_creator_avg,
        'created_rounds_count': created_rounds_count,
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

class RoundMaker(View):
    template_name = 'GPTrivia/round_maker.html'

    def get(self, request, *args, **kwargs):
        request.session['conversation_history'] = [
            {"role": "system", "content": "Your name is Swooper, the swoop snake. At the very beginning of every conversation (but NOT every single reply), the first thing you say is 'Swoop!' in a high pitched voice. You also have wings. You're sssmooth-talking, sssensual, and myssterious. Now, whenever someone says something to you, make sure to respond in the voice of that character. Also, your job is trivia round recommender. No matter what the reply is, you find a way to suggest challenging and off-the-wall trivia rounds that the user might enjoy making. And you do not under any circumstances provide actual question, only ideas for rounds. Here's an example of what you might say:'Sssmooth movesss, my friend! But you ssseem like sssomeone who might enjoy a great trivia round. How about trying a \"sssensational sssoundtrack\" round, filled with quessstionsss about famousss movie ssscores and theme sssongsss? Sssounds exciting, doesssn't it?' Also, if someone starts their message with 'SWOOP', you break out of character entirely and answer like a normal helpful assistant."}
        ]
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        user_input = request.POST.get('user_input')
        openai.api_key = os.getenv('OPENAI_API_KEY')

        # Get the conversation history from the session
        conversation_history = request.session.get('conversation_history', [])
        # Append the user's message to the conversation history
        conversation_history.append({"role": "user", "content": user_input})

        try:
            response = openai.ChatCompletion.create(
                # model="gpt-3.5-turbo",
                model="gpt-4",
                messages=conversation_history,
                max_tokens=150
            )
            print(response)
            gpt_response = response['choices'][0]['message']['content']
            conversation_history.append({"role": "assistant", "content": gpt_response})
            request.session['conversation_history'] = conversation_history
        except Exception as e:
            gpt_response = str(e)

        return JsonResponse({'gpt_response': gpt_response})

@login_required
def player_profile(request, player_name):
    context = player_profile_dict(request, player_name)
    return render(request, 'GPTrivia/player_profile.html', context)

@login_required
def home(request):
    try:
        latest_presentation = MergedPresentation.objects.latest('id')
        presentation_url = f"https://docs.google.com/presentation/d/{latest_presentation.presentation_id}/embed"
    except MergedPresentation.DoesNotExist:
        latest_presentation = None
        presentation_url = None

    presentation_name = datetime.date.strftime(datetime.date.today(), '%-m.%d.%Y')
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'generate':
            new_presentation_id, creators, round_titles, round_links = create_presentation()
            MergedPresentation.objects.create(
                name=presentation_name,
                presentation_id=new_presentation_id,
                creator_list=creators,
                round_names=round_titles,
            )
            print (new_presentation_id, creators, round_titles)
            presentation_url = f"https://docs.google.com/presentation/d/{new_presentation_id}/embed"

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
                new_round.score_alex = 0
                new_round.score_ichigo = 0
                new_round.score_megan = 0
                new_round.score_zach = 0
                new_round.score_jenny = 0
                new_round.score_debi = 0
                new_round.score_dan = 0
                new_round.score_chris = 0
                new_round.score_drew = 0
                new_round.replay = 0
                new_round.cooperative = 0
                new_round.link = round_links[round_index]
                new_round.save()

        elif action == 'update':
            updated_presentation_id, new_creators, round_titles, new_links = update_merged_presentation(latest_presentation.presentation_id,
                                                                               latest_presentation.creator_list)
            # update the MergedPresentation object that has the same presentation_id as the latest_presentation
            # by appending the new creators to the creator_list and appending the new round titles to the round_names

            latest_presentation = MergedPresentation.objects.get(presentation_id=latest_presentation.presentation_id)
            latest_presentation.round_names.extend(round_titles)
            latest_presentation.creator_list.extend(new_creators)
            latest_presentation.save()

            print(updated_presentation_id, new_creators, round_titles)

            latest_presentation.creator_list.extend(new_creators)
            latest_presentation.save()
            presentation_url = f"https://docs.google.com/presentation/d/{updated_presentation_id}/embed"

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
                new_round.score_alex = 0
                new_round.score_ichigo = 0
                new_round.score_megan = 0
                new_round.score_zach = 0
                new_round.score_jenny = 0
                new_round.score_debi = 0
                new_round.score_dan = 0
                new_round.score_chris = 0
                new_round.score_drew = 0
                new_round.replay = 0
                new_round.cooperative = 0
                new_round.link = new_links[round_index]
                new_round.save()

    return render(request, 'GPTrivia/home.html', {'presentation_url': presentation_url, 'pres_name': latest_presentation.name if latest_presentation else "None"})

@login_required
def scoresheet(request):
    players = ["Alex", "Ichigo", "Megan", "Zach", "Jenny", "Debi", "Dan", "Chris", "Drew"]
    # for the round titles, we will query the database for the MergePresentation object with the latest id
    # and get the round_names attribute
    try:
        latest_presentation = MergedPresentation.objects.latest('id')
    except MergedPresentation.DoesNotExist:
        latest_presentation = None
    if latest_presentation:
        round_titles = latest_presentation.round_names
        joker_round_indices = latest_presentation.joker_round_indices
        if joker_round_indices is None:
            # the joker round indices are a dictionary with the player name as the key and the index of the joker round as the value
            # if it is none, default to 0 for all players
            joker_round_indices = {player: 0 for player in players}

        creators = latest_presentation.creator_list
        # also get the presentation name
        presentation_name = latest_presentation.name

        pres_date = datetime.datetime.strptime(presentation_name, '%m.%d.%Y').date()
        existing_rounds = GPTriviaRound.objects.filter(date=pres_date, title__in=round_titles)

        # change the boolean values to strings
        for round in existing_rounds:
            # the boolean columns are replay and cooperative
            if round.replay:
                round.replay = "true"
            else:
                round.replay = "false"
            if round.cooperative:
                round.cooperative = "true"
            else:
                round.cooperative = "false"

        # Serialize the queryset into a JSON string and then parse it into a list of dictionaries
        existing_rounds_json = serializers.serialize('json', existing_rounds)
        existing_rounds_list = json.loads(existing_rounds_json)

        # Replace None values with null
        for round_dict in existing_rounds_list:
            for key, value in round_dict['fields'].items():
                if value is None:
                    round_dict['fields'][key] = "null"


        print(joker_round_indices)
        context = {
            'players': players,
            'round_titles': round_titles,
            'creators': creators,
            'player_color_mapping': playerColorMapping,
            'pres_name': presentation_name,
            'existing_rounds': existing_rounds_list,
            'joker_round_indices': joker_round_indices,
            'presentation_id': latest_presentation.presentation_id,
        }

    else:
        context = {
            'players': players,
            'round_titles': [],
            'creators': [],
            'player_color_mapping': playerColorMapping,
            'pres_name': "None",
            'existing_rounds': [],
            'joker_round_indices': 0,
            'presentation_id': "",
        }

    return render(request, 'GPTrivia/scoresheet.html', context)


@login_required
def scoresheet_new(request):
    return render(request, 'GPTrivia/scoresheet_new.html', {})

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

@api_view(['POST'])
def create_round(request, date, number):
    # Logic to create a new round
    print("here")
    new_round = GPTriviaRound.objects.create(date=date, round_number=number, title=f"Round {number}")  # Update with necessary fields
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
    # get the date of the round to delete
    thedate = round_to_delete.date
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
    return Response({'message': 'Round deleted successfully'})

@api_view(['POST'])
def save_scores(request):
    data = request.data
    rounds = data.get('rounds', [])
    joker_round_indices = data.get('joker_round_indices', {})
    presentation_id = data.get('presentation_id', None)
    round_names = data.get('round_names', [])
    creator_list = data.get('round_creators', [])

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
        except ObjectDoesNotExist:
            # If it does not exist, create a new instance
            trivia_round = GPTriviaRound()
        # Assign the round_data fields to the GPTriviaRound instance
        trivia_round.creator = creator
        trivia_round.title = title
        trivia_round.major_category = round_data.get('major_category')
        trivia_round.minor_category1 = round_data.get('minor_category1')
        trivia_round.minor_category2 = round_data.get('minor_category2')
        trivia_round.date = newdate
        trivia_round.round_number = round_data.get('round_number')
        trivia_round.max_score = round_data.get('max_score')
        trivia_round.score_alex = round_data.get('score_alex')
        trivia_round.score_ichigo = round_data.get('score_ichigo')
        trivia_round.score_megan = round_data.get('score_megan')
        trivia_round.score_zach = round_data.get('score_zach')
        trivia_round.score_jenny = round_data.get('score_jenny')
        trivia_round.score_debi = round_data.get('score_debi')
        trivia_round.score_dan = round_data.get('score_dan')
        trivia_round.score_chris = round_data.get('score_chris')
        trivia_round.score_drew = round_data.get('score_drew')
        trivia_round.replay = round_data.get('replay', False)
        trivia_round.cooperative = round_data.get('cooperative', False)

        # Save the instance to the database
        # first, log the trivia_round to the console
        try:
            print(trivia_round)
            trivia_round.save()
        except Exception as e:
            print(f"Error saving trivia_round: {e}")

    # Update the joker_round_indices in the MergedPresentation
    if presentation_id:
        try:
            presentation = MergedPresentation.objects.get(presentation_id=presentation_id)
            presentation.joker_round_indices = joker_round_indices
            presentation.creator_list = creator_list
            presentation.round_names = round_names
            presentation.save()
        except ObjectDoesNotExist:
            return JsonResponse({"message": "Presentation not found."}, status=400)
    elif date_str:
        try:
            presentation = MergedPresentation.objects.get(name=datetime.datetime.strptime(date_str, '%Y-%m-%d').date().strftime("%m.%d.%Y"))
            presentation.joker_round_indices = joker_round_indices
            presentation.creator_list = creator_list
            presentation.round_names = round_names
            presentation.save()
        except ObjectDoesNotExist:
            try:
                MergedPresentation.objects.create(
                    name=datetime.datetime.strptime(date_str, '%Y-%m-%d').date().strftime("%m.%d.%Y"),
                    presentation_id="",
                    creator_list=creator_list,
                    round_names=round_names,
                    joker_round_indices=joker_round_indices,
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
            )
        except Exception as e:
            print(f"Error creating MergedPresentation object: {e}")
            return JsonResponse({"message": "Error creating MergedPresentation object."}, status=400)


    return JsonResponse({"message": "Data saved successfully!"})