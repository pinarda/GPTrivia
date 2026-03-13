export const JOKER_RANDOMIZE_VALUE = '__JOKER_RANDOMIZE__';

export function pickJokerRouletteIndex(roundTitles, randomFn = Math.random) {
  if (!Array.isArray(roundTitles) || roundTitles.length === 0) {
    return null;
  }

  const boundedRandom = Math.min(Math.max(randomFn(), 0), 0.999999999);
  return Math.floor(boundedRandom * roundTitles.length);
}

export function buildJokerRouletteSequence(
  roundTitles,
  finalIndex,
  {
    fullCycles = 2,
    minDelay = 35,
    maxDelay = 960,
    easingPower = 2.05,
  } = {},
) {
  if (!Array.isArray(roundTitles) || roundTitles.length === 0 || finalIndex == null) {
    return [];
  }

  const normalizedFinalIndex = Math.max(0, Math.min(finalIndex, roundTitles.length - 1));
  const totalSteps = fullCycles * roundTitles.length + normalizedFinalIndex + 1;

  return Array.from({ length: totalSteps }, (_, stepIndex) => {
    const progress = totalSteps <= 1 ? 1 : stepIndex / (totalSteps - 1);
    const easedProgress = Math.pow(progress, easingPower);

    return {
      title: roundTitles[stepIndex % roundTitles.length],
      delay: Math.round(minDelay + easedProgress * (maxDelay - minDelay)),
    };
  });
}
