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
