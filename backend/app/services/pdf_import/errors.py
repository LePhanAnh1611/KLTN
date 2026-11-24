"""Lỗi của luồng import PDF (UC-87).

Tầng lõi ném lỗi *nghiệp vụ*, không ném HTTPException: nhờ vậy `pipeline` test
được mà không cần FastAPI, còn việc quy đổi sang mã HTTP nằm gọn ở router.
"""
from __future__ import annotations


class PdfImportError(RuntimeError):
    """Gốc chung — router bắt cái này để không sót nhánh nào."""


class DependencyMissing(PdfImportError):
    """Chưa cài pdfplumber/spaCy (hoặc model ngôn ngữ) → E1, HTTP 503."""


class LimitExceeded(PdfImportError):
    """Vượt giới hạn dung lượng hoặc số trang → E2/E3, HTTP 413."""


class InvalidPdf(PdfImportError):
    """Không phải PDF hoặc file hỏng → E4, HTTP 422."""


class NoTextFound(PdfImportError):
    """PDF mở được nhưng không có lớp text (bản scan ảnh) → E5, HTTP 422."""
