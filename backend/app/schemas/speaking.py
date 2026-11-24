"""Schema API cho module luyện nói.

Tách khỏi `app.speaking.types` (dataclass thuần) có chủ đích: tầng lõi không
được phụ thuộc vào Pydantic/FastAPI để còn bê đi nơi khác được.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AudioMetrics(BaseModel):
    duration_sec: float
    speech_sec: float
    words_per_minute: float
    pause_ratio: float
    pause_count: int
    longest_pause_sec: float
    filler_count: int
    filler_per_100_words: float
    asr_avg_confidence: float
    word_count: int
    language: str
    # 'asr_confidence' ở MVP; v2 đổi thành 'gop'/'wav2vec2' khi cắm bộ chấm âm vị
    pronunciation_source: str


class CriterionResult(BaseModel):
    level: int = Field(ge=1, le=4)
    label: str
    evidence: list[str]
    suggestion: str
    # 'rule' = suy từ số đo · 'llm' = Ollama chấm · 'fallback' = CHƯA chấm được
    scored_by: str
    reason: str


class SpeakingScores(BaseModel):
    fluency: CriterionResult
    pronunciation: CriterionResult
    grammar_vocab: CriterionResult
    coherence_task: CriterionResult


class SpeakingAssessmentResponse(BaseModel):
    # None khi gọi với save=false (chấm thử, không ghi lịch sử)
    attempt_id: int | None = None
    transcript: str
    audio_metrics: AudioMetrics
    scores: SpeakingScores
    overall_level: int = Field(ge=1, le=4)
    developmental_feedback: str
    # Cảnh báo về chất lượng bản ghi / trạng thái calibrate — giao diện PHẢI hiện
    warnings: list[str] = []
    rubric_version: str


class CriterionWeights(BaseModel):
    """Trọng số tùy chọn (rubric mục 6). Bỏ trống = bằng nhau."""

    fluency: float | None = Field(default=None, ge=0, le=5)
    pronunciation: float | None = Field(default=None, ge=0, le=5)
    grammar_vocab: float | None = Field(default=None, ge=0, le=5)
    coherence_task: float | None = Field(default=None, ge=0, le=5)


class SpeakingHealth(BaseModel):
    """Trạng thái các phụ thuộc cục bộ — để biết vì sao chấm hỏng."""

    asr_ready: bool
    asr_detail: str
    llm_ready: bool
    llm_detail: str
    ollama_model: str
    installed_models: list[str]
    # Rubric nằm ở docs/, ngoài package -> có thể thiếu khi triển khai
    rubric_ready: bool
    rubric_detail: str
    rubric_version: str
    rubric_calibrated: bool


# ---- Lưu trữ & vòng phản hồi rubric (mục 9) ----


class SpeakingAttemptRow(BaseModel):
    """Một lần luyện nói đã lưu. `scores` giữ nguyên khối JSON như lúc chấm."""

    id: int
    task_prompt: str
    transcript: str
    overall_level: int
    scores: dict
    audio_metrics: dict
    developmental_feedback: str
    warnings: list[str]
    # Sau khi calibrate, mức của hai version KHÔNG so sánh trực tiếp được
    rubric_version: str
    created_at: datetime
    has_appeal: bool = False


class SpeakingProgressPoint(BaseModel):
    attempt_id: int
    created_at: datetime
    overall_level: int
    levels: dict[str, int]
    words_per_minute: float


class SpeakingHistoryResponse(BaseModel):
    items: list[SpeakingAttemptRow]
    total: int
    page: int
    page_size: int
    # Chỉ gồm các lần chấm cùng phiên bản rubric mới nhất — xem service
    progress: list[SpeakingProgressPoint]
    progress_rubric_version: str


class SpeakingAppealCreate(BaseModel):
    """Người học báo kết quả chấm chưa đúng."""

    criterion: str = Field(
        pattern="^(fluency|pronunciation|grammar_vocab|coherence_task|overall)$",
    )
    expected_level: int | None = Field(default=None, ge=1, le=4)
    comment: str = Field(min_length=1, max_length=1000)


class SpeakingAppealRow(BaseModel):
    id: int
    attempt_id: int
    criterion: str
    expected_level: int | None
    system_level: int | None
    comment: str
    status: str
    created_at: datetime


class SpeakingAppealAdminRow(BaseModel):
    """Hàng đợi cho người làm rubric — `gap` càng lớn càng đáng xem trước."""

    id: int
    attempt_id: int
    user_name: str
    criterion: str
    system_level: int | None
    expected_level: int | None
    gap: int | None
    comment: str
    transcript: str
    task_prompt: str
    rubric_version: str
    status: str
    created_at: datetime
