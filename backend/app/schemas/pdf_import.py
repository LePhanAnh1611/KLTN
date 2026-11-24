"""Schema cho UC-87 — tạo bộ từ từ tài liệu PDF."""
from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.word_set import WordSetCreateRequest


class PdfCandidateWord(BaseModel):
    """Một từ ứng viên ở bước xem trước (chưa ghi DB)."""

    word: str                          # từ điển hình (lemma)
    lemma: str
    surface_form: str                  # dạng gặp trong tài liệu, VD "absorbs"
    part_of_speech: str | None = None
    cefr_level: str | None = None      # None = wordlist chuẩn không có từ này (BR-PDF-02)
    topic: str | None = None           # None = LLM không sẵn sàng (BR-PDF-03)
    example_sentence: str | None = None
    occurrences: int


class PdfExtractResponse(BaseModel):
    filename: str
    page_count: int
    total_words: int                   # số từ duy nhất trích được TRƯỚC khi lọc CEFR
    topics_available: bool
    warnings: list[str] = Field(default_factory=list)
    candidates: list[PdfCandidateWord] = Field(default_factory=list)


class PdfDependency(BaseModel):
    name: str
    ready: bool
    detail: str


class PdfImportHealth(BaseModel):
    """Trạng thái phụ thuộc + giới hạn hiện hành (giống /speaking/health)."""

    ready: bool                        # đủ pdfplumber + spaCy để chạy luồng
    dependencies: list[PdfDependency]
    max_file_mb: int
    max_pages: int
    max_words: int
    cefr_source: str
    cefr_word_count: int


class PdfWordSelection(BaseModel):
    """Một từ người học giữ lại ở bước xác nhận."""

    word: str = Field(min_length=1, max_length=200)
    lemma: str | None = Field(default=None, max_length=200)
    part_of_speech: str | None = Field(default=None, max_length=50)
    # Hệ thống KHÔNG tự dịch (BR-PDF-06) — để trống vẫn tạo được, sửa sau ở UC-14.
    meaning: str = Field(default="", max_length=2000)
    example: str | None = Field(default=None, max_length=2000)
    cefr_level: str | None = Field(default=None, max_length=10)
    topic: str | None = Field(default=None, max_length=100)


class WordSetFromPdfRequest(WordSetCreateRequest):
    """Bước 2: tên bộ từ (kế thừa UC-13) + danh sách từ đã duyệt."""

    source_filename: str | None = Field(default=None, max_length=255)
    words: list[PdfWordSelection] = Field(default_factory=list)
