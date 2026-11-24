"""Đọc file phụ đề .srt / .vtt — phương án dự phòng khi không lấy được từ YouTube."""
from __future__ import annotations

import re

from app.services.shadowing import CaptionError, Snippet

# 00:01:02,345 --> 00:01:04,000   (SRT)   |   01:02.345 --> 01:04.000   (VTT)
_TIME = r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})"
_CUE = re.compile(rf"^\s*{_TIME}\s*-->\s*{_TIME}")
_TAG = re.compile(r"<[^>]+>")


def _seconds(h: str | None, m: str, s: str, ms: str) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def parse_subtitles(content: str) -> list[Snippet]:
    """Đọc nội dung SRT hoặc WebVTT thành các mảnh phụ đề.

    Không phân biệt hai định dạng: cả hai đều là "dòng mốc thời gian + các dòng
    chữ, ngăn bởi dòng trống". Số thứ tự cue (SRT), dòng WEBVTT/NOTE/STYLE và
    thẻ định dạng (<i>, <c.color>…) bị bỏ qua.
    """
    snippets: list[Snippet] = []
    lines = content.replace("﻿", "").replace("\r\n", "\n").replace("\r", "\n").split("\n")

    i = 0
    while i < len(lines):
        match = _CUE.match(lines[i])
        if not match:
            i += 1
            continue
        g = match.groups()
        start = _seconds(*g[0:4])
        end = _seconds(*g[4:8])
        i += 1
        text_lines: list[str] = []
        while i < len(lines) and lines[i].strip() and not _CUE.match(lines[i]):
            text_lines.append(_TAG.sub("", lines[i]).strip())
            i += 1
        text = " ".join(t for t in text_lines if t)
        if text and end > start:
            snippets.append(Snippet(text=text, start=start, duration=end - start))

    if not snippets:
        raise CaptionError(
            "File phụ đề rỗng hoặc sai định dạng. Hỗ trợ .srt và .vtt có dòng mốc "
            "thời gian dạng 00:00:01,000 --> 00:00:03,500."
        )
    return snippets
