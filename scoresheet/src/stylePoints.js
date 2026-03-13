import {
  getDisplayNameForPlayerField,
  getPlayerFieldForName,
} from './playerScores';

function normalizeStylePointKey(playerName) {
  const playerField = getPlayerFieldForName(playerName);
  if (!playerField) {
    return '';
  }

  return getDisplayNameForPlayerField(playerField);
}

export function normalizeStylePointValue(value) {
  if (value === '' || value === null || value === undefined) {
    return null;
  }

  const numericValue = Number(value);
  if (Number.isNaN(numericValue)) {
    return null;
  }

  return numericValue;
}

export function getNormalizedStylePoints(stylePoints) {
  const normalized = {};

  Object.entries(stylePoints || {}).forEach(([playerName, value]) => {
    const normalizedKey = normalizeStylePointKey(playerName);
    const normalizedValue = normalizeStylePointValue(value);
    if (!normalizedKey || normalizedValue === null) {
      return;
    }

    normalized[normalizedKey] = normalizedValue;
  });

  return normalized;
}

export function getStylePointValue(stylePoints, playerField) {
  const normalized = getNormalizedStylePoints(stylePoints);
  const displayName = getDisplayNameForPlayerField(playerField);
  if (!displayName) {
    return null;
  }

  return Object.prototype.hasOwnProperty.call(normalized, displayName)
    ? normalized[displayName]
    : null;
}

export function hasStylePointAward(stylePoints, playerField) {
  const value = getStylePointValue(stylePoints, playerField);
  return value !== null && value > 0;
}

export function getStylePointTier(value) {
  const normalizedValue = normalizeStylePointValue(value);
  if (normalizedValue === null || normalizedValue <= 0) {
    return null;
  }

  if (normalizedValue >= 3) {
    return 'fire';
  }

  if (normalizedValue >= 2) {
    return 'gold';
  }

  return 'red';
}

export function getStylePointTheme(stylePoints, playerField) {
  const value = getStylePointValue(stylePoints, playerField);
  const tier = getStylePointTier(value);

  if (tier === 'fire') {
    return {
      tier,
      value,
      frameFill: '#ffb21f',
      frameStroke: '#7a1a00',
      lensFill: '#230307',
      highlight: '#fff1a8',
      rimHighlight: '#fff3b8',
      sparkle: false,
      sparkleColor: '#fff1a8',
      flame: true,
      flameCore: '#fff5a8',
      flameOuter: '#ff4a1a',
    };
  }

  if (tier === 'gold') {
    return {
      tier,
      value,
      frameFill: '#e9bb35',
      frameStroke: '#7b5513',
      lensFill: '#251809',
      highlight: '#fff0a8',
      rimHighlight: '#fff6c9',
      sparkle: true,
      sparkleColor: '#fff8d8',
      flame: false,
      flameCore: '',
      flameOuter: '',
    };
  }

  return {
    tier: 'red',
    value,
    frameFill: '#d91e35',
    frameStroke: '#6c0012',
    lensFill: '#240409',
    highlight: '#ff7f92',
    rimHighlight: '#ff94a3',
    sparkle: false,
    sparkleColor: '#ff94a3',
    flame: false,
    flameCore: '',
    flameOuter: '',
  };
}

export function setStylePointValue(stylePoints, playerName, value) {
  const normalized = getNormalizedStylePoints(stylePoints);
  const normalizedKey = normalizeStylePointKey(playerName);
  const normalizedValue = normalizeStylePointValue(value);

  if (!normalizedKey) {
    return normalized;
  }

  if (normalizedValue === null) {
    delete normalized[normalizedKey];
    return normalized;
  }

  normalized[normalizedKey] = normalizedValue;
  return normalized;
}

export function incrementStylePoint(stylePoints, playerName, increment = 1) {
  const normalized = getNormalizedStylePoints(stylePoints);
  const normalizedKey = normalizeStylePointKey(playerName);

  if (!normalizedKey) {
    return normalized;
  }

  const currentValue = normalized[normalizedKey] || 0;
  normalized[normalizedKey] = currentValue + increment;
  return normalized;
}
