"""UC-87 — điều phối toàn bộ pipeline N1 (bước 1 của luồng: CHƯA ghi DB).

Đây là tầng service duy nhất router được gọi. Mọi ngưỡng (dung lượng, số trang,
số từ tối đa) đọc từ `system_configs` để Admin chỉnh được ở UC-81 — không hardcode.

Bước này **không ghi bất cứ thứ gì vào DB** (BR-PDF-01): danh sách ứng viên trả
về cho client giữ, người học duyệt xong mới gọi bước 2. Nhờ vậy không cần bảng
tạm và không có rác phải dọn khi người học bỏ giữa chừng.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from app.services import config_service
from app.services.pdf_import import cefr, extractor, tokenizer, topic
from app.services.pdf_import.errors import DependencyMissing, LimitExceeded

BUILD_WORDLIST_HINT = (
    "python -m app.scripts.build_cefr_wordlist "
    "--cefrj <file> --octanove <file> --out data/cefr_wordlist.csv"
)


@dataclass(frozen=True)
class CandidateWord:
    """Một từ ứng viên đã đủ thông tin để người học quyết định giữ hay bỏ."""

    word: str                 # từ điển hình (lemma) — thứ người học sẽ học
    lemma: str
    surface_form: str         # dạng đúng như tài liệu viết, để đối chiếu
    part_of_speech: str | None
    cefr_level: str | None
    topic: str | None
    example_sentence: str | None
    occurrences: int


@dataclass(frozen=True)
class DependencyStatus:
    name: str
    ready: bool
    detail: str


@dataclass(frozen=True)
class ExtractionResult:
    page_count: int
    total_words: int          # số từ duy nhất trích được TRƯỚC khi lọc
    candidates: list[CandidateWord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    topics_available: bool = False


def max_file_mb() -> int:
    return config_service.get_int("pdf_import_max_mb")


def max_file_bytes() -> int:
    return max_file_mb() * 1024 * 1024


def max_pages() -> int:
    return config_service.get_int("pdf_import_max_pages")


def max_words() -> int:
    return config_service.get_int("pdf_import_max_words")


def check_size(size_bytes: int) -> None:
    """E2 — chặn sớm theo dung lượng, trước khi động tới pdfplumber."""
    limit = max_file_bytes()
    if size_bytes > limit:
        raise LimitExceeded(
            f"File {size_bytes / (1024 * 1024):.1f}MB vượt giới hạn {max_file_mb()}MB"
        )


def cefr_source() -> cefr.CefrSource:
    """Nguồn CEFR đang cắm.

    `CsvCefrSource` cố ý NỔ khi thiếu/hỏng file thay vì âm thầm trả None cho
    mọi từ: một wordlist rỗng làm cả cột trình độ trắng bóc mà không ai biết
    tại sao. Đổi thành `DependencyMissing` để router trả 503 kèm cách sửa.
    """
    try:
        return cefr.get_cefr_source()
    except (FileNotFoundError, ValueError) as exc:
        raise DependencyMissing(f"{exc} - dựng lại bằng: {BUILD_WORDLIST_HINT}") from exc


def cefr_source_info() -> tuple[str, int]:
    """(tên nguồn, số mục) cho health check; nguồn hỏng thì báo 0 chứ không nổ."""
    try:
        source = cefr_source()
    except DependencyMissing:
        return "chưa nạp được", 0
    size = len(source) if hasattr(source, "__len__") else 0
    return getattr(source, "name", "?"), size


def dependency_statuses() -> list[DependencyStatus]:
    """Trạng thái từng phụ thuộc — nền cho endpoint health của UC-87."""
    pdf_ready = extractor.is_available()
    spacy_ready = tokenizer.is_available()
    llm_ready = topic.is_available()
    cefr_name, cefr_size = cefr_source_info()

    return [
        DependencyStatus(
            name="pdfplumber",
            ready=pdf_ready,
            detail="Sẵn sàng" if pdf_ready else f"Chưa cài - {extractor.INSTALL_HINT}",
        ),
        DependencyStatus(
            name="spacy",
            ready=spacy_ready,
            detail=(
                f"Sẵn sàng (model {tokenizer.model_name()})"
                if spacy_ready
                else f"Chưa cài spaCy hoặc model {tokenizer.model_name()} - "
                     f"{extractor.INSTALL_HINT} rồi "
                     f"python -m spacy download {tokenizer.model_name()}"
            ),
        ),
        DependencyStatus(
            name="cefr_wordlist",
            ready=cefr_size > 0,
            detail=(
                f"{cefr_name} - {cefr_size:,} mục"
                if cefr_size
                else f"Chưa nạp được wordlist - dựng bằng: {BUILD_WORDLIST_HINT}"
            ),
        ),
        DependencyStatus(
            name="ollama",
            ready=llm_ready,
            detail=(
                "Sẵn sàng - có gán chủ đề"
                if llm_ready
                else "Không kết nối được Ollama - vẫn trích từ được, chỉ thiếu chủ đề"
            ),
        ),
    ]


def is_ready() -> bool:
    """Đủ điều kiện chạy luồng import chưa.

    Ollama KHÔNG tính vào đây: thiếu nó chỉ mất chủ đề (BR-PDF-03). Còn thiếu
    pdfplumber/spaCy thì không trích được gì, và thiếu wordlist thì cột trình
    độ trắng bóc — cả hai đều là hỏng thật.
    """
    return (
        extractor.is_available()
        and tokenizer.is_available()
        and cefr_source_info()[1] > 0
    )


def _filter_by_level(
    candidates: Sequence[tokenizer.TokenCandidate],
    levels: Sequence[str] | None,
) -> tuple[list[tokenizer.TokenCandidate], list[str | None]]:
    """Lọc theo mức CEFR đã tra được. Trả về (danh sách, mức của từng lemma).

    Tra kèm **từ loại**: wordlist phân biệt "book" danh từ (A1) với "book" động
    từ (A2), bỏ từ loại đi là mất luôn phân biệt đó.
    """
    source = cefr_source()
    resolved = [source.lookup(c.lemma, c.upos) for c in candidates]
    if not levels:
        return list(candidates), resolved

    wanted = {level.strip().upper() for level in levels if level and level.strip()}
    if not wanted:
        return list(candidates), resolved

    # Từ không tra được mức thì KHÔNG thuộc mức nào -> bị loại khi có bộ lọc.
    kept = [(c, lv) for c, lv in zip(candidates, resolved) if lv in wanted]
    return [c for c, _ in kept], [lv for _, lv in kept]


def extract_candidates(
    payload: bytes,
    *,
    cefr_levels: Sequence[str] | None = None,
    with_topics: bool = True,
) -> ExtractionResult:
    """Chạy trọn pipeline N1 trên một file PDF trong bộ nhớ.

    Ném `PdfImportError` (xem `errors.py`) cho mọi tình huống ngoại lệ; router
    quy đổi sang mã HTTP.
    """
    check_size(len(payload))

    document = extractor.extract_document(payload, max_pages=max_pages())
    tokens = tokenizer.tokenize(document.sentences)

    warnings: list[str] = []
    filtered, levels = _filter_by_level(tokens, cefr_levels)

    limit = max_words()
    if len(filtered) > limit:
        # `tokenize` đã sắp theo số lần xuất hiện giảm dần nên phần bị cắt là
        # phần ít quan trọng nhất của tài liệu.
        warnings.append(
            f"Tài liệu có {len(filtered)} từ phù hợp, chỉ hiển thị {limit} từ xuất hiện nhiều nhất."
        )
        filtered, levels = filtered[:limit], levels[:limit]

    topics: dict[str, str] = {}
    topics_available = False
    if with_topics and filtered:
        topics = topic.tag_topics([c.lemma for c in filtered])
        topics_available = bool(topics)
        if not topics_available:
            warnings.append(
                "Không gán được chủ đề (Ollama chưa sẵn sàng) - các phần còn lại vẫn đầy đủ."
            )

    candidates = [
        CandidateWord(
            word=token.word,
            lemma=token.lemma,
            surface_form=token.surface_form,
            part_of_speech=token.part_of_speech,
            cefr_level=level,
            topic=topics.get(token.lemma),
            example_sentence=token.example_sentence,
            occurrences=token.occurrences,
        )
        for token, level in zip(filtered, levels)
    ]

    if not candidates:
        warnings.append(
            "Không còn từ nào sau khi lọc. Thử bỏ bộ lọc trình độ hoặc dùng tài liệu khác."
        )

    return ExtractionResult(
        page_count=document.page_count,
        total_words=len(tokens),
        candidates=candidates,
        warnings=warnings,
        topics_available=topics_available,
    )
