"""Xuất đặc tả OpenAPI ra docs/api/ — chạy: python -m app.scripts.export_openapi

Sinh trực tiếp từ FastAPI app nên KHÔNG cần dựng server/Postgres. Dùng để người
làm frontend biết chính xác từng endpoint trả gì mà không phải chạy cả hệ thống.

Chạy lại sau mỗi lần thêm/sửa endpoint, nếu không file sẽ lệch với code.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from app.scripts._console import use_utf8_console
from app.main import app

DOCS_DIR = Path(__file__).resolve().parents[3] / "docs" / "api"

# Nhóm hiển thị theo thứ tự dễ đọc cho người làm frontend
TAG_TITLES = {
    "auth": "Xác thực & tài khoản",
    "users": "Hồ sơ người dùng",
    "home": "Trang chủ học viên",
    "dashboard": "Dashboard",
    "word-sets": "Bộ từ & từ vựng",
    "sessions": "Phiên học",
    "reviews": "Ôn tập (SRS)",
    "progress": "Tiến độ",
    "achievements": "Huy hiệu",
    "discover": "Khám phá bộ từ công khai",
    "community": "Cộng đồng",
    "notifications": "Thông báo",
    "placement": "Kiểm tra đầu vào",
    "roadmap": "Lộ trình học",
    "admin": "Quản trị",
}


def _method_rows(spec: dict) -> dict[str, list[tuple[str, str, str, str]]]:
    """{tag: [(method, path, tóm tắt, tên schema trả về)]}"""
    grouped: dict[str, list[tuple[str, str, str, str]]] = {}

    for path, operations in sorted(spec["paths"].items()):
        for method, operation in operations.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            tag = (operation.get("tags") or ["khác"])[0]
            # FastAPI đặt summary = tên hàm ("Get Me"); docstring tiếng Việt nằm ở
            # description -> lấy dòng đầu của description cho dễ đọc
            description = (operation.get("description") or "").strip()
            summary = (
                description.splitlines()[0].strip() if description
                else (operation.get("summary") or "").strip()
            )

            schema_name = "—"
            for code in ("200", "201"):
                content = operation.get("responses", {}).get(code, {}).get("content", {})
                schema = content.get("application/json", {}).get("schema", {})
                ref = schema.get("$ref") or schema.get("items", {}).get("$ref")
                if ref:
                    schema_name = ref.rsplit("/", 1)[-1]
                    if "items" in schema:
                        schema_name += "[]"
                    break
            else:
                if "204" in operation.get("responses", {}):
                    schema_name = "204 No Content"

            grouped.setdefault(tag, []).append((method.upper(), path, summary, schema_name))
    return grouped


def build_markdown(spec: dict) -> str:
    grouped = _method_rows(spec)
    total = sum(len(rows) for rows in grouped.values())

    lines = [
        "# Đặc tả API — LearningHub",
        "",
        f"Sinh tự động từ FastAPI (`python -m app.scripts.export_openapi`). **{total} endpoint.**",
        "Chi tiết kiểu dữ liệu xem `openapi.json` cùng thư mục, hoặc mở Swagger tại `/docs`",
        "khi backend đang chạy.",
        "",
        "Mọi endpoint (trừ `/auth/register`, `/auth/login`, `/auth/verify-email`,",
        "`/auth/forgot-password`, `/auth/reset-password`, `/health`) đều cần header",
        "`Authorization: Bearer <access_token>`.",
        "",
    ]

    ordered = [t for t in TAG_TITLES if t in grouped] + [
        t for t in sorted(grouped) if t not in TAG_TITLES
    ]
    for tag in ordered:
        lines += [f"## {TAG_TITLES.get(tag, tag)}", "",
                  "| Method | Đường dẫn | Mô tả | Trả về |", "|---|---|---|---|"]
        for method, path, summary, schema_name in grouped[tag]:
            lines.append(f"| {method} | `{path}` | {summary} | `{schema_name}` |")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    spec = app.openapi()

    (DOCS_DIR / "openapi.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    (DOCS_DIR / "README.md").write_text(build_markdown(spec), encoding="utf-8")

    endpoints = sum(
        1
        for operations in spec["paths"].values()
        for method in operations
        if method in {"get", "post", "put", "patch", "delete"}
    )
    print(f"Đã xuất {endpoints} endpoint -> {DOCS_DIR}")


if __name__ == "__main__":
    use_utf8_console()
    main()
