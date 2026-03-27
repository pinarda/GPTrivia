import { getPlayerFieldForName } from './playerScores';

export function parsePresentationJson(value, fallback) {
  if (value === null || value === undefined || value === '') {
    return fallback;
  }

  if (typeof value === 'object') {
    return value;
  }

  if (typeof value !== 'string') {
    return fallback;
  }

  try {
    return JSON.parse(
      value
        .replace(/'/g, '"')
        .replace(/^"/, '"')
        .replace(/"$/, '"')
        .replace(/~~~~/g, "'"),
    );
  } catch (error) {
    return fallback;
  }
}

export function resolvePresentationPlayers(playerList, defaultPlayers) {
  const parsedPlayerList = parsePresentationJson(playerList, {});
  if (!parsedPlayerList || Object.keys(parsedPlayerList).length === 0) {
    return [...defaultPlayers];
  }

  return Object.keys(parsedPlayerList)
    .map(player => getPlayerFieldForName(player))
    .filter(Boolean);
}

export function resolveJokerRoundIndices(jokerRoundIndices) {
  return parsePresentationJson(jokerRoundIndices, {});
}

export function resolveScoresheetDate(selectedDate, requestedDate, availableDates) {
  const normalizedDates = Array.isArray(availableDates) ? availableDates.filter(Boolean) : [];
  const isValidDateString = (value) => /^\d{4}-\d{2}-\d{2}$/.test(String(value || ''));

  if (selectedDate && isValidDateString(selectedDate)) {
    return selectedDate;
  }

  if (requestedDate && isValidDateString(requestedDate)) {
    return requestedDate;
  }

  if (!normalizedDates.length) {
    return '';
  }

  return [...normalizedDates].sort().reverse()[0] || '';
}
