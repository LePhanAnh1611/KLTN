import assert from 'node:assert/strict';
import test from 'node:test';
import { splitRoadmapStages } from '../src/utils/roadmap.ts';

test('C1 roadmap excludes lower levels even if API omits skipped flags', () => {
  const stages = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'].map((cefr_level, index) => ({
    id: index, title: cefr_level, cefr_level, order_index: 1,
    word_set_id: index, state: 'locked' as const, progress_pct: 0,
    items_mastered: 0, items_total: 50, is_recommended: false,
    user_word_set_id: null,
    // Reproduce the response from a backend without the new field.
    is_skipped: undefined as unknown as boolean,
  }));
  const { personalStages, skippedStages } = splitRoadmapStages(stages, 'C1');
  assert.deepEqual(personalStages.map((stage) => stage.cefr_level), ['C1', 'C2']);
  assert.deepEqual(skippedStages.map((stage) => stage.cefr_level), ['A1', 'A2', 'B1', 'B2']);
  assert.equal(personalStages[0].cefr_level, 'C1');
  assert.equal(personalStages.length, 2);
  assert.equal(splitRoadmapStages(stages, 'A1').personalStages.length, 6);
  assert.equal(splitRoadmapStages(stages, 'C2').personalStages.length, 1);
});
