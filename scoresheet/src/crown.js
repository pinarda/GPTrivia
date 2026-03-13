function normalizePlayerName(name) {
  return String(name || '')
    .replace(/^score_/, '')
    .trim()
    .toLowerCase();
}

function parsePresentationDate(presentation) {
  const name = presentation?.name;
  if (!name || typeof name !== 'string') {
    return null;
  }

  const [month, day, year] = name.split('.');
  if (!month || !day || !year) {
    return null;
  }

  return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
}

export function getDisplayNameForPlayer(playerField) {
  const name = String(playerField || '').replace(/^score_/, '');
  if (!name) {
    return '';
  }

  return name.charAt(0).toUpperCase() + name.slice(1);
}

export function getPlayerFieldForName(players, playerName) {
  const normalizedPlayerName = normalizePlayerName(playerName);
  if (!normalizedPlayerName) {
    return null;
  }

  return (players || []).find(player => normalizePlayerName(player) === normalizedPlayerName) || null;
}

export function getInheritedCrownedWinner(presentations, selectedDate) {
  if (!selectedDate) {
    return '';
  }

  const previousPresentation = (presentations || [])
    .map(presentation => ({
      presentation,
      parsedDate: parsePresentationDate(presentation),
    }))
    .filter(({ parsedDate }) => parsedDate && parsedDate < selectedDate)
    .sort((left, right) => left.parsedDate.localeCompare(right.parsedDate))
    .at(-1);

  return previousPresentation?.presentation?.crowned_winner || '';
}

export function getCrownStreak(
  presentations,
  selectedDate,
  activeWinner,
  currentNightWinner = '',
) {
  const normalizedWinner = normalizePlayerName(activeWinner);
  if (!selectedDate || !normalizedWinner) {
    return 0;
  }

  const includeCurrentNight = normalizePlayerName(currentNightWinner) === normalizedWinner;
  const eligiblePresentations = (presentations || [])
    .map(presentation => ({
      presentation,
      parsedDate: parsePresentationDate(presentation),
    }))
    .filter(({ parsedDate }) => (
      parsedDate &&
      (includeCurrentNight ? parsedDate <= selectedDate : parsedDate < selectedDate)
    ))
    .sort((left, right) => left.parsedDate.localeCompare(right.parsedDate));

  let streak = 0;

  for (let index = eligiblePresentations.length - 1; index >= 0; index -= 1) {
    const winner = eligiblePresentations[index].presentation?.crowned_winner || '';
    if (normalizePlayerName(winner) !== normalizedWinner) {
      break;
    }
    streak += 1;
  }

  return streak;
}

export function getCrownBurstParticles() {
  return [
    { x: -18, y: 44, rotate: -210, delay: 0.00, scale: 0.75 },
    { x: -10, y: 58, rotate: -140, delay: 0.04, scale: 0.95 },
    { x: -2, y: 38, rotate: -95, delay: 0.02, scale: 0.7 },
    { x: 6, y: 52, rotate: 115, delay: 0.06, scale: 0.82 },
    { x: 14, y: 46, rotate: 180, delay: 0.03, scale: 0.9 },
    { x: 20, y: 62, rotate: 240, delay: 0.08, scale: 1.0 },
    { x: -22, y: 68, rotate: -270, delay: 0.10, scale: 0.88 },
    { x: 2, y: 70, rotate: 320, delay: 0.12, scale: 0.78 },
  ];
}
