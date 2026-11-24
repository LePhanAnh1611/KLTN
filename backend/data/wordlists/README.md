# Nguồn từ vựng

Mỗi file `.tsv` là một bộ từ. Định dạng: `từ<TAB>nghĩa tiếng Việt`.

Dòng bắt đầu bằng `#` là chú thích. Dòng đầu tiên sau chú thích là **metadata**
của bộ, dạng `@ tên bộ | danh mục | độ khó | mô tả`.

Thêm `| seed=no` ở cuối dòng `@` nếu file chỉ dùng để **tra cứu** — nghĩa là
lấy IPA/từ loại/câu ví dụ cho những từ do chỗ khác tạo ra, chứ không dựng thành
bộ từ công khai. `09-lo-trinh.tsv` dùng cờ này: các chặng lộ trình (UC-84) tự
sinh bộ từ riêng, file này chỉ cấp phiên âm và câu ví dụ cho chúng.

**Chỉ cần viết từ và nghĩa.** Phiên âm IPA, từ loại và câu ví dụ do
`python -m app.scripts.build_vocab_dataset` tự lấy về (xem script đó).

Nghĩa tiếng Việt được viết tay có chủ đích: đây là phần máy dịch sai nhiều nhất
("deadline" ra "giới hạn thời gian" thay vì "hạn chót"), mà lại là phần người
học đọc nhiều nhất.

Thêm bộ mới = thêm một file `.tsv` rồi chạy lại script.

## Sửa một câu ví dụ sai

Thêm **cột thứ 3** (cũng ngăn bằng TAB) — câu viết tay này thắng cả từ điển lẫn
LLM, và không bị mất khi dựng lại dataset:

```
grocery	hàng tạp hóa	She stopped at the grocery store on her way home.
```

Dùng khi từ điển không có câu nào chứa đúng từ và câu LLM sinh ra bị gượng —
ví dụ `grocery` từng ra "…to buy some grocery" (phải là *groceries*).
