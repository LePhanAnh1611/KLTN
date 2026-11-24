from app.scripts._console import use_utf8_console
"""Dựng bộ dữ liệu từ vựng cho seed — chạy MỘT LẦN, kết quả cache lại.

    python -m app.scripts.build_vocab_dataset

Đầu vào : `data/wordlists/*.tsv` — từ + nghĩa tiếng Việt (viết tay)
Đầu ra  : `data/vocab_seed.json` — thêm phiên âm IPA, từ loại, câu ví dụ

Vì sao chia việc như vậy:

- **Nghĩa tiếng Việt viết tay.** Đây là phần máy dịch sai nhiều nhất và người
  học đọc nhiều nhất. Đo thực tế với qwen2.5:7b: "deadline" ra "giới hạn thời
  gian" thay vì "hạn chót". Sai kiểu đó không lộ ra ở test nào cả, chỉ người học
  chịu.
- **IPA / từ loại / câu ví dụ lấy tự động** từ dictionaryapi.dev (Wiktionary).
  Đây là dữ liệu khách quan, tra được, và tra nhanh (~0,2s/từ) — không có lý do
  gì ngồi gõ tay.
- **Ollama chỉ để vá chỗ thiếu.** Từ nào API không có câu ví dụ thì nhờ mô hình
  cục bộ sinh, và ĐÁNH DẤU nguồn để biết câu nào do máy viết.

Cache theo từng từ trong `data/.vocab_cache.json`: chạy lại chỉ tra những từ
mới, không đụng tới phần đã có. Nhờ vậy thêm một bộ từ không phải trả giá cho
cả tập.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
WORDLIST_DIR = ROOT / "data" / "wordlists"
OUTPUT_PATH = ROOT / "data" / "vocab_seed.json"
CACHE_PATH = ROOT / "data" / ".vocab_cache.json"

DICTIONARY_API = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
# API công cộng, không có khóa. Đo thực tế: 0,15s/lần bị chặn 429 sau ~180 từ.
REQUEST_DELAY_SEC = 0.6
REQUEST_TIMEOUT_SEC = 12.0
# Gặp 429 thì nghỉ dài rồi thử lại, thay vì bỏ từ đó luôn
RATE_LIMIT_BACKOFF_SEC = (5.0, 15.0, 40.0)
# Không đặt User-Agent thì dictionaryapi.dev trả 403
USER_AGENT = "KLTN-DKT-vocab dataset builder (educational use)"

# Từ loại API trả về -> nhãn dùng trong ứng dụng
POS_MAP = {
    "noun": "noun", "verb": "verb", "adjective": "adjective",
    "adverb": "adverb", "pronoun": "pronoun", "preposition": "preposition",
    "conjunction": "conjunction", "interjection": "interjection",
}

# Câu ví dụ quá ngắn không dạy được gì, quá dài thì khó đọc to
MIN_EXAMPLE_WORDS, MAX_EXAMPLE_WORDS = 4, 22


@dataclass
class Entry:
    word: str
    meaning: str                     # tiếng Việt, viết tay
    phonetic: str | None = None
    part_of_speech: str | None = None
    example: str | None = None
    # 'dictionary' | 'llm' | 'none' — biết câu ví dụ từ đâu ra
    example_source: str = "none"


@dataclass
class WordSetSpec:
    name: str
    category: str
    difficulty: str
    description: str
    entries: list[Entry] = field(default_factory=list)
    # False = chỉ để TRA CỨU (làm giàu IPA/ví dụ cho từ do chỗ khác tạo ra),
    # không dựng thành bộ từ công khai. Đánh dấu bằng `| seed=no` ở dòng `@`.
    seed: bool = True


# ---------------------------------------------------------------- Đọc đầu vào


def parse_wordlist(path: Path) -> WordSetSpec:
    """Đọc một file .tsv: dòng `@` là metadata, còn lại là `từ<TAB>nghĩa`."""
    name = path.stem
    spec = WordSetSpec(name=name, category="Chung", difficulty="intermediate",
                       description="")

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("@"):
            parts = [p.strip() for p in line[1:].split("|")]
            spec.name = parts[0] if parts else name
            if len(parts) > 1:
                spec.category = parts[1]
            if len(parts) > 2:
                spec.difficulty = parts[2]
            if len(parts) > 3:
                spec.description = parts[3]
            if len(parts) > 4:
                spec.seed = parts[4].lower() not in {"seed=no", "no"}
            continue

        if "\t" not in line:
            logger.warning("%s: bỏ qua dòng thiếu TAB: %r", path.name, line[:50])
            continue

        # Cột 3 (tùy chọn) là câu ví dụ VIẾT TAY — dùng khi từ điển không có câu
        # nào dùng được và câu LLM sinh ra bị sai/gượng. Đây là lối thoát duy nhất
        # để sửa vĩnh viễn một từ mà không mất khi dựng lại dataset.
        parts = [p.strip() for p in line.split("\t")]
        word, meaning = parts[0], parts[1]
        example = parts[2] if len(parts) > 2 and parts[2] else None
        if word and meaning:
            spec.entries.append(Entry(word=word, meaning=meaning, example=example,
                                      example_source="manual" if example else "none"))

    return spec


def load_wordlists(directory: Path | None = None) -> list[WordSetSpec]:
    target = directory or WORDLIST_DIR
    return [parse_wordlist(p) for p in sorted(target.glob("*.tsv"))]


# ---------------------------------------------------------------- Cache


def load_cache() -> dict:
    if CACHE_PATH.is_file():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def save_cache(cache: dict) -> None:
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")


# ---------------------------------------------------------------- Tra từ điển


def _usable_example(text: str | None, word: str) -> bool:
    """Câu dùng được: đủ dài, không quá dài, và CHỨA CẢ CỤM từ cần học.

    Ràng buộc cuối quan trọng nhất — API hay trả câu ví dụ của một nghĩa khác.
    Với cụm nhiều từ ("side effect") phải khớp CẢ CỤM: chỉ khớp "side" sẽ nhận
    nhầm câu nói về "side" theo nghĩa hoàn toàn khác.

    Khớp theo ranh giới từ nhưng cho phép đuôi biến thể ("deploy" khớp
    "deployed", "deploying") — cùng một từ, không có lý do loại.
    """
    if not text:
        return False
    words = text.split()
    if not (MIN_EXAMPLE_WORDS <= len(words) <= MAX_EXAMPLE_WORDS):
        return False
    pattern = re.compile(r"\b" + re.escape(word.lower()) + r"\w*", re.IGNORECASE)
    return pattern.search(text) is not None


def _usable_phonetic(text: str | None) -> bool:
    """IPA dùng được.

    API đôi khi trả dạng HẬU TỐ ("/-əsəs/" cho "hypothesis") — đó là phiên âm
    của phần đuôi, hiển thị cho người học sẽ gây hiểu sai cách đọc cả từ.
    """
    if not text:
        return False
    stripped = text.strip().strip("/[]").strip()
    return len(stripped) >= 2 and not stripped.startswith("-")


class LookupFailed(Exception):
    """Tra hỏng vì lý do TẠM THỜI (429, timeout, mạng).

    Phân biệt với "từ không có trong từ điển": cái sau là sự thật ổn định nên
    cache được, cái này thì KHÔNG — cache lại là vĩnh viễn mất từ đó, và chạy
    lại cũng không cứu được vì đã có sẵn trong cache.
    """


def fetch_from_dictionary(word: str) -> dict:
    """Tra IPA / từ loại / câu ví dụ.

    Trả {} nếu từ không có trong từ điển (ổn định, cache được).
    Ném `LookupFailed` nếu hỏng tạm thời — caller không được cache.
    """
    url = DICTIONARY_API.format(word=urllib.parse.quote(word))
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    payload = None
    for attempt, backoff in enumerate((0.0, *RATE_LIMIT_BACKOFF_SEC)):
        if backoff:
            logger.info("Bị chặn tốc độ, nghỉ %.0fs rồi thử lại %r", backoff, word)
            time.sleep(backoff)
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SEC) as response:
                payload = json.load(response)
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {}                    # từ không có trong từ điển — bình thường
            if exc.code != 429:
                raise LookupFailed(f"HTTP {exc.code}") from exc
            if attempt == len(RATE_LIMIT_BACKOFF_SEC):
                raise LookupFailed("bị chặn tốc độ liên tục") from exc
        except Exception as exc:             # noqa: BLE001 — nguồn ngoài
            if attempt == len(RATE_LIMIT_BACKOFF_SEC):
                raise LookupFailed(str(exc)) from exc

    if not payload:
        return {}
    entry = payload[0]

    candidates = [entry.get("phonetic")] + [
        p.get("text") for p in entry.get("phonetics", [])
    ]
    phonetic = next((c for c in candidates if _usable_phonetic(c)), None)

    part_of_speech = example = None
    for meaning in entry.get("meanings", []):
        pos = POS_MAP.get((meaning.get("partOfSpeech") or "").lower())
        for definition in meaning.get("definitions", []):
            candidate = (definition.get("example") or "").strip()
            if _usable_example(candidate, word):
                # Lấy từ loại của CHÍNH nghĩa có câu ví dụ dùng được, để hai
                # trường không nói về hai nghĩa khác nhau
                return {"phonetic": phonetic, "part_of_speech": pos, "example": candidate}
        if part_of_speech is None and pos:
            part_of_speech = pos

    return {"phonetic": phonetic, "part_of_speech": part_of_speech, "example": example}


# ---------------------------------------------------------------- Vá bằng LLM


def generate_example(word: str, meaning: str, base_url: str, model: str) -> str | None:
    """Nhờ Ollama viết câu ví dụ. Trả None nếu không dùng được."""
    system = (
        "Bạn viết câu ví dụ tiếng Anh cho người học. "
        'Trả về DUY NHẤT JSON {"sentence": "..."}. '
        "Câu NGẮN (6-14 từ), tự nhiên, BẮT BUỘC chứa từ được yêu cầu. "
        "Không giải thích."
    )
    user = f'Từ: "{word}" (nghĩa tiếng Việt: {meaning}). Viết một câu ví dụ.'

    body = json.dumps({
        "model": model, "stream": False, "format": "json",
        "options": {"temperature": 0.2, "num_predict": 120},
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }).encode()
    request = urllib.request.Request(
        f"{base_url}/api/chat", data=body, headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            content = json.load(response)["message"]["content"]
        sentence = str(json.loads(content).get("sentence") or "").strip()
    except Exception as exc:                 # noqa: BLE001
        logger.warning("Ollama không sinh được ví dụ cho %r: %s", word, exc)
        return None

    return sentence if _usable_example(sentence, word) else None


def sense_matches(word: str, meaning: str, example: str, base_url: str, model: str) -> bool:
    """Câu ví dụ có dùng từ ĐÚNG NGHĨA đang dạy không?

    `_usable_example` chỉ kiểm tra câu CÓ CHỨA từ — không đủ với từ đa nghĩa.
    Đo thực tế trên dữ liệu này: "ticket" (vé) ra câu về liên danh tranh cử,
    "station" (nhà ga) ra câu về địa vị xã hội, "map" (bản đồ) ra câu về map
    game. Người học đọc "vé" rồi thấy câu bầu cử thì học sai luôn.

    Nghi ngờ thì cho qua (trả True): LLM hỏng hoặc trả rác không được phép xóa
    một câu ví dụ vốn dĩ đúng.
    """
    system = (
        "Bạn kiểm tra câu ví dụ cho từ điển Anh-Việt. "
        'Trả về DUY NHẤT JSON {"match": true} hoặc {"match": false}. '
        "match=true nếu câu dùng từ ĐÚNG theo nghĩa tiếng Việt đã cho; "
        "match=false nếu câu dùng từ đó theo một nghĩa KHÁC. Không giải thích."
    )
    user = (f'Từ: "{word}"\nNghĩa tiếng Việt cần dạy: {meaning}\n'
            f'Câu ví dụ: "{example}"\nCâu này có dùng đúng nghĩa đó không?')

    body = json.dumps({
        "model": model, "stream": False, "format": "json",
        "options": {"temperature": 0.0, "num_predict": 40},
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }).encode()
    request = urllib.request.Request(
        f"{base_url}/api/chat", data=body, headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            content = json.load(response)["message"]["content"]
        verdict = json.loads(content).get("match")
    except Exception as exc:                 # noqa: BLE001
        logger.warning("Ollama không kiểm tra được nghĩa của %r: %s", word, exc)
        return True

    return verdict is not False


# ---------------------------------------------------------------- Dựng


def build(
    *,
    use_llm: bool = False,
    verify_sense: bool = False,
    ollama_url: str = "http://localhost:11434",
    ollama_model: str = "qwen2.5:7b",
    directory: Path | None = None,
    limit: int | None = None,
) -> dict:
    specs = load_wordlists(directory)
    cache = load_cache()

    stats = {"total": 0, "from_cache": 0, "fetched": 0, "lookup_failed": 0,
             "with_phonetic": 0, "with_example": 0, "llm_examples": 0,
             "llm_cached": 0, "no_example": 0, "sense_rejected": 0}

    for spec in specs:
        for entry in spec.entries[:limit] if limit else spec.entries:
            stats["total"] += 1
            key = entry.word.lower()

            if key in cache:
                data = cache[key]
                stats["from_cache"] += 1
            else:
                try:
                    data = fetch_from_dictionary(entry.word)
                except LookupFailed as exc:
                    # KHÔNG cache lỗi tạm thời — lần chạy sau phải thử lại được
                    logger.warning("Bỏ qua %r lần này: %s", entry.word, exc)
                    stats["lookup_failed"] += 1
                    data = {}
                else:
                    cache[key] = data
                    stats["fetched"] += 1
                time.sleep(REQUEST_DELAY_SEC)

            entry.phonetic = data.get("phonetic")
            entry.part_of_speech = data.get("part_of_speech")

            # Câu viết tay trong .tsv thắng tất cả — nó có mặt ở đó chính vì
            # câu tự động đã sai một lần rồi.
            if entry.example_source != "manual":
                entry.example = data.get("example")
                entry.example_source = "dictionary" if entry.example else "none"

                # Câu LLM đã sinh lần trước nằm trong cache — dùng lại. Không đọc
                # lại thì chạy lần sau mất hết câu (nếu bỏ --use-llm) hoặc sinh
                # lại từ đầu ~10 phút và ra câu khác (nếu có --use-llm).
                if not entry.example and data.get("llm_example"):
                    entry.example = data["llm_example"]
                    entry.example_source = "llm"
                    stats["llm_cached"] += 1

            if entry.phonetic:
                stats["with_phonetic"] += 1

            # Câu TỪ ĐIỂN có thể chứa đúng từ nhưng theo nghĩa khác (từ đa nghĩa).
            #
            # Cờ --verify-sense chỉ quyết định có HỎI LLM cho từ chưa được chấm
            # hay không. Kết luận ĐÃ CÓ trong cache thì luôn tôn trọng, kể cả khi
            # chạy không kèm cờ — nếu không, một lần build "cho nhanh" sẽ lặng lẽ
            # dựng lại đúng những câu sai nghĩa vừa loại đi.
            if entry.example_source == "dictionary":
                verdict = data.get("sense_ok")
                if verdict is None and verify_sense:
                    verdict = sense_matches(entry.word, entry.meaning,
                                            entry.example, ollama_url, ollama_model)
                    data = {**data, "sense_ok": verdict}
                    cache[key] = data
                if verdict is False:
                    logger.info("%r: câu từ điển sai nghĩa, thay bằng câu khác", entry.word)
                    stats["sense_rejected"] += 1
                    # Đã có câu thay thế thì dùng luôn, khỏi gọi lại LLM
                    if data.get("llm_example"):
                        entry.example = data["llm_example"]
                        entry.example_source = "llm"
                        stats["llm_cached"] += 1
                    else:
                        entry.example = None
                        entry.example_source = "none"

            if not entry.example and use_llm:
                generated = generate_example(entry.word, entry.meaning,
                                             ollama_url, ollama_model)
                if generated:
                    entry.example = generated
                    entry.example_source = "llm"
                    cache[key] = {**data, "llm_example": generated}
                    stats["llm_examples"] += 1

            if entry.example:
                stats["with_example"] += 1
            else:
                stats["no_example"] += 1

            # Lưu cache liên tục để dừng giữa chừng không mất công đã làm
            if stats["fetched"] % 25 == 0:
                save_cache(cache)

    save_cache(cache)

    payload = {
        "version": "1.0",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": {
            "meanings": "viết tay (data/wordlists/*.tsv)",
            "phonetic_pos_examples": "dictionaryapi.dev (Wiktionary)",
            "generated_examples": "Ollama cục bộ" if use_llm else "không dùng",
        },
        "stats": stats,
        "word_sets": [
            {
                "name": spec.name,
                "category": spec.category,
                "difficulty": spec.difficulty,
                "description": spec.description,
                "seed": spec.seed,
                "items": [
                    {
                        "word": e.word, "meaning": e.meaning,
                        "phonetic": e.phonetic, "part_of_speech": e.part_of_speech,
                        "example": e.example, "example_source": e.example_source,
                    }
                    for e in spec.entries
                ],
            }
            for spec in specs
        ],
    }

    OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return payload


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Dựng bộ dữ liệu từ vựng cho seed")
    parser.add_argument("--use-llm", action="store_true",
                        help="Nhờ Ollama viết câu ví dụ cho từ mà từ điển không có "
                             "(chậm, ~5s/từ)")
    parser.add_argument("--verify-sense", action="store_true",
                        help="Nhờ Ollama kiểm tra câu TỪ ĐIỂN có dùng đúng nghĩa "
                             "đang dạy không; sai thì viết lại (cần --use-llm)")
    parser.add_argument("--ollama-url", default="http://localhost:11434")
    parser.add_argument("--ollama-model", default="qwen2.5:7b")
    parser.add_argument("--limit", type=int, default=None,
                        help="Chỉ xử lý N từ đầu mỗi bộ (để thử nhanh)")
    args = parser.parse_args()

    payload = build(
        use_llm=args.use_llm, verify_sense=args.verify_sense,
        ollama_url=args.ollama_url,
        ollama_model=args.ollama_model, limit=args.limit,
    )

    stats = payload["stats"]
    print(f"\nĐã ghi {OUTPUT_PATH}")
    print(f"  bộ từ            : {len(payload['word_sets'])}")
    print(f"  tổng số từ       : {stats['total']}")
    print(f"  lấy từ cache     : {stats['from_cache']}")
    print(f"  tra mới          : {stats['fetched']}")
    print(f"  có phiên âm      : {stats['with_phonetic']} "
          f"({stats['with_phonetic'] / max(stats['total'], 1):.0%})")
    print(f"  có câu ví dụ     : {stats['with_example']} "
          f"({stats['with_example'] / max(stats['total'], 1):.0%})")
    if stats["llm_examples"] or stats["llm_cached"]:
        print(f"    LLM viết mới     : {stats['llm_examples']}")
        print(f"    LLM lấy lại cache: {stats['llm_cached']}")
    if stats["sense_rejected"]:
        print(f"  câu SAI NGHĨA bị loại: {stats['sense_rejected']} (đã viết lại)")
    if stats["lookup_failed"]:
        print(f"  tra HỎNG tạm thời: {stats['lookup_failed']}"
              " — chạy lại lệnh này để thử tiếp (đã có cache nên nhanh)")
    if stats["no_example"]:
        print(f"  THIẾU câu ví dụ  : {stats['no_example']}"
              " — chạy lại với --use-llm để bù")


if __name__ == "__main__":
    use_utf8_console()
    main()
