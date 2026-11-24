import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Âm thanh báo đúng / sai khi trả lời (góp ý người dùng thử 2026-10-26).
 *
 * Tổng hợp bằng Web Audio — không cần tải file âm thanh:
 *  - đúng: hai nốt đi lên (Đô–Mi cao), ngắn, sáng;
 *  - sai: một nốt trầm trượt xuống, nhẹ, không chói.
 * Bật/tắt nhớ trong localStorage của trình duyệt (chỉ là sở thích hiển thị,
 * không phải dữ liệu học).
 */

const STORAGE_KEY = 'lh.sound';

let ctx: AudioContext | null = null;

function audio(): AudioContext | null {
  if (typeof window === 'undefined') return null;
  const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  if (!ctx) ctx = new Ctor();
  if (ctx.state === 'suspended') void ctx.resume();
  return ctx;
}

function tone(ac: AudioContext, freq: number, start: number, duration: number, type: OscillatorType, peak: number, slideTo?: number) {
  const osc = ac.createOscillator();
  const gain = ac.createGain();
  osc.type = type;
  osc.frequency.setValueAtTime(freq, start);
  if (slideTo) osc.frequency.exponentialRampToValueAtTime(slideTo, start + duration);
  gain.gain.setValueAtTime(0.0001, start);
  gain.gain.exponentialRampToValueAtTime(peak, start + 0.015);
  gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
  osc.connect(gain).connect(ac.destination);
  osc.start(start);
  osc.stop(start + duration + 0.02);
}

export function playAnswerSound(correct: boolean): void {
  const ac = audio();
  if (!ac) return;
  const t = ac.currentTime + 0.01;
  if (correct) {
    tone(ac, 1046.5, t, 0.14, 'sine', 0.22);
    tone(ac, 1318.5, t + 0.09, 0.22, 'sine', 0.22);
  } else {
    tone(ac, 220, t, 0.28, 'triangle', 0.25, 150);
  }
}

function readEnabled(): boolean {
  try {
    return window.localStorage.getItem(STORAGE_KEY) !== 'off';
  } catch {
    return true;
  }
}

/** Trạng thái bật/tắt âm + hàm phát. Dùng chung cho mọi màn học. */
export function useAnswerSound() {
  const [enabled, setEnabled] = useState<boolean>(readEnabled);

  const toggle = useCallback(() => {
    setEnabled((on) => {
      const next = !on;
      try {
        window.localStorage.setItem(STORAGE_KEY, next ? 'on' : 'off');
      } catch {
        /* chế độ ẩn danh chặn localStorage — vẫn đổi được trong phiên này */
      }
      return next;
    });
  }, []);

  // Đọc lại localStorage lúc phát: nút tắt tiếng nằm ở khung phòng học, còn
  // nơi phát là trang con — hai hook khác nhau nhưng chung một công tắc.
  const play = useCallback((correct: boolean) => {
    if (readEnabled()) playAnswerSound(correct);
  }, []);

  return { enabled, toggle, play };
}

/**
 * Phát âm thanh một lần khi `result` chuyển từ chưa có (null/undefined) sang
 * đúng/sai — gắn thẳng vào trạng thái đã chấm của câu hỏi.
 */
export function useSoundOnResult(result: boolean | null | undefined, play: (correct: boolean) => void) {
  const prev = useRef(result);
  useEffect(() => {
    if ((prev.current === null || prev.current === undefined) && typeof result === 'boolean') play(result);
    prev.current = result;
  }, [result, play]);
}
