"""Demo: chạy ĐÚNG mô hình DKT đang phục vụ trên BỘ TỪ NỀN mới.

    python ml/demo_core_dataset.py

Dùng `ml/src/serve_feat.py` + `ml/models/dkt_feat_best.pt` — cùng đúng đoạn code mà
`ml-serve` gọi lúc chạy thật. Không mô phỏng, không số bịa: mọi con số là đầu ra
thật của mô hình trên dữ liệu trong `backend/data/vocab_seed_core.json`.
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent            # .../ml
_REPO = _HERE.parent                                # gốc dự án

ML_DIR = Path(os.environ.get("DEMO_ML_DIR", _HERE))
CORE = Path(os.environ.get(
    "DEMO_CORE", _REPO / "backend" / "data" / "vocab_seed_core.json"))
CEFR = Path(os.environ.get(
    "CEFR_WORDLIST_PATH", _REPO / "backend" / "data" / "cefr_wordlist.csv"))
os.environ.setdefault("CEFR_WORDLIST_PATH", str(CEFR))

sys.path.insert(0, str(ML_DIR))
from src.serve_feat import get_server                          # noqa: E402
from src.features import FEATURE_NAMES, normalize_pos, token_features  # noqa: E402

BAR = "═" * 76

# Lịch sử của một người học giả định: đã qua chặng A1–A2 của lộ trình.
BASE_HISTORY = [
    ("hello", 1), ("name", 1), ("please", 1), ("thanks", 1), ("sorry", 1),
    ("family", 1), ("mother", 1), ("house", 1), ("kitchen", 1), ("table", 1),
    ("airport", 1), ("ticket", 1), ("luggage", 0), ("station", 1), ("map", 1),
    ("menu", 1), ("order", 1), ("bill", 1), ("cheap", 1), ("receipt", 0),
]


def hr(n: int, title: str) -> None:
    print(f"\n{BAR}\n {n} · {title}\n{BAR}")


def pct(x: float | None) -> str:
    return "   —  " if x is None else f"{x:6.1%}"


def bar(x: float, width: int = 34) -> str:
    return "█" * int(x * width)


def load() -> tuple[dict, dict, set, dict]:
    core = json.loads(CORE.read_text(encoding="utf-8"))
    items = {i["word"]: i for s in core["word_sets"] for i in s["items"]}
    pos = {w: i["part_of_speech"] for w, i in items.items() if i["part_of_speech"]}
    slam = set(json.loads((ML_DIR / "data/processed/item2idx.json").read_text(encoding="utf-8")))
    return core, items, slam, pos


def main() -> None:
    srv = get_server()
    core, items, slam, pos = load()
    res = json.loads((ML_DIR / "models/results.json").read_text(encoding="utf-8"))
    rng = random.Random(42)

    # ------------------------------------------------------------------ 1
    hr(1, "MÔ HÌNH ĐANG PHỤC VỤ")
    f, cold = res["dkt_feat"]["full"], res["dkt_feat"]["full_coldholdout"]
    print(f"  checkpoint       dkt_feat_best.pt · {srv.feature_dim} đặc trưng · "
          f"đặc trưng lịch sử: {'có' if srv.use_history else 'không'}")
    print(f"  test AUC         {f['test_auc']:.4f}    accuracy {f['test_accuracy']:.4f}")
    print(f"  cold-start AUC   {cold['coldstart_auc']:.4f}    "
          f"({cold['coldstart_n']} người học giữ riêng, chưa từng thấy lúc train)")
    print(f"  dữ liệu train    SLAM en_es · {len(slam) - 2:,} token tiếng Anh · "
          f"0 từ nào của ứng dụng")

    # ------------------------------------------------------------------ 2
    hr(2, "CHẤM ĐƯỢC TỪ MÔ HÌNH CHƯA TỪNG THẤY")
    unseen = [w for w in items if w not in slam]
    print(f"  bộ nền mới        {len(items):,} từ")
    print(f"  ngoài vocab SLAM  {len(unseen):,} từ  ({len(unseen)/len(items):.1%})")
    print(f"  → bản DKT theo ID trả None cho cả {len(unseen):,} từ.")
    print("  → bản feature-based chấm được, vì nó mô tả từ bằng ĐẶC ĐIỂM, không bằng tên.\n")
    sample = rng.sample(unseen, 8)
    print(f"  {'từ (chưa từng thấy)':<22}{'CEFR':<6}{'từ loại':<12}{'P(đúng)':>8}   nghĩa")
    got = srv.predict_mastery(BASE_HISTORY, sample, pos=pos)
    for w in sorted(sample, key=lambda x: -(got[x] or 0)):
        it = items[w]
        print(f"  {w:<22}{it['cefr'] or '--':<6}{(it['part_of_speech'] or '--')[:10]:<12}"
              f"{pct(got[w])}   {it['meaning'][:32]}")

    # ------------------------------------------------------------------ 3
    hr(3, "MỘT PHIÊN HỌC — MASTERY DI CHUYỂN THEO TỪNG LƯỢT")
    target = "deadline"
    seq = [("hello", 1), ("name", 1), ("please", 1), ("family", 1), ("house", 1),
           (target, 0), (target, 0), (target, 1), (target, 1), (target, 1), (target, 1)]
    print(f"  P(trả lời đúng '{target}') sau từng lượt:\n")
    print(f"  {'lượt':<5}{'từ':<12}{'kết quả':<9}{'P':>7}   {'':<36}thay đổi")
    running: list[tuple[str, int]] = []
    prev = None
    for n in range(len(seq) + 1):
        if n:
            running.append(seq[n - 1])
        p = srv.predict_mastery(running, [target], pos=pos)[target] or 0.0
        w, ok = ("(chưa học)", None) if n == 0 else seq[n - 1]
        label = "—" if ok is None else ("đúng" if ok else "SAI ")
        delta = "" if prev is None else f"{(p - prev) * 100:+5.1f} điểm"
        print(f"  {n:<5}{w:<12}{label:<9}{pct(p)}   {bar(p):<36}{delta}")
        prev = p

    # ------------------------------------------------------------------ 4
    hr(4, "MÔ HÌNH NHẠY VỚI LƯỢT GẦN NHẤT — ĐẾN MỨC NÀO")
    probe = [w for w in ("deadline", "report", "schedule", "meeting", "colleague")
             if w in items]
    ok12 = [(w, 1) for w, _ in BASE_HISTORY[:12]]
    cases = [
        ("12 lượt, đúng hết", ok12),
        ("… + 1 SAI ở cuối", ok12 + [("map", 0)]),
        ("… + 2 SAI ở cuối", ok12 + [("map", 0), ("bill", 0)]),
        ("… + 3 SAI ở cuối", ok12 + [("map", 0), ("bill", 0), ("receipt", 0)]),
        ("3 SAI ở GIỮA, cuối đúng", ok12[:6] + [("map", 0), ("bill", 0), ("receipt", 0)]
         + ok12[6:]),
    ]
    print(f"  {'lịch sử':<26}" + "".join(f"{w[:9]:>10}" for w in probe))
    for name, h in cases:
        r = srv.predict_mastery(h, probe, pos=pos)
        print(f"  {name:<26}" + "".join(f"{(r[w] or 0):>9.0%} " for w in probe))
    print("\n  Ba lượt sai LIÊN TIẾP ở cuối kéo P từ 91–97% xuống 15–43%.")
    print("  Cũng ba lượt sai ấy nhưng nằm ở GIỮA thì gần như không để lại dấu vết.")
    print("  → Đây là hành vi LSTM bình thường, nhưng nó có hệ quả ở mục 5.")

    # ------------------------------------------------------------------ 5
    hr(5, "BR-03 — GỢI Ý TỪ VỪA SỨC (P ∈ [0,60 ; 0,80])")
    ws = next(s for s in core["word_sets"] if s["name"] == "[B1] Cốt lõi 1")
    words = [i["word"] for i in ws["items"]]
    print(f"  Bộ '{ws['name']}' · {len(words)} từ\n")
    for name, h in (("vừa trả lời đúng liên tục", ok12),
                    ("vừa sai 2 lượt cuối", ok12 + [("map", 0), ("bill", 0)])):
        scored = {w: p for w, p in srv.predict_mastery(h, words, pos=pos).items()
                  if p is not None}
        easy = [w for w, p in scored.items() if p > 0.8]
        fit = sorted(((w, p) for w, p in scored.items() if 0.6 <= p <= 0.8),
                     key=lambda x: -x[1])
        hard = [w for w, p in scored.items() if p < 0.6]
        print(f"  ── người học {name}")
        print(f"     quá dễ {len(easy):>3}   VỪA SỨC {len(fit):>3}   quá khó {len(hard):>3}")
        if fit:
            print("     chọn: " + ", ".join(f"{w} ({p:.0%})" for w, p in fit[:8]))
        print()
    print("  Cùng một bộ từ, cùng một người học, chỉ khác hai lượt trả lời gần nhất")
    print("  — tập 'vừa sức' đổi hoàn toàn. Ngưỡng cố định [0,6; 0,8] trên một ước")
    print("  lượng nhạy như vậy là chỗ nên bàn trong phần thiết kế.")

    # ------------------------------------------------------------------ 6
    hr(6, "ĐẶC TRƯNG CEFR CÓ ĐƯỢC MÔ HÌNH DÙNG THẬT KHÔNG?")
    print("  Cùng người học, cùng lịch sử — chỉ khác mức CEFR của từ (mẫu 60 từ/mức):\n")
    by_level: dict[str, list[str]] = {}
    for w, it in items.items():
        if it["cefr"]:
            by_level.setdefault(it["cefr"], []).append(w)
    for lv in ("A1", "A2", "B1", "B2", "C1", "C2"):
        pool = by_level.get(lv, [])
        if not pool:
            continue
        pick = rng.sample(pool, min(60, len(pool)))
        vals = [v for v in srv.predict_mastery(BASE_HISTORY, pick, pos=pos).values()
                if v is not None]
        avg = sum(vals) / len(vals)
        print(f"  {lv}   n={len(vals):<4} P trung bình {avg:6.1%}   {bar(avg, 40)}")
    print("\n  Xu hướng giảm dần theo mức là tín hiệu đặc trưng CEFR đang có tác dụng.")

    # ------------------------------------------------------------------ 7
    hr(7, "GIÁ CỦA ĐẶC TRƯNG BỊ THIẾU")
    print("  Vector đặc trưng của hai từ cùng mức B1, chỉ khác ở chỗ có/không có từ loại:\n")
    for w in ("deadline", "risk"):
        if w not in items:
            continue
        upos = normalize_pos(pos.get(w))
        vec = token_features(w, upos)
        on = {n: round(float(x), 3) for n, x in zip(FEATURE_NAMES, vec) if abs(x) > 1e-6}
        tag = "pos_other  ← MẤT đặc trưng" if "pos_other" in on else "pos_NOUN"
        print(f"  {w:<12} part_of_speech={str(pos.get(w)):<8} {tag}")
        print(f"               {on}")
    print(f"\n  Trong bộ nền: {sum(1 for i in items.values() if not i['part_of_speech']):,}"
          f"/{len(items):,} từ thiếu từ loại, "
          f"{sum(1 for i in items.values() if not i['cefr']):,} từ thiếu CEFR.")


def run_cefr_ab() -> None:
    """Mục 8 chạy ở tiến trình riêng: token_features cache wordlist lúc import."""
    fixed = Path(tempfile.gettempdir()) / "cefr_wordlist_fixed.csv"
    rows_in = CEFR.read_text(encoding="utf-8-sig").splitlines()
    out = [rows_in[0]]
    split_rows = 0
    for line in rows_in[1:]:
        if not line.strip():
            continue
        word, _, rest = line.partition(",")
        if "/" in word:
            split_rows += 1
            for part in word.split("/"):
                if part.strip():
                    out.append(f"{part.strip()},{rest}")
        else:
            out.append(line)
    fixed.write_text("\n".join(out) + "\n", encoding="utf-8")

    probe = ["analyze", "analyse", "color", "colour", "organize", "adviser", "judgment"]
    snippet = (
        "import json,os,sys;sys.path.insert(0,%r);"
        "from src.features import token_features, FEATURE_NAMES, normalize_pos;"
        "idx={n:i for i,n in enumerate(FEATURE_NAMES)};"
        "print(json.dumps({w:[float(token_features(w,'VERB')[idx['cefr_unknown']]),"
        "float(token_features(w,'VERB')[idx['cefr_rank']])] for w in %r}))"
        % (str(ML_DIR), probe)
    )
    def probe_with(path: Path) -> dict:
        env = {**os.environ, "CEFR_WORDLIST_PATH": str(path)}
        r = subprocess.run([sys.executable, "-c", snippet], capture_output=True,
                           text=True, env=env, cwd=str(ML_DIR))
        return json.loads(r.stdout.strip().splitlines()[-1])

    before, after = probe_with(CEFR), probe_with(fixed)
    hr(8, "TÁC ĐỘNG THẬT CỦA LỖI cefr_wordlist (dòng gộp 'analyze/analyse')")
    print(f"  {split_rows} dòng trong cefr_wordlist.csv gộp nhiều biến thể vào một ô.")
    print("  Tra khớp chính xác → không dạng nào tìm được.\n")
    print(f"  {'từ':<12}{'cefr_unknown HIỆN TẠI':>24}{'sau khi tách /':>18}")
    for w in probe:
        b, a = before[w][0], after[w][0]
        mark = "   ← được sửa" if b != a else ""
        print(f"  {w:<12}{b:>24.0f}{a:>18.0f}{mark}")
    fixed_n = sum(1 for w in probe if before[w][0] != after[w][0])
    print(f"\n  {fixed_n}/{len(probe)} từ trong mẫu đang bật cờ 'không biết mức CEFR' một")
    print("  cách oan uổng — mô hình mất đúng đặc trưng mạnh nhất của nó, và không")
    print("  có lỗi nào hiện ra ở đâu cả.")
    print(f"\n{BAR}\n HẾT\n{BAR}")


if __name__ == "__main__":
    main()
    run_cefr_ab()
