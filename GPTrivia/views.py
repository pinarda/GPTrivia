from django.shortcuts import render, redirect
from .forms import GPTriviaRoundForm
from .models import GPTriviaRound
from django.db.models import Avg, F, FloatField, Case, When, Sum, Count
import numpy as np

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
            'Chris': '#50C878',
            'Drew': '#8c564b'
        };

players = [
    'score_alex', 'score_ichigo', 'score_megan', 'score_zach', 'score_jenny', 'score_debi',
    'score_dan', 'score_chris', 'score_drew']

def home(request):
    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'gptrivia_round_form':
            gptrivia_round_form = GPTriviaRoundForm(request.POST)
            if gptrivia_round_form.is_valid():
                gptrivia_round_form.save()
                return redirect('home')

    else:
        gptrivia_round_form = GPTriviaRoundForm()

    context = {
        'gptrivia_round_form': gptrivia_round_form,
    }


    return render(request, 'GPTrivia/home.html', context)

def rounds_list(request):
    rounds = GPTriviaRound.objects.all()
    context = {'rounds': rounds,
               'playerColorMapping': playerColorMapping,}

    return render(request, 'GPTrivia/rounds_list.html', context)

def player_analysis(request):
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



    return render(request, 'GPTrivia/player_analysis.html', {
        'player_averages': player_averages,
        'player_cat_averages': player_cat_averages,
        'creators': creators,
        'categories': categories,
        'player_scores': player_scores,
        'player_cat_scores': player_cat_scores,
        'player_color_mapping': playerColorMapping,
    })

def player_profile(request, player_name):
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
    if brightness < 450:
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
        cat_avg['avg_score'] = cat_avg['avg_score'] - player_avg

    # sort the category averages by the average score
    category_averages = sorted(category_averages, key=lambda k: k['avg_score'], reverse=True)


    # save category of the round with the highest and lowest average score for the player
    max_avg = category_averages[0]['major_category']
    min_avg = category_averages[len(category_averages) - 1]['major_category']

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
    max_creator_avg = creator_averages[0]['creator']
    min_creator_avg = creator_averages[len(creator_averages) - 1]['creator']
    if max_creator_avg == player_name:
        max_creator_avg = creator_averages[1]['creator']
    if min_creator_avg == player_name:
        min_creator_avg = creator_averages[len(creator_averages) - 2]['creator']
    # if the max_creator_avg or min_creator_avg is an empty string
    # choose the next highest or lowest average score
    if max_creator_avg == "":
        max_creator_avg = creator_averages[2]['creator']
    if min_creator_avg == "":
        min_creator_avg = creator_averages[len(creator_averages) - 3]['creator']


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
    }

    return render(request, 'GPTrivia/player_profile.html', context)