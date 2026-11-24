import type { AnswerInput } from '../../types/session';

/** Keep failed requests (with the same id) and preserve DKT interaction order. */
export class AnswerQueue {
  private tasks: AnswerInput[] = [];
  private running: Promise<void> | null = null;
  private send: (answer: AnswerInput) => Promise<unknown>;
  private changed: (pending: number) => void;

  constructor(send: (answer: AnswerInput) => Promise<unknown>, changed = (_pending: number) => {}) {
    this.send = send;
    this.changed = changed;
  }

  enqueue(answer: AnswerInput): void {
    this.tasks.push({ ...answer, client_answer_id: answer.client_answer_id ?? crypto.randomUUID() });
    this.changed(this.tasks.length);
  }

  flush(): Promise<void> {
    // A caller may enqueue just after drain's last await, before its finally
    // clears running. Recheck after that promise instead of missing the tail.
    if (this.running) return this.running.then(() => this.flush());
    this.running = this.drain().finally(() => { this.running = null; });
    return this.running;
  }

  private async drain(): Promise<void> {
    while (this.tasks.length) {
      await this.send(this.tasks[0]);
      this.tasks.shift();
      this.changed(this.tasks.length);
    }
  }
}
