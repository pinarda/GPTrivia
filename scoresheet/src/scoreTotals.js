import {
  getDisplayNameForPlayerField,
  getPlayerFieldForName,
  getRoundScoreValue,
} from './playerScores';

function roundToDisplay(value) {
  return typeof value === 'number' ? parseFloat(value.toFixed(2)) : value;
}

function isNumericScore(value) {
  return typeof value === 'number' && !Number.isNaN(value);
}

function normalizeCreatorName(name) {
  if (name === 'Dad') {
    return 'Dan';
  }
  if (name === 'Mom') {
    return 'Debi';
  }
  return name;
}

function getScoreFieldForCreator(name) {
  const normalizedName = normalizeCreatorName(name || '');
  return getPlayerFieldForName(normalizedName);
}

function getRoundCreatorNames(round) {
  return [round?.creator, round?.secondary_creator]
    .map(name => normalizeCreatorName(name || ''))
    .filter(Boolean);
}

function getSelectedJokerRounds(selectedRoundSelection) {
  if (Array.isArray(selectedRoundSelection)) {
    return [...new Set(
      selectedRoundSelection.filter(title => title && title !== 'Select')
    )].slice(0, 2);
  }

  if (selectedRoundSelection && selectedRoundSelection !== 'Select') {
    return [selectedRoundSelection];
  }

  return [];
}

function getJokerRoundWeight(selectedRoundTitles) {
  return selectedRoundTitles.length > 1 ? 0.5 : 1;
}

function playerMatchesCreator(roundCreator, player) {
  const playerName = getDisplayNameForPlayerField(player);
  if (playerName === 'Dan') {
    return roundCreator === 'Dad' || roundCreator === 'Dan';
  }
  if (playerName === 'Debi') {
    return roundCreator === 'Mom' || roundCreator === 'Debi';
  }
  return roundCreator === playerName;
}

function playerMatchesAnyCreator(round, player) {
  return getRoundCreatorNames(round).some(roundCreator => playerMatchesCreator(roundCreator, player));
}

export function getEffectiveRoundScore(scores, player, round) {
  const scoreMap = scores?.[player];
  if (scoreMap && Object.prototype.hasOwnProperty.call(scoreMap, round.title)) {
    return scoreMap[round.title];
  }
  return getRoundScoreValue(round, player);
}

export function getDisplayedRoundScore(scores, player, round) {
  return roundToDisplay(getEffectiveRoundScore(scores, player, round));
}

function getSelectedCreatorRoundMedian(rounds, player, selectedRoundTitle, medianScores) {
  if (!selectedRoundTitle || selectedRoundTitle === 'Select') {
    return null;
  }

  const selectedRoundIndex = (rounds || []).findIndex(round => {
    return round.title === selectedRoundTitle && playerMatchesAnyCreator(round, player);
  });
  if (selectedRoundIndex === -1) {
    return null;
  }

  const medianScore = medianScores?.[selectedRoundIndex];
  return isNumericScore(medianScore) ? medianScore : null;
}

export function getDisplayedJokerBonus(rounds, scores, player, selectedRoundSelection, medianScores) {
  const selectedRoundTitles = getSelectedJokerRounds(selectedRoundSelection);
  if (!selectedRoundTitles.length) {
    return null;
  }

  const roundWeight = getJokerRoundWeight(selectedRoundTitles);
  let total = 0;
  let hasValue = false;

  selectedRoundTitles.forEach(selectedRoundTitle => {
    const selectedCreatorMedian = getSelectedCreatorRoundMedian(rounds, player, selectedRoundTitle, medianScores);
    if (isNumericScore(selectedCreatorMedian)) {
      total += selectedCreatorMedian * roundWeight;
      hasValue = true;
      return;
    }

    const selectedRound = (rounds || []).find(round => round.title === selectedRoundTitle);
    if (!selectedRound) {
      return;
    }

    const score = getEffectiveRoundScore(scores, player, selectedRound);
    if (isNumericScore(score)) {
      total += score * roundWeight;
      hasValue = true;
    }
  });

  return hasValue ? roundToDisplay(total) : null;
}

function getCreatorBonusState(rounds, player, selectedRoundTitle, medianScores) {
  let total = 0;
  let hasValue = false;

  (rounds || [])
    .filter(round => playerMatchesAnyCreator(round, player))
    .forEach(round => {
      const medianScore = medianScores?.[rounds.indexOf(round)];
      if (isNumericScore(medianScore)) {
        total += medianScore;
        hasValue = true;
      }
    });

  return { total, hasValue };
}

export function getDisplayedCreatorBonus(rounds, player, selectedRoundTitle, medianScores) {
  const { total, hasValue } = getCreatorBonusState(rounds, player, selectedRoundTitle, medianScores);
  return hasValue ? roundToDisplay(total) : null;
}

function getDisplayedRoundTotalState(rounds, scores, player) {
  let total = 0;
  let hasValue = false;

  (rounds || []).forEach(round => {
    const score = getDisplayedRoundScore(scores, player, round);
    if (isNumericScore(score)) {
      total += score;
      hasValue = true;
    }
  });

  return { total, hasValue };
}

export function getSortableFinalTotal(rounds, scores, player, selectedRoundTitle, medianScores) {
  const displayedRoundTotal = (rounds || []).reduce((sum, round) => {
    const score = getDisplayedRoundScore(scores, player, round);
    return sum + (isNumericScore(score) ? score : 0);
  }, 0);

  const creatorBonus = getDisplayedCreatorBonus(rounds, player, selectedRoundTitle, medianScores);
  const jokerBonus = getDisplayedJokerBonus(rounds, scores, player, selectedRoundTitle, medianScores);

  return roundToDisplay(
    displayedRoundTotal +
    (isNumericScore(creatorBonus) ? creatorBonus : 0) +
    (isNumericScore(jokerBonus) ? jokerBonus : 0)
  ) || 0;
}

export function getDisplayedFinalTotal(rounds, scores, player, selectedRoundTitle, medianScores) {
  const roundTotalState = getDisplayedRoundTotalState(rounds, scores, player);
  const creatorBonusState = getCreatorBonusState(rounds, player, selectedRoundTitle, medianScores);
  const jokerBonus = getDisplayedJokerBonus(rounds, scores, player, selectedRoundTitle, medianScores);

  if (!roundTotalState.hasValue && !creatorBonusState.hasValue && !isNumericScore(jokerBonus)) {
    return null;
  }

  return roundToDisplay(
    roundTotalState.total +
    creatorBonusState.total +
    (isNumericScore(jokerBonus) ? jokerBonus : 0)
  );
}

export function clearCreatorScoreForRound(scores, players, roundTitle, newCreatorName) {
  const creatorNames = Array.isArray(newCreatorName) ? newCreatorName : [newCreatorName];
  const creatorFields = [...new Set(
    creatorNames
      .map(name => getScoreFieldForCreator(name))
      .filter(scoreField => scoreField && (players || []).includes(scoreField))
  )];

  if (!creatorFields.length) {
    return scores;
  }

  return creatorFields.reduce((nextScores, scoreField) => ({
    ...nextScores,
    [scoreField]: {
      ...(nextScores?.[scoreField] || {}),
      [roundTitle]: null,
    },
  }), scores);
}
