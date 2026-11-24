"""Ép stdout/stderr sang UTF-8 cho các script chạy tay.

Console Windows mặc định là cp1252. In một dòng tiếng Việt có dấu sẽ ném
UnicodeEncodeError — thường ở đúng dòng tổng kết, tức SAU khi công việc đã xong,
nên nhìn như script thất bại trong khi nó đã thành công. Mã thoát khác 0 còn làm
mọi cổng chặn báo hỏng vì một lý do chẳng liên quan gì.

Gọi ở đầu khối `if __name__ == "__main__"`. (Bản song song bên ml/ là
`config.use_utf8_console`.)
"""
from __future__ import annotations

import sys


def use_utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
