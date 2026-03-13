import {
  getDisplayNameForPlayerField,
  getPlayerFieldForName as getPlayerFieldForNameFromScores,
} from './playerScores';

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
  return getDisplayNameForPlayerField(playerField);
}

export function getPlayerFieldForName(players, playerName) {
  const playerField = getPlayerFieldForNameFromScores(playerName);
  if (!playerField) {
    return null;
  }

  return (players || []).find(player => normalizePlayerName(player) === normalizePlayerName(playerField)) || null;
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

export function getCrownTheme(streak) {
  if (streak >= 4) {
    return {
      fill: '#7edcff',
      stroke: '#f5fdff',
      base: '#ddf7ff',
      leftGem: '#fefeff',
      centerGem: '#ffffff',
      rightGem: '#ccf5ff',
      trim: '#f2feff',
      accent: '#9ce8ff',
      sparkle: '#ffffff',
      textFill: '#17313f',
      textStroke: '#f7feff',
    };
  }

  if (streak === 3) {
    return {
      fill: '#f3bc34',
      stroke: '#fff1ad',
      base: '#ffeaa1',
      leftGem: '#ff9f5e',
      centerGem: '#fff2be',
      rightGem: '#d89dff',
      trim: '#fff6c8',
      accent: '#ffd86e',
      sparkle: '#fffbe4',
      textFill: '#2d1800',
      textStroke: '#fff7cf',
    };
  }

  if (streak === 2) {
    return {
      fill: '#d6e9f5',
      stroke: '#f8fdff',
      base: '#edf7ff',
      leftGem: '#b7d9ef',
      centerGem: '#ffffff',
      rightGem: '#d8efff',
      trim: '#ffffff',
      accent: '#bfe5ff',
      sparkle: '#ffffff',
      textFill: '#233241',
      textStroke: '#f7fbff',
    };
  }

  return {
    fill: '#d39a6a',
    stroke: '#f5d6bd',
    base: '#edd1b7',
    leftGem: '#ffe0c7',
    centerGem: '#fff0e3',
    rightGem: '#f5c29a',
    trim: '#f7e0ce',
    accent: '#edbf95',
    sparkle: '#fff3ea',
    textFill: '#111111',
    textStroke: '#9a5f34',
  };
}
