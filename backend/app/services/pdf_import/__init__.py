"""UC-87 — cắt bộ từ vựng ra khỏi một tài liệu PDF (nghiệp vụ N1).

Chuỗi xử lý: `extractor` (pdfplumber) → `tokenizer` (spaCy) → `cefr` (wordlist
chuẩn) → `topic` (LLM local) → `pipeline` điều phối. Router chỉ gọi `pipeline`.

Hai ràng buộc đáng nhớ:

* **CEFR không bao giờ do LLM gán.** Cùng một từ, hai lần chạy LLM ra hai mức
  khác nhau; mà mức CEFR lại là dữ liệu nền cho độ khó/lộ trình. Chỉ tra nguồn
  chuẩn (`cefr.py`), không có trong nguồn thì để trống.
* **Phụ thuộc nặng nạp muộn.** pdfplumber + spaCy không nằm trong
  `requirements.txt` (xem `requirements-import.txt`), nên `import` chỉ xảy ra
  bên trong hàm. Chưa cài thì đúng ba endpoint của UC-87 trả 503, phần còn lại
  của ứng dụng chạy bình thường.

Module này KHÔNG đọc/ghi KNOWLEDGE_STATE và KHÔNG sinh INTERACTION — thuần nội dung.
"""
