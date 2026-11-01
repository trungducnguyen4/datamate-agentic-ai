# DataMate — Spec Compliance Audit (Zalo AI Challenge 2026)

**Ngày audit:** 2026-11-01
**Phạm vi:** toàn bộ repo `zalo/` (mã nguồn, test, Dockerfile, submission, tài liệu)
**Nguồn đề bài:** `docs/spec/description_parsed.txt`, `docs/spec/rule_parsed.txt`,
`docs/spec/evaluationMetric_parsed.txt` + 2 ảnh metric (`docs/spec/eval_metric_img_1.png`,
`docs/spec/eval_metric_img_2.png`), `docs/spec/submissionGuidance_parsed.txt`,
`data/train/rulebook.md`, `data/train/calendar.csv`.

> **Kết luận ngắn: CHƯA đúng hoàn toàn đề bài.** Hệ thống hiện tại vi phạm 3 điều kiện
> bắt buộc của đề (Rule 4, 5, 8), không dùng `rulebook.md`/`calendar.csv` do BTC cung cấp,
> chỉ sinh được 5/9 kiểu đáp án, và đạt **PA = −0.485** trên chính tập train của BTC
> (2.2% đúng). Riêng câu ví dụ trong đề bài (`q_06de33fa21cc`) hệ thống trả **abstain**.

---

## 1. Bằng chứng định lượng

### 1.1 Chạy trên 3.000 câu train có nhãn (`data/train/answers.jsonl`)

Chấm theo đúng luật của đề (kể cả `alias` là các dạng được chấp nhận), script
`scripts/eval_train_pa.py`:

| Chỉ số | Giá trị |
| :--- | ---: |
| Tổng số câu | 3.000 |
| Đúng (+1) | **67 (2.2%)** |
| Sai (−1) | **1.522 (50.7%)** |
| Abstain (0) | 1.411 (47.0%) |
| **Penalized Accuracy** | **−0.4850** |

Theo từng kiểu tham chiếu:

| Kiểu ref | n | đúng | sai | abstain | PA riêng |
| :--- | ---: | ---: | ---: | ---: | ---: |
| number | 1.884 | 30 | 1.012 | 842 | −0.521 |
| percent | 578 | **0** | 227 | 351 | −0.393 |
| list | 193 | **0** | 111 | 82 | −0.575 |
| date | 145 | **0** | 84 | 61 | −0.579 |
| string | 88 | 7 | 41 | 40 | −0.386 |
| boolean | 23 | **0** | 19 | 4 | −0.826 |
| table | 19 | **0** | 16 | 3 | −0.842 |
| unanswerable | 70 | 30 | 12 | 28 | +0.257 |

→ Một file **abstain toàn bộ sẽ được PA = 0**, tức hệ hiện tại *tệ hơn* việc không trả lời gì.
0/145 `date`, 0/19 `table`, 0/578 `percent`: các kiểu này **không có intent nào sinh ra**
(xem §3.4).

### 1.2 Câu ví dụ chính thức trong đề bài

Đề bài (description, dòng 17–20) đưa ví dụ `q_06de33fa21cc` — câu này **có thật** trong
`data/train/questions.jsonl`:

```
Q    : {"id":"q_06de33fa21cc","business_id":"biz_118","question":"sp bán dc nhiều nhất tuần rồi là gì","as_of_date":"2026-03-04"}
REF  : {"id":"q_06de33fa21cc","type":"string","answer":"Xi măng Hà Tiên PCB40 bao 50kg","alias":["SP0001"]}
PRED : {"id":"q_06de33fa21cc","type":"abstain"}          ← hệ thống hiện tại
```

Nguyên nhân (`python -m scripts.eval_train_pa --limit 1` + trace intent): business `biz_118`
lưu **mỗi tháng một file/sheet**
(`so_chi_tiet_ban_hang_t02_2025 … t09_2026`). `_find_sales_columns()`
(`datamate/engine/rule_compiler.py:559`) chọn **bảng đầu tiên khớp tên** →
`so_chi_tiet_ban_hang_t02_2025`, rồi lọc `ngay >= 2026-02-23` ⇒ 0 dòng ⇒ `ABSTAIN_EMPTY_RESULT`.

### 1.3 Submission public test (`submission.jsonl`)

| Chỉ số | Giá trị |
| :--- | ---: |
| Số dòng / số câu | 1.000 / 1.000 (khớp id 100%, không thừa/thiếu) |
| `abstain` | 586 (58.6%) |
| `unanswerable` | 182 (18.2%) |
| Trả lời thực sự | **232 (23.2%)** — number 209, string 19, boolean 2, list 2 |
| `date` / `percent` / `table` | **0 / 0 / 0** |

### 1.4 Test suite

`python -m pytest tests/ -q` → **47 passed** trong 5.68 s. Nhưng cần lưu ý: các test
end-to-end và benchmark 300 câu dùng **fixture/nhãn do chính đội tự soạn**
(`tests/data/vietnamese_qa_benchmark_300.json`, `data/sample/*`), không phải nhãn BTC,
nên test xanh **không** chứng minh đúng đề.

---

## 2. Vi phạm điều kiện bắt buộc (P0 — phải sửa trước khi nộp Docker)

> ⚠️ **Lưu ý quan trọng về thứ tự sửa:** hiện tại, do P0-1/P0-2, hệ thống trả `abstain`
> (hoặc `unanswerable`) cho gần như mọi câu ⇒ PA ≈ 0. Nếu chỉ sửa P0 mà **không** cải
> thiện engine (§3), điểm sẽ **giảm còn −0.485** (đúng như đo trên train) vì các câu sai
> bị trừ điểm. Vì vậy P0 và P1 phải làm **cùng nhau** trước khi nộp.

### P0-1. Mount `/data` read-only làm **toàn bộ** câu trả lời thành `abstain`
Rule 5: *"The data directory is mounted read-only; write temporary files elsewhere."*

`datamate/data/loader.py:100-102` tạo cache SQLite **bên trong thư mục dữ liệu**:

```python
cache_dir = os.path.join(os.path.dirname(self.business_dir), ".cache_sqlite")  # = /data/.cache_sqlite
os.makedirs(cache_dir, exist_ok=True)                                          # → EROFS
```

Mô phỏng đúng điều kiện mount read-only (`python -m scripts.simulate_readonly_data`):

```
type = abstain
status = EXECUTION_ERROR | phase = LOADER | err = OSError: [Errno 30] Read-only file system
```

Agent bắt exception và trả `ABSTAIN` (`datamate/engine/agent.py:116-124`) ⇒ trên máy BTC
**1.000/1.000 câu abstain, PA = 0**. Đây là lỗi nghiêm trọng nhất về mặt tuân thủ.

### P0-2. Dockerfile trỏ sai data root → **toàn bộ** `unanswerable`
`Dockerfile:33` dùng `--data-dir /data`, trong khi gói dữ liệu chính thức có cấu trúc
`<split>/{questions.jsonl, rulebook.md, calendar.csv, data/biz_*}`
(xem `data/train/`, `data/public_test/`). Loader lại tìm `<data-dir>/<business_id>`
(`datamate/engine/agent.py:28`) ⇒ không thấy business nào ⇒ bảng rỗng ⇒ `UNANSWERABLE`
(`agent.py:57-61`).

Tái hiện bằng đúng lệnh README hướng dẫn (`README.md:122-128`, `--data-dir data/public_test`):

```
$ python -m datamate.cli --data-dir data/public_test --questions data/public_test/questions.jsonl --limit 4
{"id": "q_008fdebb6ec9", "type": "unanswerable"}
{"id": "q_009187cd2960", "type": "unanswerable"}
{"id": "q_00bf8df3ea0b", "type": "unanswerable"}
{"id": "q_00c4e24fa228", "type": "unanswerable"}
```

→ Sai cả 2 chiều: (a) tài liệu/Entrypoint sai đường dẫn; (b) khi không nạp được dữ liệu
thì trả `unanswerable` (−1) thay vì `abstain` (0) — trái tinh thần "risk-aware abstain"
mà README quảng bá.

### P0-3. Chỉ đọc **một** bảng bán hàng, trong khi dữ liệu chia theo tháng/sheet
`_find_sales_columns()` lấy bảng đầu tiên khớp `hoa_don|don_hang|ban_hang|sales|orders|giao_dich`
(`rule_compiler.py:559-563`). Trong public test: `dev_002` có 18 file `BanHang_T*`; `dev_004`
có 18 sheet `sobanhang_t*`; `dev_005` 18 file `BanHang_Thang*`; `dev_013` 14 sheet
`banhang_2025_t*`. Câu hỏi về tháng khác sẽ truy vấn nhầm bảng ⇒ 0 dòng ⇒ abstain.
**Đây là nguyên nhân gốc của ~48% abstain trên train và câu ví dụ của đề bị sai.**
Cần: union view trên mọi bảng fact cùng schema (hoặc schema-aware "virtual table").

### P0-4. Chỉ ghi `submission.jsonl` **một lần ở cuối**
`datamate/cli.py:49-62`: gom toàn bộ kết quả vào list rồi mới ghi file. Rule 7/8:
*"If the re-run exceeds the time limit or terminates early, only the answers written to
/result/submission.jsonl before termination are scored; the rest count as abstain."*
⇒ Nếu quá 6 h hoặc crash, mất **toàn bộ** điểm. Phải ghi + `flush()` từng câu.

### P0-5. Không có log (Rule 8)
Rule 8 nói BTC sẽ *"examine the logs written by your image"*. Repo không cấu hình
`logging` ra file; `agent.py` chỉ có `print` ra stdout, không có file log nào trong
`/result`. Cần ghi log có cấu trúc (id, intent, SQL, status, latency) để đối soát
reproducibility |PA(upload) − PA(re-run)| ≤ 0.03.

---

## 3. Sai lệch so với rulebook / metric (P1)

### 3.1 Không dùng `rulebook.md` và `calendar.csv` của BTC
Rulebook ghi rõ: *"Tra lịch âm trong `calendar.csv` cùng thư mục"*. Code **không đọc**
2 file này (grep `calendar.csv` / `rulebook` không có kết quả trong `datamate/`), thay vào
đó hard-code lịch 2024–2027 (`datamate/data/calendar.py:8-56`). Hệ quả: mọi thay đổi/khác
biệt lịch âm của BTC (kể cả năm ngoài 2024–2027) đều không được cập nhật, và rulebook
không thể điều chỉnh hành vi theo split.

### 3.2 Mốc thời gian sai so với rulebook (§2)
| Rulebook | Code hiện tại | Hệ quả |
| :--- | :--- | :--- |
| "Từ đầu năm, từ đầu năm tới nay" = 01/01 → **hết hôm nay** | `resolver.py:246-250` trả 01/01 → **31/12** | tính cả giao dịch tương lai |
| "Tháng M / quý Q không ghi năm: năm nay nếu không sau hôm nay, sau hôm nay thì **năm trước**" | `resolver.py:175-184`, `137-154` luôn lấy năm hiện tại | sai kỳ với tháng/quý tương lai |
| "Tết năm Y: 23 tháng Chạp → hết mùng 10 tháng Giêng" | `resolver.py:71-78` trả **đúng 1 ngày** mùng 1 | sai toàn bộ câu "dịp Tết/mùa Tết"; thiếu "so với trước Tết" |
| "N ngày gần nhất" với N bất kỳ | `resolver.py:89-94` chỉ nhận **7 ngày** | các N khác rơi về fallback |
| "Đến hết ngày X" (snapshot nợ/tồn) | không hỗ trợ | câu nợ/tồn theo mốc ngày sai hoặc abstain |
| "Ca sáng / ca chiều" (06:00–13:59 / 14:00–21:59) | không hỗ trợ | mất nhóm câu theo ca |

Ngoài ra `build_where_clause()` (`rule_compiler.py:202-224`) **không** áp ràng buộc
`ngay <= as_of` toàn cục, nên bản ghi ngày tương lai vẫn được tính (rulebook: coi như
chưa xảy ra).

### 3.3 Phạm vi nghiệp vụ còn thiếu nhiều mục của rulebook
Đã có: doanh thu, số đơn, số lượng, xếp hạng sản phẩm (SL/DT), đếm/ tổng nợ, khách mua nhiều,
tỷ lệ huỷ, đơn max/min, trung bình/đơn, sản phẩm chưa bán (boolean).

Chưa có (dù rulebook quy định rõ): nhóm hàng, quy đổi đơn vị cơ bản
(`DanhSachQuyDoi.xlsx` — hiện cộng thô `so_luong`), "hàng lời nhất" (lợi nhuận gộp),
nhân viên bán giỏi nhất, top-k (chỉ `LIMIT 1`), so sánh kỳ trước/% thay đổi/tăng trưởng,
doanh thu theo hình thức thanh toán, tỷ trọng nhóm khách, tuổi nợ & phân nhóm nợ,
snapshot nợ theo ngày, nhập hàng/tồn kho/giá vốn (§5), bảng (table) & danh sách (list)
theo yêu cầu, ngày/tháng (date).

### 3.4 Chỉ sinh được 5/9 kiểu đáp án
`AnswerType` có đủ 9 giá trị (`core/types.py:7-16`) nhưng **không intent nào** trả
`DATE`, `TABLE`, `PERCENT` (ngoài huỷ/success-rate), `BOOLEAN` (ngoài unsold),
`LIST` (ngoài danh sách nợ). Train: 0 đúng ở date/list/percent/boolean/table.

### 3.5 Metric nội bộ lệch so với BTC
- Bỏ qua `alias`: `evaluator/metric.py:186-192` chỉ đọc `accepted_forms`, trong khi
  `answers.jsonl` dùng khoá `alias` (167/3000 câu có alias). Không thể tái lập điểm BTC.
- Ref `abstain`: `metric.py:162-165` cho pred `abstain` = **correct**; đề ghi
  *"Scored as abstain regardless of the reference"*.
- `match_number` so sánh `round(float)` bằng `==` (`metric.py:8-17`) — lệch dấu phẩy động
  ở biên 2 chữ số; nên dùng sai số tuyệt đối.
- `evaluate_single_answer` không kiểm tra `pred["type"]` thuộc 9 giá trị hợp lệ.

### 3.6 Hard-code theo id business / theo sản phẩm (Rule 4)
Rule 4: *"Hard-coding answers, or logic keyed on question or business identifiers, is prohibited."*
- `loader.py:108-119`: `if self.business_id == "biz_mega_5m":` → DuckDB view vào file CSV ngoài.
- `rule_compiler.py:255`: điều kiện `LIKE '%4 lớp%'` cho một sản phẩm cụ thể.
- `datamate/ui/app.py:216-223`: bảng demo chứa `expected_answer` hard-code (chỉ UI, nhưng
  `datamate/` được COPY vào image → reviewer sẽ thấy).

### 3.7 Chưa khai báo model trong README (Rule 2)
Rule 2: *"The models used must be declared in the solution README."* README hiện không có
mục models. Hệ thống không dùng model học máy nào (thuần rule-based) — cần ghi rõ
"0 tham số, không dùng LLM/embedding" để hợp lệ. Ngược lại, `docs/spec/hf_model_reference.md`
mô tả LoRA adapter `Qwen3-0.6B` **không tồn tại trong repo** (không có weights, không có
`scripts/evaluate_finetuned.sh`) → nếu nộp kèm sẽ là khai báo sai.

### 3.8 Determinism / reproducibility (Rule 8)
- `loader.py:146` duyệt `os.listdir()` (thứ tự hệ điều hành) để tạo bảng; bảng sales được
  chọn theo thứ tự đó ⇒ thứ tự file khác nhau có thể đổi bảng ⇒ đổi đáp án.
- Tên bảng lấy từ tên file; trên Windows các file tên tiếng Việt bị mojibake
  (`bß_ung_k_phiß_u_giao_h_ang`), trên Linux (image) lại là UTF-8 ⇒ **hành vi khác nhau
  giữa máy dev và image**. Cần chuẩn hoá NFC/UTF-8 và không phụ thuộc tên file.
- Không có cơ chế log để BTC đối soát |ΔPA| như Rule 8.

### 3.9 Định dạng submission (rủi ro thấp nhưng nên sửa)
`core/types.py:38-40` bỏ hẳn khoá `"answer"` khi `unanswerable`/`abstain`. Đề chỉ nêu ví dụ
3 khoá, không nói được bỏ; scorer chính thức có thể yêu cầu key tồn tại. Nên xuất
`"answer": null` để ổn định schema.

---

## 4. Những điểm ĐÃ đúng

| Yêu cầu | Trạng thái | Ghi chú |
| :--- | :--- | :--- |
| Offline, không network (Rule 3) | ✅ | Không có HTTP/LLM call trong pipeline suy luận |
| Không human-in-the-loop (Rule 4) | ✅ | Chạy batch tự động |
| 6 giờ cho toàn bộ test (Rule 7) | ✅ | 3.000 câu + nạp 31 business: **535 s** (~0.18 s/câu); sau khi warm ~5 ms/câu |
| Không dùng test data để train (Rule 6) | ✅ | Không có training, không đọc `answers.jsonl` trong inference |
| Định dạng JSONL, id khớp 1000/1000 | ✅ | `submission.jsonl` hợp lệ UTF-8 |
| SQL read-only, chặn DDL/DML | ✅ | `engine/executor.py` (PRAGMA query_only + progress handler) |
| Nhận diện `unanswerable` cho schema thiếu cột | ✅ một phần | 30/70 đúng trên train |
| Test tự động | ✅ | 47 passed (nhưng fixture tự soạn) |

---

## 5. Kế hoạch khắc phục đề xuất (theo thứ tự ưu tiên)

**P0 — bắt buộc trước khi build Docker (ước tính 0.5–1 ngày)**
1. Loader: cache ra `tempfile.mkdtemp()` hoặc `/tmp` (không ghi vào `/data`); fallback
   `:memory:` khi FS read-only. *(P0-1)*
2. Entrypoint/CLI: tự dò data root (`/data` nếu có `biz_*`, ngược lại `/data/data`);
   giữ `--questions` mặc định nhưng cho phép `--questions` trỏ đúng file. *(P0-2)*
3. Loader: gom mọi bảng fact cùng schema thành **một view union** (`fact_sales`), map cột
   theo tên chuẩn hoá; không phụ thuộc thứ tự `os.listdir`. *(P0-3)*
4. Ghi submission theo kiểu streaming, `flush` từng dòng + log JSONL vào `/result`. *(P0-4, P0-5)*
5. Lỗi nạp dữ liệu/schema → `abstain`, chỉ `unanswerable` khi chắc chắn dữ liệu không hỗ trợ.

**P1 — đúng rulebook (ước tính 2–4 ngày)**
6. Đọc `calendar.csv` + `rulebook.md` runtime; sửa Tết (23 Chạp → mùng 10), "năm nay" →
   hôm nay, rollover tháng/quý sang năm trước, "N ngày", "đến hết ngày X", ca sáng/chiều.
7. Bổ sung intent: bảng/list/date/percent/boolean đầy đủ, top-k + tie-break theo mã,
   nhóm hàng, quy đổi đơn vị, lợi nhuận gộp, nhân viên, so sánh kỳ trước, tồn kho/nhập
   hàng/giá vốn, tuổi nợ, hình thức thanh toán.
8. Metric: dùng `alias`, sửa xử lý ref `abstain`, so sánh số theo sai số 1e-9.
9. Bỏ hard-code `biz_mega_5m`, `%4 lớp%`, dữ liệu demo trong `datamate/ui`.
10. README: khai báo model (0 tham số), cập nhật số test/kiến trúc; bỏ hoặc sửa
    `docs/spec/hf_model_reference.md`.

**P2 — chất lượng**
11. Đánh giá bằng `data/train/answers.jsonl` (có nhãn BTC) thay vì benchmark tự soạn;
    theo dõi PA theo kiểu đáp án trong CI.
12. Xử lý `.xls` (chỉ có openpyxl), file lỗi encoding, và chuẩn hoá tên bảng Unicode.

---

## 6. Ghi chú về phần "Data / Submission format" của đề
Mục **Data** (mô tả cấu trúc gói test, format submission, log) **không truy xuất được**:
`docs/spec/dataExam.html` rỗng (0 byte) và API trả `{"error_code": -10, "data": null}`.
Vì vậy các yêu cầu chi tiết về đường dẫn log/khoá JSONL chưa thể đối chiếu — cần bổ sung
tài liệu này trước khi chốt định dạng nộp.
