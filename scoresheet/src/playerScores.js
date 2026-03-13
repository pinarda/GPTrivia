export const FIXED_SCORE_FIELDS = [
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

function titleCaseWords(value) {
  return String(value || '')
    .split(/[\s_]+/)
    .filter(Boolean)
    .map(part => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

export function getPlayerFieldForName(name) {
  const normalized = String(name || '')
    .trim()
    .replace(/^score_/, '')
    .replace(/[_\s]+/g, ' ');
  if (!normalized) {
    return '';
  }

  const lowered = normalized.toLowerCase();
  if (lowered === 'dad') {
    return 'score_dan';
  }
  if (lowered === 'mom') {
    return 'score_debi';
  }

  return `score_${lowered}`;
}

export function getDisplayNameForPlayerField(playerField) {
  const rawName = String(playerField || '').replace(/^score_/, '').trim();
  if (!rawName) {
    return '';
  }

  const lowered = rawName.toLowerCase();
  if (lowered === 'dad') {
    return 'Dan';
  }
  if (lowered === 'mom') {
    return 'Debi';
  }

  return titleCaseWords(rawName);
}

export function getPlayerStorageKey(playerField) {
  const displayName = getDisplayNameForPlayerField(playerField);
  if (!displayName) {
    return '';
  }

  return displayName.toLowerCase();
}

export function getRoundExtraScores(round) {
  const extraScores = round?.extra_scores;
  if (!extraScores || typeof extraScores !== 'object') {
    return {};
  }

  const normalized = {};
  Object.entries(extraScores).forEach(([playerField, value]) => {
    const normalizedField = getPlayerFieldForName(playerField);
    if (!normalizedField) {
      return;
    }
    normalized[normalizedField] = value;
  });
  return normalized;
}

export function getMergedRoundScoreMap(round) {
  const mergedScores = {};

  FIXED_SCORE_FIELDS.forEach(field => {
    mergedScores[field] = round?.[field] ?? null;
  });

  Object.entries(getRoundExtraScores(round)).forEach(([playerField, value]) => {
    mergedScores[playerField] = value;
  });

  Object.entries(round || {}).forEach(([key, value]) => {
    if (String(key).startsWith('score_') && !Object.prototype.hasOwnProperty.call(mergedScores, key)) {
      mergedScores[key] = value;
    }
  });

  return mergedScores;
}

export function getRoundScoreValue(round, playerField) {
  const mergedScores = getMergedRoundScoreMap(round);
  if (Object.prototype.hasOwnProperty.call(mergedScores, playerField)) {
    return mergedScores[playerField];
  }
  return null;
}

export function removePlayerFromRound(round, playerField) {
  const nextRound = { ...(round || {}) };
  const normalizedField = getPlayerFieldForName(playerField);
  if (!normalizedField) {
    return nextRound;
  }

  if (FIXED_SCORE_FIELDS.includes(normalizedField)) {
    nextRound[normalizedField] = null;
  } else {
    delete nextRound[normalizedField];
  }

  const nextExtraScores = { ...getRoundExtraScores(round) };
  delete nextExtraScores[normalizedField];
  nextRound.extra_scores = nextExtraScores;

  return nextRound;
}

export function buildRoundScorePayload(round, scores, players) {
  const payload = {};
  const extraScores = {};
  const mergedScores = getMergedRoundScoreMap(round);
  const relevantPlayers = new Set([
    ...FIXED_SCORE_FIELDS,
    ...(players || []),
    ...Object.keys(mergedScores),
  ]);

  relevantPlayers.forEach(playerField => {
    const scoreMap = scores?.[playerField];
    const scoreValue = scoreMap && Object.prototype.hasOwnProperty.call(scoreMap, round.title)
      ? scoreMap[round.title]
      : mergedScores[playerField];

    if (FIXED_SCORE_FIELDS.includes(playerField)) {
      payload[playerField] = scoreValue ?? null;
      return;
    }

    if (scoreValue !== null && scoreValue !== undefined) {
      extraScores[playerField] = scoreValue;
    }
  });

  payload.extra_scores = extraScores;
  return payload;
}

export function extractPlayersFromRounds(rounds) {
  const players = new Set();

  (rounds || []).forEach(round => {
    Object.entries(getMergedRoundScoreMap(round)).forEach(([playerField, value]) => {
      if (value !== null && value !== undefined) {
        players.add(playerField);
      }
    });
  });

  return [...players];
}

export function getPlayerColor(playerField, knownColorMapping) {
  if (knownColorMapping?.[playerField]) {
    return knownColorMapping[playerField];
  }

  const seed = getDisplayNameForPlayerField(playerField);
  if (!seed) {
    return '#333333';
  }

  let hash = 0;
  for (let index = 0; index < seed.length; index += 1) {
    hash = ((hash * 31) + seed.charCodeAt(index)) % 360;
  }

  const saturation = 62;
  const lightness = 47;
  const hue = hash / 360;
  const sat = saturation / 100;
  const light = lightness / 100;

  const hueToRgb = (p, q, t) => {
    let nextT = t;
    if (nextT < 0) nextT += 1;
    if (nextT > 1) nextT -= 1;
    if (nextT < 1 / 6) return p + (q - p) * 6 * nextT;
    if (nextT < 1 / 2) return q;
    if (nextT < 2 / 3) return p + (q - p) * (2 / 3 - nextT) * 6;
    return p;
  };

  let red;
  let green;
  let blue;
  if (sat === 0) {
    red = light;
    green = light;
    blue = light;
  } else {
    const q = light < 0.5 ? light * (1 + sat) : light + sat - light * sat;
    const p = 2 * light - q;
    red = hueToRgb(p, q, hue + (1 / 3));
    green = hueToRgb(p, q, hue);
    blue = hueToRgb(p, q, hue - (1 / 3));
  }

  const componentToHex = component => Math.round(component * 255).toString(16).padStart(2, '0');
  return `#${componentToHex(red)}${componentToHex(green)}${componentToHex(blue)}`;
}
