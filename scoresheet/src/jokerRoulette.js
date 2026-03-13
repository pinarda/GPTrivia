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
    minDelay = 35,
    maxDelay = 820,
    easingPower = 1.9,
    fastDurationMs = 1500,
    slowdownCycles = 1,
  } = {},
) {
  if (!Array.isArray(roundTitles) || roundTitles.length === 0 || finalIndex == null) {
    return [];
  }

  const normalizedFinalIndex = Math.max(0, Math.min(finalIndex, roundTitles.length - 1));
  const fastSteps = Math.max(roundTitles.length, Math.round(fastDurationMs / minDelay));
  const baseSlowdownSteps = Math.max(
    roundTitles.length,
    Math.ceil(roundTitles.length * slowdownCycles),
  );
  const baseSteps = fastSteps + baseSlowdownSteps;
  const remainderNeeded = (
    normalizedFinalIndex - ((baseSteps - 1) % roundTitles.length) + roundTitles.length
  ) % roundTitles.length;
  const totalSteps = baseSteps + remainderNeeded;
  const slowdownStepCount = Math.max(1, totalSteps - fastSteps);

  return Array.from({ length: totalSteps }, (_, stepIndex) => {
    const isFastPhase = stepIndex < fastSteps;
    const slowdownIndex = Math.max(0, stepIndex - fastSteps);
    const progress = slowdownStepCount <= 1 ? 1 : slowdownIndex / (slowdownStepCount - 1);
    const easedProgress = Math.pow(progress, easingPower);

    return {
      title: roundTitles[stepIndex % roundTitles.length],
      delay: isFastPhase
        ? minDelay
        : Math.round(minDelay + easedProgress * (maxDelay - minDelay)),
    };
  });
}
