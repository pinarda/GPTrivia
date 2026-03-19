import datetime
import json

import numpy as np
import pandas as pd
from django.http import JsonResponse
from scipy.stats import pearsonr
from sklearn.decomposition import PCA

from GPTrivia.models import GPTriviaRound, MergedPresentation
from django.views import View
from django.db.models import Q
from .player_scores import (
    MIN_ANALYSIS_ROUNDS,
    display_name_for_player_field,
    flatten_round_for_analysis,
    get_category_color,
    get_eligible_player_fields,
    get_round_score_map,
    get_player_color,
    player_field_for_name,
)



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


def _analysis_current_trivia_date():
    return datetime.date.today()


def _format_score_value(value):
    if value is None or pd.isna(value):
        return ''
    numeric_value = float(value)
    if numeric_value.is_integer():
        return str(int(numeric_value))
    return f'{numeric_value:g}'

class PlayerAnalysisPlot(View):
    @staticmethod
    def _parse_misc_flags(misc):
        if misc is None:
            return set()
        if isinstance(misc, (list, tuple, set)):
            values = misc
        else:
            values = str(misc).split(',')
        normalized = set()
        for value in values:
            cleaned = str(value or '').strip().lower()
            if cleaned:
                normalized.add(cleaned)
        return normalized

    @staticmethod
    def _should_include_coop(misc):
        normalized_misc = PlayerAnalysisPlot._parse_misc_flags(misc)
        return bool(normalized_misc & {'1', 'true', 'yes', 'on', 'include_coop'})

    @staticmethod
    def _should_include_inactive(misc):
        normalized_misc = PlayerAnalysisPlot._parse_misc_flags(misc)
        return bool(normalized_misc & {'include_inactive', 'show_inactive'})

    def _apply_misc_filters(self, queryset, misc):
        if not self._should_include_coop(misc):
            queryset = queryset.exclude(cooperative=True)
        return queryset

    @staticmethod
    def _recenter_correlation_matrix(corr_matrix):
        if corr_matrix.empty:
            return corr_matrix

        recentered = corr_matrix.copy()
        mask = ~np.eye(len(recentered), dtype=bool)
        off_diagonal_values = recentered.where(mask).stack(dropna=True)
        if not off_diagonal_values.empty:
            off_diagonal_mean = off_diagonal_values.mean()
            recentered = recentered.where(~mask, recentered - off_diagonal_mean)
        np.fill_diagonal(recentered.values, 1.0)
        return recentered

    @staticmethod
    def _queryset_to_records(queryset):
        return [flatten_round_for_analysis(round_obj) for round_obj in queryset]

    @staticmethod
    def _records_with_scores(records):
        scored_records = []
        for record in records:
            if any(
                value is not None
                for key, value in record.items()
                if str(key).startswith('score_')
            ):
                scored_records.append(record)
        return scored_records

    @staticmethod
    def _records_to_df(records):
        if not records:
            return pd.DataFrame()
        return pd.DataFrame(records)

    def _score_columns(self, df):
        eligible_player_fields = getattr(self, 'eligible_player_fields', set())
        return [
            col for col in df.columns
            if str(col).startswith('score_') and (not eligible_player_fields or col in eligible_player_fields)
        ]

    @staticmethod
    def _recently_active_player_fields(rounds):
        cutoff_date = _analysis_current_trivia_date() - datetime.timedelta(days=365)
        active_fields = set()

        for round_obj in rounds or []:
            round_date = getattr(round_obj, 'date', None)
            if not round_date or round_date < cutoff_date:
                continue

            for player_field, score_value in get_round_score_map(round_obj, include_null_fixed=False).items():
                if isinstance(score_value, (int, float)):
                    active_fields.add(player_field)

        return active_fields

    def get(self, request):
        creator = request.GET.get('creator', '')
        category = request.GET.get('category', '')
        player = request.GET.get('player', '')
        misc = request.GET.get('misc', '') or request.GET.get('include_coop', '')
        chart_type = request.GET.get('chart_type', '')
        dadj = request.GET.get('dadj', '')
        queryset_rounds_1 = self._apply_misc_filters(GPTriviaRound.objects.all(), misc)
        all_round_objects = list(queryset_rounds_1)
        recently_active_fields = self._recently_active_player_fields(all_round_objects)
        self.recently_active_player_fields = set(recently_active_fields)
        self.recently_active_player_names = {
            display_name_for_player_field(player_field)
            for player_field in self.recently_active_player_fields
        }
        self.global_eligible_player_fields = set(
            get_eligible_player_fields(all_round_objects, min_rounds=MIN_ANALYSIS_ROUNDS)
        )
        if self._should_include_inactive(misc):
            self.eligible_player_fields = set(self.global_eligible_player_fields)
        else:
            self.eligible_player_fields = set(self.global_eligible_player_fields) & recently_active_fields

        selected_player_field = player_field_for_name(player) if player else ''
        if selected_player_field and selected_player_field in self.global_eligible_player_fields:
            self.eligible_player_fields.add(selected_player_field)

        if player and selected_player_field not in self.global_eligible_player_fields:
            return JsonResponse(
                {'error': f'Player {player} has not played enough rounds for analysis'},
                status=400,
            )
        queryset_rounds = self.filter_data(queryset_rounds_1, creator, category, player, misc)
        filtered_rounds = self._records_with_scores(self._queryset_to_records(queryset_rounds))
        all_rounds = self._records_with_scores(self._queryset_to_records(queryset_rounds_1))

        if chart_type == 'chart1':
            return self.get_chart1_data(filtered_rounds, all_rounds, creator, category, player, misc)
        if chart_type == 'bar':
            return self.get_bar_data(filtered_rounds, all_rounds, creator, category, player, misc)
        if chart_type == 'violin':
            return self.get_violin_data(filtered_rounds, all_rounds, creator, category, player, misc)
        if chart_type == 'pca':
            return self.get_pca_data(filtered_rounds, all_rounds, creator, category, player, misc)
        if chart_type == 'corr':
            return self.get_correlation_matrix(filtered_rounds, all_rounds, creator, category, player, misc)
        if chart_type == 'category_bar':
            return self.category_bar_chart(filtered_rounds, all_rounds, creator, category, player, misc)
        if chart_type == 'creator_bar':
            return self.category_bar_chart(filtered_rounds, all_rounds, creator, "None", player, misc)
        if chart_type == 'player_bar':
            return self.category_bar_chart(filtered_rounds, all_rounds, creator, category, player, misc)
        if chart_type == 'player_cat_bar':
            return self.category_bar_chart(filtered_rounds, all_rounds, creator, "None", player, misc)
        if chart_type == 'category_violin_summary':
            return self.category_violin_chart(filtered_rounds, all_rounds, creator, category, "", misc)
        if chart_type == 'creator_violin_summary':
            return self.category_violin_chart(filtered_rounds, all_rounds, creator, "None", "", misc)
        if chart_type == 'player_violin':
            return self.category_violin_chart(filtered_rounds, all_rounds, creator, category, player, misc)
        if chart_type == 'creator_violin':
            return self.category_violin_chart(filtered_rounds, all_rounds, creator, "None", player, misc)
        if chart_type == 'time_series_creator':
            return self.time_series_creator(filtered_rounds, all_rounds, creator, category, player, misc)
        if chart_type == 'rounds_table':
            return self.get_table_data(filtered_rounds, creator, category, player, misc)
        if chart_type == 'bias_chart':
            return self.get_bias_chart_data(filtered_rounds, all_rounds, creator, category, player, misc, dadj)
        if chart_type == 'trivia_night_streak':
            return self.trivia_night_streak(filtered_rounds, self._queryset_to_records(queryset_rounds_1), creator, category, player, misc)
        if chart_type == 'joker_percentage':
            return self.joker_percentage(filtered_rounds, all_rounds, creator, category, player, misc)
        if chart_type == 'joker_creator_summary':
            return self.joker_selection_summary(player, group_by='creator', creator=creator, category=category, misc=misc)
        if chart_type == 'joker_category_summary':
            return self.joker_selection_summary(player, group_by='category', creator=creator, category=category, misc=misc)
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
        if not rounds:
            return JsonResponse({'columns': [], 'rounds': []})

        df = self._records_to_df(rounds)
        score_columns = self._score_columns(df)
        rounds_list = df[['title', 'date', 'major_category', 'max_score', 'round_number', 'cooperative', 'link',
                          'creator', *score_columns]].to_dict(orient='records')

        if player:
            player_column = player_field_for_name(player)
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
        df = self._records_to_df(rounds)

        # Filter columns that start with "score_"
        score_columns = self._score_columns(df)
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
        df = self._records_to_df(rounds)
        unfiltered_df = self._records_to_df(unfiltered_rounds)
        score_columns = self._score_columns(df)
        if not score_columns:
            return JsonResponse({'error': 'No score columns found'}, status=400)
        mean_scores = df[score_columns].mean(skipna=True)
        unfiltered_mean_scores = unfiltered_df[score_columns].mean(skipna=True)
        players = [display_name_for_player_field(col) for col in score_columns]
        plot_values = mean_scores - unfiltered_mean_scores
        # turn the plot values into a list, and use the playernames as the x-axis
        plot_values = plot_values.tolist()

        colors = [get_player_color(player) for player in players]
        # omit the player name that is equal to the creator
        plot_values = [plot_values[i] for i, player_name in enumerate(players) if player_name.lower() != creator.lower()]
        plot_values = [0 if np.isnan(value) else value for value in plot_values]

        colors = [color for i, color in enumerate(colors) if players[i].lower() != creator.lower()]

        if creator and any(player_name.lower() == creator.lower() for player_name in players):
            name = f'{creator.capitalize()}\'s'
        else:
            name = f'All'

        if category:
            cat = f' {category}'
        else:
            cat = ''

        players = [player_name for player_name in players if player_name.lower() != creator.lower()]
        # sort the scores in descending order, (and the players accordingly, and also the colors)
        plot_values, players, colors = zip(*sorted(zip(plot_values, players, colors), reverse=True))
        #replace all nan plot values with 0

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
        df = self._records_to_df(rounds)
        unfiltered_df = self._records_to_df(unfiltered_rounds)
        score_columns = self._score_columns(df)
        if not score_columns:
            return JsonResponse({'error': 'No score columns found'}, status=400)

        players = [display_name_for_player_field(col) for col in score_columns]
        colors = [get_player_color(player_name) for player_name in players]
        max_scores = df['max_score'].replace(0, np.nan)
        unfiltered_max_scores = unfiltered_df['max_score'].replace(0, np.nan)

        data = []

        for col, player, color in zip(score_columns, players, colors):
            if player.lower() != creator.lower():
                normalized_scores = (df[col] / max_scores) * 10
                normalized_baseline = (unfiltered_df[col] / unfiltered_max_scores) * 10
                adjusted_scores = normalized_scores - normalized_baseline.mean(skipna=True)
                plot_scores = []
                hover_texts = []

                for row_index, adjusted_score in adjusted_scores.items():
                    if np.isnan(adjusted_score):
                        continue
                    raw_score = df.at[row_index, col]
                    max_score = df.at[row_index, 'max_score']
                    percent_score = normalized_scores.loc[row_index]
                    title = df.at[row_index, 'title']
                    plot_scores.append(adjusted_score)
                    hover_texts.append(
                        f"{title}<br>"
                        f"Raw score: {_format_score_value(raw_score)}/{_format_score_value(max_score)} "
                        f"({percent_score:.2f}/10)<br>"
                        f"Difference vs typical score: {adjusted_score:+.2f} points"
                    )

                mean_score_diff = np.mean(plot_scores) if plot_scores else 0
                data.append({
                    'player': player,
                    'scores': plot_scores,
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
                'title': f"Score Above or Below Each Player's Typical Score on {name}{cat} Rounds",
                'xaxis': 'Player',
                'yaxis': 'Points vs Typical Score'
            }
            return JsonResponse(response_data)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def get_pca_data(self, rounds, unfiltered_rounds, creator, category, player, misc):
        # Create a DataFrame from the queryset
        df = self._records_to_df(rounds)

        # Filter columns that start with "score_"
        score_columns = self._score_columns(df)
        # remove the column that is equal to the creator
        creator_field = player_field_for_name(creator) if creator else ''
        score_columns = [col for col in score_columns if col != creator_field]
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

        players = [display_name_for_player_field(col) for col in score_columns]
        if creator:
            name = f'{creator.capitalize()}\'s'
        else:
            name = f'All'

        if category:
            cat = f' {category}'
        else:
            cat = ''

        colors = [get_player_color(player_name) for player_name in players]

        c = [display_name_for_player_field(col) for col in score_columns]
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
        df = self._records_to_df(filtered_rounds)

        # Filter columns that start with "score_"
        score_columns = self._score_columns(df)
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
        corr_matrix = self._recenter_correlation_matrix(corr_matrix)
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

        c = [display_name_for_player_field(col) for col in score_columns]


        return JsonResponse({
            'title_corr': f"Correlation Matrix for {name}{cat} Rounds",
            'title_p_values': f"P-Values Matrix for {name}{cat} Rounds",
            'correlation_matrix': corr_matrix_json,
            'p_values_matrix': p_values_matrix_json,
            'columns': c
        })

    def get_bias_chart_data(self, filtered_rounds, queryset_rounds, creator, category, player, misc, dadj):
        # Create a DataFrame from the queryset
        df = self._records_to_df(filtered_rounds)

        # Filter columns that start with "score_"
        score_columns = self._score_columns(df)
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

        c = [display_name_for_player_field(col) for col in score_columns]



        return JsonResponse({
            'title_corr': f"Creator Favoritism Chart for {name}{cat} Rounds",
            'correlation_matrix': corr_matrix_json,
            'columns': c
        })

    def category_bar_chart(self, rounds, unfiltered_rounds, creator, category, player, misc):
        df = self._records_to_df(rounds)
        score_columns = self._score_columns(df)
        if not score_columns:
            return JsonResponse({'error': 'No score columns found'}, status=400)
        max_scores = df['max_score'].replace(0, np.nan)
        # filter the dataframe for each unique major category and compute the mean scores
        if player:
            player_column = player_field_for_name(player)
            if player_column not in df.columns:
                return JsonResponse({'error': f'Score column for player {player} not found'}, status=400)
            if category == "":
                # If player is defined, use only the corresponding score column
                mean_scores = df.groupby('major_category')[player_column].mean()
                # subtract the mean score of the player from the mean score of the category
                mean_scores = mean_scores - df[player_column].mean()
                cat_name = "Category"
            elif creator == "":
                mean_scores = df.groupby('creator')[player_column].mean()
                # subtract the mean score of the player from the mean score of the category
                mean_scores = mean_scores - df[player_column].mean()
                cat_name = "Creator"
            title_prefix = 'Mean Score'
            yaxis_title = 'Mean Score'
        else:
            normalized_scores = df[score_columns].div(max_scores, axis=0) * 10
            if category == "":
                mean_scores = normalized_scores.groupby(df['major_category']).mean().mean(axis=1)
                cat_name = "Category"
                # and the list of all unique major categories
            elif creator == "":
                mean_scores = normalized_scores.groupby(df['creator']).mean().mean(axis=1)
                cat_name = "Creator"
            title_prefix = 'Mean Normalized Score'
            yaxis_title = 'Mean Normalized Score (0-10)'
        if player and category and creator == "":
            # remove the key corresponding to the player from the mean_scores dictionary
            mean_scores = mean_scores.drop(player)
        categories = mean_scores.index.tolist()



        # unfiltered_mean_scores = pd.DataFrame(list(unfiltered_rounds.values()))[score_columns].mean(skipna=True)
        players = [display_name_for_player_field(col) for col in score_columns]
        # plot_values = mean_scores - unfiltered_mean_scores
        # turn the plot values into a list, and use the playernames as the x-axis
        plot_values = mean_scores.tolist()

        # colors = [playerColorMapping.get(player.capitalize(), '#333333') for player in players]
        # omit the player name that is equal to the creator
        plot_values = [0 if np.isnan(value) else value for value in plot_values]

        # colors = [color for i, color in enumerate(colors) if players[i] != creator.lower()]

        if creator and any(player_name.lower() == creator.lower() for player_name in players):
            name = f'{creator.capitalize()}\'s'
        else:
            name = f'All'

        x = df.groupby('major_category')[score_columns].mean().mean(axis=1)
        y = mean_scores.index.tolist()
        if category in y:
            cat = f' {category}'
        else:
            cat = ''

        players = [player_name for player_name in players if player_name.lower() != creator.lower()]
        # sort the scores in descending order, (and the players accordingly, and also the colors)
        plot_values, categories = zip(*sorted(zip(plot_values, categories), reverse=True))
        #replace all nan plot values with 0

        if cat_name == "Category":
            colors = [get_category_color(category_name) for category_name in categories]
        else:
            if not self._should_include_inactive(misc):
                active_name_set = getattr(self, 'recently_active_player_names', set())
                filtered_triplets = [
                    (value, category_name)
                    for value, category_name in zip(plot_values, categories)
                    if category_name in active_name_set
                ]
                if not filtered_triplets:
                    return JsonResponse({
                        'categories': [],
                        'mean_values': [],
                        'colors': [],
                        'title': f'{title_prefix} on {name}{cat} Rounds by {cat_name}',
                        'xaxis': cat_name,
                        'yaxis': yaxis_title,
                    })
                plot_values, categories = zip(*filtered_triplets)
            colors = [get_player_color(category_name) for category_name in categories]

        try:
            response_data = {
                'categories': categories,
                'mean_values': plot_values,
                'colors': colors,
                'title': f'{title_prefix} on {name}{cat} Rounds by {cat_name}',
                'xaxis': cat_name,
                'yaxis': yaxis_title
            }
            return JsonResponse(response_data)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def category_violin_chart(self, rounds, unfiltered_rounds, creator, category, player, misc):
        df = self._records_to_df(rounds)
        score_columns = self._score_columns(df)
        if not score_columns:
            return JsonResponse({'error': 'No score columns found'}, status=400)

        # Ensure player column is available if specified
        if player:
            player_column = player_field_for_name(player)
            if player_column not in df.columns:
                return JsonResponse({'error': f'Score column for player {player} not found'}, status=400)

        if player:
            player_column = player_field_for_name(player)
            player_percentages = (df[player_column] / df['max_score'].replace(0, np.nan)) * 10
            player_mean_percentage = player_percentages.mean(skipna=True)

            if category == "":
                group_column = 'major_category'
                cat_name = "Category"
            elif creator == "":
                group_column = 'creator'
                cat_name = "Creator"
            else:
                return JsonResponse({'error': 'Invalid violin grouping'}, status=400)

            grouped_rows = []
            for group_value, group_df in df.groupby(group_column):
                group_scores = []
                group_hover_texts = []
                for _, row in group_df.iterrows():
                    raw_score = row.get(player_column)
                    max_score = row.get('max_score')
                    if pd.isna(raw_score) or pd.isna(max_score) or max_score == 0:
                        continue
                    percent_score = (raw_score / max_score) * 10
                    adjusted_score = percent_score - player_mean_percentage
                    group_scores.append(adjusted_score)
                    group_hover_texts.append(
                        f"{row.get('title', '')}<br>"
                        f"Raw score: {_format_score_value(raw_score)}/{_format_score_value(max_score)} "
                        f"({percent_score:.2f}/10)<br>"
                        f"Difference vs player mean: {adjusted_score:+.2f} points"
                    )

                if group_scores:
                    grouped_rows.append({
                        'label': group_value,
                        'scores': group_scores,
                        'hover_text': group_hover_texts,
                        'mean': sum(group_scores) / len(group_scores),
                    })

            data = pd.DataFrame(grouped_rows)
        else:
            if category == "":
                group_column = 'major_category'
                cat_name = "Category"
            elif creator == "":
                group_column = 'creator'
                cat_name = "Creator"
            else:
                return JsonResponse({'error': 'Invalid violin grouping'}, status=400)

            grouped_rows = []
            for group_value, group_df in df.groupby(group_column):
                group_scores = []
                group_hover_texts = []
                for _, row in group_df.iterrows():
                    max_score = row.get('max_score')
                    if pd.isna(max_score) or max_score == 0:
                        continue
                    round_title = row.get('title', '')
                    for score_column in score_columns:
                        raw_score = row.get(score_column)
                        if pd.isna(raw_score):
                            continue
                        normalized_score = (raw_score / max_score) * 10
                        player_label = display_name_for_player_field(score_column)
                        group_scores.append(normalized_score)
                        group_hover_texts.append(
                            f"{round_title}<br>"
                            f"Player: {player_label}<br>"
                            f"Raw score: {_format_score_value(raw_score)}/{_format_score_value(max_score)} "
                            f"({normalized_score:.2f}/10)"
                        )

                if group_scores:
                    grouped_rows.append({
                        'label': group_value,
                        'scores': group_scores,
                        'hover_text': group_hover_texts,
                        'mean': sum(group_scores) / len(group_scores),
                    })

            data = pd.DataFrame(grouped_rows)

        if data.empty:
            return JsonResponse({
                'categories': [],
                'plot_data': [],
                'hover_texts': [],
                'colors': [],
                'title': f'Distribution of Normalized Scores by {cat_name}',
                'xaxis': cat_name,
                'yaxis': 'Points vs Player Mean' if player else 'Normalized Score (0-10)',
            })

        if player:
            if category and creator == "":
                data = data[data['label'] != player]

        data = data.sort_values(by='mean', ascending=False)

        # Prepare data for plotting
        categories = data.iloc[:, 0].tolist()
        plot_data = data['scores'].tolist()
        hover_texts = data['hover_text'].tolist()

        if cat_name == "Category":
            colors = [get_category_color(category_name) for category_name in categories]
        else:
            colors = [get_player_color(category_name) for category_name in categories]

        try:
            response_data = {
                'categories': categories,
                'plot_data': plot_data,
                'hover_texts': hover_texts,
                'colors': colors,
                'title': f'Distribution of Normalized Scores by {cat_name}',
                'xaxis': cat_name,
                'yaxis': 'Points vs Player Mean' if player else 'Normalized Score (0-10)'
            }
            return JsonResponse(response_data)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    def time_series_creator(self, rounds, unfiltered_rounds, creator, category, player, misc):
        df = self._records_to_df(rounds)

        if creator:
            name = f'{creator.capitalize()}\'s'
        else:
            name = f'All'

        if category:
            cat = f' {category}'
        else:
            cat = ''

        if player:
            player_column = player_field_for_name(player)
            if player_column not in df.columns:
                return JsonResponse({'error': f'Score column for player {player} not found'}, status=400)

            # Filter the DataFrame to include only the relevant player's score column and date
            score_columns = [col for col in self._score_columns(df) if col != player_column]
            player_data = df[['date', 'title', player_column, 'max_score', 'cooperative', 'creator'] + score_columns]
            player_data = player_data.dropna(subset=[player_column])
            if not self._should_include_coop(misc):
                player_data = player_data[player_data['cooperative'] == False]
            player_data['date'] = pd.to_datetime(player_data['date'])
            player_data = player_data.sort_values(by='date')
            max_score_series = player_data['max_score'].replace(0, np.nan)
            player_data['scaled_score'] = player_data[player_column].div(max_score_series).mul(10)
            scaled_peer_scores = player_data[score_columns].div(max_score_series, axis=0).mul(10)
            player_data['mean_score'] = scaled_peer_scores.mean(axis=1)
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
                    'colors': get_player_color(player),
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
        df = self._records_to_df(unfiltered_rounds)

        if df.empty:
            return JsonResponse({'error': 'No rounds found'}, status=400)

        # Filter columns
        score_columns = self._score_columns(df)

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

    @staticmethod
    def _parse_analysis_json(value, fallback):
        if value in (None, '', []):
            return fallback
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value.replace("'", '"'))
            except Exception:
                return fallback
        return fallback

    @staticmethod
    def _selected_joker_titles(selection):
        if isinstance(selection, list):
            return list(dict.fromkeys(
                title for title in selection
                if title and title != 'Select'
            ))[:2]
        if isinstance(selection, str) and selection and selection != 'Select':
            return [selection]
        return []

    @staticmethod
    def _presentation_date(name):
        if not name:
            return pd.NaT
        return pd.to_datetime(name, format='%m.%d.%Y', errors='coerce')

    @staticmethod
    def _player_key_candidates(player_name):
        player_field = player_field_for_name(player_name)
        display_name = display_name_for_player_field(player_field or player_name)
        candidates = {
            str(player_name or '').strip(),
            str(player_name or '').strip().lower(),
            display_name,
            display_name.lower(),
            player_field,
            player_field.replace('score_', '') if player_field else '',
        }
        return {candidate for candidate in candidates if candidate}

    def _selected_titles_for_player(self, joker_round_indices, player_name):
        joker_map = self._parse_analysis_json(joker_round_indices, {})
        if not isinstance(joker_map, dict):
            return []

        key_candidates = self._player_key_candidates(player_name)
        for key, value in joker_map.items():
            if str(key).strip() in key_candidates or str(key).strip().lower() in key_candidates:
                return self._selected_joker_titles(value)
        return []

    def _effective_joker_round_score(self, round_obj, player_field):
        score_value = getattr(round_obj, player_field, None)
        if pd.notna(score_value):
            return float(score_value)

        player_name = display_name_for_player_field(player_field)
        creator_names = {
            display_name_for_player_field(getattr(round_obj, 'creator', '')),
            display_name_for_player_field(getattr(round_obj, 'secondary_creator', '')),
        }
        creator_names.discard('')
        if player_name not in creator_names:
            return None

        other_scores = []
        for key, value in round_obj.__dict__.items():
            if not str(key).startswith('score_') or key == player_field:
                continue
            if pd.notna(value):
                other_scores.append(float(value))

        if not other_scores:
            return None
        return float(np.median(other_scores))

    def joker_selection_summary(self, player, group_by='creator', creator='', category='', misc=''):
        player_field = player_field_for_name(player)
        if not player_field:
            return JsonResponse({'error': 'Player not found'}, status=400)
        if self._should_include_inactive(misc):
            eligible_creator_names = {
                display_name_for_player_field(player_field)
                for player_field in getattr(self, 'global_eligible_player_fields', set())
            }
        else:
            eligible_creator_names = getattr(self, 'recently_active_player_names', set())

        presentations = MergedPresentation.objects.all()
        selected_rounds = []

        for presentation in presentations:
            presentation_date = self._presentation_date(getattr(presentation, 'name', ''))
            if pd.isna(presentation_date):
                continue

            joker_titles = self._selected_titles_for_player(
                getattr(presentation, 'joker_round_indices', None),
                player,
            )
            if not joker_titles:
                continue

            date_value = presentation_date.date()
            rounds_on_date = list(self._apply_misc_filters(GPTriviaRound.objects.filter(date=date_value), misc))
            if not rounds_on_date:
                continue

            for round_title in joker_titles:
                matching_round = next(
                    (round_obj for round_obj in rounds_on_date if round_obj.title == round_title),
                    None,
                )
                if not matching_round:
                    continue
                if creator:
                    round_creator_labels = {
                        display_name_for_player_field(getattr(matching_round, 'creator', '')),
                        display_name_for_player_field(getattr(matching_round, 'secondary_creator', '')),
                    }
                    if creator not in round_creator_labels:
                        continue
                if category and getattr(matching_round, 'major_category', '') != category:
                    continue
                selected_rounds.append(matching_round)

        bucket_counts = {}
        bucket_jokered_scores = {}
        bucket_overall_scores = {}

        for round_obj in selected_rounds:
            if group_by == 'creator':
                labels = [
                    display_name_for_player_field(getattr(round_obj, 'creator', '')),
                    display_name_for_player_field(getattr(round_obj, 'secondary_creator', '')),
                ]
                labels = [
                    label for label in labels
                    if label and label in eligible_creator_names
                ]
            else:
                labels = [getattr(round_obj, 'major_category', '') or 'Uncategorized']

            effective_score = self._effective_joker_round_score(round_obj, player_field)
            normalized_score = None
            if effective_score is not None and getattr(round_obj, 'max_score', None) not in (None, 0):
                normalized_score = float(effective_score) / float(round_obj.max_score)

            for label in labels:
                bucket_counts[label] = bucket_counts.get(label, 0) + 1
                if normalized_score is not None:
                    bucket_jokered_scores.setdefault(label, []).append(normalized_score)

        all_rounds_queryset = self._apply_misc_filters(GPTriviaRound.objects.all(), misc)
        if creator:
            all_rounds_queryset = all_rounds_queryset.filter(
                Q(creator=creator) | Q(secondary_creator=creator)
            )
        if category:
            all_rounds_queryset = all_rounds_queryset.filter(major_category=category)

        for round_obj in all_rounds_queryset:
            raw_score = get_round_score_map(round_obj, include_null_fixed=False).get(player_field)
            max_score = getattr(round_obj, 'max_score', None)
            if raw_score is None or max_score in (None, 0):
                continue

            normalized_player_score = float(raw_score) / float(max_score)
            if group_by == 'creator':
                labels = [
                    display_name_for_player_field(getattr(round_obj, 'creator', '')),
                    display_name_for_player_field(getattr(round_obj, 'secondary_creator', '')),
                ]
                labels = [
                    label for label in labels
                    if label and label in eligible_creator_names
                ]
            else:
                labels = [getattr(round_obj, 'major_category', '') or 'Uncategorized']

            for label in labels:
                bucket_overall_scores.setdefault(label, []).append(normalized_player_score)

        title = 'Most Jokered Creators' if group_by == 'creator' else 'Most Jokered Categories'
        xaxis = 'Creator' if group_by == 'creator' else 'Category'

        if not bucket_counts:
            return JsonResponse({
                'title': title,
                'xaxis': xaxis,
                'yaxis': 'Times Jokered',
                'labels': [],
                'counts': [],
                'colors': [],
                'avg_jokered_scores': [],
                'avg_overall_scores': [],
                'best_labels': [],
                'empty_message': 'No joker selections found for this player yet.',
            })

        sorted_items = sorted(bucket_counts.items(), key=lambda item: (-item[1], item[0].lower()))
        labels = [label for label, _ in sorted_items]
        counts = [count for _, count in sorted_items]
        avg_jokered_scores = [
            (sum(bucket_jokered_scores[label]) / len(bucket_jokered_scores[label])) if bucket_jokered_scores.get(label) else None
            for label in labels
        ]
        avg_overall_scores = [
            (sum(bucket_overall_scores[label]) / len(bucket_overall_scores[label])) if bucket_overall_scores.get(label) else None
            for label in labels
        ]

        valid_best_scores = {
            label: avg_overall_scores[index]
            for index, label in enumerate(labels)
            if avg_overall_scores[index] is not None
        }
        top_labels = []
        if valid_best_scores:
            ranked_labels = sorted(
                valid_best_scores.items(),
                key=lambda item: (-item[1], -bucket_counts.get(item[0], 0), item[0].lower())
            )
            top_labels = [
                {'label': label, 'rank': rank}
                for rank, (label, _) in enumerate(ranked_labels[:3], start=1)
            ]
        best_labels = [entry['label'] for entry in top_labels[:1]]

        return JsonResponse({
            'title': title,
            'xaxis': xaxis,
            'yaxis': 'Times Jokered',
            'labels': labels,
            'counts': counts,
            'colors': [
                get_player_color(label) if group_by == 'creator' else get_category_color(label)
                for label in labels
            ],
            'avg_jokered_scores': avg_jokered_scores,
            'avg_overall_scores': avg_overall_scores,
            'best_labels': best_labels,
            'top_labels': top_labels,
            'empty_message': 'No joker selections found for this player yet.',
        })

    def joker_percentage(self, rounds, unfiltered_rounds, creator, category, player, misc):
        merged_presentations = MergedPresentation.objects.all()
        trivia_rounds = unfiltered_rounds

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
        rounds_df = self._records_to_df(trivia_rounds)

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
                player_column = player_field_for_name(player)

                if player_column not in rounds_on_date.columns:
                    continue

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
