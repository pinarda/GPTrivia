import {
  buildRoundScorePayload,
  FIXED_SCORE_FIELDS,
  getPlayerFieldForName,
  getPlayerStorageKey,
  getRoundExtraScores,
} from './playerScores';

const SCORE_FIELDS = FIXED_SCORE_FIELDS;

const ROUND_FIELDS = [
  'creator',
  'secondary_creator',
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
  'extra_scores',
  ...SCORE_FIELDS,
];

const EMPTY_PRESENTATION_STATE = {
  round_names: [],
  creator_list: [],
  joker_round_indices: {},
  player_list: {},
  host: '',
  scorekeeper: '',
  tiebreak_winner: '',
  crowned_winner: '',
  notes: '',
  style_points: {},
};

function stableSerialize(value) {
  if (Array.isArray(value)) {
    return `[${value.map(stableSerialize).join(',')}]`;
  }

  if (value && typeof value === 'object') {
    const keys = Object.keys(value).sort();
    return `{${keys.map(key => `${JSON.stringify(key)}:${stableSerialize(value[key])}`).join(',')}}`;
  }

  return JSON.stringify(value === undefined ? null : value);
}

function valuesEqual(left, right) {
  return stableSerialize(left) === stableSerialize(right);
}

function parseMaybeJson(value, fallback) {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }

  if (typeof value === 'object') {
    return value;
  }

  try {
    return JSON.parse(value.replace(/'/g, '"'));
  } catch (error) {
    return fallback;
  }
}

export function createClientId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }

  return `client-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function createMutationId() {
  return `mutation-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function normalizeStylePoints(stylePoints) {
  const parsedStylePoints = parseMaybeJson(stylePoints, {});
  const normalized = {};

  Object.entries(parsedStylePoints || {}).forEach(([player, value]) => {
    if (value === '' || value === undefined || value === null) {
      return;
    }

    const numericValue = Number(value);
    normalized[player] = Number.isNaN(numericValue) ? value : numericValue;
  });

  return normalized;
}

export function normalizeSelectedRounds(selectedRounds) {
  const normalized = {};

  Object.entries(selectedRounds || {}).forEach(([player, roundSelection]) => {
    const roundTitles = Array.isArray(roundSelection)
      ? [...new Set(roundSelection.filter(title => title && title !== 'Select'))].slice(0, 2)
      : (roundSelection && roundSelection !== 'Select' ? [roundSelection] : []);

    if (!roundTitles.length) {
      return;
    }

    const playerField = getPlayerFieldForName(player);
    const playerKey = getPlayerStorageKey(playerField);
    if (!playerKey) {
      return;
    }

    normalized[playerKey] = roundTitles.length === 1 ? roundTitles[0] : roundTitles;
  });

  return normalized;
}

export function normalizePlayerList(players) {
  const normalized = {};

  (players || []).forEach(player => {
    const playerField = getPlayerFieldForName(player);
    if (playerField) {
      normalized[playerField] = playerField;
    }
  });

  return normalized;
}

function resolveScoreValue(scoreField, roundTitle, scores, round) {
  const scoreMap = scores?.[scoreField];
  if (scoreMap && Object.prototype.hasOwnProperty.call(scoreMap, roundTitle)) {
    return scoreMap[roundTitle];
  }

  if (Object.prototype.hasOwnProperty.call(getRoundExtraScores(round), scoreField)) {
    return getRoundExtraScores(round)[scoreField];
  }

  return round[scoreField] ?? null;
}

export function buildRoundState(round, index, state) {
  const roundTitle = round.title || '';

  const roundState = {
    id: round.id || 0,
    creator: state.roundCreators?.[roundTitle] ?? round.creator ?? '',
    secondary_creator: state.secondaryRoundCreators?.[roundTitle] ?? round.secondary_creator ?? '',
    title: roundTitle,
    major_category: state.selectedMajorCategories?.[roundTitle] ?? round.major_category ?? '',
    minor_category1: state.selectedMinor1Categories?.[roundTitle] ?? round.minor_category1 ?? '',
    minor_category2: state.selectedMinor2Categories?.[roundTitle] ?? round.minor_category2 ?? '',
    date: round.date || '',
    round_number: index + 1,
    max_score: state.maxScores?.[roundTitle] ?? round.max_score ?? 10,
    replay: state.isReplay?.[roundTitle] ?? round.replay ?? false,
    cooperative: state.cooperativeStatus?.[roundTitle] ?? round.cooperative ?? false,
    notes: round.notes || '',
    link: round.link || '',
    extra_scores: {},
  };

  const scorePayload = buildRoundScorePayload(round, state.scores, state.players);
  SCORE_FIELDS.forEach(scoreField => {
    roundState[scoreField] = scorePayload[scoreField] ?? resolveScoreValue(scoreField, roundTitle, state.scores, round);
  });
  roundState.extra_scores = scorePayload.extra_scores || {};

  return roundState;
}

export function buildPresentationState(state) {
  return {
    round_names: (state.rounds || []).map(round => round.title || ''),
    creator_list: (state.rounds || []).map(round => state.roundCreators?.[round.title] ?? round.creator ?? ''),
    joker_round_indices: normalizeSelectedRounds(state.selectedRounds),
    player_list: normalizePlayerList(state.players),
    host: state.host || '',
    scorekeeper: state.scorekeeper || '',
    tiebreak_winner: state.tiebreakWinner || '',
    crowned_winner: state.crownedWinner || '',
    notes: state.notes || '',
    style_points: normalizeStylePoints(state.stylePoints),
  };
}

export function makeRoundSnapshot(round) {
  const snapshot = {};

  ROUND_FIELDS.forEach(field => {
    if (field === 'extra_scores') {
      snapshot[field] = round[field] ?? {};
      return;
    }
    snapshot[field] = round[field] ?? null;
  });

  return snapshot;
}

export function makePresentationSnapshot(selectedPresentation) {
  if (!selectedPresentation) {
    return { ...EMPTY_PRESENTATION_STATE };
  }

  return {
    round_names: Array.isArray(selectedPresentation.round_names) ? selectedPresentation.round_names : [],
    creator_list: Array.isArray(selectedPresentation.creator_list) ? selectedPresentation.creator_list : [],
    joker_round_indices: parseMaybeJson(selectedPresentation.joker_round_indices, {}),
    player_list: parseMaybeJson(selectedPresentation.player_list, {}),
    host: selectedPresentation.host || '',
    scorekeeper: selectedPresentation.scorekeeper || '',
    tiebreak_winner: selectedPresentation.tiebreak_winner || '',
    crowned_winner: selectedPresentation.crowned_winner || '',
    notes: selectedPresentation.notes || '',
    style_points: normalizeStylePoints(selectedPresentation.style_points),
  };
}

export function buildScoresheetPatch(state) {
  const round_updates = [];
  const currentRoundStates = (state.rounds || []).map((round, index) => buildRoundState(round, index, state));

  currentRoundStates.forEach(roundState => {
    const baseRound = state.serverRoundSnapshot?.[roundState.id] || {};
    const fields = {};

    Object.entries(roundState).forEach(([field, value]) => {
      if (field === 'id') {
        return;
      }

      const normalizedValue = value === undefined ? null : value;
      const baseValue = baseRound[field] === undefined ? null : baseRound[field];
      if (!valuesEqual(normalizedValue, baseValue)) {
        fields[field] = normalizedValue;
      }
    });

    if (Object.keys(fields).length > 0) {
      round_updates.push({ id: roundState.id, fields });
    }
  });

  const presentation_updates = {};
  const currentPresentationState = buildPresentationState(state);
  const basePresentationState = state.serverPresentationSnapshot || EMPTY_PRESENTATION_STATE;

  Object.entries(currentPresentationState).forEach(([field, value]) => {
    const baseValue = basePresentationState[field];
    if (!valuesEqual(value, baseValue)) {
      presentation_updates[field] = value;
    }
  });

  return {
    round_updates,
    presentation_updates,
    selected_date: state.selectedDate || '',
  };
}

export function hasScoresheetChanges(patch) {
  return patch.round_updates.length > 0 || Object.keys(patch.presentation_updates).length > 0;
}

export function applyPatchToRoundSnapshot(snapshot, roundUpdates) {
  const nextSnapshot = { ...(snapshot || {}) };

  (roundUpdates || []).forEach(update => {
    nextSnapshot[update.id] = {
      ...(nextSnapshot[update.id] || {}),
      ...update.fields,
    };
  });

  return nextSnapshot;
}

export function applyPatchToPresentationSnapshot(snapshot, presentationUpdates) {
  return {
    ...EMPTY_PRESENTATION_STATE,
    ...(snapshot || {}),
    ...(presentationUpdates || {}),
    style_points: normalizeStylePoints(
      presentationUpdates && Object.prototype.hasOwnProperty.call(presentationUpdates, 'style_points')
        ? presentationUpdates.style_points
        : snapshot?.style_points
    ),
  };
}

function parsePresentationNameDate(presentationName) {
  const name = String(presentationName || '');
  if (!name.includes('.')) {
    return '';
  }

  const [month, day, year] = name.split('.');
  if (!month || !day || !year) {
    return '';
  }

  return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
}

function formatPresentationNameDate(selectedDate) {
  if (!selectedDate || !selectedDate.includes('-')) {
    return '';
  }

  const [year, month, day] = selectedDate.split('-');
  if (!year || !month || !day) {
    return '';
  }

  return `${month.padStart(2, '0')}.${day.padStart(2, '0')}.${year}`;
}

export function applyPresentationFieldsForSelectedDate(presentations, selectedDate, fields) {
  if (!selectedDate || !fields || Object.keys(fields).length === 0) {
    return presentations || [];
  }

  let didUpdateExistingRow = false;
  const nextPresentations = (presentations || []).map((presentation) => {
    if (parsePresentationNameDate(presentation?.name) !== selectedDate) {
      return presentation;
    }

    didUpdateExistingRow = true;
    return {
      ...presentation,
      ...fields,
    };
  });

  if (didUpdateExistingRow) {
    return nextPresentations;
  }

  const nextPresentationName = formatPresentationNameDate(selectedDate);
  if (!nextPresentationName) {
    return nextPresentations;
  }

  return [
    ...nextPresentations,
    {
      name: nextPresentationName,
      presentation_id: '',
      ...fields,
    },
  ].sort((left, right) => (
    parsePresentationNameDate(left?.name).localeCompare(parsePresentationNameDate(right?.name))
  ));
}

export function shouldIgnoreScoresheetMessage(message, clientId, pendingMutationIds) {
  if (!message || !message.client_id || !message.mutation_id) {
    return false;
  }

  return message.client_id === clientId && pendingMutationIds.has(message.mutation_id);
}
