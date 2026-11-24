import { useCallback, useEffect, useState } from 'react';

/** UC-29 — phát âm bằng Web Speech API của trình duyệt (không cần dịch vụ ngoài).
 *
 * E1: trình duyệt không hỗ trợ -> `supported = false`, nơi gọi ẩn/khóa nút loa.
 *
 * Bug #6: bỏ nút Chậm/Vừa/Nhanh — với giọng máy của trình duyệt ba mức nghe gần
 * như không khác nhau nên chỉ gây rối. Đọc ở một tốc độ cố định, hơi chậm hơn
 * mặc định cho người học.
 *
 * Bug #11: hội thoại cần giọng khớp giới tính nhân vật (Emma là nữ). Web Speech
 * API không có trường giới tính cho giọng, nên chọn theo tên giọng phổ biến của
 * Windows/Chrome/Edge/macOS; không tìm được thì chỉnh cao độ cho gần đúng.
 */

const SPEECH_RATE = 0.85;
/** Khóa cũ của bộ chọn tốc độ — dọn đi để không còn rác trong localStorage. */
const LEGACY_RATE_KEY = 'dkt-speech-rate';

export type VoiceGender = 'female' | 'male';

export interface SpeakOptions {
  /** Giới tính giọng mong muốn. Bỏ trống = giọng tiếng Anh mặc định. */
  gender?: VoiceGender;
}

// Tên giọng (chữ thường) theo giới tính, gom từ các giọng có sẵn trên Windows
// (Microsoft *), Chrome (Google *), Edge (giọng Online Natural) và macOS.
const FEMALE_HINTS = [
  'female', 'woman', 'zira', 'aria', 'jenny', 'michelle', 'ana', 'emma', 'ava',
  'sonia', 'libby', 'maisie', 'natasha', 'clara', 'hazel', 'susan', 'catherine',
  'heather', 'linda', 'samantha', 'karen', 'moira', 'tessa', 'victoria', 'fiona',
  'serena', 'allison', 'kate', 'google us english',
];
const MALE_HINTS = [
  'male', 'man', 'david', 'mark', 'guy', 'davis', 'tony', 'jason', 'christopher',
  'eric', 'brian', 'andrew', 'roger', 'steffan', 'ryan', 'thomas', 'william',
  'george', 'richard', 'james', 'daniel', 'alex', 'fred', 'tom', 'oliver', 'rishi',
];

function matches(name: string, hints: string[]): boolean {
  // So khớp theo từ để 'emma' không dính vào tên khác, và 'male' không dính 'female'
  const words = name.toLowerCase().replace(/[^a-z ]/g, ' ').split(/\s+/);
  const joined = ` ${words.join(' ')} `;
  return hints.some((h) => joined.includes(` ${h} `));
}

function isSupported(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window;
}

/** Ưu tiên giọng tiếng Anh (en-US trước) đúng giới tính; không có thì để trình duyệt tự chọn. */
function pickEnglishVoice(gender?: VoiceGender): SpeechSynthesisVoice | null {
  const english = window.speechSynthesis
    .getVoices()
    .filter((v) => v.lang?.toLowerCase().startsWith('en'))
    .sort((a, b) => Number(b.lang === 'en-US') - Number(a.lang === 'en-US'));
  if (!english.length) return null;
  if (!gender) return english[0];

  const own = gender === 'female' ? FEMALE_HINTS : MALE_HINTS;
  const other = gender === 'female' ? MALE_HINTS : FEMALE_HINTS;
  return (
    english.find((v) => matches(v.name, own) && !matches(v.name, other))
    ?? english.find((v) => matches(v.name, own))
    ?? null
  );
}

export function useSpeech() {
  const supported = isSupported();
  const [speaking, setSpeaking] = useState(false);

  // Danh sách giọng nạp bất đồng bộ ở một số trình duyệt
  useEffect(() => {
    if (!supported) return;
    try { window.localStorage.removeItem(LEGACY_RATE_KEY); } catch { /* bỏ qua */ }
    const warm = () => window.speechSynthesis.getVoices();
    warm();
    window.speechSynthesis.addEventListener('voiceschanged', warm);
    return () => window.speechSynthesis.removeEventListener('voiceschanged', warm);
  }, [supported]);

  // Dừng đọc khi rời trang, tránh tiếng còn vang sang màn khác
  useEffect(() => () => {
    if (isSupported()) window.speechSynthesis.cancel();
  }, []);

  const speak = useCallback((text: string, options: SpeakOptions = {}) => {
    if (!supported || !text.trim()) return;

    window.speechSynthesis.cancel();          // bấm liên tiếp thì đọc câu mới
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    utterance.rate = SPEECH_RATE;

    const voice = pickEnglishVoice(options.gender);
    if (voice) {
      utterance.voice = voice;
      utterance.lang = voice.lang;
    } else if (options.gender) {
      // Máy không có giọng đúng giới tính: đổi cao độ để ít nhất nghe gần vai hơn
      const fallback = pickEnglishVoice();
      if (fallback) utterance.voice = fallback;
      utterance.pitch = options.gender === 'female' ? 1.4 : 0.8;
    }

    utterance.onstart = () => setSpeaking(true);
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);

    window.speechSynthesis.speak(utterance);
  }, [supported]);

  const stop = useCallback(() => {
    if (supported) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
    }
  }, [supported]);

  return { supported, speak, stop, speaking };
}
