"""UC-95 — tra cứu từ."""
from __future__ import annotations

from pydantic import BaseModel


class DictionaryEntry(BaseModel):
    """Một nghĩa tìm được, kèm chỗ nó đang nằm."""
    word: str
    phonetic: str | None
    part_of_speech: str | None
    meaning: str
    example: str | None
    word_set_id: int
    word_set_name: str
    #: True = từ này nằm trong thư viện của chính người tra (đã học/đã tải).
    in_my_library: bool


class DictionaryResult(BaseModel):
    query: str
    #: Mức CEFR tra từ wordlist chuẩn (CEFR-J + Octanove). None = không có trong
    #: nguồn — KHÔNG suy đoán, giống nguyên tắc của UC-87.
    cefr_level: str | None
    #: Người tra đã có từ này trong thư viện chưa — quyết định hiện nút "Thêm
    #: vào bộ từ" hay nút "Mở bộ đang chứa".
    in_my_library: bool
    entries: list[DictionaryEntry]
    #: Gợi ý khi không khớp chính xác (gõ sai, hoặc dạng chia).
    suggestions: list[str]
