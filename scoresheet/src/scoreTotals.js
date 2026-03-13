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
  if (!normalizedName) {
    return '';
  }
  return `score_${normalizedName.charAt(0).toLowerCase()}${normalizedName.slice(1)}`;
}

function playerMatchesCreator(roundCreator, player) {
  const playerName = player.replace('score_', '').charAt(0).toUpperCase() + player.replace('score_', '').slice(1);
  if (playerName === 'Dan') {
    return roundCreator === 'Dad' || roundCreator === 'Dan';
  }
  if (playerName === 'Debi') {
    return roundCreator === 'Mom' || roundCreator === 'Debi';
  }
  return roundCreator === playerName;
}

export function getEffectiveRoundScore(scores, player, round) {
  const scoreMap = scores?.[player];
  if (scoreMap && Object.prototype.hasOwnProperty.call(scoreMap, round.title)) {
    return scoreMap[round.title];
  }
  return round[player] ?? null;
}

export function getDisplayedRoundScore(scores, player, round) {
  return roundToDisplay(getEffectiveRoundScore(scores, player, round));
}

export function getDisplayedJokerBonus(rounds, scores, player, selectedRoundTitle) {
  if (!selectedRoundTitle || selectedRoundTitle === 'Select') {
    return null;
  }

  const selectedRound = (rounds || []).find(round => round.title === selectedRoundTitle);
  if (!selectedRound) {
    return null;
  }

  const score = getEffectiveRoundScore(scores, player, selectedRound);
  return isNumericScore(score) ? roundToDisplay(score) : null;
}

function getCreatorBonusState(rounds, player, selectedRoundTitle, medianScores) {
  let total = 0;
  let hasValue = false;

  (rounds || [])
    .filter(round => playerMatchesCreator(round.creator, player))
    .forEach(round => {
      if (selectedRoundTitle === round.title) {
        return;
      }

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
  const jokerBonus = getDisplayedJokerBonus(rounds, scores, player, selectedRoundTitle);

  return roundToDisplay(
    displayedRoundTotal +
    (isNumericScore(creatorBonus) ? creatorBonus : 0) +
    (isNumericScore(jokerBonus) ? jokerBonus : 0)
  ) || 0;
}

export function getDisplayedFinalTotal(rounds, scores, player, selectedRoundTitle, medianScores) {
  const roundTotalState = getDisplayedRoundTotalState(rounds, scores, player);
  const creatorBonusState = getCreatorBonusState(rounds, player, selectedRoundTitle, medianScores);
  const jokerBonus = getDisplayedJokerBonus(rounds, scores, player, selectedRoundTitle);

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
  const scoreField = getScoreFieldForCreator(newCreatorName);
  if (!scoreField || !(players || []).includes(scoreField)) {
    return scores;
  }

  return {
    ...scores,
    [scoreField]: {
      ...(scores?.[scoreField] || {}),
      [roundTitle]: null,
    },
  };
}
