# DataMate — Compliance Audit & Remediation Log (Zalo AI Challenge 2026)

**Ngày audit:** 2026-11-01 · **Cập nhật:** sau khi khắc phục cụm P0 + P1
**Phạm vi:** toàn bộ repo `zalo/` (mã nguồn, test, Dockerfile, submission, tài liệu)
**Nguồn đề bài:** `docs/spec/description_parsed.txt`, `docs/spec/rule_parsed.txt`,
`docs/spec/evaluationMetric_parsed.txt` + 2 ảnh metric (`docs/spec/eval_metric_img_1.png`,
`docs/spec/eval_metric_img_2.png`), `docs/spec/submissionGuidance_parsed.txt`,
`data/train/rulebook.md`, `data/train/calendar.csv`.

---

## 0. Trạng thái hiện tại (TL;DR)

| Hạng mục | Trước khắc phục | Sau khắc phục |
| :--- | :--- | :--- |
| PA trên 3.000 câu train (nhãn BTC) | **−0.4850** | **{{PA_AFTER}}** |
| Số câu đúng | 67 (2.2%) | {{CORRECT_AFTER}} |
| Câu ví dụ chính thức `q_06de33fa21cc` | `abstain` (sai) | `string` — **đúng** |
| Mount `/data` read-only | crash loader → **100% abstain** | chạy bình thường (cache `/tmp`) |
| Docker `--data-dir /data` | **100% unanswerable** | tự dò `/data/data` |
| Bảng bán hàng chia theo tháng | chỉ đọc 1 bảng | union toàn bộ (+ join header/chi tiết) |
| `calendar.csv` của BTC | không dùng (hard-code 2024–2027) | đọc runtime, Tết đúng rulebook |
| Ghi submission | 1 lần ở cuối | streaming từng câu + log JSONL |
| Metric nội bộ | bỏ qua `alias` | dùng `alias`, ref `abstain` đúng đề |
| Test suite | 47 passed | 56 passed |

**Còn lại (chưa đạt "hoàn toàn"):** engine vẫn chỉ sinh được một phần các kiểu đáp án
(`date`, `table`, `percent` hầu như chưa có intent), nhiều mục rulebook (§3 top-k/quy đổi
đơn vị/lợi nhuận/nhân viên, §4 tuổi nợ, §5 kho – nhập hàng) chưa làm; xem §5.

---

## 1. Bằng chứng định lượng

### 1.1 Trước khắc phục (baseline của repo)

Script `scripts/eval_train_pa.py` (chấm PA chuẩn BTC, dùng cả `alias`):

| Chỉ số | Giá trị |
| :--- | ---: |
| Đúng (+1) | 67 (2.2%) |
| Sai (−1) | 1.522 (50.7%) |
| Abstain (0) | 1.411 (47.0%) |
| **PA** | **−0.4850** |

Nguyên nhân chính: chỉ đọc **một** bảng fact (tháng đầu tiên) → câu hỏi tháng khác trả rỗng;
không có intent cho `date`/`table`/`percent`; lỗi mount read-only và sai data root.

### 1.2 Sau khắc phục

| Chỉ số | Giá trị |
| :--- | ---: |
| Đúng (+1) | {{CORRECT_AFTER}} |
| Sai (−1) | {{WRONG_AFTER}} |
| Abstain (0) | {{ABSTAIN_AFTER}} |
| **PA** | **{{PA_AFTER}}** |

Chi tiết theo kiểu đáp án: xem `{{EVAL_LOG}}`.

### 1.3 Câu ví dụ chính thức trong đề bài

```
Q    : {"id":"q_06de33fa21cc","business_id":"biz_118","question":"sp bán dc nhiều nhất tuần rồi là gì","as_of_date":"2026-03-04"}
REF  : {"id":"q_06de33fa21cc","type":"string","answer":"Xi măng Hà Tiên PCB40 bao 50kg","alias":["SP0001"]}
PRED : {"id":"q_06de33fa21cc","type":"string","answer":"Xi măng Hà Tiên PCB40 bao 50kg"}   ✅
```

### 1.4 Test suite

`python -m pytest tests/ -q` → **56 passed** (thêm `tests/test_p0_p1_fixes.py`).

---

## 2. P0 — đã khắc phục

### P0-1. Mount `/data` read-only (Rule 5) ✅
**Trước:** `loader.py` tạo `.cache_sqlite` **trong thư mục dữ liệu**
(`os.makedirs(dirname(business_dir)/.cache_sqlite)`) → `EROFS` → mọi câu `abstain`.

**Sau:** cache ghi ra `$TMPDIR/datamate_cache` (hoặc `DATAMATE_CACHE_DIR`), khoá theo
`business_id + hash(tên file, kích thước)`; nếu không ghi được thì fallback SQLite
in-memory; build vào `.building` rồi `os.replace` để tránh cache dở dang.

**Kiểm chứng:** `python -m scripts.simulate_readonly_data` → `type = number`,
`status = SUCCESS` (trước: `abstain` / `OSError Errno 30`).

### P0-2. Data root và layout gói test (Rule 7) ✅
**Trước:** `Dockerfile` chạy `--data-dir /data` nhưng gói test có `data/` lồng bên trong
(`/data/questions.jsonl` + `/data/data/biz_*`) → không thấy business → 100% `unanswerable`.

**Sau:** `DataMateAgent._resolve_data_root()` dò `/data` và `/data/data`; business không
tồn tại → **`abstain`** (an toàn hơn `unanswerable`), không còn 100% sai.

**Kiểm chứng:** `python -m datamate.cli --data-dir data/public_test ...` →
`Resolved data root: .../data/public_test/data`.

### P0-3. Union bảng fact chia theo tháng + header/chi tiết ✅
**Trước:** `_find_sales_columns()` lấy bảng đầu tiên khớp tên; dữ liệu chia 18 file
`BanHang_T*`/`sobanhang_t*` → truy vấn nhầm tháng → rỗng.

**Sau:** `datamate/data/union_view.py`:
- `UNION ALL` mọi bảng dòng hàng cùng schema (chuẩn hoá cột `ngay`, `ten_san_pham`,
  `so_luong`, `thanh_tien`, `trang_thai`, `khach_hang`, `ma_hoa_don`, `don_gia`, `giam_gia`);
- nếu gặp mô hình header + chi tiết (`danhsachhoadon` + `...chitiet`), tạo
  `JOIN` theo mã hoá đơn;
- tạo index `order_id`/`date`/`customer` trên các bảng nguồn để tránh nested-loop N×M.

**Kiểm chứng:** `biz_118` (18 bảng tháng, 46.001 dòng) → câu ví dụ trả đúng;
`biz_106` (header + 2 shard chi tiết, 129.416 dòng) → doanh thu tháng tính được;
`dev_003` (2 file `BanHang_TongHop`) → union 102.204 dòng.

### P0-4. Ghi submission streaming (Rule 7/8) ✅
`datamate/cli.py` mở file và `flush()` sau **từng câu** → nếu quá 6 h/crash, BTC vẫn chấm
được các dòng đã ghi (trước đây ghi một lần ở cuối).

### P0-5. Log đối soát (Rule 8) ✅
Mỗi lần chạy sinh `/result/submission_log.jsonl` (mặc định cạnh output) gồm
`id, status, intent, sql, error_phase, error_message, latency_ms` — đủ để BTC đối soát
|PA(upload) − PA(re-run)|.

---

## 3. P1 — đã khắc phục

### 3.1 Đọc `calendar.csv` của BTC ✅
`datamate/data/calendar_csv.py` nạp `calendar.csv` (2024-01-01 → 2027-12-31), đổi ngày
âm ↔ dương, tính khoảng tháng âm. Agent tự tìm `calendar.csv` trong data root, thư mục cha
hoặc `/data`.

### 3.2 Sửa mốc thời gian theo rulebook ✅
| Rulebook | Trước | Sau |
| :--- | :--- | :--- |
| "Dịp Tết/mùa Tết" = 23 tháng Chạp → hết mùng 10 tháng Giêng | trả đúng 1 ngày mùng 1 | đúng khoảng (2026: 2026-02-10 → 2026-02-26) |
| "Mùng 1/2/3 Tết" | cả dịp Tết | đúng ngày (2026 mùng 2 = 2026-02-18) |
| "Trước Tết" | không hỗ trợ | cùng số ngày ngay trước 23 Chạp |
| "Từ đầu năm/năm nay" | 01/01 → 31/12 (gồm tương lai) | 01/01 → **hết hôm nay** |
| "Tháng Giêng", "Rằm tháng Giêng" | hard-code | theo `calendar.csv` |

### 3.3 Metric dùng `alias` + ref `abstain` ✅
`datamate/evaluator/metric.py`:
- string: chấp nhận `answer` + mọi dạng trong `alias`/`accepted_forms`;
- list: `alias` là list-of-list, so từng vị trí;
- ref `abstain` → luôn `abstain` (đúng câu "Scored as abstain regardless of the reference");
- so sánh số theo sai số `1e-9` thay vì `round(float) ==`.

---

## 4. Sửa thêm ngoài danh sách P0/P1 (cùng nguyên nhân gốc)

1. **Chuẩn hoá ngày theo từng giá trị**: dữ liệu trộn `2026-01-01`, `01/01/2026`,
   `9 thg 8 2026` → parser mới trong `loader.py` (trước chỉ xét giá trị đầu tiên).
2. **Nhận diện cột viết tắt** (`tt` = thành tiền, `dg` = đơn giá, `hd` = mã hoá đơn ...)
   trong `schema_inspector.py`, có kiểm tra kiểu dữ liệu mẫu.
3. **Lọc trạng thái NULL-safe**: `(status IS NULL OR status NOT LIKE '%hủy%' ...)` — trước
   đây bảng không có trạng thái bị loại sạch.
4. **Guard "có mốc thời gian nhưng bảng không có cột ngày"** → `abstain` thay vì trả số
   all-time (âm điểm oan).
5. **Chọn bảng sales theo điểm** (ưu tiên có ngày/thành tiền/sản phẩm) thay vì bảng đầu tiên.
6. **UI**: case demo "kỳ vọng abstain" được chấm riêng (metric không còn coi ref abstain là đúng).
7. **Executor**: timeout theo thời gian thực (10 s) + trần opcode 20M, tránh treo.

---

## 5. Còn lại — chưa "đúng hoàn toàn" (P2)

| # | Hạng mục | Trạng thái |
| :--- | :--- | :--- |
| 1 | Sinh đủ 9 kiểu đáp án | `date`/`table` gần như chưa có intent; `percent` chỉ có huỷ/success-rate |
| 2 | Rulebook §1 | thiếu đơn trả hàng, doanh thu theo hình thức thanh toán, tỷ trọng nhóm khách, tỷ lệ huỷ trên **mọi** đơn đặt trong kỳ |
| 3 | Rulebook §3 | thiếu top-k, quy đổi đơn vị (`DanhSachQuyDoi.xlsx`), "hàng lời nhất", nhân viên bán giỏi nhất, xác định khách theo tên |
| 4 | Rulebook §4 | thiếu snapshot nợ theo ngày, tuổi nợ, loại COD/sàn TMĐT khỏi công nợ |
| 5 | Rulebook §5 | kho/nhập hàng/giá vốn/lợi nhuận gần như chưa làm |
| 6 | Hard-code | `loader.py` còn nhánh `biz_mega_5m`; `rule_compiler.py` còn `LIKE '%4 lớp%'`; UI còn đáp án demo — cần bỏ để sạch Rule 4 |
| 7 | Tài liệu | `docs/spec/hf_model_reference.md` mô tả adapter Qwen3-0.6B **không có trong repo** → nên xoá hoặc sửa |
| 8 | Mục "Data/Submission format" | `dataExam` API trả `error_code -10`, `dataExam.html` rỗng → chưa đối chiếu được yêu cầu log/khoá JSONL chi tiết |
| 9 | Hiệu năng cold start | lần chạy đầu phải parse toàn bộ xlsx (~1 phút/business); vẫn trong hạn 6 h nhưng nên cache sẵn hoặc tối ưu |

---

## 6. Cách tái lập

```bash
# 1) Toàn bộ test
python -m pytest tests/ -q

# 2) Đo PA trên train (có nhãn BTC), chấm theo alias
python -m scripts.eval_train_pa --data-dir data/train/data

# 3) Mô phỏng /data read-only
python -m scripts.simulate_readonly_data

# 4) Chạy như BTC (mount read-only, layout /data/data)
python -m datamate.cli --data-dir data/public_test \
  --questions data/public_test/questions.jsonl --output submission.jsonl

# 5) Docker
docker build -t datamate-solution:latest .
docker run --rm --network none -v $(pwd)/data/public_test:/data:ro -v $(pwd)/result:/result datamate-solution:latest
```

---

## 7. Ghi chú về phần "Data / Submission format"

Mục **Data** (cấu trúc gói test, format submission, log) không truy xuất được:
`docs/spec/dataExam.html` rỗng và API trả `{"error_code": -10, "data": null}`.
Các yêu cầu chi tiết về đường dẫn log/khoá JSONL vì vậy vẫn **chưa đối chiếu được**.
