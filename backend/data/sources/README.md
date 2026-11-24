# Nguồn dữ liệu bộ từ vựng nền

## Bổ sung lộ trình C1/C2 (13/10/2026)

Nguồn từ bổ sung: **Octanove Labs, Octanove Vocabulary Profile C1/C2,
version 1.0**, bản sao tại `backend/data/octanove-vocabulary-profile-c1c2-1.0.csv`.
Nguồn gốc và điều khoản đã kiểm tra:
<https://github.com/openlanguageprofiles/olp-en-cefrj#terms-of-use>.
Giấy phép **CC BY-SA 4.0**: <https://creativecommons.org/licenses/by-sa/4.0/>.
Phần danh sách từ/nhãn CEFR điều chỉnh từ Octanove được chia sẻ theo CC BY-SA 4.0;
ghi công Octanove Labs khi phân phối. Nghĩa, IPA và ví dụ vẫn mang giấy phép riêng
của từng nguồn được mô tả bên dưới.

Thay đổi: bổ sung headword C1/C2 ngoài NGSL/NAWL, bỏ từ thiếu nghĩa tiếng Việt,
loại trùng và từ được nguồn CEFR tổng hợp xếp ở mức thấp hơn. Không tự đoán nhãn
CEFR hoặc sinh nghĩa mới. Có 1.524 từ bổ sung; tổng C1: 847, C2: 793.
Từ thiếu ví dụ/IPA để trống; `meaning_confidence` giữ cờ cần rà soát.
Các bộ không gộp đuôi sang mức CEFR khác. Từ chưa xếp mức không vào lộ trình.

Script dựng mặc định dùng nguồn này; có thể truyền `--advanced PATH`.
Sau khi dựng lại dữ liệu, chạy `python -m app.scripts.sync_roadmap` trong
`backend/` để đồng bộ chặng. Lệnh chạy lại được, vô hiệu hóa chặng cũ và giữ
nguyên bộ từ, bản sao, lịch sử học. Không cần chạy lại seed demo hoặc xóa dữ liệu.

Thư mục này giữ **bản sao đúng thời điểm** của mọi nguồn dùng để dựng
`backend/data/vocab_seed_core.json`. Giữ lại ở đây thay vì chỉ ghi link vì hai lý do:
khóa luận phải tái lập được sau khi bảo vệ, và vài nguồn trong số này đã thay đổi
hoặc bị gỡ ít nhất một lần.

Dựng lại:

```bash
cd backend
pip install -r requirements-dev.txt       # kèm openpyxl + wordfreq (không có trong requirements.txt)
python -m app.scripts.build_core_dataset \
    --ngsl      data/sources/ngsl.txt \
    --nawl      data/sources/nawl.txt \
    --ngsl-xlsx data/sources/NGSL_with_SFI.xlsx \
    --dict      data/sources/english-vietnamese.txt \
    --wikt      data/sources/vi2enwikitxt.txt \
    --cefr      data/cefr_wordlist.csv \
    --examples  data/sources/examples_manual.tsv \
    --examples  data/sources/examples_llm.tsv \
    --meanings  data/sources/meanings_llm.tsv \
    --meanings  data/sources/meanings_llm_review.tsv \
    --meanings  data/sources/meanings_curated.tsv \
    --meanings  data/sources/meanings_manual.tsv \
    --phonetics data/sources/phonetics_manual.tsv \
    --audit     data/audit_sample.csv \
    --out       data/vocab_seed_core.json
```

Bỏ `--examples` / `--meanings` thì dataset vẫn dựng được, nhưng **mất 1.838 câu ví
dụ và 174 nghĩa viết đè** — độ phủ câu ví dụ tụt từ 100% xuống ~51%. Cả hai cờ nhận
nhiều lần; thứ tự truyền KHÔNG quyết định ai thắng — `EXAMPLE_PRIORITY` quyết định:
`manual` > `llm` > `fvdp`, nên câu viết tay luôn thắng câu máy sinh dù đứng ở đâu.
`--audit` xuất mẫu kiểm định 200 từ phân tầng để rà chất lượng nghĩa.

---

## 1. Danh sách từ — quyết định HỌC TỪ NÀO

### NGSL 1.x — New General Service List (2.809 từ)

Browne, C., Culligan, B. & Phillips, J. (2013). Corpus 273 triệu từ (Cambridge
English Corpus). Phủ **~92%** văn bản tiếng Anh phổ thông.

* `ngsl.txt` — danh sách lemma
* `NGSL_with_SFI.xlsx` — kèm thứ hạng và chỉ số tần suất SFI, dùng để **xếp thứ tự dạy**
* Giấy phép: **CC BY-SA 4.0** — bắt buộc ghi công
* Trang chủ: <https://www.newgeneralservicelist.com>

### NAWL 1.x — New Academic Word List (959 từ)

Cùng nhóm tác giả, căn khớp với NGSL: các từ **học thuật** nằm ngoài NGSL.
Giấy phép và cách ghi công như trên.

> **Vì sao dừng ở ~3.750 từ.** NGSL phủ 92% văn bản phổ thông, NAWL thêm phần học
> thuật. Nới rộng nữa chủ yếu thêm từ hiếm — chúng làm loãng gợi ý DKT (BR-03 cần
> P(đúng) ∈ [0,6; 0,8], từ quá hiếm luôn nằm dưới ngưỡng) mà hầu như không tăng độ
> phủ văn bản. Đây là điểm dừng có lý do, không phải điểm dừng vì hết sức.

---

## 2. Nghĩa tiếng Việt, IPA, từ loại, ví dụ

### `english-vietnamese.txt` — từ điển Anh–Việt định dạng FVDP (~104.000 mục)

Định dạng gốc của **Free Vietnamese Dictionary Project** (Hồ Ngọc Đức):

```
@headword /ipa/
*  danh từ
- nghĩa tiếng Việt
=english example+ bản dịch tiếng Việt
```

Một mục cho đủ bốn thứ: **IPA, từ loại, nhiều nghĩa tiếng Việt, ví dụ kèm bản dịch**.
Độ phủ trên NGSL đo được **99,8%**.

> ⚠️ **PHẢI KIỂM TRA TRƯỚC KHI NỘP.** Bản sao này lấy từ một repository GitHub
> **không kèm file LICENSE**. Dữ liệu gốc là FVDP, phát hành theo **GPL** — một
> giấy phép copyleft áp lên chính dữ liệu. Trước khi nộp khóa luận cần:
>
> 1. xác nhận nguồn gốc và phiên bản FVDP đang dùng;
> 2. ghi công đúng trong phần "Nguồn dữ liệu";
> 3. nếu cần giấy phép thoáng hơn, đổi sang nguồn khác — script tách riêng bước
>    lấy nghĩa nên chỉ phải thay một hàm.

> ⚠️ **Đây là bản số hóa một từ điển cũ.** Ba hệ quả đã đo được:
>
> * **Nghĩa đầu tiên thường là nghĩa cổ**, không phải nghĩa thông dụng:
>   `stage` mở đầu bằng "bệ, dài"; `profile` ra "nét mặt nhìn nghiêng";
>   `decade` ra "bộ mười".
> * **Có lỗi chính tả**: "có kiên quan" (phải là "liên quan").
> * **Thiếu từ hiện đại**: website, blog, globalization, biodiversity.
>
> Đó chính là lý do có bước đối chứng dưới đây và trường `meaning_confidence`.

### `vi2enwikitxt.txt` — từ điển Việt–Anh từ Wiktionary (28.865 mục)

Sinh từ **en.wiktionary.org** qua `wiktextract` (bản sao tháng 1/2026), lấy lại từ
repository `Trannosaur/published_dicts`. Giấy phép: **CC BY-SA 3.0**.

Dùng để **ĐỐI CHỨNG**, không phải làm nguồn nghĩa chính: script đảo nó thành chỉ mục
Anh→Việt (25.644 khóa) rồi hỏi một câu duy nhất — *nghĩa mà từ điển chính đưa ra có
được một nguồn độc lập, hiện đại hơn, xác nhận không?* Nếu có nghĩa nào trong danh
sách của từ điển chính được xác nhận thì lấy **nghĩa đó** thay vì nghĩa đầu tiên.
Riêng thay đổi này sửa được `stage` → "sân khấu", `relative` → "tương đối",
`price` → "giá".

Chỉ mục đảo của một từ điển song ngữ vốn nhiễu (`approval` → "a ha"), nên nó **không
bao giờ tự ghi đè** nghĩa; chỉ gợi ý và gắn cờ.

---

## 3. Trình độ CEFR

`backend/data/cefr_wordlist.csv` — đã có sẵn trong dự án, dựng bởi
`build_cefr_wordlist.py` từ CEFR-J Vocabulary Profile 1.5 (Tono Lab, TUFS) và
Octanove Vocabulary Profile C1/C2 1.0 (CC BY-SA 4.0).

> 🐛 **Lỗi đã phát hiện ở file này.** 188 dòng gộp nhiều biến thể chính tả vào một ô:
> `analyze/analyse`, `color/colour`, `adviser/advisor`. `CsvCefrSource.lookup()` tra
> khớp chính xác, nên **không dạng nào tìm được** — cả `analyze` lẫn `analyse` đều
> trượt. Hệ quả: UC-87 không gán được CEFR cho những từ đó, và đặc trưng `cefr_unknown`
> của DKT bật sai cho một nhóm từ rất thông dụng. Script này đã tách `/` khi nạp;
> **`app/services/pdf_import/cefr.py` thì chưa** — nên sửa `_load()` cho khớp.

---

## 4. Tần suất

`wordfreq` (PyPI) — thang Zipf, corpus tiếng Anh tổng quát độc lập với dữ liệu huấn
luyện. Ghi vào từng item để đối chiếu; đặc trưng thật vẫn do `ml/src/features.py` tự tính.

---

## 4b. Sửa phiên âm & nghĩa — bug #8, #9 (2026-10-20)

**Phiên âm (#8).** Ba lỗi nằm ngay trong cách đọc/dữ liệu FVDP, script nay tự xử lý:
- FVDP gộp biến thể vào một dòng và lặp dòng đó dưới tên từng biến thể
  (`@ethical /'eθik/ (ethical) /'eθikəl/`); trước đây lấy cặp IPA đầu -> 40 từ mang
  IPA của từ khác (ethical, biological, employee, therapy…). Nay lấy IPA đứng ngay
  sau ngoặc trùng headword (`_headword_ipa`).
- IPA hỏng trong file nguồn — mất ký tự khi chuyển mã (`@what /w t/`), chép chữ viết
  vào chỗ IPA (`@problem /problem/`), mảnh thuật ngữ (`/vertical/`) — bị phát hiện và
  **để trống** thay vì hiện sai (`_broken_ipa`, ~300 từ). Mục thuật ngữ viết hoa không
  có IPA thì lấy IPA của mục viết thường (+164 từ có IPA: bank, market, share…).
- Chỗ dữ liệu nguồn tự nó sai: viết đè ở `phonetics_manual.tsv` (`--phonetics`).

**Nghĩa & từ loại (#9).** Script lấy khối nghĩa ĐẦU TIÊN của FVDP, thường là nghĩa
cổ hoặc từ loại hiếm (say = danh từ "vải chéo", sell = "sự làm thất vọng").
`meanings_llm_review.tsv` rà 1.249 từ (toàn bộ A1–B1 `needs-review`/`single-source`
+ nghĩa rác mọi mức): sửa 1.039 nghĩa, 341 từ loại (cột 4), 210 từ đọc qua thấy ổn
chỉ đổi nhãn sang `llm`. Tất cả mang `meaning_source = llm` — **chưa có người xác
nhận**; rà xong thì đổi `# source: manual`.

**Nghĩa chọn lọc 1 nghĩa/từ (#9 tiếp, 2026-10-26).** Rà xong A1–B1 vẫn còn B2–C2 phần lớn là nghĩa FVDP chưa đối chứng (fusion = "sự nấu chảy", niche = "hốc thường", conditional bị gắn động từ). `meanings_curated.tsv` soạn lại 219 từ của 4 bộ lỗi nặng nhất — B2 · Từ 1–50/51–100/101–150 và Học thuật C1 · Từ 1–69 — mỗi từ ĐÚNG MỘT nghĩa (nghĩa Cambridge đặt lên đầu, hoặc nghĩa khớp câu ví dụ) và từ loại đúng. Nguồn `curated` thắng `llm`, thua `manual`; vì chưa ai duyệt nên item vẫn ghi `meaning_source/confidence = llm`. Duyệt xong đổi `# source: manual` -> `confirmed`. Kèm hai sửa trong script: từ loại (cột 4) nay đi theo DÒNG THẮNG thay vì file nạp sau cùng; nguồn `manual` ghi `meaning_confidence = confirmed` (trước ghi `manual`, nhãn UI không hiểu).

Trắc nghiệm/ghép cặp chỉ hiện **nghĩa chính** của mỗi đáp án (`quiz_service.answer_label`: cụm đầu trước `, ; /`), cho mọi bộ kể cả bộ người học tự nhập; loại nhiễu trùng nghĩa vẫn so trên nghĩa đầy đủ.

**Đưa vào DB đang chạy.** Item trong DB là bản sao lúc seed, dựng lại JSON không cập
nhật được DB. Sau khi dựng lại bộ nền:

```bash
python -m app.scripts.sync_seed_content          # chạy thử, in số trường sẽ đổi
python -m app.scripts.sync_seed_content --apply  # ghi thật
```

Cập nhật tại chỗ (giữ Interaction/mastery), không đụng chữ người học tự nhập/tự sửa.

## 5. LLM cục bộ — dùng ở đâu, và đúng bao nhiêu

Bản đầu của tài liệu này ghi "không LLM ở bất kỳ bước nào". Điều đó **không còn đúng**
và phải nói thẳng. Số liệu thật trên `vocab_seed_core.json` (3.748 từ):

| Trường | Giá trị | Số từ | Nguồn |
|---|---|---:|---|
| `example_source` | `fvdp` | 1.910 | câu ví dụ có sẵn trong từ điển FVDP |
| `example_source` | `llm` | 1.838 | LLM cục bộ sinh — `examples_llm.tsv` |
| `meaning_source` | `fvdp` | 3.574 | từ điển FVDP (đã đối chứng Wiktionary) |
| `meaning_source` | `llm` | 174 | LLM viết đè — `meanings_llm.tsv` |

**Vì sao chấp nhận LLM ở đây mà không chấp nhận ở chỗ khác.** Hai chỗ bị cấm dùng LLM
(`build_vocab_dataset.py`, `pdf_import/cefr.py`) là nơi LLM sẽ quyết định **nhãn** —
nghĩa của từ, trình độ CEFR — thứ người học không kiểm chứng được và hai lần chạy ra
hai kết quả. Câu ví dụ thì khác: nó **minh họa** một nghĩa đã chốt từ nguồn khác, sai
thì nhìn là thấy, và nếu không có nó thì 49% số từ hiển thị trống.

**Điều kiện bắt buộc — đánh dấu, không trộn.** Mọi item đều mang `example_source` và
`meaning_source`, nên phần LLM sinh luôn tách ra đếm và rà lại được. 174 nghĩa viết đè
còn mang thêm `meaning_confidence: llm` = *chưa có người xác nhận*. Không được bỏ hai
trường này, cũng không được ghi `fvdp` cho nội dung LLM sinh.

---

## Những gì KHÔNG dùng

* **Không LLM làm nguồn NGHĨA chính, và không LLM cho CEFR** — cùng lý do đã nêu trong
  `build_vocab_dataset.py` và `pdf_import/cefr.py`: hai lần chạy ra hai kết quả, người
  học không có cách nào kiểm chứng. LLM chỉ sinh **câu ví dụ**, cộng 174 nghĩa viết đè
  có gắn cờ riêng — xem mục 5.
* **Không Oxford 3000/5000** — có bản quyền, không phân phối lại được.
* **Không dịch máy** cho phần nghĩa.

## Ghi công tối thiểu trong khóa luận

> Danh sách từ: NGSL và NAWL (Browne, Culligan & Phillips, 2013),
> <newgeneralservicelist.com>, CC BY-SA 4.0.
> Trình độ CEFR: CEFR-J Vocabulary Profile 1.5 (Tono Lab, TUFS) và Octanove
> Vocabulary Profile C1/C2 1.0, CC BY-SA 4.0.
> Đối chứng nghĩa: English Wiktionary qua wiktextract (Ylönen, 2022), CC BY-SA 3.0.
> Nghĩa tiếng Việt, phiên âm và ví dụ: Free Vietnamese Dictionary Project (Hồ Ngọc Đức).
