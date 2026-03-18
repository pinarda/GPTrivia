export function getScoreCellJokerAction(currentJokerRounds, roundTitle, secondaryJokerMode = false) {
  const normalizedRounds = Array.isArray(currentJokerRounds)
    ? currentJokerRounds.filter(Boolean)
    : [];
  const roundIsJoker = Boolean(roundTitle && normalizedRounds.includes(roundTitle));

  if (roundIsJoker) {
    return {
      label: 'Clear Joker',
      mode: 'clear',
    };
  }

  if (secondaryJokerMode && normalizedRounds.length === 1) {
    return {
      label: 'Add as 2nd Joker',
      mode: 'secondary',
    };
  }

  if (secondaryJokerMode && normalizedRounds.length >= 2) {
    return {
      label: 'Replace 2nd Joker',
      mode: 'secondary',
    };
  }

  return {
    label: 'Set as Joker',
    mode: 'primary',
  };
}
