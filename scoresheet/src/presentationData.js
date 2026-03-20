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
  if (!normalizedDates.length) {
    return '';
  }

  if (selectedDate && normalizedDates.includes(selectedDate)) {
    return selectedDate;
  }

  if (requestedDate && normalizedDates.includes(requestedDate)) {
    return requestedDate;
  }

  return [...normalizedDates].sort().reverse()[0] || '';
}
