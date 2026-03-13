import hashlib
import json
import re
import ast


FIXED_SCORE_FIELDS = (
    'score_alex',
    'score_ichigo',
    'score_megan',
    'score_zach',
    'score_jenny',
    'score_debi',
    'score_dan',
    'score_chris',
    'score_drew',
    'score_jeff',
    'score_dillon',
    'score_paige',
    'score_tom',
)

MIN_ANALYSIS_ROUNDS = 50

ROUND_BASE_FIELDS = (
    'id',
    'creator',
    'title',
    'major_category',
    'minor_category1',
    'minor_category2',
    'date',
    'round_number',
    'max_score',
    'replay',
    'cooperative',
    'notes',
    'link',
)

KNOWN_PLAYER_COLOR_MAPPING = {
    'Alex': '#D2042D',
    'Ichigo': '#ff7f0e',
    'Megan': '#8e4585',
    'Zach': '#A020F0',
    'Jenny': '#ffef00',
    'Debi': '#8551ff',
    'Dan': '#560000',
    'Chris': '#005427',
    'Drew': '#8c564b',
    'Jeff': '#66FF66',
    'Paige': '#FF6666',
    'Dillon': '#0000FF',
    'Tom': '#000042',
    'Unknown': '#333333',
}

PLAYER_NAME_ALIASES = {
    'dad': 'Dan',
    'mom': 'Debi',
}


def _clean_player_name(value):
    cleaned = re.sub(r'[_\s]+', ' ', str(value or '').strip())
    return cleaned.strip()


def display_name_for_player_field(player_field):
    name = str(player_field or '')
    if name.startswith('score_'):
        name = name[6:]

    name = _clean_player_name(name)
    if not name:
        return ''

    aliased = PLAYER_NAME_ALIASES.get(name.lower())
    if aliased:
        return aliased

    if name.lower() in {known.lower(): known for known in KNOWN_PLAYER_COLOR_MAPPING}.keys():
        for known in KNOWN_PLAYER_COLOR_MAPPING:
            if known.lower() == name.lower():
                return known

    return ' '.join(part.capitalize() for part in name.split(' '))


def player_field_for_name(name):
    display_name = display_name_for_player_field(name)
    if not display_name:
        return ''
    if not re.search(r'[A-Za-z]', display_name):
        return ''
    return f"score_{display_name.lower()}"


def normalize_player_field(player_field):
    if not player_field:
        return ''

    if str(player_field).startswith('score_'):
        return player_field_for_name(display_name_for_player_field(player_field))

    return player_field_for_name(player_field)


def normalize_player_list(player_list):
    if not player_list:
        return []

    if isinstance(player_list, dict):
        values = list(player_list.keys())
    elif isinstance(player_list, (list, tuple, set)):
        values = list(player_list)
    else:
        values = [player_list]

    normalized = []
    seen = set()
    for value in values:
        player_field = normalize_player_field(value)
        if player_field and player_field not in seen:
            normalized.append(player_field)
            seen.add(player_field)
    return normalized


def iter_round_extra_score_fields(round_obj):
    extra_scores = getattr(round_obj, 'extra_scores', None) or {}
    if isinstance(extra_scores, str):
        try:
            extra_scores = json.loads(extra_scores.replace("'", '"'))
        except Exception:
            try:
                extra_scores = ast.literal_eval(extra_scores)
            except Exception:
                extra_scores = {}
    if not isinstance(extra_scores, dict):
        return {}

    normalized = {}
    for key, value in extra_scores.items():
        player_field = normalize_player_field(key)
        if not player_field:
            continue
        normalized[player_field] = value
    return normalized


def get_round_score_map(round_obj, include_null_fixed=True):
    score_map = {}

    for field in FIXED_SCORE_FIELDS:
        value = getattr(round_obj, field, None)
        if include_null_fixed or value is not None:
            score_map[field] = value

    score_map.update(iter_round_extra_score_fields(round_obj))
    return score_map


def set_round_score_map(round_obj, score_map):
    normalized_score_map = {}
    for key, value in (score_map or {}).items():
        player_field = normalize_player_field(key)
        if not player_field:
            continue
        normalized_score_map[player_field] = value

    extra_scores = {}
    for field in FIXED_SCORE_FIELDS:
        setattr(round_obj, field, normalized_score_map.get(field))

    for field, value in normalized_score_map.items():
        if field in FIXED_SCORE_FIELDS:
            continue
        if value is None:
            continue
        extra_scores[field] = value

    round_obj.extra_scores = extra_scores
    return round_obj


def round_has_any_score(round_obj):
    return any(value is not None for value in get_round_score_map(round_obj).values())


def flatten_round_for_analysis(round_obj, include_null_fixed=True):
    round_data = {field: getattr(round_obj, field) for field in ROUND_BASE_FIELDS}
    round_data.update(get_round_score_map(round_obj, include_null_fixed=include_null_fixed))
    round_data['extra_scores'] = iter_round_extra_score_fields(round_obj)
    return round_data


def collect_player_fields(rounds=None, presentations=None, include_fixed=True):
    player_fields = set(FIXED_SCORE_FIELDS if include_fixed else [])

    for round_obj in rounds or []:
        player_fields.update(iter_round_extra_score_fields(round_obj).keys())
        creator_field = player_field_for_name(getattr(round_obj, 'creator', ''))
        if creator_field:
            player_fields.add(creator_field)

    for presentation in presentations or []:
        player_fields.update(normalize_player_list(getattr(presentation, 'player_list', None)))
        for creator in getattr(presentation, 'creator_list', []) or []:
            creator_field = player_field_for_name(creator)
            if creator_field:
                player_fields.add(creator_field)

    return sort_player_fields(player_fields)


def sort_player_fields(player_fields):
    fixed_index = {field: index for index, field in enumerate(FIXED_SCORE_FIELDS)}

    return sorted(
        set(player_fields or []),
        key=lambda field: (
            0 if field in fixed_index else 1,
            fixed_index.get(field, 0),
            display_name_for_player_field(field).lower(),
        ),
    )


def get_all_player_fields(round_queryset, presentation_queryset):
    return collect_player_fields(
        rounds=list(round_queryset),
        presentations=list(presentation_queryset),
        include_fixed=True,
    )


def get_player_round_counts(rounds):
    counts = {}

    for round_obj in rounds or []:
        if isinstance(round_obj, dict):
            score_map = {
                key: value
                for key, value in round_obj.items()
                if str(key).startswith('score_') and value is not None
            }
        else:
            score_map = get_round_score_map(round_obj, include_null_fixed=False)

        for player_field, value in score_map.items():
            if value is None:
                continue
            counts[player_field] = counts.get(player_field, 0) + 1

    return counts


def get_eligible_player_fields(rounds, min_rounds=MIN_ANALYSIS_ROUNDS):
    round_counts = get_player_round_counts(rounds)
    eligible_fields = [
        player_field
        for player_field, count in round_counts.items()
        if count >= min_rounds
    ]
    return sort_player_fields(eligible_fields)


def get_all_player_display_names(round_queryset, presentation_queryset):
    return [display_name_for_player_field(field) for field in get_all_player_fields(round_queryset, presentation_queryset)]


def _hsl_to_hex(hue, saturation, lightness):
    hue = hue / 360.0
    saturation = saturation / 100.0
    lightness = lightness / 100.0

    def hue_to_rgb(p, q, t):
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    if saturation == 0:
        red = green = blue = lightness
    else:
        q = lightness * (1 + saturation) if lightness < 0.5 else lightness + saturation - lightness * saturation
        p = 2 * lightness - q
        red = hue_to_rgb(p, q, hue + 1 / 3)
        green = hue_to_rgb(p, q, hue)
        blue = hue_to_rgb(p, q, hue - 1 / 3)

    return '#{:02x}{:02x}{:02x}'.format(
        round(red * 255),
        round(green * 255),
        round(blue * 255),
    )


def get_player_color(player_name):
    display_name = display_name_for_player_field(player_name)
    if not display_name:
        return KNOWN_PLAYER_COLOR_MAPPING['Unknown']

    if display_name in KNOWN_PLAYER_COLOR_MAPPING:
        return KNOWN_PLAYER_COLOR_MAPPING[display_name]

    digest = hashlib.sha1(display_name.encode('utf-8')).hexdigest()
    hue = int(digest[:8], 16) % 360
    return _hsl_to_hex(hue, 62, 47)


def build_player_color_mapping(player_names):
    mapping = {'Unknown': KNOWN_PLAYER_COLOR_MAPPING['Unknown']}

    for player_name in player_names or []:
        display_name = display_name_for_player_field(player_name)
        if not display_name:
            continue
        mapping[display_name] = get_player_color(display_name)

    return mapping


def build_player_text_mapping(player_names):
    text_mapping = {}
    for player_name in player_names or []:
        display_name = display_name_for_player_field(player_name)
        if not display_name:
            continue
        player_color = get_player_color(display_name)
        brightness = (
            int(player_color[1:3], 16) +
            int(player_color[3:5], 16) +
            int(player_color[5:7], 16)
        )
        text_mapping[display_name] = 'white' if brightness < 480 else 'black'
    return text_mapping
