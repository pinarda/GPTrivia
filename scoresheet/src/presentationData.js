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

  return Object.keys(parsedPlayerList);
}

export function resolveJokerRoundIndices(jokerRoundIndices) {
  return parsePresentationJson(jokerRoundIndices, {});
}
