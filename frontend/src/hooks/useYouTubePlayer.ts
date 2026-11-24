import { useCallback, useEffect, useRef, useState } from 'react';

/** Trình phát YouTube chính thức (IFrame Player API) — phát đúng một đoạn rồi dừng.
 *
 * Không tải video về máy chủ: mọi thứ phát qua iframe của YouTube, dùng tên miền
 * youtube-nocookie để không đặt cookie theo dõi trước khi người học bấm phát. */

interface YTPlayer {
  playVideo(): void;
  pauseVideo(): void;
  seekTo(seconds: number, allowSeekAhead: boolean): void;
  getCurrentTime(): number;
  setPlaybackRate(rate: number): void;
  destroy(): void;
}

interface YTNamespace {
  Player: new (el: HTMLElement, opts: Record<string, unknown>) => YTPlayer;
}

declare global {
  interface Window {
    YT?: YTNamespace;
    onYouTubeIframeAPIReady?: () => void;
  }
}

let apiPromise: Promise<YTNamespace> | null = null;

function loadApi(): Promise<YTNamespace> {
  if (window.YT?.Player) return Promise.resolve(window.YT);
  if (apiPromise) return apiPromise;
  apiPromise = new Promise((resolve, reject) => {
    const previous = window.onYouTubeIframeAPIReady;
    window.onYouTubeIframeAPIReady = () => {
      previous?.();
      if (window.YT) resolve(window.YT);
    };
    const script = document.createElement('script');
    script.src = 'https://www.youtube.com/iframe_api';
    script.async = true;
    script.onerror = () => {
      apiPromise = null;
      reject(new Error('Không tải được trình phát YouTube. Kiểm tra kết nối mạng.'));
    };
    document.head.appendChild(script);
  });
  return apiPromise;
}

/** Đệm hai đầu đoạn: mốc phụ đề hay lệch vài trăm mili giây. */
const PAD_SEC = 0.25;

export function useYouTubePlayer(videoId: string | undefined) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const playerRef = useRef<YTPlayer | null>(null);
  const timerRef = useRef<number | null>(null);
  const [ready, setReady] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const stopTimer = () => {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  };

  useEffect(() => {
    if (!videoId || !containerRef.current) return undefined;
    let cancelled = false;
    const mount = document.createElement('div');
    containerRef.current.replaceChildren(mount);

    loadApi()
      .then((YT) => {
        if (cancelled) return;
        playerRef.current = new YT.Player(mount, {
          videoId,
          host: 'https://www.youtube-nocookie.com',
          width: '100%',
          height: '100%',
          playerVars: { rel: 0, modestbranding: 1, playsinline: 1, cc_load_policy: 0 },
          events: {
            onReady: () => { if (!cancelled) setReady(true); },
            onError: (e: { data: number }) => {
              if (cancelled) return;
              setError(e.data === 101 || e.data === 150
                ? 'Chủ video không cho phát trong trang khác.'
                : 'Không phát được video này.');
            },
          },
        });
      })
      .catch((e: Error) => { if (!cancelled) setError(e.message); });

    return () => {
      cancelled = true;
      stopTimer();
      playerRef.current?.destroy();
      playerRef.current = null;
      setReady(false);
      setPlaying(false);
    };
  }, [videoId]);

  /** Phát từ `start` tới `end` (giây) rồi tự dừng. */
  const playSegment = useCallback((start: number, end: number, rate = 1) => {
    const player = playerRef.current;
    if (!player) return;
    stopTimer();
    player.setPlaybackRate(rate);
    player.seekTo(Math.max(0, start - PAD_SEC), true);
    player.playVideo();
    setPlaying(true);
    timerRef.current = window.setInterval(() => {
      if (player.getCurrentTime() >= end + PAD_SEC) {
        player.pauseVideo();
        stopTimer();
        setPlaying(false);
      }
    }, 100);
  }, []);

  const pause = useCallback(() => {
    stopTimer();
    playerRef.current?.pauseVideo();
    setPlaying(false);
  }, []);

  return { containerRef, ready, playing, error, playSegment, pause };
}
