import {
  applyPatchToPresentationSnapshot,
  applyPatchToRoundSnapshot,
  buildScoresheetPatch,
  shouldIgnoreScoresheetMessage,
} from './sync';
import {
  getDisplayNameForPlayer,
  getInheritedCrownedWinner,
  getPlayerFieldForName,
} from './crown';
import { DEFAULT_VISIBLE_PLAYERS } from './defaultPlayers';
import {
  clearCreatorScoreForRound,
  getDisplayedCreatorBonus,
  getDisplayedFinalTotal,
  getDisplayedJokerBonus,
  getDisplayedRoundScore,
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
