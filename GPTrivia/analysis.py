import numpy as np
import pandas as pd
from django.http import JsonResponse
from scipy.stats import pearsonr
from sklearn.decomposition import PCA

from GPTrivia.models import GPTriviaRound, MergedPresentation
from django.views import View
from .views import playerColorMapping
from django.db.models import Q



def calculate_pvalues(df):
    dfcols = pd.DataFrame(columns=df.columns)
    pvalues = dfcols.transpose().join(dfcols, how='outer')
    for r in df.columns:
        for c in df.columns:
            tmp = df[df[r].notnull() & df[c].notnull()]
            if len(tmp) < 2:
                pvalues[r][c] = 1
            else:
                pvalues[r][c] = round(pearsonr(tmp[r], tmp[c])[1], 4)
    return pvalues

class PlayerAnalysisPlot(View):

    def get(self, request):
        creator = request.GET.get('creator', '')
        category = request.GET.get('category', '')
        player = request.GET.get('player', '')
        misc = request.GET.get('misc', '')
        chart_type = request.GET.get('chart_type', '')
        dadj = request.GET.get('dadj', '')
        queryset_rounds_1 = GPTriviaRound.objects.all()
        # remove any rounds where all the scores are nan
        score_fields = [
            'score_alex', 'score_ichigo', 'score_megan', 'score_zach', 'score_jenny',
            'score_debi', 'score_dan', 'score_chris', 'score_drew', 'score_jeff',
            'score_dillon', 'score_paige', 'score_tom'
        ]
        score_filter = Q()
        for field in score_fields:
            score_filter |= ~Q(**{field: None})
        queryset_rounds = queryset_rounds_1.filter(score_filter)

        filtered_rounds = self.filter_data(queryset_rounds, creator, category, player, misc)
        # for each round, scale the scores to be out of 10 by dividing by the max score
        for round_data in filtered_rounds:
            max_score = round_data.max_score
            if max_score:  # Ensure max_score is not None or 0 to avoid division errors
                for field in score_fields:
                    score_value = getattr(round_data, field)
                    if score_value is not None:  # Ensure score_value is not None
                        adjusted_score = (score_value / max_score) * 10
                        setattr(round_data, field, adjusted_score)

        if chart_type == 'chart1':
            return self.get_chart1_data(filtered_rounds, queryset_rounds, creator, category, player, misc)
        if chart_type == 'bar':
            return self.get_bar_data(filtered_rounds, queryset_rounds, creator, category, player, misc)
        if chart_type == 'violin':
            return self.get_violin_data(filtered_rounds, queryset_rounds, creator, category, player, misc)
        if chart_type == 'pca':
            return self.get_pca_data(filtered_rounds, queryset_rounds, creator, category, player, misc)
        if chart_type == 'corr':
            return self.get_correlation_matrix(filtered_rounds, queryset_rounds, creator, category, player, misc)
        if chart_type == 'category_bar':
            return self.category_bar_chart(filtered_rounds, queryset_rounds, creator, category, player, misc)
        if chart_type == 'creator_bar':
            return self.category_bar_chart(filtered_rounds, queryset_rounds, creator, "None", player, misc)
        if chart_type == 'player_bar':
            return self.category_bar_chart(filtered_rounds, queryset_rounds, creator, category, player, misc)
        if chart_type == 'player_cat_bar':
            return self.category_bar_chart(filtered_rounds, queryset_rounds, creator, "None", player, misc)
        if chart_type == 'player_violin':
            return self.category_violin_chart(filtered_rounds, queryset_rounds, creator, category, player, misc)
        if chart_type == 'creator_violin':
            return self.category_violin_chart(filtered_rounds, queryset_rounds, creator, "None", player, misc)
        if chart_type == 'time_series_creator':
            return self.time_series_creator(filtered_rounds, queryset_rounds, creator, category, player, misc)
        if chart_type == 'rounds_table':
            return self.get_table_data(filtered_rounds, creator, category, player, misc)
        if chart_type == 'bias_chart':
            return self.get_bias_chart_data(filtered_rounds, queryset_rounds, creator, category, player, misc, dadj)
        if chart_type == 'trivia_night_streak':
            return self.trivia_night_streak(filtered_rounds, queryset_rounds_1, creator, category, player, misc)
        if chart_type == 'joker_percentage':
            return self.joker_percentage(filtered_rounds, queryset_rounds, creator, category, player, misc)
        else:
            return JsonResponse({'error': 'Invalid chart type'}, status=400)

    def filter_data(self, queryset, creator, category, player, misc):
        if creator:
            queryset = queryset.filter(creator=creator)
        if category:
            queryset = queryset.filter(major_category=category)
        # if player:
        #     queryset = queryset.filter(player=player)
        return queryset

    def get_table_data(self, rounds, creator, category, player, misc):
        score_columns = [col for col in rounds.values()[0].keys() if col.startswith('score_')]
        rounds_list = list(
            rounds.values('title', 'date', 'major_category', 'max_score', 'round_number', 'cooperative', 'link',
                          'creator', *score_columns))

        if player:
            player_column = f'score_{player.lower()}'
            if player_column not in score_columns:
                return JsonResponse({'error': f'Score column for player {player} not found'}, status=400)
            for round_data in rounds_list:
                round_data['player_score'] = round_data[player_column]
                # also include the mean score for the round, not including the player
                scores = [round_data[col] for col in score_columns if pd.notna(round_data[col]) and col != player_column]
                round_data['difficulty_score'] = sum(scores) / len(scores) if scores else None
        else:
            for round_data in rounds_list:
                scores = [round_data[col] for col in score_columns if pd.notna(round_data[col])]
                round_data['mean_score'] = sum(scores) / len(scores) if scores else None

        columns = ['title', 'date', 'major_category', 'max_score', 'round_number', 'cooperative', 'link', 'creator']
        if player:
            columns.append('player_score')
            columns.append('difficulty_score')
        else:
            columns.append('mean_score')

        # Remove score columns from rounds_list to avoid unnecessary data being passed
        for round_data in rounds_list:
            for col in score_columns:
                del round_data[col]

        # Convert rounds_list to a DataFrame for sorting
        df = pd.DataFrame(rounds_list)

        # Sort by date (descending) and then by round number (ascending)
        df = df.sort_values(by=['date', 'round_number'], ascending=[False, True])

        # Convert back to a list of dictionaries
        sorted_rounds_list = df.to_dict(orient='records')

        # delete any rounds where the player score is nan
        if player:
            sorted_rounds_list = [round_data for round_data in sorted_rounds_list if pd.notna(round_data['player_score'])]


        return JsonResponse({'columns': columns, 'rounds': sorted_rounds_list})

    def get_chart1_data(self, rounds, unfiltered_rounds, creator, category, player, misc):
        # Create a DataFrame from the queryset
        df = pd.DataFrame(list(rounds.values()))

        # Filter columns that start with "score_"
        score_columns = [col for col in df.columns if col.startswith('score_')]
        if not score_columns:
            return JsonResponse({'error': 'No score columns found'}, status=400)

        # Get all unique major categories
        major_categories = df['major_category'].unique()

        # Initialize a DataFrame to hold the average scores
        avg_scores_df = pd.DataFrame(columns=score_columns, index=major_categories)

        # Compute the average score for each major category
        for category in major_categories:
            filtered_df = df[df['major_category'] == category]
            avg_scores = filtered_df[score_columns].mean(skipna=True)
            avg_scores_df.loc[category] = avg_scores

        avg_scores_df = avg_scores_df.where(pd.notnull(avg_scores_df), None)

        # Compute the overall average score for each major category
        avg_scores_df['overall_average'] = avg_scores_df.mean(axis=1, skipna=True)

        # Sort categories by the overall average score
        avg_scores_df = avg_scores_df.sort_values(by='overall_average', ascending=False)

        # Prepare data for 3D surface plot
        x = score_columns
        y = avg_scores_df.index.tolist()
        z = avg_scores_df.drop(columns='overall_average').values.tolist()

        # Ensure the JSON response is properly formatted
        try:
            response_data = {
                'x': x,
                'y': y,
                'z': z
            }
            return JsonResponse(response_data)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def get_bar_data(self, rounds, unfiltered_rounds, creator, category, player, misc):
        df = pd.DataFrame(list(rounds.values()))
        score_columns = [col for col in df.columns if col.startswith('score_')]
        if not score_columns:
            return JsonResponse({'error': 'No score columns found'}, status=400)
        mean_scores = df[score_columns].mean(skipna=True)
        unfiltered_mean_scores = pd.DataFrame(list(unfiltered_rounds.values()))[score_columns].mean(skipna=True)
        players = [col.replace('score_', '') for col in score_columns]
        plot_values = mean_scores - unfiltered_mean_scores
        # turn the plot values into a list, and use the playernames as the x-axis
        plot_values = plot_values.tolist()

        colors = [playerColorMapping.get(player.capitalize(), '#333333') for player in players]
        # omit the player name that is equal to the creator
        plot_values = [plot_values[i] for i, player in enumerate(players) if player != creator.lower()]
        plot_values = [0 if np.isnan(value) else value for value in plot_values]

        colors = [color for i, color in enumerate(colors) if players[i] != creator.lower()]

        if creator.lower() in players:
            name = f'{creator.capitalize()}\'s'
        else:
            name = f'All'

        if category:
            cat = f' {category}'
        else:
            cat = ''

        players = [player for player in players if player != creator.lower()]
        # sort the scores in descending order, (and the players accordingly, and also the colors)
        plot_values, players, colors = zip(*sorted(zip(plot_values, players, colors), reverse=True))
        #replace all nan plot values with 0

        # capitolize the player names
        players = [player.capitalize() for player in players]
        try:
            response_data = {
                'players': players,
                'mean_values': plot_values,
                'colors': colors,
                'title': f'Mean Score Increase by Player on {name}{cat} Rounds',
                'xaxis': 'Player',
                'yaxis': 'Mean Score'
            }
            return JsonResponse(response_data)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def get_violin_data(self, rounds, unfiltered_rounds, creator, category, player, misc):
        df = pd.DataFrame(list(rounds.values()))
        unfiltered_df = pd.DataFrame(list(unfiltered_rounds.values()))
        score_columns = [col for col in df.columns if col.startswith('score_')]
        if not score_columns:
            return JsonResponse({'error': 'No score columns found'}, status=400)

        players = [col.replace('score_', '').capitalize() for col in score_columns]
        colors = [playerColorMapping.get(player.capitalize(), '#333333') for player in players]

        data = []

        for col, player, color in zip(score_columns, players, colors):
            if player.lower() != creator.lower():
                scores = df[col] - unfiltered_df[col].mean(skipna=True)
                # before we drop the scores, we need to drop the corresponding titles
                titles = df['title'].tolist()
                titles = [title for title, score in zip(titles, scores) if not np.isnan(score)]
                scores = scores.dropna().tolist()
                mean_score_diff = np.mean(scores)
                # titles = df['title'].tolist()
                hover_texts = [f"{title} - Score: {score:.2f}" for title, score in zip(titles, scores)]
                data.append({
                    'player': player,
                    'scores': scores,
                    'color': color,
                    'mean_score_diff': mean_score_diff,
                    'hover_texts': hover_texts
                })

        data = sorted(data, key=lambda x: x['mean_score_diff'], reverse=True)
        # Remove mean_score_diff from data before sending to frontend
        for d in data:
            d.pop('mean_score_diff')

        if creator in players:
            name = f'{creator.capitalize()}\'s'
        else:
            name = f'All'

        if category:
            cat = f' {category}'
        else:
            cat = ''

        try:
            response_data = {
                'data': data,
                'title': f"Score Difference by Player on {name}{cat} Rounds",
                'xaxis': 'Player',
                'yaxis': 'Score Difference'
            }
            return JsonResponse(response_data)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def get_pca_data(self, rounds, unfiltered_rounds, creator, category, player, misc):
        # Create a DataFrame from the queryset
        df = pd.DataFrame(list(rounds.values()))

        # Filter columns that start with "score_"
        score_columns = [col for col in df.columns if col.startswith('score_')]
        # remove the column that is equal to the creator
        score_columns = [col for col in score_columns if col != f'score_{creator.lower()}']
        if not score_columns:
            return JsonResponse({'error': 'No score columns found'}, status=400)

        score_data = df[score_columns]
        # score_data = score_data.fillna(score_data.mean())
        # don't fill in with the column mean, fill in with the row mean
        score_data = score_data.fillna(score_data.mean(axis=1))
        # also replace any Nones with the row mean
        score_data = score_data.where(pd.notnull(score_data), score_data.mean(axis=1), axis=0)

        # Perform PCA
        pca = PCA(n_components=3)
        principal_components = pca.fit_transform(score_data)
        loadings = pca.components_.T  # Transpose to align with original variables

        # Add PCA components to the dataframe
        df['PC1'] = principal_components[:, 0]
        df['PC2'] = principal_components[:, 1]
        df['PC3'] = principal_components[:, 2]

        # Determine the extreme values (e.g., top and bottom 5%)
        percentile_threshold = 1

        def get_extreme_titles(component):
            upper_threshold = np.percentile(df[component], 100 - percentile_threshold)
            lower_threshold = np.percentile(df[component], percentile_threshold)

            extreme_rows = df[(df[component] >= upper_threshold) | (df[component] <= lower_threshold)]
            return extreme_rows['title'].tolist()

        extreme_titles_pc1 = get_extreme_titles('PC1')
        extreme_titles_pc2 = get_extreme_titles('PC2')
        extreme_titles_pc3 = get_extreme_titles('PC3')

        players = [col.replace('score_', '').capitalize() for col in score_columns]
        if creator:
            name = f'{creator.capitalize()}\'s'
        else:
            name = f'All'

        if category:
            cat = f' {category}'
        else:
            cat = ''

        colors = [playerColorMapping.get(player.capitalize(), '#333333') for player in players]

        c = [col.replace('score_', '').capitalize() for col in score_columns]
        # Prepare the data for JSON response
        result = {
            'PC1': principal_components[:, 0].tolist(),
            'PC2': principal_components[:, 1].tolist(),
            'PC3': loadings[:, 2].tolist(),
            'loadings': {
                'PC1': loadings[:, 0].tolist(),
                'PC2': loadings[:, 1].tolist(),
                'PC3': loadings[:, 2].tolist(),
                'variables': c
            },
            'extreme_titles': {
                'PC1': extreme_titles_pc1,
                'PC2': extreme_titles_pc2,
                'PC3': extreme_titles_pc3
            },
            'title': f"PCA Similarity for {name}{cat} Rounds",
            'colors': colors,
        }

        return JsonResponse(result)

    def get_correlation_matrix(self, filtered_rounds, queryset_rounds, creator, category, player, misc):
        # Create a DataFrame from the queryset
        df = pd.DataFrame(list(filtered_rounds.values()))

        # Filter columns that start with "score_"
        score_columns = [col for col in df.columns if col.startswith('score_')]
        if not score_columns:
            return JsonResponse({'error': 'No score columns found'}, status=400)

        score_data = df[score_columns]
        # Fill NaN values with the mean of each column
        # score_data = score_data.fillna(score_data.mean())

        score_data = score_data - score_data.mean(skipna=True)

        # Subtract the mean of each row
        score_data = score_data.sub(score_data.mean(axis=1), axis=0)
        # score_data = score_data.where(pd.notnull(score_data), 0, axis=0)

        # Compute the correlation matrix
        corr_matrix = score_data.corr()
        p_values_matrix = pd.DataFrame(np.zeros_like(corr_matrix), columns=score_columns, index=score_columns)
        p_values_matrix = calculate_pvalues(score_data)
        # score_data = score_data.where(pd.notnull(score_data), 0, axis=0)
        # for i in range(len(score_columns)):
        #     for j in range(len(score_columns)):
        #         if i != j:
        #             corr, p_value = pearsonr(score_data.iloc[:, i], score_data.iloc[:, j])
        #             p_values_matrix.iloc[i, j] = p_value

        # Convert the correlation matrix and p-values matrix to JSON
        # replace any nans in the correlation matrix with 0
        corr_matrix = corr_matrix.where(pd.notnull(corr_matrix), 0)
        corr_matrix_json = corr_matrix.to_dict()
        p_values_matrix = p_values_matrix.where(pd.notnull(p_values_matrix), 1)
        p_values_matrix_json = p_values_matrix.to_dict()

        if creator:
            name = f'{creator.capitalize()}\'s'
        else:
            name = f'All'

        if category:
            cat = f' {category}'
        else:
            cat = ''

        c = [col.replace('score_', '').capitalize() for col in score_columns]


        return JsonResponse({
            'title_corr': f"Correlation Matrix for {name}{cat} Rounds",
            'title_p_values': f"P-Values Matrix for {name}{cat} Rounds",
            'correlation_matrix': corr_matrix_json,
            'p_values_matrix': p_values_matrix_json,
            'columns': c
        })

    def get_bias_chart_data(self, filtered_rounds, queryset_rounds, creator, category, player, misc, dadj):
        # Create a DataFrame from the queryset
        df = pd.DataFrame(list(filtered_rounds.values()))

        # Filter columns that start with "score_"
        score_columns = [col for col in df.columns if col.startswith('score_')]
        if not score_columns:
            return JsonResponse({'error': 'No score columns found'}, status=400)

        score_data = df[score_columns]
        # Fill NaN values with the mean of each column
        # score_data = score_data.fillna(score_data.mean())


        # Subtract the mean of each row
        if dadj == "true":
            score_data = score_data.sub(score_data.mean(axis=1), axis=0)
        # score_data = score_data.where(pd.notnull(score_data), 0, axis=0)
        score_data = score_data - score_data.mean(skipna=True)
        if dadj == "true":
            score_data = score_data.sub(score_data.mean(axis=1), axis=0)

        # add the creator column to the score data
        score_data['creator'] = df['creator']

        # Filter the rounds by the creator and compute the mean of each column for every creator
        creator_mean_scores = score_data.groupby('creator')[score_columns].mean()



        corr_matrix = creator_mean_scores.where(pd.notnull(creator_mean_scores), 0)
        # for the case where creator = player, we need to set the matrix elements to 0
        #remember, the player column is "score_player" where player is the player name,
        # but the creator column is "creator", so we CANNOT just do creator.lower() in score_columns,
        # we need to check if the creator column is in the score_columns



        for cr in creator_mean_scores.index:
            if "score_" + cr.lower() in score_columns:
                corr_matrix.loc[cr, "score_" + cr.lower()] = 0

        # shift the columns to have mean 0
        corr_matrix = corr_matrix - corr_matrix.mean(skipna=True)

        for cr in creator_mean_scores.index:
            if "score_" + cr.lower() in score_columns:
                corr_matrix.loc[cr, "score_" + cr.lower()] = 0

        # adjust the nonzero values so that the rows are centered around 0



        corr_matrix_json = corr_matrix.to_dict()

        if creator:
            name = f'{creator.capitalize()}\'s'
        else:
            name = f'All'

        if category:
            cat = f' {category}'
        else:
            cat = ''

        c = [col.replace('score_', '').capitalize() for col in score_columns]



        return JsonResponse({
            'title_corr': f"Bias Chart for {name}{cat} Rounds",
            'correlation_matrix': corr_matrix_json,
            'columns': c
        })

    def category_bar_chart(self, rounds, unfiltered_rounds, creator, category, player, misc):
        df = pd.DataFrame(list(rounds.values()))
        score_columns = [col for col in df.columns if col.startswith('score_')]
        if not score_columns:
            return JsonResponse({'error': 'No score columns found'}, status=400)
        # filter the dataframe for each unique major category and compute the mean scores
        if player:
            player_column = f'score_{player.lower()}'
            if player_column not in df.columns:
                return JsonResponse({'error': f'Score column for player {player} not found'}, status=400)
            if category == "":
                # If player is defined, use only the corresponding score column
                mean_scores = df.groupby('major_category')[player_column].mean()
                # subtract the mean score of the player from the mean score of the category
                mean_scores = mean_scores - df[player_column].mean()
                cat_name = "Category"
            elif creator == "":
                mean_scores = df.groupby('creator')[f'score_{player.lower()}'].mean()
                # subtract the mean score of the player from the mean score of the category
                mean_scores = mean_scores - df[player_column].mean()
                cat_name = "Creator"
        else:
            if category == "":
                mean_scores = df.groupby('major_category')[score_columns].mean().mean(axis=1)
                cat_name = "Category"
                # and the list of all unique major categories
            elif creator == "":
                mean_scores = df.groupby('creator')[score_columns].mean().mean(axis=1)
                cat_name = "Creator"
        if player and category and creator == "":
            # remove the key corresponding to the player from the mean_scores dictionary
            mean_scores = mean_scores.drop(player)
        categories = mean_scores.index.tolist()



        # unfiltered_mean_scores = pd.DataFrame(list(unfiltered_rounds.values()))[score_columns].mean(skipna=True)
        players = [col.replace('score_', '') for col in score_columns]
        # plot_values = mean_scores - unfiltered_mean_scores
        # turn the plot values into a list, and use the playernames as the x-axis
        plot_values = mean_scores.tolist()

        # colors = [playerColorMapping.get(player.capitalize(), '#333333') for player in players]
        # omit the player name that is equal to the creator
        plot_values = [0 if np.isnan(value) else value for value in plot_values]

        # colors = [color for i, color in enumerate(colors) if players[i] != creator.lower()]

        if creator.lower() in players:
            name = f'{creator.capitalize()}\'s'
        else:
            name = f'All'

        x = df.groupby('major_category')[score_columns].mean().mean(axis=1)
        y = mean_scores.index.tolist()
        if category in y:
            cat = f' {category}'
        else:
            cat = ''

        players = [player for player in players if player != creator.lower()]
        # sort the scores in descending order, (and the players accordingly, and also the colors)
        plot_values, categories = zip(*sorted(zip(plot_values, categories), reverse=True))
        #replace all nan plot values with 0

        # capitalize the player names
        players = [player.capitalize() for player in players]
        colors = [playerColorMapping.get(player.capitalize(), '#FFFFFF') for player in categories]

        try:
            response_data = {
                'categories': categories,
                'mean_values': plot_values,
                'colors': colors,
                'title': f'Mean Score on {name}{cat} Rounds by {cat_name}',
                'xaxis': cat_name,
                'yaxis': 'Mean Score'
            }
            return JsonResponse(response_data)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def category_violin_chart(self, rounds, unfiltered_rounds, creator, category, player, misc):
        df = pd.DataFrame(list(rounds.values()))
        score_columns = [col for col in df.columns if col.startswith('score_')]
        if not score_columns:
            return JsonResponse({'error': 'No score columns found'}, status=400)

        # Ensure player column is available if specified
        if player:
            player_column = f'score_{player.lower()}'
            if player_column not in df.columns:
                return JsonResponse({'error': f'Score column for player {player} not found'}, status=400)

        # Prepare data for violin plot
        if player:
            player_column = f'score_{player.lower()}'
            if category == "":

                data = df.groupby('major_category')[player_column].apply(list).reset_index(name='scores')
                # add the titles column to the data
                data['titles'] = df.groupby('major_category')['title'].apply(list).reset_index(name='titles')['titles']
                cat_name = "Category"
            elif creator == "":
                data = df.groupby('creator')[player_column].apply(list).reset_index(name='scores')
                # add the titles column to the data
                data['titles'] = df.groupby('creator')['title'].apply(list).reset_index(name='titles')['titles']
                cat_name = "Creator"
        else:
            if category == "":
                data = df.groupby('major_category')[score_columns].apply(
                    lambda x: x.values.flatten().tolist()).reset_index(name='scores')
                # add the titles column to the data
                data['titles'] = df.groupby('major_category')['title'].apply(list).reset_index(name='titles')['titles']
                cat_name = "Category"
            elif creator == "":
                data = df.groupby('creator')[score_columns].apply(lambda x: x.values.flatten().tolist()).reset_index(
                    name='scores')
                # add the titles column to the data
                data['titles'] = df.groupby('creator')['title'].apply(list).reset_index(name='titles')['titles']
                cat_name = "Creator"

        # let's also add the title of the round to the data
        # data['titles'] = df.groupby('major_category')['title'].apply(list).reset_index(name='titles')['titles']

        # Filter out categories without data
        # first filter out the titles if the corresponding scores are nan
        data['titles'] = data.apply(lambda row: [title for score, title in zip(row['scores'], row['titles']) if pd.notna(score)], axis=1)
        data['scores'] = data.apply(lambda row: [score for score, title in zip(row['scores'], row['titles']) if pd.notna(score)], axis=1)
        data = data[data['scores'].apply(lambda x: len(x) > 0)]


        # Calculate means for sorting
        data['mean'] = data['scores'].apply(lambda x: sum(x) / len(x) if len(x) > 0 else 0)
        data = data.sort_values(by='mean', ascending=False)

        # subtract the mean of the player from the data
        if player and category == "" and creator == "":
            data['scores'] = data['scores'].apply(lambda x: [score - df[player_column].mean() for score in x])
        elif player and category and creator == "":
            data['scores'] = data['scores'].apply(lambda x: [score - df[player_column].mean() for score in x])
        elif player and category == "" and creator:
            data['scores'] = data['scores'].apply(lambda x: [score - df[player_column].mean() for score in x])

        # if the player is specified, remove the player from the data
        if player and category and creator == "":
            data = data[data['creator'] != player]

        #now set the hover text for each data point to be the title of the round
        data['hover_text'] = data.apply(lambda row: [f'{title} ({score:.2f})' for title, score in zip(row['titles'], row['scores'])], axis=1)

        # Prepare data for plotting
        categories = data.iloc[:, 0].tolist()
        plot_data = data.iloc[:, 1].tolist()
        hover_texts = data['hover_text'].tolist()

        colors = [playerColorMapping.get(player.capitalize(), '#FFFFFF') for player in categories]

        try:
            response_data = {
                'categories': categories,
                'plot_data': plot_data,
                'hover_texts': hover_texts,
                'colors': colors,
                'title': f'Distribution of Scores by {cat_name}',
                'xaxis': cat_name,
                'yaxis': 'Scores'
            }
            return JsonResponse(response_data)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def time_series_creator(self, rounds, unfiltered_rounds, creator, category, player, misc):
        df = pd.DataFrame(list(rounds.values()))

        if creator:
            name = f'{creator.capitalize()}\'s'
        else:
            name = f'All'

        if category:
            cat = f' {category}'
        else:
            cat = ''

        if player:
            player_column = f'score_{player.lower()}'
            if player_column not in df.columns:
                return JsonResponse({'error': f'Score column for player {player} not found'}, status=400)

            # Filter the DataFrame to include only the relevant player's score column and date
            score_columns = [col for col in df.columns if col.startswith('score_') and col != player_column]
            player_data = df[['date', 'title', player_column, 'max_score', 'cooperative', 'creator'] + score_columns]
            player_data = player_data.dropna(subset=[player_column])
            # also drop any rows whose value in the cooperative column is True
            player_data = player_data[player_data['cooperative'] == False]
            player_data['date'] = pd.to_datetime(player_data['date'])
            player_data = player_data.sort_values(by='date')

            player_data['scaled_score'] = (player_data[player_column] / player_data['max_score']) * 10

            # scale the score columns by the max score as well
            # for col in score_columns:
                # player_data[col] = (player_data[col] / player_data['max_score']) * 10

            player_data['mean_score'] = player_data[score_columns].mean(axis=1)
            player_data['adjusted_score'] = player_data['scaled_score'] - player_data['mean_score']

            player_mean2 = player_data['adjusted_score'].mean()
            player_data['final_score'] = player_data['adjusted_score']
            # Compute the moving average of the most recent 10 scores
            # if category == "" and creator == "":
            #     span = 36
            #     player_data['moving_average'] = player_data['final_score'].rolling(window=span).mean()
            # else:
            #     span = 5
            #     player_data['moving_average'] = player_data['final_score'].rolling(window=span).mean()

            if category == "" and creator == "":
                span = 12
            else:
                span = 2

            player_data['moving_average'] = player_data['final_score'].ewm(halflife=span, adjust=False).mean()

            # Extract the dates and moving average scores for plotting

            player_mean = player_data['moving_average'].mean()
            player_data['moving_average'] = player_data['moving_average'] - player_mean

            player_data['adjusted_final_score'] = player_data['final_score'] - player_mean2

            # set the first span-1 values of adjusted_final_score to 0
            if category == "" and creator == "":
                player_data['moving_average'].iloc[:span*3 - 1] = 0
            else:
                player_data['moving_average'].iloc[:span * 2 - 1] = 0

            plot_values = player_data[['date', 'moving_average', 'title', 'adjusted_final_score', 'creator']].dropna()


            try:
                response_data = {
                    'dates': plot_values['date'].dt.strftime('%Y-%m-%d').tolist(),
                    'mean_values': plot_values['moving_average'].tolist(),
                    'titles': plot_values['title'].tolist(),
                    'creators': plot_values['creator'].tolist(),
                    'adjusted_scores': plot_values['adjusted_final_score'].tolist(),
                    'colors': playerColorMapping.get(player.capitalize(), '#FFFFFF'),
                    'title': f'Performance ({span}-Round Halflife EWMA) on {name}{cat} Rounds',
                    'xaxis': "Week",
                    'yaxis': 'Mean Score Adjustment'
                }
                return JsonResponse(response_data)
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=500)
        else:
            return JsonResponse({'error': 'Player not specified'}, status=400)

    def trivia_night_streak(self, rounds, unfiltered_rounds, creator, category, player, misc):
        # Create a DataFrame from the queryset
        df = pd.DataFrame(list(unfiltered_rounds.values()))

        if df.empty:
            return JsonResponse({'error': 'No rounds found'}, status=400)

        # Filter columns
        score_columns = [col for col in df.columns if col.startswith('score_')]

        # Sort DataFrame by date
        df = df.sort_values(by='date')

        # Calculate the streak
        df['date'] = pd.to_datetime(df['date'])
        df = df.drop_duplicates(subset='date')  # Ensure unique dates

        streaks = []
        current_streak = 0
        last_date = None

        for date in df['date']:
            if last_date is None or (date - last_date).days <= 7:
                current_streak += 1
            else:
                current_streak = 1
            streaks.append(current_streak)
            last_date = date

        df['streak'] = streaks

        # Prepare data for plot
        plot_data = {
            'dates': df['date'].dt.strftime('%Y-%m-%d').tolist(),
            'streaks': df['streak'].tolist(),
            'title': 'Trivia Night Streak'
        }

        return JsonResponse(plot_data)

    def joker_percentage(self, rounds, unfiltered_rounds, creator, category, player, misc):
        merged_presentations = MergedPresentation.objects.all()
        trivia_rounds = GPTriviaRound.objects.all()

        # Parse dates from MergedPresentation
        merged_data = []
        for mp in merged_presentations:
            date = pd.to_datetime(mp.name, format='%m.%d.%Y')
            merged_data.append({
                'date': date,
                'joker_round_indices': mp.joker_round_indices,
                'round_names': mp.round_names,
                'creator_list': mp.creator_list
            })

        # Prepare the dataframe for analysis
        merged_df = pd.DataFrame(merged_data)
        rounds_df = pd.DataFrame(list(trivia_rounds.values()))

        # Convert the 'date' column to datetime
        rounds_df['date'] = pd.to_datetime(rounds_df['date'])

        # Initialize the result dictionary
        result = {}

        # Iterate over each trivia night in the merged presentations
        for index, row in merged_df.iterrows():
            date = row['date']
            joker_indices = row['joker_round_indices']
            round_names = row['round_names']
            creators = row['creator_list']

            # Filter rounds that match the current date
            rounds_on_date = rounds_df[rounds_df['date'] == date]

            if rounds_on_date.empty:
                continue

            # Initialize the dictionary for the current date
            result[str(date.date())] = {}

            # Iterate over each player's jokered round
            for player, joker_round_name in joker_indices.items():
                player_column = f'score_{player.lower()}'

                if player_column not in rounds_on_date.columns:
                    continue

                # for debugging, print rounds_on_date, rounds_on_date['title'], joker_round_name, player_column
                print(rounds_on_date)
                print(rounds_on_date['title'])
                print(joker_round_name)
                print(player_column)

                d = rounds_on_date[rounds_on_date['title'] == joker_round_name]

                if d.empty:
                    continue
                joker_round_score = \
                    d[player_column].values[0]

                other_scores = rounds_on_date[rounds_on_date['title'] != joker_round_name][
                    player_column].dropna().values

                highest_other_score = max(other_scores) if len(other_scores) > 0 else 0

                # Determine if the joker round is the highest scoring round
                result[str(date.date())][player.capitalize()] = joker_round_score >= highest_other_score

        # Convert the result dictionary to a DataFrame for easier handling in the frontend
        result_df = pd.DataFrame(result).T

        # Calculate the fraction for each player
        fractions = {}
        for player in result_df.columns:
            player_data = result_df[player]
            num_true = player_data.sum()
            num_total = player_data.count()
            fractions[player] = num_true / num_total if num_total > 0 else None

        return JsonResponse(fractions)