"""Bước 1 của N1 — trích văn bản khỏi PDF bằng pdfplumber.

Điểm quan trọng: **giữ ranh giới câu**. Bước 5 của N1 lấy câu gốc trong tài liệu
làm câu ví dụ, nên nếu ở đây trả về một khối text phẳng thì thông tin đã mất và
không dựng lại được.

pdfplumber nạp muộn (xem `pdf_import/__init__.py`).
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field

from app.services.pdf_import.errors import (
    DependencyMissing,
    InvalidPdf,
    LimitExceeded,
    NoTextFound,
)

INSTALL_HINT = "pip install -r requirements-import.txt"

# Ngắt câu ở . ! ? … khi theo sau là khoảng trắng + chữ hoa/số. Cố tình KHÔNG
# dùng bộ ngắt câu của spaCy: bước này phải chạy được cả khi spaCy chưa cài, và
# quan trọng hơn là ranh giới câu ở đây chỉ để trích dẫn lại nguyên văn.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[\"'“(\[]?[A-Z0-9])")

# PDF hay chèn dấu nối cuối dòng ("informa-\ntion") — nối lại trước khi tách câu
_HYPHEN_LINEBREAK = re.compile(r"(\w)-\n(\w)")
_WHITESPACE = re.compile(r"[ \t\r\f\v]+")


@dataclass(frozen=True)
class ExtractedDocument:
    """Kết quả trích: số trang + các câu theo đúng thứ tự xuất hiện."""

    page_count: int
    sentences: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(self.sentences)


def is_available() -> bool:
    """pdfplumber đã cài chưa (dùng cho health check)."""
    try:
        import pdfplumber  # noqa: F401
    except ImportError:
        return False
    return True


def split_sentences(text: str) -> list[str]:
    """Tách một khối text thành câu, đã chuẩn hóa khoảng trắng."""
    if not text:
        return []
    text = _HYPHEN_LINEBREAK.sub(r"\1\2", text)
    sentences: list[str] = []
    for block in text.split("\n"):
        for piece in _SENTENCE_SPLIT.split(block):
            cleaned = _WHITESPACE.sub(" ", piece).strip()
            if cleaned:
                sentences.append(cleaned)
    return _merge_wrapped_lines(sentences)


def _merge_wrapped_lines(sentences: list[str]) -> list[str]:
    """Ghép các dòng bị xuống hàng giữa chừng thành một câu.

    PDF xuống dòng theo chiều rộng trang chứ không theo câu, nên tách thô theo
    `\\n` sẽ cắt câu làm đôi. Quy tắc: dòng không kết thúc bằng dấu câu thì nối
    tiếp vào dòng sau.
    """
    merged: list[str] = []
    buffer = ""
    for sentence in sentences:
        # Dòng mới bắt đầu bằng chữ HOA thì gần như chắc chắn là câu mới, còn
        # dòng trước đó là tiêu đề/chú thích. Không tách ra thì tiêu đề bị dán
        # vào câu sau và câu ví dụ nào cũng mở đầu bằng tên chương.
        if buffer and sentence[:1].isupper():
            merged.append(buffer)
            buffer = ""
        buffer = f"{buffer} {sentence}".strip() if buffer else sentence
        if buffer.endswith((".", "!", "?", "…", ":", ";")):
            merged.append(buffer)
            buffer = ""
    if buffer:
        merged.append(buffer)
    return merged


def extract_document(payload: bytes, *, max_pages: int) -> ExtractedDocument:
    """Mở PDF trong bộ nhớ và trả về các câu của nó.

    Không ghi file tạm: tài liệu người học tải lên chỉ tồn tại trong RAM của
    request, đúng tinh thần privacy của module luyện nói.
    """
    # Kiểm đầu vào TRƯỚC khi đòi thư viện: file rỗng là lỗi của người gửi, báo
    # "chưa cài pdfplumber" ở đây sẽ chỉ sai hướng.
    if not payload:
        raise InvalidPdf("File rỗng")

    try:
        import pdfplumber
    except ImportError as exc:
        raise DependencyMissing(
            f"Chưa cài pdfplumber - cài bằng: {INSTALL_HINT}"
        ) from exc

    sentences: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(payload)) as pdf:
            page_count = len(pdf.pages)
            if page_count > max_pages:
                raise LimitExceeded(
                    f"Tài liệu {page_count} trang, vượt giới hạn {max_pages} trang"
                )
            for page in pdf.pages:
                sentences.extend(split_sentences(page.extract_text() or ""))
    except (DependencyMissing, LimitExceeded):
        raise
    except Exception as exc:  # noqa: BLE001 — pdfplumber ném đủ loại lỗi khi file hỏng
        raise InvalidPdf(f"Không đọc được file PDF: {exc}") from exc

    if not sentences:
        raise NoTextFound(
            "Không trích được chữ nào từ tài liệu. Nhiều khả năng đây là bản scan "
            "ảnh - cần chạy OCR trước khi tải lên."
        )

    return ExtractedDocument(page_count=page_count, sentences=sentences)
