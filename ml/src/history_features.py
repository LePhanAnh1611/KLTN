"""Đặc trưng LỊCH SỬ giữa một người học và một từ, tính nhân quả theo chuỗi.

Vì sao cần: `features.py` mô tả *bản thân từ* (CEFR, từ loại, độ dài, tần suất) —
những thứ giống nhau với mọi người học. Nhưng "người này đã gặp từ này 4 lần,
đúng 3, lần gần nhất cách đây 12 bước" mới là tín hiệu mạnh nhất cho việc nhớ hay
quên. Mục 2.2 `docs/system-spec.md` liệt kê đúng những thứ này (số lần đúng/sai,
recency, số lần ôn) và bản feature-based đầu tiên còn thiếu chúng.

Đây cũng là chỗ DKT theo ID đang có lợi thế ngầm: mỗi từ một chiều riêng nên
mạng tự nhớ được lịch sử của từng từ. Bản feature-based không có chiều riêng nào
nên phải đưa lịch sử vào một cách tường minh.

NHÂN QUẢ: đặc trưng tại vị trí p chỉ được dùng thông tin ở các vị trí < p. Vi
phạm điều này là rò rỉ nhãn — mô hình sẽ đẹp trên giấy và vô dụng khi chạy thật.
Vì vậy mọi bộ đếm đều cập nhật SAU khi đã ghi xong đặc trưng của vị trí đó.
"""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

#: THÍ NGHIỆM ĐÃ CHẠY, KẾT QUẢ ÂM — để False.
#:
#: Ý tưởng: thêm `elapsed_days` (số ngày thật kể từ lần gặp trước) để mô hình
#: trả lời được "bao giờ thì quên", thứ mà `recency` (đếm theo BƯỚC) không làm
#: được. Đã hiện thực đầy đủ, huấn luyện lại trên subset (38 chiều, test-AUC
#: 0,8079 so với 0,8080 của bản 37 chiều — không đổi), rồi dò xem mô hình có
#: dùng chiều đó không. Cùng một lịch sử, chỉ đổi số ngày trôi qua:
#:
#:     water  0 ngày=0,9700 · 1=0,9715 · 7=0,9743 · 30=0,9767
#:
#: Dự đoán **TĂNG** theo thời gian — ngược chiều quên. Không phải lỗi cài đặt:
#: SLAM là dữ liệu luyện tập mà THỜI ĐIỂM ÔN DO CHÍNH BỘ LẬP LỊCH CỦA DUOLINGO
#: CHỌN. Khoảng cách dài không có nghĩa "bỏ quên lâu" mà là "hệ thống thấy từ
#: này đã chắc nên mới để lâu". Biến thời gian bị nhiễu bởi đúng cái chính sách
#: sinh ra nó, nên không thể nhận dạng được tác động nhân quả của nó
#: (confounding by indication).
#:
#: Kết luận: KHÔNG học được quy luật quên từ SLAM. Muốn học phải có dữ liệu mà
#: khoảng cách ôn không do bộ lập lịch quyết định — log của chính hệ thống này
#: sau khi có người dùng thật, hoặc một nhánh ngẫu nhiên hóa khoảng cách.
#:
#: Giữ nguyên đường dẫn dữ liệu (`days` vẫn được tiền xử lý lưu lại) để bật lại
#: bằng một dòng khi có dữ liệu phù hợp.
WITH_ELAPSED_DAYS = False

HISTORY_NAMES: tuple[str, ...] = (
    "seen_count",      # đã gặp bao nhiêu lần (log, chuẩn hóa)
    "correct_ratio",   # tỉ lệ đúng trong các lần đã gặp
    "recency",         # khoảng cách tới lần gặp gần nhất (log, chuẩn hóa)
    "never_seen",      # cờ: đây là lần đầu tiên
    "prev_correct",    # lần gặp ngay trước đó có đúng không
) + (("elapsed_days",) if WITH_ELAPSED_DAYS else ())
HISTORY_DIM = len(HISTORY_NAMES)

# Ba mốc bão hòa dưới đây là HỢP ĐỒNG giữa lúc huấn luyện và lúc phục vụ:
# `serve_feat.py` import thẳng từ đây thay vì chép lại. Chép một hằng số chuẩn
# hóa là cách âm thầm nhất để lệch train/serve — API vẫn 200, số vẫn có, chỉ sai.
LOG_SEEN = math.log(21.0)     # bão hòa quanh 20 lần gặp
LOG_GAP = math.log(101.0)     # bão hòa quanh khoảng cách 100 bước
LOG_DAYS = math.log(31.0)     # bão hòa quanh 30 ngày — SLAM chỉ dài tối đa
                               # 29,9 ngày nên lấy mốc lớn hơn là phí độ phân
                               # giải ở đúng vùng dữ liệu thật nằm.


def sequence_history(items: np.ndarray, corrects: np.ndarray,
                     days: np.ndarray | None = None) -> np.ndarray:
    """(L, HISTORY_DIM) — lịch sử của người học với từng từ, tính nhân quả.

    Lần đầu gặp một từ thì `never_seen=1`, còn `correct_ratio`/`prev_correct` để
    0.5 — nghĩa là "không biết", chứ không phải "sai". Điền 0 vào đó sẽ dạy mô
    hình rằng từ mới nào cũng là từ vừa trả lời sai.

    `elapsed_days` là chiều được thêm sau, và là chiều quan trọng nhất cho việc
    lập lịch. `recency` đếm theo BƯỚC trong chuỗi: một từ bỏ quên 9 ngày và một
    từ vừa gặp hôm qua, nếu cách nhau cùng số bước, trông y hệt nhau. Quên là
    chuyện của thời gian thực. Thiếu chiều này thì mô hình không thể trả lời
    "bao giờ thì quên", và mọi lịch ôn dựng trên nó đều đoán mò về thời gian.

    `days=None` -> chiều này để 0 ở mọi vị trí, dùng khi nguồn dữ liệu không có
    mốc thời gian. Nó KHÁC "vừa gặp xong" (cũng là 0): phân biệt được nhờ
    `never_seen` và `recency` đi kèm.
    """
    length = len(items)
    out = np.zeros((length, HISTORY_DIM), dtype=np.float32)

    seen: dict[int, int] = defaultdict(int)
    n_correct: dict[int, int] = defaultdict(int)
    last_pos: dict[int, int] = {}
    last_correct: dict[int, int] = {}

    for p in range(length):
        item = int(items[p])
        count = seen[item]

        if count == 0:
            out[p] = (0.0, 0.5, 0.0, 1.0, 0.5, 0.0)[:HISTORY_DIM]
        else:
            gap = p - last_pos[item]
            elapsed = 0.0
            if days is not None:
                elapsed = min(
                    math.log1p(max(0.0, float(days[p]) - float(days[last_pos[item]])))
                    / LOG_DAYS,
                    1.0,
                )
            out[p] = (
                min(math.log1p(count) / LOG_SEEN, 1.0),
                n_correct[item] / count,
                min(math.log1p(gap) / LOG_GAP, 1.0),
                0.0,
                float(last_correct[item]),
                elapsed,
            )[:HISTORY_DIM]

        # Cập nhật SAU khi đã ghi -> vị trí p không nhìn thấy chính nó.
        seen[item] = count + 1
        n_correct[item] += int(corrects[p])
        last_pos[item] = p
        last_correct[item] = int(corrects[p])

    return out
