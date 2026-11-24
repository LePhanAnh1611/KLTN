import assert from 'node:assert/strict';
import test from 'node:test';
import { describeSetProgress } from '../src/utils/setProgress.ts';

test('chưa học gì thì mời bắt đầu, thanh trống', () => {
  const v = describeSetProgress({ total: 50, mastered: 0, learning: 0 });
  assert.equal(v.masteredPct, 0);
  assert.equal(v.learningPct, 0);
  assert.equal(v.fresh, 50);
  assert.match(v.hint, /bắt đầu/);  // 'Chưa học · bắt đầu vài từ thôi'
});

test('đã học nhưng chưa thuộc vẫn hiện trên thanh (không còn 0% vô nghĩa)', () => {
  const v = describeSetProgress({ total: 50, mastered: 0, learning: 20 });
  assert.equal(v.learningPct, 40);
  assert.equal(v.fresh, 30);
  assert.equal(v.done, false);
  assert.match(v.hint, /Còn 50 từ/);
  assert.doesNotMatch(v.hint, /sắp thuộc/);
});

test('mục tiêu chặng 80%: đếm ngược theo mục tiêu, có mốc trên thanh', () => {
  const v = describeSetProgress({ total: 50, mastered: 32, learning: 10, goal: 40 });
  assert.equal(v.goalPct, 80);
  assert.match(v.hint, /Còn 8 từ/);
  const done = describeSetProgress({ total: 50, mastered: 40, learning: 0, goal: 40 });
  assert.equal(done.done, true);
  assert.match(done.hint, /qua chặng/);
});

test('dữ liệu lệch (learning + mastered > total) bị kẹp, không tràn thanh', () => {
  const v = describeSetProgress({ total: 10, mastered: 8, learning: 9 });
  assert.equal(v.learning, 2);
  assert.ok(v.masteredPct + v.learningPct <= 100);
});

test('thuộc cả bộ', () => {
  const v = describeSetProgress({ total: 6, mastered: 6, learning: 0 });
  assert.equal(v.done, true);
  assert.match(v.hint, /cả bộ/);
});

test('câu gợi ý khớp thanh: chưa thuộc = đang học + chưa học, không ghi "sắp thuộc"', () => {
  const v = describeSetProgress({ total: 69, mastered: 10, learning: 46 });
  assert.equal(v.fresh, 13);
  assert.equal(v.hint, 'Còn 59 từ chưa thuộc · ôn 46 từ đang học trước');
});
