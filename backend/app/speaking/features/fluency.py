"""C1 Fluency — trích đặc trưng từ mốc thời gian của ASR (rubric mục 5).

Toàn bộ hàm ở đây là hàm thuần trên `Transcript`: không mạng, không model, nên
test được bằng dữ liệu dựng tay và chạy trong mili-giây.
"""
from __future__ import annotations

import re

from app.speaking.rubric.thresholds import load_thresholds
from app.speaking.types import FluencyFeatures, Transcript

# Từ đệm tiếng Anh. Whisper thường phiên "uh"/"um" thành "uh,"/"Um" nên so sánh
# sau khi chuẩn hóa. "like"/"you know" CỐ Ý không nằm ở đây: chúng là từ có
# nghĩa thật, đếm bừa sẽ phạt oan người nói đúng ngữ pháp.
FILLERS = {
    "uh", "um", "erm", "hmm", "mmm", "eh", "ah", "er", "uhh", "umm",
}
_PUNCT = re.compile(r"[^\w']", re.UNICODE)


def _normalize(text: str) -> str:
    return _PUNCT.sub("", text).lower()


def count_fillers(transcript: Transcript) -> tuple[int, list[str]]:
    hits = [w.text for w in transcript.words if _normalize(w.text) in FILLERS]
    return len(hits), hits


def find_pauses(transcript: Transcript, min_pause_sec: float) -> list[float]:
    """Độ dài các khoảng lặng GIỮA các từ vượt ngưỡng.

    Chỉ tính khoảng giữa hai từ; khoảng lặng đầu/cuối bản ghi không phản ánh độ
    trôi chảy (người học bấm ghi âm rồi mới nói).
    """
    pauses: list[float] = []
    for previous, current in zip(transcript.words, transcript.words[1:]):
        gap = current.start - previous.end
        if gap >= min_pause_sec:
            pauses.append(round(gap, 3))
    return pauses


def extract(transcript: Transcript) -> FluencyFeatures:
    config = load_thresholds()["fluency"]
    min_pause = float(config["min_pause_sec"])

    words = transcript.words
    duration = transcript.duration_sec

    pauses = find_pauses(transcript, min_pause)
    pause_total = sum(pauses)

    # Thời gian thực sự nói = từ lúc bắt đầu từ đầu tiên tới hết từ cuối, trừ đi
    # các khoảng lặng. Không lấy `duration` vì nó gồm cả im lặng đầu/cuối.
    span = (words[-1].end - words[0].start) if len(words) >= 2 else duration
    speech = max(0.0, span - pause_total)

    filler_count, _ = count_fillers(transcript)
    # WPM tính trên phần THỰC SỰ nói: người dừng lâu đã bị phạt ở pause_ratio rồi,
    # tính cả khoảng lặng vào WPM nữa là phạt hai lần cùng một lỗi.
    wpm = (len(words) / speech * 60.0) if speech > 0 else 0.0
    pause_ratio = (pause_total / span) if span > 0 else 0.0

    return FluencyFeatures(
        duration_sec=round(duration, 2),
        speech_sec=round(speech, 2),
        words_per_minute=round(wpm, 1),
        pause_ratio=round(pause_ratio, 3),
        pause_count=len(pauses),
        longest_pause_sec=round(max(pauses), 2) if pauses else 0.0,
        filler_count=filler_count,
        filler_per_100_words=round(
            (filler_count / len(words) * 100.0) if words else 0.0, 1
        ),
    )
