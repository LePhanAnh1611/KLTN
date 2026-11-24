"""Dựng BỘ TỪ VỰNG NỀN (NGSL + NAWL) — chạy một lần, kết quả cache lại.

    python -m app.scripts.build_core_dataset \
        --ngsl   data/sources/ngsl.txt \
        --nawl   data/sources/nawl.txt \
        --ngsl-xlsx data/sources/NGSL_with_SFI.xlsx \
        --dict   data/sources/english-vietnamese.txt \
        --wikt   data/sources/vi2enwikitxt.txt \
        --cefr   data/cefr_wordlist.csv \
        --out    data/vocab_seed_core.json

Khác `build_vocab_dataset.py` ở chỗ nào, và vì sao tách ra làm hai script:

  build_vocab_dataset.py  — 8 bộ CHỦ ĐỀ, nghĩa viết tay, ~320 từ.
                            Chất lượng cao nhất, quy mô nhỏ, người chọn từng từ.
  build_core_dataset.py   — bộ NỀN theo tần suất, ~3.750 từ, nghĩa lấy từ
                            từ điển. Quy mô lớn, không ai đọc hết được bằng tay,
                            nên MỌI trường đều mang `*_source` và `meaning_confidence`.

Hai bộ bổ sung cho nhau chứ không thay thế: bộ chủ đề để người học chọn theo
nhu cầu, bộ nền để lộ trình và gợi ý DKT có đủ từ để làm việc.

NGUYÊN TẮC (giống script cũ):
  - KHÔNG dùng LLM ở bất kỳ bước nào.
  - Thiếu dữ liệu thì để trống, không bịa.
  - Mọi trường tự sinh đều truy nguyên được về nguồn.

NGUỒN & GIẤY PHÉP: xem data/sources/README.md — PHẢI trích dẫn trong khóa luận.
"""
from __future__ import annotations

from app.scripts._console import use_utf8_console

import argparse
import csv
import datetime
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl
from wordfreq import zipf_frequency

# Nhãn từ loại tiếng Việt -> nhãn tiếng Anh mà backend đang lưu.
# Phải nằm trong _LABEL_TO_UPOS của ml/src/features.py, nếu không mô hình
# rơi vào pos_other và mất một đặc trưng.
POS_VI_TO_EN = [
    ("ngoại động từ", "verb"),
    ("nội động từ", "verb"),
    ("trợ động từ", "auxiliary"),
    ("động từ", "verb"),
    ("danh từ riêng", "proper noun"),
    ("danh từ", "noun"),
    ("tính từ", "adjective"),
    ("phó từ", "adverb"),
    ("trạng từ", "adverb"),
    ("giới từ", "preposition"),
    ("liên từ", "conjunction"),
    ("đại từ", "pronoun"),
    ("thán từ", "interjection"),
    ("mạo từ", "determiner"),
    ("số từ", "numeral"),
    ("từ hạn định", "determiner"),
]

# Nhãn lĩnh vực / sắc thái mở đầu một nghĩa: "(thông tục)", "(âm nhạc)"...
# Giữ lại thì gloss dài và rối; bỏ đi thì mất sắc thái. Ta TÁCH ra để dùng riêng.
_DOMAIN_RE = re.compile(r"^\(([^)]{1,40})\)\s*")
# Dòng headword có thể mang thêm biến thể phía sau:
#   @through /θru:/ (thro) /θru:/ (thro') /θru:/
# nên IPA là cặp /.../ ĐẦU TIÊN, còn từ là phần đứng trước nó — không phải
# cặp cuối dòng. Bắt sai chỗ này làm mất khoảng 3% từ thông dụng nhất
# (have, through, role, tomorrow...) mà không báo lỗi gì.
_IPA_RE = re.compile(r"/([^/]{1,80})/")
# ...NHƯNG cặp /.../ đầu tiên là IPA của dạng ĐẦU NHÓM, chưa chắc là của chính
# headword. FVDP gộp các biến thể vào cùng một dòng và lặp dòng đó dưới tên
# từng biến thể:
#   @ethic   /'eθik/ (ethical) /'eθikəl/
#   @ethical /'eθik/ (ethical) /'eθikəl/     <- 'ethical' phải lấy /'eθikəl/
# Bug #8: lấy cặp đầu làm 'ethical' mang phiên âm của 'ethic' (43 từ trong bộ
# nền dính lỗi này: biological, employee, therapy, everyone...). Quy tắc: nếu
# headword xuất hiện trong ngoặc thì lấy IPA đứng ngay sau ngoặc đó.
_VARIANT_IPA_RE = re.compile(r"\(([^()]{1,60})\)\s*/([^/]{1,80})/")


def _headword_ipa(head: str) -> tuple[str, str | None]:
    """Tách dòng `@...` thành (headword, IPA của CHÍNH headword đó)."""
    m = _IPA_RE.search(head)
    if not m:
        return head.strip(), None
    word = head[: m.start()].strip()
    ipa = m.group(1).strip()
    for variant, variant_ipa in _VARIANT_IPA_RE.findall(head[m.end():]):
        if variant.strip() == word:
            ipa = variant_ipa.strip()
            break
    return word, "/" + ipa + "/"


# Phiên âm HỎNG ngay trong file FVDP (bug #8) — phát hiện để bỏ, không đoán:
#   - mất ký tự IPA khi chuyển mã: "@what /w t/", "@up / p/", "@with /wi /"
#   - chép chữ viết vào chỗ IPA: "@problem /problem/", "@floor /floor/"
#   - mục thuật ngữ cắt sai: "@Horizontal / vertical / ... merger" -> "/vertical/"
# Chép chữ viết chỉ được tin khi cách viết trùng cách đọc thật (in, get, red):
# chỉ phụ âm "thẳng" và nguyên âm i/e ngắn, không cụm đọc khác chữ (th, ng, ck...).
_SPELLED_LIKE_IPA = re.compile(r"[bdfghklmnprstvwz]*(?:[ie][bdfghklmnprstvwz]+)*")
_NOT_LIKE_IPA = re.compile(r"th|sh|ch|ph|gh|wh|ng|nk|er|ir|([a-z])\1")


def _strip_notes(inner: str) -> str:
    """Bỏ chú thích trong ngoặc giữa IPA — "(Mỹ)", "(thông tục)" — mà FVDP hay
    ghi lẫn vào và nhiều chỗ đã vỡ mã ("(Àthtục)")."""
    return re.sub(r"\s+", " ", re.sub(r"\s*\([^)]*\)\s*", " ", inner)).strip()


def _clean_ipa(ipa: str) -> str:
    return "/" + _strip_notes(ipa[1:-1]) + "/"


def _broken_ipa(ipa: str, word: str, headwords: set[str]) -> bool:
    """True nếu IPA lấy từ FVDP là rác (xem chú thích phía trên)."""
    inner = ipa[1:-1] if len(ipa) >= 2 else ipa
    if not inner.strip():
        return True
    if " " not in word:
        if inner != inner.strip():
            return True
        # Nhiều cách đọc ngăn bằng ',' hoặc '-' là hợp lệ (/ði:, ði, ðə/); khoảng
        # trắng NẰM TRONG một cách đọc mới là dấu ký tự bị rơi (/w t/, /wi 'dr :/).
        # (',' đứng sát chữ là dấu trọng âm phụ, KHÔNG phải dấu ngăn: /,intrə'dju:s/)
        forms = re.split(r"\s*,\s+|\s+[-–]\s+", _strip_notes(inner))
        if any(not f or re.search(r"\s", f) for f in forms):
            return True
    if not re.fullmatch(r"[a-z]+", inner):
        return False                       # có ký hiệu IPA / trọng âm -> tin
    if inner == word.lower():
        return not (_SPELLED_LIKE_IPA.fullmatch(inner) and not _NOT_LIKE_IPA.search(inner))
    # chữ thường thuần, khác từ đích, lại đúng là một headword dài -> mảnh chữ cắt sai
    return len(inner) >= 5 and inner in headwords


def _pos_en(pos_vi: str) -> str | None:
    text = pos_vi.lower()
    for vi, en in POS_VI_TO_EN:
        if vi in text:
            return en
    return None


def parse_fvdp(path: Path) -> dict[str, dict]:
    entries: dict[str, dict] = {}
    word: str | None = None
    rec: dict | None = None
    block: dict | None = None

    with path.open(encoding="utf-8-sig", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n").strip()
            if not line:
                continue

            if line.startswith("@"):
                word, phonetic = _headword_ipa(line[1:].strip())
                # Từ điển dùng '_' nối cụm từ; ta chỉ quan tâm từ đơn nên giữ nguyên.
                rec = {"phonetic": phonetic, "pos_blocks": []}
                block = None
                # Một headword có thể xuất hiện nhiều lần (đồng âm khác nghĩa).
                # Giữ lần ĐẦU: từ điển xếp nghĩa phổ biến trước.
                entries.setdefault(word, rec)
                rec = entries[word]
                if rec.get("phonetic") is None and phonetic:
                    rec["phonetic"] = phonetic
                continue

            if rec is None:
                continue

            if line.startswith("*"):
                pos_vi = line[1:].strip().strip(",")
                block = {
                    "pos_vi": pos_vi,
                    "pos": _pos_en(pos_vi),
                    "senses": [],
                    "examples": [],
                }
                rec["pos_blocks"].append(block)
                continue

            if line.startswith("-"):
                sense = line[1:].strip()
                if not sense:
                    continue
                domain = None
                m = _DOMAIN_RE.match(sense)
                if m:
                    domain = m.group(1)
                    sense = sense[m.end():].strip()
                if not sense:
                    continue
                if block is None:
                    block = {"pos_vi": "", "pos": None, "senses": [], "examples": []}
                    rec["pos_blocks"].append(block)
                block["senses"].append({"gloss": sense, "domain": domain})
                continue

            if line.startswith("="):
                body = line[1:]
                if "+" not in body:
                    continue
                en, vi = body.split("+", 1)
                en = en.replace("_", " ").strip()
                vi = vi.strip()
                if not en or not vi:
                    continue
                if block is None:
                    block = {"pos_vi": "", "pos": None, "senses": [], "examples": []}
                    rec["pos_blocks"].append(block)
                block["examples"].append({"en": en, "vi": vi})

    return entries


_DEF_RE = re.compile(r"\d+\.\s*\(([^)]*)\)\s*(.+)")
# Bỏ các mục chỉ trỏ sang mục khác — chúng không mang nghĩa.
_SKIP = re.compile(r"^(alternative|abbreviation|acronym|initialism|obsolete form|"
                   r"archaic form|misspelling|synonym of|clipping of|romanization)", re.I)
_PAREN = re.compile(r"\s*\([^)]*\)")
_QUOTED = re.compile(r"[“”\"']")


def build_wikt_index(path: Path) -> dict[str, list[str]]:
    index: dict[str, set[str]] = defaultdict(set)
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        vi_head, _, defs = parts[0], parts[1], parts[2]
        vi_head = vi_head.strip()
        # Chỉ giữ từ/cụm tiếng Việt thường; bỏ tên riêng và chữ Hán.
        if not vi_head or vi_head[0].isupper() or len(vi_head) > 30:
            continue
        for chunk in defs.split("<br />"):
            chunk = chunk.strip()
            if chunk.startswith(">"):        # dòng ví dụ
                continue
            m = _DEF_RE.match(chunk)
            if not m:
                continue
            pos, gloss = m.group(1).strip().lower(), m.group(2).strip()
            if pos in {"name", "character", "suffix", "prefix", "infix"}:
                continue
            if _SKIP.match(gloss):
                continue
            gloss = _PAREN.sub("", gloss)
            gloss = _QUOTED.sub("", gloss).strip()
            # "to arrive, to reach" -> hai gloss riêng
            for g in re.split(r"[,;]", gloss):
                g = g.strip().lower()
                g = re.sub(r"^(to|a|an|the)\s+", "", g)
                if not g or len(g) > 40 or " " in g and len(g.split()) > 3:
                    continue
                index[g].add(vi_head)
    return {k: sorted(v)[:12] for k, v in index.items() if v}



SEED = 42
CEFR_ORDER = {"A1": 1, "A2": 2, "B1": 3, "B2": 4, "C1": 5, "C2": 6}
DIFFICULTY = {"A1": "beginner", "A2": "beginner", "B1": "intermediate",
              "B2": "intermediate", "C1": "advanced", "C2": "advanced"}

# --- Chuẩn hóa chính tả Mỹ -> Anh -------------------------------------------
# CEFR-J dùng chính tả Anh; NGSL dùng chính tả Mỹ. Không bắc cầu chỗ này thì
# ~400 từ rất thông dụng (program, center, color, organize...) bị gắn
# `cefr_unknown` một cách oan uổng — mô hình mất đặc trưng mạnh nhất của nó.
US_TO_UK_EXACT = {
    "program": "programme", "gray": "grey", "toward": "towards",
    "judgment": "judgement", "airplane": "aeroplane", "aluminum": "aluminium",
    "check": "cheque", "tire": "tyre", "plow": "plough", "mold": "mould",
    "skillful": "skilful", "fulfill": "fulfil", "enroll": "enrol",
    "install": "instal", "jewelry": "jewellery", "pajamas": "pyjamas",
    "practice": "practise", "story": "storey", "whiskey": "whisky",
}
US_TO_UK_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(.+)or$"), r"\1our"),          # color -> colour
    (re.compile(r"(.+)ors$"), r"\1ours"),
    (re.compile(r"(.+)ization$"), r"\1isation"),  # organization -> organisation
    (re.compile(r"(.+)ize$"), r"\1ise"),          # organize -> organise
    (re.compile(r"(.+)izing$"), r"\1ising"),
    (re.compile(r"(.+)yze$"), r"\1yse"),          # analyze -> analyse
    (re.compile(r"(.+)ter$"), r"\1tre"),          # center -> centre
    (re.compile(r"(.+)ters$"), r"\1tres"),
    (re.compile(r"(.+)se$"), r"\1ce"),            # defense -> defence
    (re.compile(r"(.+)log$"), r"\1logue"),        # catalog -> catalogue
    (re.compile(r"(.+)eled$"), r"\1elled"),
    (re.compile(r"(.+)eling$"), r"\1elling"),
]

# Gloss là tham chiếu chéo, không phải nghĩa -> chỉ dùng khi không còn gì khác.
_CROSSREF = re.compile(r"^(xem\b|như\b|viết tắt của\b|dạng của\b|số nhiều của\b)", re.I)
_WS = re.compile(r"\s{2,}")


def uk_variants(word: str) -> list[str]:
    out = []
    if word in US_TO_UK_EXACT:
        out.append(US_TO_UK_EXACT[word])
    for rx, repl in US_TO_UK_RULES:
        if rx.match(word):
            cand = rx.sub(repl, word)
            if cand != word:
                out.append(cand)
    return out


# --- Nạp nguồn ---------------------------------------------------------------
def load_list(path: Path) -> list[str]:
    words = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        words.append(line.split("\t")[0].strip().lower())
    return words


def load_ngsl_rank(path: Path) -> dict[str, int]:
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb[wb.sheetnames[0]]
    rank: dict[str, int] = {}
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        lemma, _wl, r = row[0], row[1], row[2]
        if lemma and isinstance(r, int):
            rank.setdefault(str(lemma).strip().lower(), r)
    return rank


def load_cefr(path: Path) -> dict[str, str]:
    best: dict[str, str] = {}
    with path.open(encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            raw = row["word"].strip().lower()
            lv = row["cefr_level"].strip()
            if lv not in CEFR_ORDER:
                continue
            # 188 dòng gộp nhiều biến thể vào một ô: "analyze/analyse",
            # "adviser/advisor". Tra khớp chính xác thì KHÔNG dạng nào tìm được
            # — phải tách ra thành từng khóa riêng.
            for w in (p.strip() for p in raw.split("/")):
                if not w:
                    continue
                if w not in best or CEFR_ORDER[lv] < CEFR_ORDER[best[w]]:
                    best[w] = lv
    return best


def cefr_of(word: str, table: dict[str, str]) -> tuple[str | None, str]:
    """Trả (mức, nguồn). nguồn = 'direct' | 'uk-variant' | ''."""
    if word in table:
        return table[word], "direct"
    for cand in uk_variants(word):
        if cand in table:
            return table[cand], "uk-variant"
    return None, ""


# --- Chọn nghĩa / ví dụ ------------------------------------------------------
def _has_real_sense(block: dict) -> bool:
    """Khối chỉ toàn tham chiếu chéo ('Xem COMMON AGRICULTURAL POLICY') không phải nghĩa."""
    return any(not _CROSSREF.match(s["gloss"]) for s in block["senses"])


def pick_block(rec: dict) -> dict | None:
    """Khối từ loại tốt nhất: có nghĩa THẬT, ưu tiên khối nhận dạng được từ loại."""
    blocks = [b for b in rec["pos_blocks"] if b["senses"]]
    if not blocks:
        return None
    real = [b for b in blocks if _has_real_sense(b)] or blocks
    with_pos = [b for b in real if b["pos"]]
    return (with_pos or real)[0]


def strip_parens(text: str) -> str:
    """Bỏ mọi cụm trong ngoặc, kể cả lồng nhau: 'giá ((nghĩa đen) & (bóng))' -> 'giá'."""
    out, depth = [], 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return _WS.sub(" ", "".join(out)).strip(" ,.;&")


def clean_gloss(raw: str) -> str:
    gloss = strip_parens(raw)
    gloss = gloss.split(";")[0].strip()      # nhiều nghĩa tách bằng ';' -> lấy nghĩa đầu
    gloss = _WS.sub(" ", gloss).strip(" ,.")
    if len(gloss) > 60:                      # cắt ở dấu phẩy, không cắt giữa chữ
        cut = gloss[:60].rfind(",")
        gloss = (gloss[:cut] if cut > 20 else gloss[:60]).strip(" ,")
    return gloss


def short_gloss(block: dict, wikt: list[str]) -> tuple[str, str, str]:
    """(gloss ngắn, gloss gốc đầy đủ, độ tin cậy).

    Từ điển chính xếp nghĩa theo lối từ điển cũ, KHÔNG theo tần suất: `stage`
    mở đầu bằng 'bệ, dài' chứ không phải 'sân khấu'. Nên trước khi lấy nghĩa
    đầu tiên, ta hỏi một nguồn độc lập (Wiktionary, bản 2026) xem nghĩa nào
    trong danh sách được xác nhận — và lấy nghĩa đó.

    Trả 'confirmed' nếu hai nguồn gặp nhau, 'single-source' nếu chỉ còn một.
    """
    senses = block["senses"]
    real = [s for s in senses if not _CROSSREF.match(s["gloss"])] or senses
    wikt_set = {w.lower() for w in wikt}

    for s in real:
        gloss = clean_gloss(s["gloss"])
        if not gloss:
            continue
        parts = [p.strip().lower() for p in gloss.split(",") if p.strip()]
        if any(p in wikt_set for p in parts):
            return gloss, s["gloss"].strip(), "confirmed"

    # Có nguồn đối chứng nhưng KHÔNG nghĩa nào khớp: đây đúng là nhóm hay sai
    # nhất (từ điển cũ để nghĩa cổ lên đầu — 'profile' ra 'nét mặt nhìn
    # nghiêng', 'decade' ra 'bộ mười'). Không tự đổi, vì chỉ mục đảo cũng nhiễu;
    # đánh dấu để người rà.
    label = "needs-review" if wikt_set else "single-source"
    for s in real:
        gloss = clean_gloss(s["gloss"])
        if gloss:
            return gloss, s["gloss"].strip(), label
    return "", "", ""


#: Thứ tự ưu tiên nguồn câu ví dụ. Càng nhỏ càng thắng.
#: Số nhỏ thắng. `curated` (bug #9, 2026-10-26) = nghĩa chọn lọc 1 nghĩa/từ theo
#: Cambridge, do máy soạn theo yêu cầu chủ dự án nhưng CHƯA có người duyệt —
#: thắng `llm` đại trà, thua `manual` (đã duyệt). Xem `MEANING_LABELS`.
EXAMPLE_PRIORITY = {"manual": 0, "curated": 1, "llm": 2, "tatoeba": 2, "fvdp": 3}

#: Nguồn trong file viết đè -> (meaning_source, meaning_confidence) ghi vào item.
#: `curated` chưa ai duyệt nên ghi ra là `llm` (CLAUDE.md: nội dung máy sinh phải
#: đếm tách được); `manual` là người đã kiểm -> `confirmed` (nhãn mà UI hiểu).
MEANING_LABELS = {"curated": ("llm", "llm"), "manual": ("manual", "confirmed")}


def load_example_overrides(paths: list[Path]) -> dict[str, dict]:
    """Nạp các file câu ví dụ viết đè, ưu tiên cao hơn câu lấy từ từ điển.

    Định dạng TSV, mỗi dòng: `từ<TAB>câu tiếng Anh<TAB>bản dịch tiếng Việt`.
    Dòng `#` là chú thích; dòng `# source: manual` khai báo nguồn cho cả file
    (mặc định `manual`). Nhờ khai báo này mà một câu người viết và một câu máy
    sinh không bao giờ lẫn vào nhau trong `example_source`.

    Vì sao cần cơ chế này: câu ví dụ trong từ điển gốc là cụm ngắn và cũ
    ("a man of sixty winters"). Sửa trong ứng dụng thì chỉ sửa BẢN SAO của một
    người và mất sau lần seed sau; sửa ở đây thì lần dựng nào cũng giữ.
    Cùng tinh thần với cột TSV thứ ba của `build_vocab_dataset.py`.
    """
    overrides: dict[str, dict] = {}
    for path in paths or []:
        if not path.is_file():
            raise SystemExit(f"Không thấy file câu ví dụ: {path}")
        source = "manual"
        for raw in path.read_text(encoding="utf-8-sig").splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                tag = line.lstrip("#").strip().lower()
                if tag.startswith("source:"):
                    source = tag.split(":", 1)[1].strip() or "manual"
                continue
            parts = [c.strip() for c in line.split("\t")]
            if len(parts) < 2 or not parts[0] or not parts[1]:
                continue
            word = parts[0].lower()
            cand = {"en": parts[1], "vi": parts[2] if len(parts) > 2 else "", "source": source,
                    "cols": parts}
            old = overrides.get(word)
            if old is None or EXAMPLE_PRIORITY.get(source, 9) < EXAMPLE_PRIORITY.get(old["source"], 9):
                overrides[word] = cand
    return overrides


#: Nhãn tiếng Việt mặc định khi file sửa nghĩa đổi từ loại mà FVDP không có
#: khối đúng từ loại đó.
POS_EN_TO_VI = {
    "noun": "danh từ", "verb": "động từ", "adjective": "tính từ", "adverb": "phó từ",
    "preposition": "giới từ", "conjunction": "liên từ", "pronoun": "đại từ",
    "determiner": "từ hạn định", "interjection": "thán từ", "auxiliary": "trợ động từ",
}


def load_meaning_overrides(paths: list[Path]) -> dict[str, dict]:
    """Nạp file sửa nghĩa viết đè. Cùng định dạng với file câu ví dụ:
    `từ<TAB>nghĩa tiếng Việt<TAB>ghi chú[<TAB>từ loại]`, dòng `# source: <tên>` khai nguồn.

    Cột 4 (tùy chọn, bug #9) sửa luôn TỪ LOẠI: khối nghĩa đầu tiên của FVDP hay
    là từ loại hiếm (say = danh từ "vải chéo"), sửa nghĩa mà giữ từ loại cũ thì
    thẻ hiện "say · noun · nói" — vẫn sai. Có cột 4 thì script chọn lại khối
    FVDP đúng từ loại đó (để nhãn tiếng Việt và câu ví dụ đi cùng nghĩa).

    Từ điển gốc xếp nghĩa theo lối từ điển cũ nên nghĩa đầu tiên đôi khi là
    nghĩa cổ hoặc nghĩa chuyên ngành hiếm: `crash` ra "vải thô", `mental` ra
    "cằm". Bước đối chứng Wiktionary gắn cờ được phần lớn những chỗ đó nhưng
    không tự sửa được. File này là chỗ ghi nghĩa đúng vào, và nó thắng mọi
    nguồn tự động.
    """
    fixes = load_example_overrides(paths)
    for word, fix in fixes.items():
        # Từ loại đi cùng DÒNG THẮNG (theo EXAMPLE_PRIORITY). Trước đây file nạp
        # sau luôn ghi đè từ loại dù nghĩa của nó thua -> nghĩa một nguồn, từ loại
        # nguồn khác.
        cols = fix.get("cols", [])
        pos = cols[3] if len(cols) > 3 and cols[3] else None
        if pos and pos not in POS_EN_TO_VI:
            raise SystemExit(f"Từ loại không hợp lệ cho '{word}': {pos}")
        fix["pos"] = pos
    return fixes


def load_phonetic_overrides(paths: list[Path]) -> dict[str, dict]:
    """Nạp file sửa phiên âm viết đè: `từ<TAB>/IPA/<TAB>ghi chú`, dòng
    `# source: <tên>` khai nguồn (mặc định `manual`).

    Dùng cho chỗ CHÍNH từ điển gốc sai mà quy tắc tách biến thể không cứu được
    (ví dụ FVDP ghi `afterward` kèm IPA của `afterwards`). Thắng mọi nguồn tự động.
    """
    fixes = load_example_overrides(paths)
    for word, fix in fixes.items():
        ipa = fix["en"].strip()
        if not (ipa.startswith("/") and ipa.endswith("/")):
            raise SystemExit(f"Phiên âm viết đè của '{word}' phải dạng /.../: {ipa}")
    return fixes


def pick_example(block: dict, word: str) -> dict | None:
    """Ví dụ tốt nhất: có chứa chính từ đó, đủ dài để thành câu, không quá dài."""
    best, best_score = None, -1.0
    for ex in block["examples"]:
        en = ex["en"].strip()
        n = len(en.split())
        if n < 3 or n > 20:
            continue
        score = 0.0
        if re.search(rf"\b{re.escape(word)}", en, re.I):
            score += 2.0
        if en[:1].isupper():
            score += 1.0
        if en.rstrip().endswith((".", "!", "?")):
            score += 1.0
        score += min(n, 12) / 24.0          # dài vừa phải thì hơn cụm 3 từ
        if score > best_score:
            best, best_score = ex, score
    return best


# --- Dựng ---------------------------------------------------------------------
def main(args) -> None:
    out_path: Path = args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path: Path = args.audit or out_path.with_name("audit_sample.csv")
    report_path = out_path.with_name(out_path.stem + "_report.json")
    items_per_set = args.per_set
    if items_per_set < 1:
        raise ValueError("--per-set must be positive")
    rng = random.Random(SEED)

    fvdp = parse_fvdp(args.dict_file)
    fvdp_keys = {k.lower(): k for k in fvdp}
    headwords = set(fvdp_keys)
    wikt = build_wikt_index(args.wikt_file) if args.wikt_file else {}
    overrides = load_example_overrides(args.examples)
    meaning_fix = load_meaning_overrides(args.meanings)
    phonetic_fix = load_phonetic_overrides(args.phonetics)
    if phonetic_fix:
        print(f"Phiên âm viết đè: {len(phonetic_fix):,} từ")
    if meaning_fix:
        print(f"Nghĩa viết đè: {len(meaning_fix):,} từ "
              f"({', '.join(sorted({o['source'] for o in meaning_fix.values()}))})")
    if overrides:
        print(f"Câu ví dụ viết đè: {len(overrides):,} từ "
              f"({', '.join(sorted({o['source'] for o in overrides.values()}))})")
    cefr = load_cefr(args.cefr)
    rank = load_ngsl_rank(args.ngsl_xlsx)

    sources = [("NGSL", load_list(args.ngsl)), ("NAWL", load_list(args.nawl))]
    with args.advanced.open(encoding="utf-8-sig") as fh:
        advanced = {row["headword"].strip().lower(): row["CEFR"].strip()
                    for row in csv.DictReader(fh)}
    sources.append(("Octanove", sorted(
        (word for word, level in advanced.items()
         if level in ("C1", "C2") and cefr.get(word) in ("C1", "C2")
         and re.fullmatch(r"[a-z]+(?:[- ][a-z]+)*", word)),
        key=lambda word: (-zipf_frequency(word, "en"), word),
    )))
    seen: set[str] = set()
    records: list[dict] = []
    stats: Counter[str] = Counter()

    for source, words in sources:
        for order, word in enumerate(words):
            if word in seen:
                stats["trùng, bỏ"] += 1
                continue
            seen.add(word)
            stats[f"{source}: đầu vào"] += 1

            key = fvdp_keys.get(word)
            rec = fvdp.get(key) if key else None
            block = pick_block(rec) if rec else None
            if block is None:
                stats["bỏ: không có nghĩa tiếng Việt"] += 1
                continue

            wikt_cands = wikt.get(word, [])
            gloss, gloss_full, confidence = short_gloss(block, wikt_cands)
            fix = meaning_fix.get(word)
            meaning_source = "fvdp"
            if fix:
                meaning_source, confidence = MEANING_LABELS.get(
                    fix["source"], (fix["source"], fix["source"]))
                gloss = fix["en"]
            pos, pos_src, pos_vi = block["pos"] or "", "fvdp" if block["pos"] else "", block["pos_vi"]
            if fix and fix.get("pos") and fix["pos"] != block["pos"]:
                pos, pos_src = fix["pos"], meaning_source
                same = [b for b in rec["pos_blocks"] if b["pos"] == pos and b["senses"]]
                if same:
                    block = same[0]            # ví dụ FVDP lấy theo đúng từ loại mới
                    # nhãn FVDP đôi khi dính dạng chia: "động từ sold" -> "động từ"
                    pos_vi = re.sub(r"(\s+[A-Za-z;]+)+\s*$", "", block["pos_vi"]).strip(" ,") or POS_EN_TO_VI[pos]
                else:
                    pos_vi = POS_EN_TO_VI[pos]
                stats["từ loại viết đè"] += 1
            if not gloss:
                stats["bỏ: nghĩa rỗng sau khi làm sạch"] += 1
                continue

            level, level_src = cefr_of(word, cefr)
            # IPA: mục đã lấy nghĩa trước, rồi mục viết thường đúng chữ (mục thuật
            # ngữ viết hoa thường không có IPA); bỏ IPA hỏng — thiếu thì để trống.
            phonetic, phonetic_src = "", ""
            for cand_rec in (rec, fvdp.get(word)):
                cand = (cand_rec or {}).get("phonetic") or ""
                if cand and not _broken_ipa(cand, word, headwords):
                    phonetic, phonetic_src = _clean_ipa(cand), "fvdp"
                    break
                if cand:
                    stats["IPA hỏng trong nguồn, bỏ"] += 1
            pfix = phonetic_fix.get(word)
            if pfix:
                phonetic, phonetic_src = pfix["en"], pfix["source"]
            example = overrides.get(word) or pick_example(block, word)
            example_source = (example or {}).get("source", "fvdp" if example else "")

            records.append({
                "word": word,
                "meaning": gloss,
                "meaning_full": gloss_full,
                "meaning_source": meaning_source,
                "meaning_confidence": confidence,
                "meaning_alt": ", ".join(wikt_cands[:5]),
                "phonetic": phonetic,
                "phonetic_source": phonetic_src,
                "part_of_speech": pos,
                "part_of_speech_source": pos_src,
                "part_of_speech_vi": pos_vi,
                "example": (example or {}).get("en", ""),
                "example_vi": (example or {}).get("vi", ""),
                "example_source": example_source,
                "cefr": level or "",
                "cefr_source": level_src,
                "list": source,
                "rank": rank.get(word, 10_000 + order),
                "zipf": round(zipf_frequency(word, "en"), 2),
            })
            stats[f"{source}: giữ"] += 1
            stats["có IPA"] += bool(phonetic)
            stats["IPA viết đè"] += bool(pfix)
            stats["có ví dụ"] += bool(example)
            if example:
                stats[f"ví dụ từ nguồn: {example_source}"] += 1
            stats["có từ loại"] += bool(pos)
            stats["có CEFR"] += bool(level)
            stats[f"CEFR nguồn: {level_src or 'không có'}"] += 1
            stats[f"nghĩa: {confidence}"] += 1
            stats["có đối chứng Wiktionary"] += bool(wikt_cands)

    # --- Gom thành bộ từ ------------------------------------------------------
    by_band: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in records:
        band = r["cefr"] or "NA"
        by_band[(r["list"], band)].append(r)

    # Chia theo (danh mục, mức CEFR) rồi cắt khúc. Có một bẫy ở đây: chia thuần
    # túy theo kích thước sinh ra những bộ 2-3 từ ở đuôi mỗi mức ("[C2] Cốt lõi 1"
    # đúng 2 từ). Một bộ 2 từ vô dụng trên giao diện, nên có bước gộp ở dưới.
    MIN_SET = max(20, items_per_set // 2)
    band_order = ["A1", "A2", "B1", "B2", "C1", "C2", "NA"]
    raw_sets: list[dict] = []
    for source in ("NGSL", "NAWL", "Octanove"):
        label = {"NGSL": "Cốt lõi", "NAWL": "Học thuật", "Octanove": "Nâng cao"}[source]
        for band in band_order:
            group = sorted(by_band.get((source, band), []), key=lambda r: r["rank"])
            if not group:
                continue
            for i in range(0, len(group), items_per_set):
                raw_sets.append({
                    "source": source, "label": label, "bands": [band],
                    "items": group[i:i + items_per_set],
                })

    # Gộp những khúc quá nhỏ vào khúc liền trước CÙNG danh mục; hết đường lùi
    # thì gộp vào khúc liền sau. Nhờ vậy không bộ nào dưới MIN_SET từ, trừ khi
    # cả danh mục chỉ có bấy nhiêu.
    merged: list[dict] = []
    for spec in raw_sets:
        prev = merged[-1] if merged else None
        if (len(spec["items"]) < MIN_SET and prev is not None
                and prev["source"] == spec["source"]
                and prev["bands"] == spec["bands"]):
            prev["items"] += spec["items"]
            for b in spec["bands"]:
                if b not in prev["bands"]:
                    prev["bands"].append(b)
        else:
            merged.append(spec)
    if (len(merged) > 1 and len(merged[0]["items"]) < MIN_SET
            and merged[0]["source"] == merged[1]["source"]
            and merged[0]["bands"] == merged[1]["bands"]):
        merged[1]["items"] = merged[0]["items"] + merged[1]["items"]
        merged[1]["bands"] = merged[0]["bands"] + merged[1]["bands"]
        merged.pop(0)

    def band_label(bands: list[str]) -> str:
        names = ["Chưa xếp mức" if b == "NA" else b for b in bands]
        return names[0] if len(names) == 1 else f"{names[0]}–{names[-1]}"

    # Tên bộ nói THẲNG bộ này là gì: mức CEFR + vị trí trong mức đó theo tần
    # suất. Tên cũ ("[A1] Cốt lõi 7") chỉ là số thứ tự, không cho người học biết
    # gì — mà đặt tên theo CHỦ ĐỀ thì không đặt được: cách chia ở trên gom theo
    # (nguồn × mức CEFR × tần suất), nên trong một bộ các từ hoàn toàn ngẫu
    # nhiên về chủ đề ([A1] Cốt lõi 4 = course, house, group, case, woman...).
    # Bịa một cái tên chủ đề cho nhóm đó là nói dối người học.
    #
    # Vị trí đếm TRONG MỨC, không dùng `rank` gốc: rank là hạng toàn cục trong
    # NGSL/NAWL, mà các mức đan xen nhau nên bộ A1 đầu tiên có rank 1–51 chứ
    # không phải 1–50. Số đếm trong mức mới là thứ người học hiểu được
    # ("mình đang ở 50 từ A1 đầu tiên").
    def set_name(label: str, name_band: str, lo: int, hi: int) -> str:
        # "Chưa xếp mức" không phải một mức, nên không ghép thẳng vào tên được
        # ("Học thuật Chưa xếp mức" đọc như lỗi); cho vào ngoặc.
        band = f"(chưa xếp mức)" if name_band == "Chưa xếp mức" else name_band
        scope = band if label == "Cốt lõi" else f"{label} {band}"
        return f"{scope} · Từ {lo}–{hi}"

    def set_desc(label: str, name_band: str, lo: int, hi: int,
                 n: int, source: str) -> str:
        where = ("chưa xếp mức CEFR" if name_band == "Chưa xếp mức"
                 else f"mức {name_band}")
        return (f"{n} từ {label.lower()} {where} — vị trí {lo}–{hi} trong nhóm, "
                f"xếp theo tần suất {source}.")

    word_sets = []
    seen_in_band: Counter[tuple[str, str]] = Counter()
    for spec in merged:
        bands, label, source = spec["bands"], spec["label"], spec["source"]
        name_band = band_label(bands)
        key = (label, name_band)
        lo = seen_in_band[key] + 1
        hi = seen_in_band[key] + len(spec["items"])
        seen_in_band[key] = hi
        # Độ khó lấy theo mức CAO NHẤT trong bộ — prior cold-start nên thận trọng.
        real = [b for b in bands if b != "NA"]
        top = max(real, key=lambda b: CEFR_ORDER[b]) if real else None
        word_sets.append({
            "name": set_name(label, name_band, lo, hi),
            "category": label,
            "difficulty": DIFFICULTY.get(top, "intermediate"),
            "description": set_desc(label, name_band, lo, hi, len(spec["items"]), source),
            "seed": True,
            "cefr": top or "",
            "list": source,
            "items": spec["items"],
        })

    payload = {
        "version": "2.0",
        "generated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": {
            "headwords": "NGSL 1.x + NAWL 1.x + Octanove C1/C2 1.0 — CC BY-SA 4.0; xem data/sources/README.md",
            "meanings": "Từ điển Anh-Việt định dạng FVDP (Free Vietnamese Dictionary Project)",
            "phonetic_pos_examples": "cùng nguồn FVDP (IPA, từ loại, ví dụ kèm bản dịch); IPA viết đè: data/sources/phonetics_manual.tsv — xem --phonetics",
            "cefr": "CEFR-J Vocabulary Profile 1.5 (Tono Lab, TUFS) + Octanove C1/C2 1.0 (CC BY-SA 4.0)",
            "example_overrides": "data/sources/examples_*.tsv nếu có — xem --examples",
            # Trường này TỰ TÍNH từ stats, không viết tay. Bản trước hardcode
            # "không dùng ở bất kỳ bước nào" và câu đó thành sai ngay khi
            # examples_llm.tsv ra đời — file dữ liệu tự khai gian về nguồn gốc
            # của chính nó. Nguồn duy nhất của sự thật là số item đã đếm được.
            "llm": (
                f"không quyết định nhãn (nghĩa gốc, CEFR). Có sinh: "
                f"{stats.get('ví dụ từ nguồn: llm', 0)} câu ví dụ, "
                f"{stats.get('nghĩa: llm', 0)} nghĩa viết đè — "
                f"tra bằng example_source/meaning_source == 'llm'"
            ),
        },
        "stats": {
            "total": len(records),
            "word_sets": len(word_sets),
            **{k: v for k, v in sorted(stats.items())},
        },
        "word_sets": word_sets,
    }
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    # --- Mẫu kiểm định 200 từ -------------------------------------------------
    # Mẫu PHÂN TẦNG: 100 từ nhóm cần rà, 60 nhóm một nguồn, 40 nhóm đã đối chứng.
    # Lấy ngẫu nhiên đều thì 46% công sức đổ vào nhóm đã có hai nguồn đồng ý —
    # đúng nhóm ít khả năng sai nhất.
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in records:
        buckets[r["meaning_confidence"]].append(r)
    sample = []
    for label, n in (("needs-review", 100), ("single-source", 60), ("confirmed", 40)):
        pool = buckets.get(label, [])
        sample += rng.sample(pool, min(n, len(pool)))
    sample.sort(key=lambda r: r["rank"])
    with audit_path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["word", "cefr", "part_of_speech", "phonetic", "meaning",
                    "do_tin_cay", "goi_y_wiktionary", "meaning_full",
                    "example", "example_vi", "nghia_dung? (d/s)", "ghi_chu"])
        for r in sample:
            w.writerow([r["word"], r["cefr"], r["part_of_speech"], r["phonetic"],
                        r["meaning"], r["meaning_confidence"], r["meaning_alt"],
                        r["meaning_full"], r["example"], r["example_vi"], "", ""])

    report = {"stats": payload["stats"],
              "sets": [{"name": s["name"], "items": len(s["items"])} for s in word_sets]}
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    total = len(records)
    print(f"Đã ghi          : {out_path}")
    print(f"Mẫu kiểm định   : {audit_path}")
    print(f"Tổng từ giữ lại : {total:,}")
    print(f"Số bộ từ        : {len(word_sets)}")
    for field in ("có IPA", "có ví dụ", "có từ loại", "có CEFR",
                  "nghĩa: confirmed", "có đối chứng Wiktionary"):
        print(f"  {field:<12} {stats[field]:>5,} = {stats[field] / total:6.1%}")
    print("\nChi tiết:")
    for k, v in sorted(stats.items()):
        print(f"  {k:<36} {v:>6,}")

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Dựng bộ từ vựng nền NGSL + NAWL")
    p.add_argument("--ngsl", type=Path, required=True, help="danh sách NGSL (1 từ/dòng hoặc TSV)")
    p.add_argument("--nawl", type=Path, required=True, help="danh sách NAWL")
    p.add_argument("--ngsl-xlsx", type=Path, required=True, dest="ngsl_xlsx",
                   help="NGSL kèm SFI (.xlsx) — lấy thứ hạng tần suất")
    p.add_argument("--dict", type=Path, required=True, dest="dict_file",
                   help="từ điển Anh-Việt định dạng FVDP (.txt)")
    p.add_argument("--wikt", type=Path, default=None, dest="wikt_file",
                   help="từ điển Việt-Anh Wiktionary (.txt) để đối chứng nghĩa")
    p.add_argument("--meanings", type=Path, action="append", default=[],
                   help="file TSV sửa nghĩa viết đè; từ<TAB>nghĩa<TAB>ghi chú")
    p.add_argument("--phonetics", type=Path, action="append", default=[],
                   help="file TSV sửa phiên âm viết đè; từ<TAB>/IPA/<TAB>ghi chú")
    p.add_argument("--examples", type=Path, action="append", default=[],
                   help="file TSV câu ví dụ viết đè (dùng nhiều lần được); "
                        "từ<TAB>câu tiếng Anh<TAB>bản dịch")
    p.add_argument("--cefr", type=Path, required=True, help="cefr_wordlist.csv")
    p.add_argument("--advanced", type=Path,
                   default=Path(__file__).resolve().parents[2] / "data" / "octanove-vocabulary-profile-c1c2-1.0.csv",
                   help="Octanove C1/C2 1.0, CC BY-SA 4.0")
    p.add_argument("--out", type=Path, required=True, help="vocab_seed_core.json")
    p.add_argument("--audit", type=Path, default=None,
                   help="CSV mẫu kiểm định (mặc định: cạnh --out)")
    p.add_argument("--per-set", type=int, default=50, dest="per_set",
                   help="số từ mỗi bộ (mặc định 50)")
    return p.parse_args()


if __name__ == "__main__":
    use_utf8_console()
    main(parse_args())
