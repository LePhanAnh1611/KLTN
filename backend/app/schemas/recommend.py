from __future__ import annotations

from pydantic import BaseModel


class RecommendedItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    word: str
    phonetic: str | None
    part_of_speech: str | None
    meaning: str
    example: str | None
    example_vi: str | None = None   # bản dịch câu ví dụ, hiện sau khi trả lời
    #: Cờ độ tin cậy của nghĩa. Có mặt ở đây vì màn Học chính là lúc người ta
    #: thuộc lòng cái nghĩa — cảnh báo chỉ nằm ở trang chi tiết bộ thì đến muộn.
    meaning_confidence: str | None = None
    mastery: float       # P(đúng) dự đoán
    in_band: bool        # có nằm trong vùng vừa sức [0.6, 0.8] (BR-03) không
    #: Pilot — 'band' = chọn theo vùng vừa sức · 'explore' = chọn ngẫu nhiên để
    #: thăm dò. Client gửi lại nguyên giá trị này khi ghi câu trả lời.
    selection: str = "band"
