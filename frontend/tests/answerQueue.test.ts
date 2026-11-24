import assert from 'node:assert/strict';
import test from 'node:test';
import { AnswerQueue } from '../src/components/games/answerQueue.ts';

test('completion waits for every answer, including one added during a request', async () => {
  let release!: () => void;
  const gate = new Promise<void>((resolve) => { release = resolve; });
  const sent: number[] = [];
  const queue = new AnswerQueue(async (answer) => {
    if (!sent.length) await gate;
    sent.push(answer.item_id);
  });
  queue.enqueue({ item_id: 1, is_correct: false });
  const draining = queue.flush();
  queue.enqueue({ item_id: 2, is_correct: true });
  let completed = false;
  const finish = queue.flush().then(() => { completed = true; });
  await Promise.resolve();
  assert.equal(completed, false);
  release();
  await Promise.all([draining, finish]);
  assert.deepEqual(sent, [1, 2]);
  assert.equal(completed, true);
});

test('lost responses keep the same answer id on retry and preserve order', async () => {
  const sent: string[] = [];
  let fail = true;
  const pending: number[] = [];
  const queue = new AnswerQueue(async (answer) => {
    sent.push(answer.client_answer_id!);
    if (fail) { fail = false; throw new Error('lost response'); }
  }, (count) => pending.push(count));
  queue.enqueue({ item_id: 1, is_correct: false });
  queue.enqueue({ item_id: 2, is_correct: true });
  await assert.rejects(queue.flush(), /lost response/);
  assert.equal(pending.at(-1), 2);
  await queue.flush();
  assert.equal(sent[0], sent[1]);
  assert.notEqual(sent[1], sent[2]);
  assert.equal(pending.at(-1), 0);
});

test('a tail enqueued between drain and finally is included in flush', async () => {
  const sent: number[] = [];
  const queue = new AnswerQueue(async (answer) => { sent.push(answer.item_id); });
  queue.enqueue({ item_id: 1, is_correct: true });
  const first = queue.flush();
  // The drain continuation finishes before its finally clears running.
  await Promise.resolve();
  queue.enqueue({ item_id: 2, is_correct: false });
  await queue.flush();
  await first;
  assert.deepEqual(sent, [1, 2]);
});
