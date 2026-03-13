import {
  applyPatchToPresentationSnapshot,
  applyPatchToRoundSnapshot,
  buildScoresheetPatch,
  shouldIgnoreScoresheetMessage,
} from './sync';
import {
  getCrownTheme,
  getCrownStreak,
  getDisplayNameForPlayer,
  getInheritedCrownedWinner,
  getPlayerFieldForName,
} from './crown';
import { DEFAULT_VISIBLE_PLAYERS } from './defaultPlayers';
import {
  resolveJokerRoundIndices,
  resolvePresentationPlayers,
} from './presentationData';
import {
  buildJokerRouletteSequence,
  JOKER_RANDOMIZE_VALUE,
  pickJokerRouletteIndex,
} from './jokerRoulette';
import {
  getPlayerIconUrl,
  readPlayerIconMap,
} from './playerIcons';
import {
  extractPlayersFromRounds,
  getDisplayNameForPlayerField,
  getRoundExtraScores,
  getPlayerStorageKey,
  removePlayerFromRound,
} from './playerScores';
import {
  getNormalizedStylePoints,
  getStylePointTheme,
  getStylePointTier,
  hasStylePointAward,
  incrementStylePoint,
  setStylePointValue,
} from './stylePoints';
import {
  clearCreatorScoreForRound,
  getDisplayedCreatorBonus,
  getDisplayedFinalTotal,
  getDisplayedJokerBonus,
  getDisplayedRoundScore,
  getSortableFinalTotal,
} from './scoreTotals';

describe('scoresheet sync helpers', () => {
  test('buildScoresheetPatch only includes changed round and presentation fields', () => {
    const state = {
      rounds: [
        {
          id: 1,
          title: 'Round 1',
          creator: 'Alex',
          major_category: 'Science',
          minor_category1: 'Physics',
          minor_category2: 'Space',
          date: '2026-03-12',
          round_number: 1,
          max_score: 10,
          replay: false,
          cooperative: false,
          notes: '',
          link: 'https://example.com/round-1',
          score_alex: 5,
          score_megan: 7,
        },
      ],
      roundCreators: { 'Round 1': 'Alex' },
      selectedMajorCategories: { 'Round 1': 'Science' },
      selectedMinor1Categories: { 'Round 1': 'Physics' },
      selectedMinor2Categories: { 'Round 1': 'Space' },
      maxScores: { 'Round 1': 10 },
      isReplay: { 'Round 1': false },
      cooperativeStatus: { 'Round 1': false },
      scores: {
        score_alex: { 'Round 1': 8.5 },
        score_megan: { 'Round 1': 7 },
      },
      selectedRounds: { score_alex: 'Round 1' },
      players: ['score_alex', 'score_megan'],
      host: 'Jenny',
      scorekeeper: 'Megan',
      tiebreakWinner: '',
      notes: 'Updated notes',
      stylePoints: { Alex: 1.5 },
      selectedDate: '2026-03-12',
      serverRoundSnapshot: {
        1: {
          creator: 'Alex',
          title: 'Round 1',
          major_category: 'Science',
          minor_category1: 'Physics',
          minor_category2: 'Space',
          date: '2026-03-12',
          round_number: 1,
          max_score: 10,
          replay: false,
          cooperative: false,
          notes: '',
          link: 'https://example.com/round-1',
          score_alex: 5,
          score_megan: 7,
          score_ichigo: null,
          score_jenny: null,
          score_zach: null,
          score_debi: null,
          score_dan: null,
          score_chris: null,
          score_drew: null,
          score_tom: null,
          score_jeff: null,
          score_paige: null,
          score_dillon: null,
          extra_scores: {},
        },
      },
      serverPresentationSnapshot: {
        round_names: ['Round 1'],
        creator_list: ['Alex'],
        joker_round_indices: {},
        player_list: { score_alex: 'score_alex', score_megan: 'score_megan' },
        host: 'Alex',
        scorekeeper: 'Megan',
        tiebreak_winner: '',
        crowned_winner: '',
        notes: '',
        style_points: {},
      },
    };

    expect(buildScoresheetPatch(state)).toEqual({
      round_updates: [
        {
          id: 1,
          fields: {
            score_alex: 8.5,
          },
        },
      ],
      presentation_updates: {
        host: 'Jenny',
        joker_round_indices: { alex: 'Round 1' },
        notes: 'Updated notes',
        style_points: { Alex: 1.5 },
      },
      selected_date: '2026-03-12',
    });
  });

  test('shouldIgnoreScoresheetMessage only ignores matching sender and mutation ids', () => {
    const pendingMutationIds = new Set(['mutation-1']);

    expect(
      shouldIgnoreScoresheetMessage(
        { client_id: 'client-1', mutation_id: 'mutation-1' },
        'client-1',
        pendingMutationIds,
      ),
    ).toBe(true);

    expect(
      shouldIgnoreScoresheetMessage(
        { client_id: 'client-2', mutation_id: 'mutation-1' },
        'client-1',
        pendingMutationIds,
      ),
    ).toBe(false);

    expect(
      shouldIgnoreScoresheetMessage(
        { client_id: 'client-1', mutation_id: 'mutation-2' },
        'client-1',
        pendingMutationIds,
      ),
    ).toBe(false);
  });

  test('applyPatch helpers merge updates into stored snapshots', () => {
    const nextRoundSnapshot = applyPatchToRoundSnapshot(
      {
        1: { title: 'Round 1', score_alex: 5 },
      },
      [
        { id: 1, fields: { score_alex: 8.5 } },
        { id: 2, fields: { title: 'Round 2', score_megan: 7 } },
      ],
    );
    const nextPresentationSnapshot = applyPatchToPresentationSnapshot(
      {
        host: 'Alex',
        style_points: {},
      },
      {
        host: 'Jenny',
        style_points: { Alex: '1.5' },
      },
    );

    expect(nextRoundSnapshot).toEqual({
      1: { title: 'Round 1', score_alex: 8.5 },
      2: { title: 'Round 2', score_megan: 7 },
    });
    expect(nextPresentationSnapshot.host).toBe('Jenny');
    expect(nextPresentationSnapshot.style_points).toEqual({ Alex: 1.5 });
  });
});

describe('scoresheet crown helpers', () => {
  test('uses the immediately previous presentation for the inherited crown', () => {
    expect(
      getInheritedCrownedWinner(
        [
          { name: '03.10.2026', crowned_winner: 'Alex' },
          { name: '03.11.2026', crowned_winner: 'Megan' },
          { name: '03.12.2026', crowned_winner: '' },
        ],
        '2026-03-12',
      ),
    ).toBe('Megan');
  });

  test('matches crowned winners to score fields case-insensitively', () => {
    expect(getPlayerFieldForName(['score_alex', 'score_megan'], 'mEgAn')).toBe('score_megan');
    expect(getDisplayNameForPlayer('score_alex')).toBe('Alex');
  });

  test('shows the inherited streak before the current night is crowned', () => {
    expect(
      getCrownStreak(
        [
          { name: '03.10.2026', crowned_winner: 'Megan' },
          { name: '03.11.2026', crowned_winner: 'Megan' },
          { name: '03.12.2026', crowned_winner: '' },
        ],
        '2026-03-12',
        'Megan',
        '',
      ),
    ).toBe(2);
  });

  test('extends the streak once the current night is explicitly crowned', () => {
    expect(
      getCrownStreak(
        [
          { name: '03.10.2026', crowned_winner: 'Megan' },
          { name: '03.11.2026', crowned_winner: 'Megan' },
          { name: '03.12.2026', crowned_winner: 'Megan' },
        ],
        '2026-03-12',
        'Megan',
        'Megan',
      ),
    ).toBe(3);
  });

  test('computes the streak for an explicitly crowned past night so the historic crown tier matches', () => {
    const streak = getCrownStreak(
      [
        { name: '03.10.2026', crowned_winner: 'Alex' },
        { name: '03.11.2026', crowned_winner: 'Alex' },
        { name: '03.12.2026', crowned_winner: 'Alex' },
        { name: '03.13.2026', crowned_winner: '' },
      ],
      '2026-03-12',
      'Alex',
      'Alex',
    );

    expect(streak).toBe(3);
    expect(getCrownTheme(streak).fill).toBe('#f3bc34');
  });

  test('maps streak tiers to bronze, silver, gold, and diamond crown themes', () => {
    expect(getCrownTheme(1).fill).toBe('#d39a6a');
    expect(getCrownTheme(1).textFill).toBe('#111111');
    expect(getCrownTheme(2).fill).toBe('#d6e9f5');
    expect(getCrownTheme(2).trim).toBe('#ffffff');
    expect(getCrownTheme(3).fill).toBe('#f3bc34');
    expect(getCrownTheme(3).trim).toBe('#fff6c8');
    expect(getCrownTheme(4).fill).toBe('#7edcff');
    expect(getCrownTheme(4).sparkle).toBe('#ffffff');
  });
});

describe('scoresheet player defaults', () => {
  test('only shows the default eight players before saved data expands the roster', () => {
    expect(DEFAULT_VISIBLE_PLAYERS).toEqual([
      'score_alex',
      'score_ichigo',
      'score_megan',
      'score_zach',
      'score_jenny',
      'score_debi',
      'score_dan',
      'score_chris',
    ]);
  });

  test('hydrates player and joker data from object payloads', () => {
    expect(
      resolvePresentationPlayers(
        { score_alex: 'score_alex', score_megan: 'score_megan' },
        DEFAULT_VISIBLE_PLAYERS,
      ),
    ).toEqual(['score_alex', 'score_megan']);

    expect(
      resolveJokerRoundIndices({ alex: 'Round 1', megan: 'Round 2' }),
    ).toEqual({ alex: 'Round 1', megan: 'Round 2' });
  });

  test('normalizes saved arbitrary player names into score fields', () => {
    expect(
      resolvePresentationPlayers(
        { 'Sam Guest': 'Sam Guest', score_alex: 'score_alex' },
        DEFAULT_VISIBLE_PLAYERS,
      ),
    ).toEqual(['score_sam guest', 'score_alex']);
  });

  test('preserves a saved empty-night roster instead of restoring default players', () => {
    expect(
      resolvePresentationPlayers(
        { score_alex: 'score_alex', score_megan: 'score_megan' },
        DEFAULT_VISIBLE_PLAYERS,
      ),
    ).toEqual(['score_alex', 'score_megan']);
  });

  test('only infers players from rounds when they actually have stored scores', () => {
    expect(
      extractPlayersFromRounds([
        { title: 'Round 1', score_alex: null, score_guest: null },
        { title: 'Round 2', score_alex: 5, extra_scores: { score_guest: 8 } },
      ]),
    ).toEqual(['score_alex', 'score_guest']);
  });

  test('parses stringified extra_scores and ignores invalid ghost keys', () => {
    expect(
      getRoundExtraScores({
        extra_scores: "{'score_bobo the dodo': 8, '0': '{', '1': '}'}",
      }),
    ).toEqual({
      'score_bobo the dodo': 8,
    });
  });

  test('removing a player clears their stored scores for the night', () => {
    expect(
      removePlayerFromRound(
        {
          title: 'Round 1',
          score_alex: 6,
          score_guest: 9,
          extra_scores: { score_guest: 9 },
        },
        'score_guest',
      ),
    ).toEqual({
      title: 'Round 1',
      score_alex: 6,
      extra_scores: {},
    });

    expect(
      removePlayerFromRound(
        {
          title: 'Round 1',
          score_alex: 6,
          extra_scores: {},
        },
        'score_alex',
      ),
    ).toEqual({
      title: 'Round 1',
      score_alex: null,
      extra_scores: {},
    });
  });

  test('uses the same player storage keys for joker hydration as save payloads', () => {
    expect(getPlayerStorageKey('score_alex')).toBe('alex');
    expect(getPlayerStorageKey('score_sam guest')).toBe('sam guest');
    expect(getDisplayNameForPlayerField('score_sam guest')).toBe('Sam Guest');
  });
});

describe('scoresheet player icon helpers', () => {
  test('reads the embedded icon map from the DOM', () => {
    document.body.innerHTML = '<script id="scoresheet-player-icons" type="application/json">{\"Alex\":\"/media/profile_icons/alex_icon.png\"}</script>';

    expect(readPlayerIconMap(document)).toEqual({
      Alex: '/media/profile_icons/alex_icon.png',
    });
  });

  test('resolves a player icon by field name or display name', () => {
    const iconMap = {
      Alex: '/media/profile_icons/alex_icon.png',
    };

    expect(getPlayerIconUrl(iconMap, 'score_alex')).toBe('/media/profile_icons/alex_icon.png');
    expect(getPlayerIconUrl(iconMap, 'Alex')).toBe('/media/profile_icons/alex_icon.png');
    expect(getPlayerIconUrl(iconMap, 'score_unknown')).toBe('');
  });
});

describe('scoresheet joker roulette helpers', () => {
  test('keeps a stable randomize sentinel value', () => {
    expect(JOKER_RANDOMIZE_VALUE).toBe('__JOKER_RANDOMIZE__');
  });

  test('picks a valid roulette index from the available rounds', () => {
    expect(pickJokerRouletteIndex(['Round 1', 'Round 2', 'Round 3'], () => 0)).toBe(0);
    expect(pickJokerRouletteIndex(['Round 1', 'Round 2', 'Round 3'], () => 0.61)).toBe(1);
    expect(pickJokerRouletteIndex(['Round 1', 'Round 2', 'Round 3'], () => 0.99)).toBe(2);
    expect(pickJokerRouletteIndex([], () => 0.4)).toBeNull();
  });

  test('builds a slowing roulette sequence that lands on the requested round', () => {
    const sequence = buildJokerRouletteSequence(
      ['Round 1', 'Round 2', 'Round 3'],
      1,
      { minDelay: 50, maxDelay: 200, fastDurationMs: 150, slowdownCycles: 1 },
    );

    expect(sequence.slice(0, 3).map(step => step.title)).toEqual([
      'Round 1',
      'Round 2',
      'Round 3',
    ]);
    expect(sequence.slice(0, 3).every(step => step.delay === 50)).toBe(true);
    expect(sequence[0].delay).toBeLessThan(sequence[sequence.length - 1].delay);
    expect(sequence[sequence.length - 1].title).toBe('Round 2');
  });

  test('default roulette timing keeps a short fast phase and then slows down gradually', () => {
    const sequence = buildJokerRouletteSequence(['Round 1', 'Round 2', 'Round 3'], 2);

    expect(sequence.slice(0, 14).every(step => step.delay <= 40)).toBe(true);
    const firstSlowdownStep = sequence.find(step => step.delay > 35);
    expect(firstSlowdownStep).toBeDefined();
    expect(firstSlowdownStep.delay).toBeLessThan(90);
    expect(sequence.length).toBeGreaterThan(22);
    expect(sequence.length).toBeLessThan(28);
    expect(sequence[sequence.length - 1].delay).toBeGreaterThanOrEqual(680);
    expect(sequence[sequence.length - 1].delay).toBeLessThanOrEqual(740);
    expect(sequence[sequence.length - 1].title).toBe('Round 3');
  });
});

describe('scoresheet style point helpers', () => {
  test('normalizes stored style points to display names and numbers', () => {
    expect(
      getNormalizedStylePoints({
        'score_alex': '1',
        'bobo the dodo': '2.5',
        Unknown: '',
      }),
    ).toEqual({
      Alex: 1,
      'Bobo The Dodo': 2.5,
    });
  });

  test('incrementing a style point awards and preserves the running total', () => {
    expect(incrementStylePoint({ Alex: 1 }, 'score_alex')).toEqual({ Alex: 2 });
    expect(incrementStylePoint({}, 'bobo the dodo')).toEqual({ 'Bobo The Dodo': 1 });
  });

  test('setting and clearing style point values keeps award visibility in sync', () => {
    const withAward = setStylePointValue({}, 'score_alex', '1.5');
    expect(withAward).toEqual({ Alex: 1.5 });
    expect(hasStylePointAward(withAward, 'score_alex')).toBe(true);

    const withoutAward = setStylePointValue(withAward, 'Alex', '');
    expect(withoutAward).toEqual({});
    expect(hasStylePointAward(withoutAward, 'score_alex')).toBe(false);
  });

  test('maps style point totals to red, gold, and on-fire sunglasses tiers', () => {
    expect(getStylePointTier(1)).toBe('red');
    expect(getStylePointTier(2)).toBe('gold');
    expect(getStylePointTier(3)).toBe('fire');

    expect(getStylePointTheme({ Alex: 1 }, 'score_alex').frameFill).toBe('#d91e35');
    expect(getStylePointTheme({ Alex: 2 }, 'score_alex').frameFill).toBe('#e9bb35');
    expect(getStylePointTheme({ Alex: 3 }, 'score_alex').flame).toBe(true);
  });
});

describe('scoresheet total helpers', () => {
  test('displayed total matches displayed row values and bonuses', () => {
    const rounds = [
      { title: 'Round 1', creator: 'Megan', score_alex: 0.335 },
      { title: 'Round 2', creator: 'Alex', score_alex: 1.555 },
      { title: 'Round 3', creator: 'Jenny', score_alex: 2.005 },
    ];
    const scores = {
      score_alex: {
        'Round 1': 0.335,
        'Round 2': 1.555,
        'Round 3': 2.005,
      },
    };
    const medianScores = [0.444, 0.888, 0.111];

    const displayedRoundSum = rounds.reduce(
      (sum, round) => sum + getDisplayedRoundScore(scores, 'score_alex', round),
      0,
    );
    const displayedJokerBonus = getDisplayedJokerBonus(rounds, scores, 'score_alex', 'Round 3');
    const displayedCreatorBonus = getDisplayedCreatorBonus(rounds, 'score_alex', 'Round 3', medianScores);

    expect(getDisplayedFinalTotal(rounds, scores, 'score_alex', 'Round 3', medianScores)).toBe(
      parseFloat((displayedRoundSum + displayedJokerBonus + displayedCreatorBonus).toFixed(2)),
    );
  });

  test('blank nights stay blank in creator bonus and total cells', () => {
    const rounds = [
      { title: 'Round 1', creator: 'Megan', score_alex: null },
      { title: 'Round 2', creator: 'Jenny', score_alex: null },
    ];
    const scores = {
      score_alex: {
        'Round 1': null,
        'Round 2': null,
      },
    };

    expect(getDisplayedCreatorBonus(rounds, 'score_alex', 'Select', [null, null])).toBeNull();
    expect(getDisplayedFinalTotal(rounds, scores, 'score_alex', 'Select', [null, null])).toBeNull();
    expect(getSortableFinalTotal(rounds, scores, 'score_alex', 'Select', [null, null])).toBe(0);
  });

  test('actual entered zeroes still display as zero', () => {
    const rounds = [
      { title: 'Round 1', creator: 'Alex', score_alex: 0 },
    ];
    const scores = {
      score_alex: {
        'Round 1': 0,
      },
    };

    expect(getDisplayedCreatorBonus(rounds, 'score_alex', 'Select', [0])).toBe(0);
    expect(getDisplayedJokerBonus(rounds, scores, 'score_alex', 'Round 1')).toBe(0);
    expect(getDisplayedFinalTotal(rounds, scores, 'score_alex', 'Round 1', [0])).toBe(0);
  });

  test('duplicate titles still produce a total that matches the visible cells', () => {
    const rounds = [
      { title: 'Shared Title', creator: 'Megan', score_alex: 1 },
      { title: 'Shared Title', creator: 'Jenny', score_alex: 5 },
    ];
    const scores = {
      score_alex: {
        'Shared Title': 4,
      },
    };

    expect(getDisplayedRoundScore(scores, 'score_alex', rounds[0])).toBe(4);
    expect(getDisplayedRoundScore(scores, 'score_alex', rounds[1])).toBe(4);
    expect(getDisplayedFinalTotal(rounds, scores, 'score_alex', 'Select', [])).toBe(8);
  });

  test('creator change clears the transformed creator score for tracked players', () => {
    expect(
      clearCreatorScoreForRound(
        {
          score_dan: { 'Round 1': 7 },
          score_alex: { 'Round 1': 5 },
        },
        ['score_alex', 'score_dan'],
        'Round 1',
        'Dad',
      ),
    ).toEqual({
      score_dan: { 'Round 1': null },
      score_alex: { 'Round 1': 5 },
    });
  });
});
