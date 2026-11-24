"""UC-95 — tra cứu từ trong kho dữ liệu hệ thống."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.dictionary import DictionaryResult
from app.services import dictionary_service

router = APIRouter()


@router.get("", response_model=DictionaryResult)
def lookup(
    q: str = Query(min_length=1, max_length=100, description="Từ cần tra"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DictionaryResult:
    """Tra một từ: mức CEFR + các nghĩa có trong thư viện của bạn và bộ công khai.

    Không tìm thấy vẫn trả **200 kèm gợi ý**, không phải 404 — phép tra đã chạy
    xong, chỉ là kết quả rỗng, và giao diện cần phân biệt hai chuyện đó.
    """
    return dictionary_service.lookup(db, current_user, q)
