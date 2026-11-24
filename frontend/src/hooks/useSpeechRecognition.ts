import { useCallback, useEffect, useRef, useState } from 'react';

/** Bao bọc Web Speech API (SpeechRecognition) để chấm phát âm.
 *
 * Chỉ Chrome/Edge hỗ trợ (bản có tiền tố `webkit`); Firefox thì không — nơi gọi
 * phải xử lý `supported = false`. Cần quyền micro và trang chạy qua HTTPS hoặc
 * localhost.
 */

// Kiểu của Web Speech API chưa có trong lib.dom mặc định
interface RecognitionAlternative { transcript: string; confidence: number }
interface RecognitionResult { length: number; [index: number]: RecognitionAlternative }
interface RecognitionResultList { length: number; [index: number]: RecognitionResult }
interface RecognitionEvent extends Event { results: RecognitionResultList }
interface RecognitionErrorEvent extends Event { error: string }

interface SpeechRecognitionLike extends EventTarget {
  lang: string;
  interimResults: boolean;
  maxAlternatives: number;
  continuous: boolean;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: RecognitionEvent) => void) | null;
  onerror: ((event: RecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
}

type RecognitionCtor = new () => SpeechRecognitionLike;

function getCtor(): RecognitionCtor | null {
  if (typeof window === 'undefined') return null;
  const w = window as unknown as {
    SpeechRecognition?: RecognitionCtor;
    webkitSpeechRecognition?: RecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export type RecognitionError = 'not-allowed' | 'no-speech' | 'unknown';

const ERROR_TEXT: Record<RecognitionError, string> = {
  'not-allowed': 'Bạn cần cho phép trình duyệt dùng micro để chấm phát âm.',
  'no-speech': 'Không nghe thấy gì. Hãy bấm rồi đọc to và rõ.',
  unknown: 'Không nhận dạng được, thử lại nhé.',
};

export function recognitionErrorText(error: RecognitionError): string {
  return ERROR_TEXT[error];
}

export function useSpeechRecognition() {
  const supported = getCtor() !== null;
  const [listening, setListening] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  // Ngắt micro khi rời màn để không thu tiếp ở nền
  useEffect(() => () => recognitionRef.current?.abort(), []);

  const listen = useCallback(
    (onResult: (alternatives: string[]) => void, onError: (e: RecognitionError) => void) => {
      const Ctor = getCtor();
      if (!Ctor) return;

      recognitionRef.current?.abort();

      const recognition = new Ctor();
      recognition.lang = 'en-US';
      recognition.interimResults = false;
      recognition.continuous = false;
      recognition.maxAlternatives = 5;   // xét nhiều phương án cho công bằng

      recognition.onresult = (event) => {
        const result = event.results[0];
        const alternatives: string[] = [];
        for (let i = 0; i < result.length; i += 1) {
          alternatives.push(result[i].transcript);
        }
        onResult(alternatives);
      };
      recognition.onerror = (event) => {
        const code: RecognitionError =
          event.error === 'not-allowed' || event.error === 'service-not-allowed'
            ? 'not-allowed'
            : event.error === 'no-speech' ? 'no-speech' : 'unknown';
        onError(code);
      };
      recognition.onend = () => setListening(false);

      recognitionRef.current = recognition;
      setListening(true);
      recognition.start();
    },
    [],
  );

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
    setListening(false);
  }, []);

  /** Hủy lượt thu đang chạy (bug #5): gỡ handler TRƯỚC khi abort để lượt bị hủy
   * không trả kết quả và không báo lỗi 'aborted' ra màn hình. */
  const cancel = useCallback(() => {
    const r = recognitionRef.current;
    if (r) {
      r.onresult = null;
      r.onerror = null;
      r.onend = null;
      r.abort();
    }
    recognitionRef.current = null;
    setListening(false);
  }, []);

  return { supported, listening, listen, stop, cancel };
}
