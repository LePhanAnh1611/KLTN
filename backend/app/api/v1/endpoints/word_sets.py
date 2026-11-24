from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.item import ImportReport, ItemCreateRequest, ItemResponse, ItemUpdateRequest
from app.schemas.pdf_import import (
    PdfCandidateWord,
    PdfDependency,
    PdfExtractResponse,
    PdfImportHealth,
    WordSetFromPdfRequest,
)
from app.schemas.quiz import ClozeQuestion, MatchingRound, QuizQuestion, TypingQuestion
from app.schemas.recommend import RecommendedItem
from app.schemas.word_set import (
    PublishRequest,
    WordSetCreateRequest,
    WordSetResponse,
    WordSetUpdateRequest,
)
from app.services import item_service, quiz_service, recommend_service, word_set_service
from app.services.pdf_import import pipeline
from app.services.pdf_import.errors import (
    DependencyMissing,
    InvalidPdf,
    LimitExceeded,
    NoTextFound,
    PdfImportError,
)

router = APIRouter()


# ---- Tạo bộ từ từ PDF (UC-87) ----
#
# Ba route này khai TRƯỚC `/{word_set_id}` để "pdf-import"/"extract-pdf" không bị
# FastAPI thử ép sang int rồi trả 422 khó hiểu.


@router.get("/pdf-import/health", response_model=PdfImportHealth)
def pdf_import_health(_: User = Depends(get_current_user)) -> PdfImportHealth:
    """UC-87 — phụ thuộc nào đã sẵn sàng, giới hạn hiện hành là bao nhiêu."""
    cefr_name, cefr_size = pipeline.cefr_source_info()
    return PdfImportHealth(
        ready=pipeline.is_ready(),
        dependencies=[
            PdfDependency(name=d.name, ready=d.ready, detail=d.detail)
            for d in pipeline.dependency_statuses()
        ],
        max_file_mb=pipeline.max_file_mb(),
        max_pages=pipeline.max_pages(),
        max_words=pipeline.max_words(),
        cefr_source=cefr_name,
        cefr_word_count=cefr_size,
    )


@router.post("/extract-pdf", response_model=PdfExtractResponse)
async def extract_pdf(
    file: UploadFile = File(..., description="Tài liệu PDF"),
    cefr_levels: str | None = Form(
        default=None, description="Lọc theo mức CEFR, phân tách bằng dấu phẩy (VD 'A2,B1')"
    ),
    _: User = Depends(get_current_user),
) -> PdfExtractResponse:
    """UC-87 bước 1 — trích từ vựng để xem trước. KHÔNG ghi gì vào DB (BR-PDF-01)."""
    filename = file.filename or "document.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Chỉ nhận file .pdf",
        )

    payload = await file.read()
    levels = [part.strip() for part in cefr_levels.split(",")] if cefr_levels else None

    try:
        result = pipeline.extract_candidates(payload, cefr_levels=levels)
    except DependencyMissing as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    except LimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(exc)
        ) from exc
    except (InvalidPdf, NoTextFound) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except PdfImportError as exc:                 # nhánh còn sót — không nuốt lỗi im lặng
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    return PdfExtractResponse(
        filename=filename,
        page_count=result.page_count,
        total_words=result.total_words,
        topics_available=result.topics_available,
        warnings=result.warnings,
        candidates=[PdfCandidateWord(**vars(c)) for c in result.candidates],
    )


@router.post("/from-pdf", response_model=WordSetResponse, status_code=status.HTTP_201_CREATED)
def create_word_set_from_pdf(
    data: WordSetFromPdfRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WordSetResponse:
    """UC-87 bước 2 — người học đã bỏ từ rác, giờ mới ghi vào thư viện."""
    return word_set_service.create_word_set_from_pdf(db, current_user, data)


# ---- Word sets (UC-13, UC-16, UC-17) ----


@router.post("", response_model=WordSetResponse, status_code=status.HTTP_201_CREATED)
def create_word_set(
    data: WordSetCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WordSetResponse:
    return word_set_service.create_word_set(db, current_user, data)


@router.get("", response_model=list[WordSetResponse])
def list_word_sets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WordSetResponse]:
    return word_set_service.list_word_sets(db, current_user)


@router.get("/{word_set_id}", response_model=WordSetResponse)
def get_word_set(
    word_set_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WordSetResponse:
    return word_set_service.get_word_set(db, current_user, word_set_id)


@router.patch("/{word_set_id}", response_model=WordSetResponse)
def update_word_set(
    word_set_id: int,
    data: WordSetUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WordSetResponse:
    return word_set_service.update_word_set(db, current_user, word_set_id, data)


@router.delete("/{word_set_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_word_set(
    word_set_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    word_set_service.delete_word_set(db, current_user, word_set_id)


@router.post("/{word_set_id}/cover", response_model=WordSetResponse)
def upload_cover(
    word_set_id: int,
    file: UploadFile = File(..., description="Ảnh bìa (jpg/png/webp, tối đa 5MB)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WordSetResponse:
    """UC-13 — tải ảnh bìa cho bộ từ."""
    return word_set_service.update_cover(db, current_user, word_set_id, file)


@router.delete("/{word_set_id}/cover", response_model=WordSetResponse)
def remove_cover(
    word_set_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WordSetResponse:
    """UC-13 — gỡ ảnh bìa, quay về bìa sinh tự động."""
    return word_set_service.delete_cover(db, current_user, word_set_id)


@router.patch("/{word_set_id}/publish", response_model=WordSetResponse)
def set_publish(
    word_set_id: int,
    data: PublishRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WordSetResponse:
    return word_set_service.set_publish(db, current_user, word_set_id, data)


# ---- Items (UC-14, UC-15) ----


@router.get("/{word_set_id}/items", response_model=list[ItemResponse])
def list_items(
    word_set_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ItemResponse]:
    return item_service.list_items(db, current_user, word_set_id)


@router.post("/{word_set_id}/items", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def create_item(
    word_set_id: int,
    data: ItemCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ItemResponse:
    return item_service.create_item(db, current_user, word_set_id, data)


@router.patch("/{word_set_id}/items/{item_id}", response_model=ItemResponse)
def update_item(
    word_set_id: int,
    item_id: int,
    data: ItemUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ItemResponse:
    return item_service.update_item(db, current_user, word_set_id, item_id, data)


@router.delete("/{word_set_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    word_set_id: int,
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    item_service.delete_item(db, current_user, word_set_id, item_id)


@router.post("/{word_set_id}/items/import", response_model=ImportReport)
def import_items(
    word_set_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ImportReport:
    return item_service.import_items_csv(db, current_user, word_set_id, file)


# ---- Quiz (UC-26) ----


@router.get("/{word_set_id}/quiz", response_model=list[QuizQuestion])
def generate_quiz(
    word_set_id: int,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[QuizQuestion]:
    return quiz_service.generate_quiz(db, current_user, word_set_id, limit)


# ---- Gợi ý item vừa sức (UC-65) ----


@router.get("/{word_set_id}/recommend", response_model=list[RecommendedItem])
def recommend(
    word_set_id: int,
    limit: int = 10,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RecommendedItem]:
    return recommend_service.recommend_items(db, current_user, word_set_id, limit)


@router.get("/{word_set_id}/cloze", response_model=list[ClozeQuestion])
def generate_cloze(
    word_set_id: int,
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ClozeQuestion]:
    """UC-28 — bài điền khuyết dựng từ câu ví dụ (E1: chưa có ví dụ dùng được -> 400)."""
    return quiz_service.generate_cloze(db, current_user, word_set_id, limit)


@router.get("/{word_set_id}/typing", response_model=list[TypingQuestion])
def generate_typing(
    word_set_id: int,
    limit: int = Query(default=10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TypingQuestion]:
    """UC-89 — bài gõ từ: thấy nghĩa tiếng Việt, tự gõ lại từ tiếng Anh."""
    return quiz_service.generate_typing(db, current_user, word_set_id, limit)


@router.get("/{word_set_id}/matching", response_model=MatchingRound)
def generate_matching(
    word_set_id: int,
    size: int | None = Query(default=None, ge=2, le=12),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MatchingRound:
    """UC-28 — một lượt ghép cặp từ ↔ nghĩa (số cặp mặc định lấy từ cấu hình)."""
    return quiz_service.generate_matching(db, current_user, word_set_id, size)
