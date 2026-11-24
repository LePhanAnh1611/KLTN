"""Nhận dạng link YouTube, lấy phụ đề tiếng Anh và tiêu đề video.

Phụ đề lấy bằng `youtube-transcript-api` — thư viện KHÔNG chính thức: YouTube
Data API chỉ cho tải phụ đề của video do chính mình sở hữu. Thư viện có thể hỏng
khi YouTube đổi cách hoạt động; video đã nạp không bị ảnh hưởng vì phụ đề đã nằm
trong DB, và luôn có phương án dự phòng là tải file .srt/.vtt.

Tiêu đề/kênh lấy qua oEmbed — endpoint CHÍNH THỨC, không cần khóa API. oEmbed
trả 401 khi chủ video tắt chế độ nhúng, nên nó cũng là cách kiểm tra "video có
phát được trong trang của mình không" trước khi người học mất công.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import httpx

from app.services.shadowing import CaptionError, Snippet

_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com",
          "youtube-nocookie.com", "www.youtube-nocookie.com"}
ENGLISH = ["en", "en-US", "en-GB", "en-CA", "en-AU"]


def parse_video_id(url_or_id: str) -> str:
    """Trả mã video 11 ký tự từ link YouTube (hoặc chính mã đó). Sai → ValueError."""
    raw = (url_or_id or "").strip()
    if _ID.match(raw):
        return raw

    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").lower()
    candidate: str | None = None
    if host in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.lstrip("/").split("/")[0]
    elif host in _HOSTS:
        if parsed.path == "/watch":
            candidate = (parse_qs(parsed.query).get("v") or [None])[0]
        else:
            parts = [p for p in parsed.path.split("/") if p]
            if len(parts) >= 2 and parts[0] in {"embed", "shorts", "live", "v"}:
                candidate = parts[1]

    if candidate and _ID.match(candidate):
        return candidate
    raise ValueError(
        "Link không phải video YouTube hợp lệ. Dùng dạng "
        "https://www.youtube.com/watch?v=… hoặc https://youtu.be/…"
    )


@dataclass(frozen=True)
class CaptionTrack:
    kind: str            # 'manual' | 'generated'
    language: str
    snippets: list[Snippet]


@dataclass(frozen=True)
class VideoMeta:
    title: str
    channel: str | None


def fetch_captions(video_id: str) -> CaptionTrack:
    """Phụ đề tiếng Anh: ưu tiên bản người đăng tạo, không có mới dùng bản tự động."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api import _errors as yt_errors
    except ImportError as exc:  # pragma: no cover - thiếu gói là lỗi cài đặt
        raise CaptionError(
            "Máy chủ chưa cài youtube-transcript-api. Tải file phụ đề lên thay thế.",
            blocked=True,
        ) from exc

    try:
        listing = YouTubeTranscriptApi().list(video_id)
        try:
            transcript = listing.find_manually_created_transcript(ENGLISH)
            kind = "manual"
        except yt_errors.NoTranscriptFound:
            transcript = listing.find_generated_transcript(ENGLISH)
            kind = "generated"
        fetched = transcript.fetch()
    except yt_errors.NoTranscriptFound as exc:
        raise CaptionError(
            "Video không có phụ đề tiếng Anh. Tải file .srt/.vtt lên nếu bạn có."
        ) from exc
    except yt_errors.TranscriptsDisabled as exc:
        raise CaptionError("Chủ video đã tắt phụ đề. Tải file .srt/.vtt lên nếu bạn có.") from exc
    except (yt_errors.VideoUnavailable, yt_errors.InvalidVideoId) as exc:
        raise CaptionError("Video không tồn tại hoặc đã bị gỡ.") from exc
    except (yt_errors.VideoUnplayable, yt_errors.AgeRestricted) as exc:
        raise CaptionError("Video bị giới hạn (riêng tư/giới hạn độ tuổi), không dùng được.") from exc
    except yt_errors.CouldNotRetrieveTranscript as exc:
        # RequestBlocked, IpBlocked, PoTokenRequired, YouTubeRequestFailed…
        raise CaptionError(
            "YouTube đang chặn yêu cầu lấy phụ đề từ máy chủ. Thử lại sau, hoặc "
            "tải file .srt/.vtt lên.",
            blocked=True,
        ) from exc
    except Exception as exc:  # noqa: BLE001 - lỗi mạng bất kỳ
        raise CaptionError(
            f"Không kết nối được tới YouTube ({type(exc).__name__}). Tải file phụ đề lên thay thế.",
            blocked=True,
        ) from exc

    snippets = [Snippet(text=s.text, start=float(s.start), duration=float(s.duration))
                for s in fetched]
    return CaptionTrack(kind=kind, language=fetched.language_code, snippets=snippets)


def fetch_meta(video_id: str, timeout: float = 8.0) -> VideoMeta:
    """Tiêu đề + kênh qua oEmbed. 401/403 = tắt nhúng, 404 = không tồn tại/riêng tư."""
    url = "https://www.youtube.com/oembed"
    params = {"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"}
    try:
        resp = httpx.get(url, params=params, timeout=timeout)
    except httpx.HTTPError as exc:
        raise CaptionError(
            "Không kết nối được tới YouTube để kiểm tra video.", blocked=True
        ) from exc

    if resp.status_code in (401, 403):
        raise CaptionError("Chủ video không cho phép nhúng video vào trang khác.")
    if resp.status_code == 404 or resp.status_code == 400:
        raise CaptionError("Video không tồn tại, đã bị gỡ hoặc đang để riêng tư.")
    if resp.status_code >= 400:
        raise CaptionError(f"YouTube trả lỗi {resp.status_code}.", blocked=True)

    data = resp.json()
    return VideoMeta(title=str(data.get("title") or video_id)[:300],
                     channel=(data.get("author_name") or None))
