"""UC-93 — so sánh ĐỊNH LƯỢNG lịch ôn DKT (UC-66) với SM-2 (UC-34).

Khóa luận nói SM-2 là baseline để đối chiếu, nhưng suốt từ đầu chưa có phép đo
nào so hai bộ lập lịch với nhau. Đây là phép đo đó.

## Vì sao phải mô phỏng

Muốn so hai lịch ôn trên người thật thì phải chia đôi người học, cho mỗi nửa một
lịch, chạy vài tháng. Đề tài không có điều kiện đó. Cách còn lại là mô phỏng —
nhưng mô phỏng chỉ có giá trị nếu **bộ mô phỏng không phải là mô hình của bên
nào cả**. Nếu trí nhớ giả lập chạy đúng theo công thức mà DKT giả định thì DKT
thắng vì định nghĩa, không phải vì tốt hơn.

## Ba lựa chọn thiết kế, và lý do

**1. Chân lý là đường quên hàm mũ, độ khó lấy từ SLAM thật.**
`P(nhớ) = 2^(-Δngày / h)`; `h` (nửa đời) dài ra sau mỗi lần nhớ được, ngắn lại
khi quên. Độ khó từng từ = **tỉ lệ sai thực nghiệm trên SLAM**, không phải số
bịa. Cả SM-2 lẫn DKT đều KHÔNG biết công thức này.

**2. Có hiệu ứng "khó vừa phải" (desirable difficulty).**
Nhớ lại được một từ đang chớm quên củng cố trí nhớ mạnh hơn nhiều so với ôn lại
từ vừa mới học xong. Đây là hiện tượng có thật trong tâm lý học nhận thức
(Bjork), và nó chính là lý do lập lịch có ý nghĩa: không có nó thì ôn sớm hay
muộn cũng như nhau, và mọi bộ lập lịch đều hòa.

**3. SM-2 được ưu ái, có chủ ý.**
SM-2 cần người học tự chấm "Lại/Khó/Tốt/Dễ". Ở đây mức đó suy ra từ **xác suất
nhớ THẬT** của bộ mô phỏng — tức SM-2 được cấp một tín hiệu nội bộ mà ngoài đời
nó không bao giờ có. Thiên vị này là cố ý: nếu DKT vẫn thắng khi đối thủ được
xem bài thì kết luận vững hơn hẳn.

Thêm một nhánh **đối chứng ngây thơ** (ôn lại đúng 3 ngày một lần) để biết
khoảng cách giữa hai bộ lập lịch thông minh đáng bao nhiêu so với việc không
nghĩ gì.

## Điều kiện thi đấu giống hệt nhau

Cùng tập người học, cùng seed, cùng kho từ, cùng ngân sách mỗi ngày, cùng luật
đưa từ mới vào. Khác nhau ĐÚNG một chỗ: hôm nay ôn từ nào.

Chạy:  python -m src.schedule_sim            (mặc định)
       python -m src.schedule_sim --quick    (bản nhỏ để thử)
"""
from __future__ import annotations

import argparse
import json
import math
import pickle
import random
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from src.serve_feat import FeatureDKTServer  # noqa: E402

# ---------------------------------------------------------------- tham số chân lý
# Bộ mô phỏng trí nhớ. Đây là GIẢ ĐỊNH, không phải số đo — mọi kết luận đều phải
# đọc kèm điều kiện này, và phần --sensitivity kiểm xem thứ hạng có đổi không.
H_INIT = 2.0           # nửa đời (ngày) ngay sau lần học đầu
H_MIN = 0.5            # sàn khi quên
H_MAX = 400.0          # trần, tránh nửa đời chạy ra vô hạn
GAIN = 1.2             # hệ số dài ra khi nhớ được
FAIL_SHRINK = 0.40     # nửa đời còn lại bao nhiêu khi quên
DESIRABLE_LO = 0.30    # củng cố tối thiểu (ôn khi vừa mới học)
DESIRABLE_HI = 3.30    # củng cố thêm khi ôn lúc sắp quên

# HIỆU CHỈNH — hai hằng số trên KHÔNG chọn tùy ý, và tuyệt đối không chỉnh cho
# tới khi bên nào đó thắng. Tiêu chí là NGOÀI và cố định trước khi chạy: điểm ôn
# tối ưu của bộ mô phỏng (chỗ kỳ vọng log-tăng-trưởng nửa đời mỗi lượt ôn đạt
# cực đại) phải rơi vào **≈0,90** — đúng mức nhớ mục tiêu mặc định của FSRS/Anki
# và khớp tài liệu về giãn cách.
#
# Bộ tham số đầu tiên tôi chọn theo cảm tính cho cực đại ở p≈0,98, nghĩa là bộ
# mô phỏng đang nói "ôn liên tục là tốt nhất" — trái ngược toàn bộ cơ sở của
# spaced repetition. Với nó, nhánh đối chứng ôn dày thắng mọi nơi, và đó là tạo
# tác của tham số chứ không phải kết quả. `python -m src.schedule_sim --calib`
# in lại điểm tối ưu để kiểm.
CALIB_TARGET_P = 0.90

# ---------------------------------------------------------------- tham số thi đấu
HORIZON_DAYS = 60      # số ngày học
DELAY_DAYS = 14        # nghỉ hẳn bao lâu trước bài kiểm tra trì hoãn
DAILY_BUDGET = 20      # số lượt trả lời mỗi ngày (ngân sách công sức)
POOL_SIZES = (90, 300)  # KÍCH THƯỚC KHO TỪ — chiều quét quan trọng nhất.
                        # Kho nhỏ mà ngân sách rộng thì ôn dày đặc lúc nào cũng
                        # thắng, và so hai lịch giãn cách trở nên vô nghĩa. Giãn
                        # cách chỉ có giá trị khi kho từ vượt quá sức ôn.
NEW_PER_DAY = 5        # trần từ mới mỗi ngày — không có trần thì lịch nào rảnh
                       # ngân sách sẽ đổ hết kho từ vào ngày đầu rồi quên sạch
N_LEARNERS = 120
MASTERED_P = 0.9       # BR-01: coi là "đã thuộc" khi P(nhớ) >= ngưỡng này
FIXED_INTERVAL = 3     # nhánh đối chứng ngây thơ

# Ánh xạ mastery -> số ngày, SAO ĐÚNG `review_service.mastery_to_interval_days`
# của backend (UC-66). Hai chỗ phải khớp nhau; đổi một bên là số đo hết nghĩa.
DKT_INTERVALS = ((0.60, 1), (0.75, 2), (0.90, 4), (1.01, 7))

# SM-2 tự chấm: suy từ xác suất nhớ THẬT (tín hiệu oracle — ưu ái SM-2).
SM2_HARD_P = 0.60
SM2_GOOD_P = 0.85

SIM_FORMAT = "quiz"    # cùng một dạng bài cho mọi nhánh
OUT_PATH = (Path(__file__).resolve().parent.parent.parent
            / "docs" / "experiments" / "scheduler_comparison.json")


# ================================================================= chân lý trí nhớ
@dataclass
class Trace:
    """Vết nhớ THẬT của một từ với một người học — không bộ lập lịch nào thấy."""
    half_life: float = H_INIT
    last_day: float = 0.0
    seen: bool = False


def recall_prob(trace: Trace, day: float) -> float:
    if not trace.seen:
        return 0.0
    return 2.0 ** (-max(0.0, day - trace.last_day) / trace.half_life)


def reinforce(trace: Trace, day: float, correct: bool, difficulty: float,
              ability: float, p_before: float) -> None:
    """Cập nhật vết nhớ sau một lượt trả lời."""
    if correct:
        # Nhớ lại được lúc sắp quên (p thấp) củng cố mạnh hơn hẳn lúc vừa học.
        effort = DESIRABLE_LO + (DESIRABLE_HI - DESIRABLE_LO) * (1.0 - p_before)
        grow = 1.0 + GAIN * (1.0 - difficulty) * ability * effort
        trace.half_life = min(H_MAX, trace.half_life * grow)
    else:
        trace.half_life = max(H_MIN, trace.half_life * FAIL_SHRINK)
    trace.last_day = day
    trace.seen = True


# ================================================================= dân số mô phỏng
def word_difficulty() -> dict[str, float]:
    """Độ khó từng từ = tỉ lệ SAI thực nghiệm trên SLAM (dữ liệu thật)."""
    idx2token = {v: k for k, v in json.loads(
        (config.PROCESSED_DIR / "item2idx.json").read_text(encoding="utf-8")).items()}
    with open(config.PROCESSED_DIR / "sequences.pkl", "rb") as fh:
        sequences = pickle.load(fh)

    wrong: dict[int, int] = {}
    total: dict[int, int] = {}
    for seq in sequences.values():
        for item, correct in zip(seq["items"], seq["corrects"]):
            item = int(item)
            total[item] = total.get(item, 0) + 1
            wrong[item] = wrong.get(item, 0) + (1 - int(correct))

    out: dict[str, float] = {}
    for item, n in total.items():
        if n < 30:                      # quá ít lượt thì tỉ lệ không đáng tin
            continue
        token = idx2token.get(item)
        if token and not token.startswith("<"):
            out[token] = min(0.75, max(0.05, wrong[item] / n))
    return out


@dataclass
class Learner:
    seed: int
    ability: float
    pool: list[str]                                   # thứ tự đưa từ mới vào
    traces: dict[str, Trace] = field(default_factory=dict)
    history: list[tuple[str, int]] = field(default_factory=list)
    #: Mốc ngày của từng lượt trong `history` — mô hình có thời gian thì mới
    #: tính được `elapsed_days`, và mới trả lời được "bao giờ thì quên".
    history_days: list[float] = field(default_factory=list)
    introduced: list[str] = field(default_factory=list)


def build_learners(difficulty: dict[str, float], n: int, pool_size: int,
                   seed: int) -> list[Learner]:
    """Cùng một tập người học dùng lại cho MỌI nhánh (cùng seed, cùng kho từ)."""
    rng = random.Random(seed)
    tokens = sorted(difficulty)
    learners = []
    for i in range(n):
        r = random.Random(seed + i)
        learners.append(Learner(
            seed=seed + i,
            # năng lực ghi nhớ khác nhau giữa người học
            ability=max(0.35, min(2.0, r.gauss(1.0, 0.28))),
            pool=r.sample(tokens, pool_size),
        ))
    _ = rng
    return learners


def fresh(learner: Learner) -> Learner:
    """Bản sao sạch của người học — để nhánh sau không thừa hưởng nhánh trước."""
    return Learner(seed=learner.seed, ability=learner.ability, pool=list(learner.pool))


# ================================================================= các bộ lập lịch
class Scheduler:
    """Giao diện chung: quyết định hôm nay ôn từ nào, và bao giờ ôn lại."""
    name = "?"

    def __init__(self) -> None:
        self.due_day: dict[str, float] = {}

    def pick(self, learner: Learner, day: int, budget: int) -> list[str]:
        due = [w for w in learner.introduced if self.due_day.get(w, 0.0) <= day]
        due.sort(key=lambda w: (self.due_day.get(w, 0.0), w))
        return due[:budget]

    def update(self, learner: Learner, day: int, results: list[tuple[str, bool, float]]) -> None:
        raise NotImplementedError


def sm2_step(quality: int, interval: int, ease: float, reps: int) -> tuple[int, float, int]:
    """Một bước SM-2 — CHÉP ĐÚNG `backend/app/services/sm2_service.sm2_step`.

    Không import được từ backend vì hàm đó nằm trong module kéo theo cả
    SQLAlchemy và tầng model. Nên nó được chép lại ở đây, và ràng buộc bằng
    hợp đồng: script ghi lại quỹ đạo SM-2 cho một chuỗi mức cố định vào phần
    `contract` của file kết quả, còn `backend/tests/test_scheduler_experiment.py`
    tính lại quỹ đạo ấy bằng chính hàm của backend rồi so. Lệch một bên là test
    đỏ ngay, không âm thầm trôi.
    """
    if quality < 3:
        reps = 0
        interval = 1
    else:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 6
        else:
            interval = max(1, round(interval * ease))
        reps += 1
    ease = max(1.3, ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    return interval, round(ease, 2), reps


class Sm2Scheduler(Scheduler):
    """UC-34. Mức tự chấm suy từ xác suất nhớ THẬT — oracle, ưu ái SM-2."""
    name = "sm2"

    def __init__(self) -> None:
        super().__init__()
        self.state: dict[str, tuple[int, float, int]] = {}   # interval, ease, reps

    @staticmethod
    def rating(correct: bool, p_before: float) -> str:
        if not correct:
            return "again"
        if p_before < SM2_HARD_P:
            return "hard"
        if p_before < SM2_GOOD_P:
            return "good"
        return "easy"

    def update(self, learner: Learner, day: int, results) -> None:
        for word, correct, p_before in results:
            interval, ease, reps = self.state.get(word, (1, 2.5, 0))
            quality = {"again": 1, "hard": 3, "good": 4, "easy": 5}[
                self.rating(correct, p_before)]
            interval, ease, reps = sm2_step(quality, interval, ease, reps)
            self.state[word] = (interval, ease, reps)
            self.due_day[word] = day + interval


class DktScheduler(Scheduler):
    """UC-66. Mastery do chính checkpoint đang phục vụ chấm, rồi ánh xạ ra ngày."""
    name = "dkt"

    def __init__(self, scorer: "BatchScorer", pos: dict[str, str]) -> None:
        super().__init__()
        self.scorer = scorer
        self.pos = pos

    @staticmethod
    def interval_days(mastery: float) -> int:
        for ceiling, days in DKT_INTERVALS:
            if mastery < ceiling:
                return days
        return DKT_INTERVALS[-1][1]

    def update(self, learner: Learner, day: int, results) -> None:
        words = [w for w, _, _ in results]
        if not words:
            return
        # Chấm SAU khi đã ghi hết lượt trong ngày vào lịch sử — đúng như hệ thống
        # thật: mastery cập nhật xong phiên rồi mới đặt lịch (UC-64 -> UC-66).
        mastery = self.scorer.score(learner, words, self.pos, target_day=float(day))
        for word in words:
            self.due_day[word] = day + self.interval_days(mastery[word])


class HalfLifeScheduler(Scheduler):
    """Lịch ôn NHẮM MỨC NHỚ MỤC TIÊU — bản sửa đề xuất cho UC-66.

    Khác chỗ nào so với `DktScheduler`:

    * Bản cũ hỏi "mastery rơi vào bậc nào" rồi tra bảng {1,2,4,7} ngày. Mastery
      là P(trả lời đúng NGAY BÂY GIỜ), không phụ thuộc thời gian, nên bảng đó
      đang dùng một đại lượng phi thời gian để ra quyết định về thời gian.
    * Bản này giữ một ước lượng **nửa đời** `ĥ` (ngày) cho từng (người, từ), rồi
      đặt lịch tại `t = ĥ · log2(1/mục_tiêu)` — tức quay lại đúng lúc xác suất
      nhớ tụt xuống mức mục tiêu. Với mục tiêu 0,90 thì `t ≈ 0,152·ĥ`.

    DKT vẫn giữ vai trò nó GIỎI và đã đo được (AUC 0,8382): ước lượng người này
    nắm từ này đến đâu. Con số đó điều biến tốc độ giãn của `ĥ` — từ đã chắc thì
    giãn nhanh, từ còn yếu giãn chậm. Nó KHÔNG bị hỏi "bao giờ thì quên", câu mà
    nó chưa từng được huấn luyện để trả lời.

    GIỚI HẠN, phải nói rõ khi đọc kết quả: nhánh này và bộ mô phỏng cùng giả
    định quên theo hàm mũ. Mô phỏng vì thế chỉ chứng minh được luật "nhắm mức
    nhớ mục tiêu" có ích DƯỚI giả định đó, không chứng minh được giả định đúng
    với người thật. Giả định này là chuẩn trong tài liệu về giãn cách
    (Ebbinghaus, HLR, FSRS) chứ không phải do tôi bịa cho hợp kết quả, và SM-2
    cũng là một luật theo thời gian — nên phép so vẫn công bằng giữa hai bên.
    """
    name = "dkt_hl"

    #: Cùng con số dùng để hiệu chỉnh bộ mô phỏng — mức nhớ mục tiêu mặc định
    #: của FSRS/Anki. Đặt một lần theo tiêu chí ngoài, không chỉnh sau khi xem
    #: kết quả.
    TARGET = CALIB_TARGET_P
    H_START = 2.0        # nửa đời ước lượng sau lần học đầu
    G_BASE = 1.6         # hệ số giãn nền, cùng bậc với ease mặc định 2,5 của SM-2
    SHRINK = 0.5         # quên thì nửa đời ước lượng giảm một nửa
    H_CAP = 365.0

    def __init__(self, scorer: "BatchScorer", pos: dict[str, str]) -> None:
        super().__init__()
        self.scorer = scorer
        self.pos = pos
        self.h: dict[str, float] = {}

    def update(self, learner: Learner, day: int, results) -> None:
        words = [w for w, _, _ in results]
        if not words:
            return
        mastery = self.scorer.score(learner, words, self.pos, target_day=float(day))
        for word, correct, _ in results:
            h = self.h.get(word, self.H_START)
            if correct:
                # Từ mà DKT thấy người này nắm chắc thì giãn nhanh hơn.
                h = min(self.H_CAP, h * self.G_BASE * (0.5 + mastery[word]))
            else:
                h = max(0.5, h * self.SHRINK)
            self.h[word] = h
            # Quay lại đúng lúc P(nhớ) tụt tới mục tiêu: 2^(-t/h) = mục tiêu.
            interval = max(1, round(h * math.log2(1.0 / self.TARGET)))
            self.due_day[word] = day + interval


class FixedScheduler(Scheduler):
    """Đối chứng ngây thơ: cứ đúng FIXED_INTERVAL ngày ôn lại, bất kể gì."""
    name = "fixed"

    def update(self, learner: Learner, day: int, results) -> None:
        for word, _, _ in results:
            self.due_day[word] = day + FIXED_INTERVAL


# ================================================================= chấm DKT theo lô
class BatchScorer:
    """Chấm nhiều target trong MỘT lượt chạy mô hình.

    Dùng lại đúng bộ tính đặc trưng của đường phục vụ (`FeatureDKTServer`) chứ
    không tự viết lại: thí nghiệm mà tính đặc trưng khác lúc phục vụ thì nó đang
    đo một mô hình khác với mô hình người dùng gặp. Chỗ duy nhất khác là gộp
    target thành lô để 60 ngày × 120 người chạy xong trong vài phút.
    """

    def __init__(self, server: FeatureDKTServer):
        self.server = server

    def _prepare(self, learner: "Learner", pos: dict[str, str]):
        srv = self.server
        tokens = [t for t, _ in learner.history]
        corrects = [int(c) for _, c in learner.history]
        formats: list[str | None] = [SIM_FORMAT] * len(tokens)
        days = learner.history_days or None

        rows, stats = srv._history_rows(tokens, corrects, formats, pos, days)
        window = rows[-(srv.max_len - 1):] if srv.max_len > 1 else rows[:0]
        aligned = corrects[-len(window):] + [0]
        return window, stats, aligned, len(tokens)

    @torch.no_grad()
    def score(self, learner: "Learner", targets: list[str], pos: dict[str, str],
              target_day: float | None = None) -> dict[str, float]:
        srv = self.server
        window, stats, aligned, length = self._prepare(learner, pos)
        batch = np.stack([
            np.concatenate([
                window,
                srv._target_row(t, pos, SIM_FORMAT, stats, length, target_day)[None, :],
            ], axis=0)
            for t in targets
        ])
        logits = srv.model(torch.from_numpy(batch),
                           torch.tensor([aligned] * len(targets), dtype=torch.long))[:, -1]
        return dict(zip(targets, torch.sigmoid(logits).tolist()))

    @torch.no_grad()
    def best_intervals(self, learner: "Learner", targets: list[str], pos: dict[str, str],
                       today: float, candidates: tuple[int, ...],
                       target_retention: float) -> dict[str, int]:
        """Khoảng cách DÀI NHẤT mà mô hình còn dự đoán P(nhớ) >= mục tiêu.

        Đây là chỗ khác hẳn `mastery_to_interval_days`: thay vì hỏi "mastery rơi
        vào bậc nào" rồi tra bảng, ta hỏi thẳng mô hình "nếu quay lại sau t ngày
        thì còn nhớ không?" cho từng t, rồi chọn t lớn nhất còn đạt. Chỉ hỏi được
        câu đó khi mô hình THẤY thời gian.

        Gộp tất cả (từ × mốc thời gian) vào một lô duy nhất — nếu chạy mô hình
        một lần cho mỗi mốc thì thí nghiệm chậm gấp `len(candidates)` lần.
        """
        srv = self.server
        window, stats, aligned, length = self._prepare(learner, pos)

        rows = [
            np.concatenate([
                window,
                srv._target_row(t, pos, SIM_FORMAT, stats, length,
                                today + gap)[None, :],
            ], axis=0)
            for gap in candidates
            for t in targets
        ]
        logits = srv.model(torch.from_numpy(np.stack(rows)),
                           torch.tensor([aligned] * len(rows), dtype=torch.long))[:, -1]
        probs = torch.sigmoid(logits).reshape(len(candidates), len(targets)).tolist()

        out: dict[str, int] = {}
        for j, word in enumerate(targets):
            chosen = candidates[0]
            for i, gap in enumerate(candidates):
                if probs[i][j] >= target_retention:
                    chosen = gap
            out[word] = chosen
        return out

    def selftest(self, pos: dict[str, str]) -> None:
        """Bản gộp lô phải cho ĐÚNG số như đường phục vụ chạy từng target."""
        hist = [("the", 1), ("water", 0), ("book", 1), ("run", 1)]
        days = [0.0, 1.0, 3.0, 6.0]
        targets = ["water", "book", "elephant"]
        probe = Learner(seed=0, ability=1.0, pool=[])
        probe.history = list(hist)
        probe.history_days = list(days)
        mine = self.score(probe, targets, pos, target_day=8.0)
        ref = self.server.predict_mastery(
            hist, targets, pos=pos,
            history_formats=[SIM_FORMAT] * len(hist), target_format=SIM_FORMAT,
            history_days=days, target_day=8.0,
        )
        for t in targets:
            if abs(mine[t] - float(ref[t])) > 1e-5:
                raise RuntimeError(
                    f"Gộp lô lệch đường phục vụ ở '{t}': {mine[t]} vs {ref[t]}"
                )


# ================================================================= một lần thi đấu
def run_arm(scheduler_factory, learners: list[Learner], difficulty: dict[str, float],
            horizon: int, budget: int) -> dict:
    """Chạy một bộ lập lịch trên cả dân số, trả về số đo."""
    daily_recall: list[float] = []
    reviews = wasted = late = introduced_total = 0
    per_learner: list[float] = []
    gaps: list[float] = []          # khoảng cách thật giữa hai lần gặp một từ
    p_at_review: list[float] = []   # P(nhớ) ngay trước mỗi lượt ôn

    schedulers = [scheduler_factory() for _ in learners]
    states = [fresh(l) for l in learners]

    for day in range(horizon):
        for learner, sched in zip(states, schedulers):
            # Chương trình học được CỐ ĐỊNH: mỗi ngày đúng NEW_PER_DAY từ mới,
            # cùng thứ tự, không phụ thuộc bộ lập lịch. Nếu để từ mới lấp chỗ
            # trống của ngân sách thì ba nhánh sẽ học số từ khác nhau, và mọi so
            # sánh sau đó là so hai chương trình học chứ không phải hai lịch ôn.
            fresh_words = [w for w in learner.pool if w not in learner.traces][:NEW_PER_DAY]

            # Chọn từ ôn TRƯỚC khi ghi từ mới vào `introduced`. Nếu ghi trước thì
            # từ mới chưa có `due_day` sẽ mặc định là 0, tức vừa được coi là "đến
            # hạn ôn" vừa được học mới — học hai lần trong một ngày, mà lại còn
            # chen lên trước những từ thực sự quá hạn.
            # Từ mới ăn trước vào ngân sách; phần còn lại mới dành cho ôn.
            picked = sched.pick(learner, day, max(0, budget - len(fresh_words)))

            for word in fresh_words:
                learner.traces[word] = Trace()
                learner.introduced.append(word)

            results: list[tuple[str, bool, float]] = []
            rng = random.Random(learner.seed * 1000 + day)

            for word in picked + fresh_words:
                trace = learner.traces[word]
                diff = difficulty[word]
                if not trace.seen:
                    p = max(0.05, 1.0 - diff)      # lần đầu: nhìn thấy rồi trả lời
                else:
                    p = recall_prob(trace, day)
                    reviews += 1
                    gaps.append(day - trace.last_day)
                    p_at_review.append(p)
                    if p >= 0.95:
                        wasted += 1
                    elif p < 0.50:
                        late += 1
                correct = rng.random() < p
                reinforce(trace, day, correct, diff, learner.ability, p)
                learner.history.append((word, int(correct)))
                learner.history_days.append(float(day))
                results.append((word, correct, p))

            introduced_total += len(fresh_words)
            sched.update(learner, day, results)

        daily_recall.append(round(sum(
            recall_prob(l.traces[w], day + 1) for l in states for w in l.introduced
        ), 1))

    # Bài kiểm tra TRÌ HOÃN: nghỉ hẳn DELAY_DAYS rồi mới đo. Đây mới là thứ nói
    # lên chất lượng lập lịch — đo ngay lúc vừa ôn xong thì lịch nào cũng đẹp.
    #
    # Chỉ số chính là **số từ còn nhớ kỳ vọng** (tổng P(nhớ)), không phải số từ
    # vượt ngưỡng 0,9. Sau hai tuần không đụng đến, gần như không từ nào còn ở
    # trên 0,9, nên đếm theo ngưỡng cho ra 0 ở cả ba nhánh — một con số không
    # phân biệt được gì thì không phải phép đo.
    delayed_day = horizon + DELAY_DAYS
    for l in states:
        per_learner.append(round(sum(
            recall_prob(l.traces[w], delayed_day) for w in l.introduced
        ), 4))
    recall_delayed = sum(per_learner)
    mastered_delayed = sum(
        1 for l in states for w in l.introduced
        if recall_prob(l.traces[w], delayed_day) >= MASTERED_P
    )

    return {
        "introduced": introduced_total,
        "reviews": reviews,
        "recall_end": daily_recall[-1] if daily_recall else 0.0,
        "recall_delayed": round(recall_delayed, 1),
        "mastered_delayed": mastered_delayed,
        "recall_per_100_reviews": round(100.0 * recall_delayed / max(1, reviews), 2),
        "wasted_reviews": wasted,
        "late_reviews": late,
        "wasted_pct": round(100.0 * wasted / max(1, reviews), 1),
        "late_pct": round(100.0 * late / max(1, reviews), 1),
        "mean_gap_days": round(float(np.mean(gaps)) if gaps else 0.0, 2),
        "mean_p_at_review": round(float(np.mean(p_at_review)) if p_at_review else 0.0, 3),
        "daily_recall": daily_recall,
        "per_learner_delayed": per_learner,
    }


def paired_gap(a: list[float], b: list[float], seed: int = 7, n_boot: int = 5000) -> dict:
    """Chênh lệch theo từng người học + khoảng tin cậy 95% (bootstrap ghép cặp).

    Ghép cặp vì mỗi người học chạy qua CẢ HAI lịch với cùng năng lực, cùng kho
    từ, cùng seed — so trung bình hai nhóm rời rạc sẽ vứt mất phần lớn thông tin.
    Bootstrap thay cho kiểm định tham số: không cần giả định phân phối chuẩn, và
    không phải kéo thêm scipy vào chỉ để lấy một con p.
    """
    diff = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    rng = np.random.default_rng(seed)
    boots = rng.choice(diff, size=(n_boot, diff.size), replace=True).mean(axis=1)
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {
        "mean_diff": round(float(diff.mean()), 3),
        "ci95": [round(float(lo), 3), round(float(hi), 3)],
        "win_rate": round(float((diff > 0).mean()), 3),
        "n_learners": int(diff.size),
    }


def sm2_contract() -> list[list[float]]:
    """Quỹ đạo SM-2 cho một chuỗi mức cố định — backend test so lại chuỗi này."""
    interval, ease, reps = 1, 2.5, 0
    out = []
    for quality in (4, 4, 5, 3, 1, 4, 4, 5, 5, 3):
        interval, ease, reps = sm2_step(quality, interval, ease, reps)
        out.append([quality, interval, ease, reps])
    return out


def dkt_contract() -> list[list[float]]:
    grid = [0.0, 0.3, 0.55, 0.6, 0.7, 0.75, 0.8, 0.89, 0.9, 0.95, 1.0]
    return [[m, DktScheduler.interval_days(m)] for m in grid]


def main() -> int:
    ap = argparse.ArgumentParser(description="So sánh lịch ôn DKT vs SM-2")
    ap.add_argument("--quick", action="store_true", help="bản nhỏ để thử luồng")
    ap.add_argument("--calib", action="store_true",
                    help="chỉ in điểm ôn tối ưu của bộ mô phỏng rồi thoát")
    ap.add_argument("--learners", type=int, default=N_LEARNERS)
    ap.add_argument("--days", type=int, default=HORIZON_DAYS)
    ap.add_argument("--budgets", type=int, nargs="+", default=[10, 20, 30])
    ap.add_argument("--pools", type=int, nargs="+", default=list(POOL_SIZES))
    ap.add_argument("--out", type=Path, default=OUT_PATH)
    args = ap.parse_args()

    if args.calib:
        print(f"Muc tieu hieu chinh: P(nho) = {CALIB_TARGET_P}")
        for diff in (0.10, 0.25, 0.40, 0.55, 0.70):
            best = max(
                ((p / 100, (p / 100) * math.log(
                    1 + GAIN * (1 - diff) * (DESIRABLE_LO
                                             + (DESIRABLE_HI - DESIRABLE_LO) * (1 - p / 100)))
                  + (1 - p / 100) * math.log(FAIL_SHRINK))
                 for p in range(30, 100)),
                key=lambda t: t[1],
            )
            print(f"  do kho={diff:.2f} -> on toi uu khi P(nho)={best[0]:.2f}")
        return 0

    if args.quick:
        args.learners, args.days = 12, 20
        args.budgets, args.pools = [20], [90, 300]

    config.set_seed()
    started = time.time()

    print("Nap do kho tu SLAM...", flush=True)
    difficulty = word_difficulty()
    pos = json.loads((config.PROCESSED_DIR / "token_pos.json").read_text(encoding="utf-8"))
    difficulty = {w: d for w, d in difficulty.items() if w in pos}
    print(f"  {len(difficulty)} tu co du luot de uoc luong do kho", flush=True)

    server = FeatureDKTServer()
    scorer = BatchScorer(server)
    scorer.selftest(pos)
    print("  Gop lo khop duong phuc vu.", flush=True)

    arms = {
        "sm2": lambda: Sm2Scheduler(),
        "dkt": lambda: DktScheduler(scorer, pos),
        "dkt_hl": lambda: HalfLifeScheduler(scorer, pos),
        "fixed": lambda: FixedScheduler(),
    }

    runs: dict[str, dict] = {}
    for pool in args.pools:
        learners = build_learners(difficulty, args.learners, pool, config.SEED)
        for budget in args.budgets:
            for name, factory in arms.items():
                t0 = time.time()
                res = run_arm(factory, learners, difficulty, args.days, budget)
                res["pool"] = pool
                runs[f"{name}@b{budget}p{pool}"] = res
                print(f"  [kho={pool:3d} ngan sach={budget:2d}] {name:5s} "
                      f"nho duoc(tri hoan)={res['recall_delayed']:8.1f}  "
                      f"luot on={res['reviews']:6d}  ({time.time() - t0:.0f}s)", flush=True)

    main_budget = args.budgets[len(args.budgets) // 2]
    comparisons = {}
    for pool in args.pools:
        for b in args.budgets:
            suffix = f"@b{b}p{pool}"
            comparisons[f"dkt_vs_sm2{suffix}"] = paired_gap(
                runs[f"dkt{suffix}"]["per_learner_delayed"],
                runs[f"sm2{suffix}"]["per_learner_delayed"])
            comparisons[f"dkt_vs_fixed{suffix}"] = paired_gap(
                runs[f"dkt{suffix}"]["per_learner_delayed"],
                runs[f"fixed{suffix}"]["per_learner_delayed"])
            comparisons[f"dkthl_vs_sm2{suffix}"] = paired_gap(
                runs[f"dkt_hl{suffix}"]["per_learner_delayed"],
                runs[f"sm2{suffix}"]["per_learner_delayed"])
            comparisons[f"dkthl_vs_dkt{suffix}"] = paired_gap(
                runs[f"dkt_hl{suffix}"]["per_learner_delayed"],
                runs[f"dkt{suffix}"]["per_learner_delayed"])

    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "setup": {
            "learners": args.learners,
            "horizon_days": args.days,
            "delay_days": DELAY_DAYS,
            "budgets": args.budgets,
            "main_budget": main_budget,
            "pools": args.pools,
            "main_pool": args.pools[-1],
            "mastered_threshold": MASTERED_P,
            "n_words": len(difficulty),
            "model": "dkt_feat_best.pt",
            "seconds": round(time.time() - started, 1),
        },
        "memory_model": {
            "form": "P(nho) = 2^(-delta_ngay / half_life)",
            "h_init": H_INIT, "h_min": H_MIN, "gain": GAIN,
            "fail_shrink": FAIL_SHRINK,
            "desirable_difficulty": [DESIRABLE_LO, DESIRABLE_HI],
            "difficulty_source": "ti le sai thuc nghiem tren SLAM en_es",
        },
        "runs": {k: {kk: vv for kk, vv in v.items() if kk != "per_learner_delayed"}
                 for k, v in runs.items()},
        "comparisons": comparisons,
        "contract": {"sm2_trajectory": sm2_contract(), "dkt_intervals": dkt_contract()},
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nDa ghi {args.out}  ({time.time() - started:.0f}s)")
    for pool in args.pools:
        for b in args.budgets:
            c = comparisons[f"dkt_vs_sm2@b{b}p{pool}"]
            print(f"  kho={pool:3d} ngan sach={b:2d}: DKT - SM2 = {c['mean_diff']:+7.2f} "
                  f"tu/nguoi (CI95 {c['ci95'][0]:+.2f}..{c['ci95'][1]:+.2f}, "
                  f"thang {c['win_rate']*100:3.0f}% nguoi hoc)")
    return 0


if __name__ == "__main__":
    config.use_utf8_console()
    sys.exit(main())
