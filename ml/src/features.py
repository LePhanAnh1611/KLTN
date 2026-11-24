"""Vector đặc trưng cho một token — nền của biến thể DKT feature-based.

Mục 2.2 `docs/system-spec.md` đòi mô hình **tổng quát hóa sang từ chưa từng thấy**.
DKT gốc mã hóa item bằng chỉ số trong một vocab cố định nên không làm được: gặp
từ ngoài vocab là chịu. Cách thoát là đừng mô tả từ bằng *danh tính* nữa mà mô tả
bằng *đặc điểm* — mô hình học "loại từ như thế này thì khó nhớ thế nào", chứ
không học riêng về từ `deadline`.

BẤT BIẾN BẮT BUỘC của module này
--------------------------------
**Mọi đặc trưng phải tính được cho một từ mô hình CHƯA TỪNG THẤY.**

Nghe hiển nhiên nhưng rất dễ vi phạm: dùng tần suất token đếm trên chính corpus
huấn luyện là một đặc trưng "ngon" — và phá hỏng toàn bộ mục đích, vì từ mới
không có số đếm nào. Vì vậy tần suất lấy từ `wordfreq` (một corpus tiếng Anh
tổng quát, độc lập với dữ liệu huấn luyện), CEFR lấy từ wordlist chuẩn, còn từ
loại lấy từ nhãn UPOS — SLAM có sẵn cột này và spaCy sinh ra đúng bộ nhãn ấy cho
từ của ứng dụng, nên hai bên khớp nhau tự nhiên.

Từ nào thiếu dữ liệu thì có CỜ RIÊNG báo thiếu (`cefr_unknown`, `freq_unknown`)
thay vì lặng lẽ điền 0 — để mô hình học được rằng "không biết" tự nó cũng là
một tín hiệu, và để lúc phân tích còn tách được ra mà nhìn.
"""
from __future__ import annotations

import csv
import functools
import os
from pathlib import Path

import numpy as np

CEFR_ORDER = ("A1", "A2", "B1", "B2", "C1", "C2")

# Bộ nhãn UPOS. Giữ nguyên tên chuẩn để SLAM (cột 3 của file thô) và spaCy
# (`token.pos_`) dùng chung được mà không cần bảng quy đổi nào.
UPOS_TAGS = (
    "NOUN", "VERB", "ADJ", "ADV", "PRON", "DET", "ADP", "AUX",
    "NUM", "CCONJ", "SCONJ", "PART", "PROPN", "INTJ",
)

MAX_LEN = 20          # độ dài từ, cắt ngọn để chuẩn hóa về [0, 1]
MAX_ZIPF = 8.0        # thang Zipf thực tế nằm trong khoảng 0–8

FEATURE_NAMES: tuple[str, ...] = (
    *(f"cefr_{lv}" for lv in CEFR_ORDER),
    # Thang THỨ BẬC bên cạnh one-hot, và đây không phải chi tiết thừa.
    #
    # Corpus huấn luyện (SLAM en_es) gần như không có từ C1/C2: đếm được đúng 5
    # token trên 2.226. Nếu chỉ có one-hot thì hai cột `cefr_C1`/`cefr_C2` là hai
    # hướng KHÔNG BAO GIỜ được học, mà từ vựng của ứng dụng lại bật chúng thường
    # xuyên -> lúc phục vụ mô hình đọc phải một chiều vô nghĩa.
    #
    # Thang thứ bậc vá đúng chỗ đó: mô hình học được quan hệ đơn điệu "mức càng
    # cao càng khó" trên A1–B2 rồi ngoại suy sang C1/C2 một cách hợp lý.
    "cefr_rank",
    "cefr_unknown",
    *(f"pos_{tag}" for tag in UPOS_TAGS),
    "pos_other",
    "length",
    "zipf",
    "freq_unknown",
    "is_capitalized",
    "has_non_alpha",
)
FEATURE_DIM = len(FEATURE_NAMES)


def _default_cefr_path() -> Path:
    override = os.getenv("CEFR_WORDLIST_PATH", "").strip()
    if override:
        return Path(override)
    # Dùng chung file với backend thay vì nhân đôi dữ liệu: hai bên phải gán
    # cùng một mức cho cùng một từ, tách ra là sớm muộn cũng lệch.
    return Path(__file__).resolve().parents[2] / "backend" / "data" / "cefr_wordlist.csv"


@functools.lru_cache(maxsize=1)
def load_cefr(path: str | None = None) -> dict[str, str]:
    """{từ -> mức CEFR}. Thiếu file thì trả rỗng (mọi từ sẽ mang cờ unknown)."""
    target = Path(path) if path else _default_cefr_path()
    levels: dict[str, str] = {}
    try:
        with target.open(encoding="utf-8-sig", newline="") as fh:
            rows = (line for line in fh if not line.lstrip().startswith("#"))
            for row in csv.DictReader(rows):
                word = (row.get("word") or "").strip().lower()
                level = (row.get("cefr_level") or "").strip().upper()
                if word and level in CEFR_ORDER:
                    levels.setdefault(word, level)
    except OSError:
        pass
    return levels


@functools.lru_cache(maxsize=1)
def _zipf_fn():
    """`wordfreq` chỉ cần lúc dựng đặc trưng; thiếu nó thì suy giảm mềm."""
    try:
        from wordfreq import zipf_frequency
    except ImportError:
        return None
    return zipf_frequency


#: Nhãn từ loại "người đọc" mà backend đang lưu (UC-87 `POS_LABELS`, và dữ liệu
#: lấy từ dictionaryapi) -> UPOS. Không có bảng này thì mọi từ của ứng dụng rơi
#: vào `pos_other` và mất một đặc trưng mà mô hình được huấn luyện để dùng.
_LABEL_TO_UPOS = {
    "noun": "NOUN", "verb": "VERB", "adjective": "ADJ", "adj": "ADJ",
    "adverb": "ADV", "adv": "ADV", "pronoun": "PRON", "determiner": "DET",
    "preposition": "ADP", "conjunction": "CCONJ", "interjection": "INTJ",
    "numeral": "NUM", "number": "NUM", "auxiliary": "AUX", "particle": "PART",
    "proper noun": "PROPN",
}


#: Chế độ học của ứng dụng -> dạng bài của SLAM. Quy về BẢN CHẤT nhận thức chứ
#: không theo tên gọi, vì đó mới là thứ mô hình học được từ 2,6 triệu lượt SLAM:
#:   reverse_tap       - đáp án bày sẵn, chỉ cần nhận ra
#:   reverse_translate - tự sản sinh lại từ
#:   listen            - nghe rồi sản sinh
FORMAT_ALIASES = {
    # nhận diện
    "quiz": "reverse_tap", "matching": "reverse_tap", "flashcard": "reverse_tap",
    "dkt_smart": "reverse_tap", "sm2": "reverse_tap",
    "srs_review": "reverse_tap", "weak_review": "reverse_tap",
    "reverse_tap": "reverse_tap",
    # nhớ chủ động
    "typing": "reverse_translate", "cloze": "reverse_translate",
    "reverse_translate": "reverse_translate",
    # nghe
    "dictation": "listen", "listen": "listen",
    # "mixed" cố ý KHÔNG có mặt: một phiên trộn gồm nhiều dạng khác nhau, gán cho
    # nó một dạng duy nhất là nói dối mô hình. Từng lượt trả lời trong phiên trộn
    # phải gửi dạng bài THẬT của lượt đó.
}


def format_code(name: str | None) -> int:
    """Mã dạng bài để đưa vào đặc trưng. Không nhận ra -> mã 'other'."""
    import config as _config

    key = FORMAT_ALIASES.get((name or "").strip().lower())
    return _config.FORMAT2CODE.get(key, _config.FORMAT_OTHER)


def normalize_pos(raw: str | None) -> str | None:
    """Nhận cả nhãn UPOS lẫn nhãn tiếng Anh dạng chữ thường; không nhận ra thì None."""
    if not raw:
        return None
    text = raw.strip()
    if text.upper() in UPOS_TAGS:
        return text.upper()
    return _LABEL_TO_UPOS.get(text.lower())


def token_features(token: str, upos: str | None = None) -> np.ndarray:
    """Vector đặc trưng của một token. Luôn trả đúng `FEATURE_DIM` chiều.

    `upos` là nhãn từ loại nếu biết (SLAM có sẵn; spaCy sinh ra cho từ ứng dụng).
    Không biết thì để None — sẽ rơi vào `pos_other`.
    """
    vec = np.zeros(FEATURE_DIM, dtype=np.float32)
    idx = {name: i for i, name in enumerate(FEATURE_NAMES)}
    word = (token or "").strip()
    lower = word.lower()

    level = load_cefr().get(lower)
    if level:
        vec[idx[f"cefr_{level}"]] = 1.0
        vec[idx["cefr_rank"]] = CEFR_ORDER.index(level) / (len(CEFR_ORDER) - 1)
    else:
        vec[idx["cefr_unknown"]] = 1.0

    tag = normalize_pos(upos) or ""
    if tag in UPOS_TAGS:
        vec[idx[f"pos_{tag}"]] = 1.0
    else:
        vec[idx["pos_other"]] = 1.0

    vec[idx["length"]] = min(len(word), MAX_LEN) / MAX_LEN

    zipf = _zipf_fn()
    score = zipf(lower, "en") if zipf is not None and lower else 0.0
    if score > 0:
        vec[idx["zipf"]] = min(score, MAX_ZIPF) / MAX_ZIPF
    else:
        vec[idx["freq_unknown"]] = 1.0

    vec[idx["is_capitalized"]] = 1.0 if word[:1].isupper() else 0.0
    vec[idx["has_non_alpha"]] = 0.0 if word.isalpha() else 1.0
    return vec


def build_matrix(tokens: list[str], upos: dict[str, str] | None = None) -> np.ndarray:
    """Ma trận (len(tokens), FEATURE_DIM) theo đúng thứ tự `tokens`.

    Dùng để dựng sẵn bảng tra cho vocab huấn luyện; lúc phục vụ thì gọi
    `token_features` trực tiếp cho từ mới.
    """
    pos_map = upos or {}
    return np.stack([token_features(t, pos_map.get(t)) for t in tokens])


def describe(token: str, upos: str | None = None) -> dict[str, float]:
    """Bản đọc được bằng mắt — để soi lúc phân tích, không dùng khi huấn luyện."""
    vec = token_features(token, upos)
    return {name: float(v) for name, v in zip(FEATURE_NAMES, vec) if v}
