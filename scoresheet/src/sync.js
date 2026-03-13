const SCORE_FIELDS = [
  'score_alex',
  'score_ichigo',
  'score_megan',
  'score_zach',
  'score_jenny',
  'score_debi',
  'score_dan',
  'score_chris',
  'score_drew',
  'score_tom',
  'score_jeff',
  'score_paige',
  'score_dillon',
];

const ROUND_FIELDS = [
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

  Object.entries(selectedRounds || {}).forEach(([player, roundTitle]) => {
    if (!roundTitle || roundTitle === 'Select') {
      return;
    }

    const playerName = player.replace('score_', '');
    normalized[playerName.charAt(0).toLowerCase() + playerName.slice(1)] = roundTitle;
  });

  return normalized;
}

export function normalizePlayerList(players) {
  const normalized = {};

  (players || []).forEach(player => {
    normalized[player] = player;
  });

  return normalized;
}

function resolveScoreValue(scoreField, roundTitle, scores, round) {
  const scoreMap = scores?.[scoreField];
  if (scoreMap && Object.prototype.hasOwnProperty.call(scoreMap, roundTitle)) {
    return scoreMap[roundTitle];
  }

  return round[scoreField] ?? null;
}

export function buildRoundState(round, index, state) {
  const roundTitle = round.title || '';

  const roundState = {
    id: round.id || 0,
    creator: state.roundCreators?.[roundTitle] ?? round.creator ?? '',
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
  };

  SCORE_FIELDS.forEach(scoreField => {
    roundState[scoreField] = resolveScoreValue(scoreField, roundTitle, state.scores, round);
  });

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

export function shouldIgnoreScoresheetMessage(message, clientId, pendingMutationIds) {
  if (!message || !message.client_id || !message.mutation_id) {
    return false;
  }

  return message.client_id === clientId && pendingMutationIds.has(message.mutation_id);
}
