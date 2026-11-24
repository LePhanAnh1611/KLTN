import { useCallback, useEffect, useRef, useState } from 'react';

/** Ghi âm bằng MediaRecorder — không cần thư viện ngoài.
 *
 * Khác `useSpeechRecognition` (dùng cho chấm phát âm mức từ): ở đây trình duyệt
 * KHÔNG nhận dạng gì cả, chỉ thu tiếng rồi gửi file lên server. Nhận dạng do
 * Whisper chạy trên máy chủ đảm nhiệm, nên kết quả không phụ thuộc trình duyệt
 * và dữ liệu không đi qua dịch vụ của bên thứ ba.
 */
export interface AudioRecorderState {
  supported: boolean;
  recording: boolean;
  /** Giây đã ghi — cập nhật mỗi 200ms để hiện đồng hồ. */
  elapsedSec: number;
  blob: Blob | null;
  objectUrl: string | null;
  error: string | null;
  start: () => Promise<void>;
  stop: () => void;
  reset: () => void;
}

/** Định dạng ưu tiên theo thứ tự trình duyệt hỗ trợ tốt dần. */
const PREFERRED_TYPES = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/ogg;codecs=opus',
  'audio/mp4',
];

function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === 'undefined') return undefined;
  return PREFERRED_TYPES.find((type) => MediaRecorder.isTypeSupported(type));
}

export function useAudioRecorder(maxSeconds = 180): AudioRecorderState {
  const [recording, setRecording] = useState(false);
  const [elapsedSec, setElapsed] = useState(0);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<number | null>(null);
  const startedAtRef = useRef(0);

  const supported =
    typeof navigator !== 'undefined'
    && !!navigator.mediaDevices?.getUserMedia
    && typeof MediaRecorder !== 'undefined';

  const cleanup = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
    // Tắt đèn micro ngay khi dừng — để stream sống là trình duyệt vẫn báo đang thu
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    recorderRef.current = null;
  }, []);

  const stop = useCallback(() => {
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop();
    setRecording(false);
  }, []);

  const start = useCallback(async () => {
    setError(null);
    if (!supported) {
      setError('Trình duyệt này không hỗ trợ ghi âm. Hãy dùng Chrome, Edge hoặc Firefox.');
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        // Bật xử lý nền của trình duyệt: bản ghi sạch hơn thì Whisper nghe chuẩn
        // hơn, mà điểm C2 lại phụ thuộc trực tiếp vào độ tin cậy nhận dạng.
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      streamRef.current = stream;

      const mimeType = pickMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      chunksRef.current = [];

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const recorded = new Blob(chunksRef.current, {
          type: mimeType ?? 'audio/webm',
        });
        setBlob(recorded);
        setObjectUrl((previous) => {
          if (previous) URL.revokeObjectURL(previous);
          return URL.createObjectURL(recorded);
        });
        cleanup();
      };

      recorderRef.current = recorder;
      recorder.start();
      startedAtRef.current = Date.now();
      setElapsed(0);
      setBlob(null);
      setRecording(true);

      timerRef.current = window.setInterval(() => {
        const seconds = (Date.now() - startedAtRef.current) / 1000;
        setElapsed(seconds);
        if (seconds >= maxSeconds) stop();
      }, 200);
    } catch (exception) {
      cleanup();
      setRecording(false);
      const name = (exception as DOMException)?.name;
      setError(
        name === 'NotAllowedError'
          ? 'Bạn chưa cho phép truy cập micro. Bật quyền micro cho trang này rồi thử lại.'
          : name === 'NotFoundError'
            ? 'Không tìm thấy micro nào trên máy.'
            : 'Không mở được micro.',
      );
    }
  }, [supported, maxSeconds, stop, cleanup]);

  const reset = useCallback(() => {
    setBlob(null);
    setElapsed(0);
    setError(null);
    setObjectUrl((previous) => {
      if (previous) URL.revokeObjectURL(previous);
      return null;
    });
  }, []);

  // Rời trang giữa chừng vẫn phải tắt micro và thu hồi object URL
  useEffect(() => () => {
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop();
    cleanup();
    setObjectUrl((previous) => {
      if (previous) URL.revokeObjectURL(previous);
      return null;
    });
  }, [cleanup]);

  return { supported, recording, elapsedSec, blob, objectUrl, error, start, stop, reset };
}
