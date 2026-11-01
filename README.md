# DataMate — Agentic AI for Vietnamese Tabular Data QA
> Giải pháp cho bảng đấu **DataMate - Talking To Your Data Through Agentic AI** (Zalo AI Challenge 2026).

---

## 🎯 Tổng quan Kiến trúc

DataMate Agentic AI được thiết kế theo kiến trúc 4 lớp bảo đảm tính chính xác và an toàn điểm số cao nhất theo thang đo **Penalized Accuracy (PA)** (+1 đúng, 0 abstain, -1 sai):

```
┌────────────────────────────────────────────────────────────────────────┐
│                        User Natural Language Query                     │
│                    + As-Of Date + Business Package                     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 1. Data Ingestion & Schema Inspector                                   │
│    - Nạp .csv, .xlsx, .sqlite và README.md vào SQLite in-memory        │
│    - Tự động nhận diện vai trò ngữ nghĩa của cột (date, amount,        │
│      quantity, status, product, customer, debt)                        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. Vietnamese Temporal & Calendar Resolver                             │
│    - Xử lý ngày tương đối ("tuần rồi", "tháng trước", "hôm qua", ...) │
│    - Tra cứu lịch Âm - Dương & ngày lễ truyền thống (Tết, Rằm)        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 3. Safe Execution & Business Rule Compiler                             │
│    - Biên dịch câu hỏi thành kế hoạch truy vấn SQL an toàn             │
│    - Xử lý lọc đơn hợp lệ, nhóm, sắp xếp tie-breaker theo rulebook    │
│    - Tự động phát hiện câu hỏi thiếu dữ liệu -> UNANSWERABLE          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 4. Normalization, Formatting & Risk-Aware Abstain                      │
│    - Chuẩn hóa Unicode NFC, lowercase, giữ nguyên dấu tiếng Việt       │
│    - Định dạng đúng 9 kiểu đầu ra: number, percent, string, date,      │
│      boolean, list, table, unanswerable, abstain                       │
│    - Fallback về ABSTAIN khi rủi ro cao để tránh bị trừ 1 điểm        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  Output: submission.jsonl (Leaderboard Ready)          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Cấu trúc Thư mục

```
zalo/
├── datamate/                  # Gói mã nguồn chính
│   ├── core/                  # Data types, model Pydantic, bộ chuẩn hóa string
│   │   ├── types.py           # 9 kiểu dữ liệu đáp án & schema submission
│   │   └── normalizer.py      # Chuẩn hóa chuỗi và so khớp theo luật BTC
│   ├── data/                  # Nạp dữ liệu đa định dạng & tra cứu lịch
│   │   ├── loader.py          # Load CSV, multi-sheet Excel, SQLite (cache ra /tmp)
│   │   ├── calendar.py        # Fallback lịch âm 2024 - 2027
│   │   ├── calendar_csv.py    # Đọc calendar.csv của BTC (Tết, tháng Giêng, rằm...)
│   │   ├── union_view.py      # Gộp bảng fact theo tháng + join header/chi tiết
│   │   └── schema_inspector.py# Phân tích schema và vai trò ngữ nghĩa của cột
│   ├── temporal/              # Phân giải mốc thời gian tiếng Việt
│   │   └── resolver.py        # Xử lý các cụm từ chỉ thời gian đối chiếu as_of_date
│   ├── engine/                # Bộ thực thi truy vấn & Agent điều phối
│   │   ├── executor.py        # Safe read-only SQLite execution
│   │   ├── rule_compiler.py   # Biên dịch logic nghiệp vụ thành SQL
│   │   └── agent.py           # DataMate Agent điều phối toàn luồng
│   ├── evaluator/             # Bộ tính điểm Penalized Accuracy chuẩn BTC
│   │   └── metric.py          # So khớp chính xác 9 kiểu đầu ra & tính PA
│   └── cli.py                 # CLI chạy hàng loạt trên questions.jsonl
├── docs/spec/                 # Toàn bộ tài liệu, luật thi & ảnh metric từ BTC
├── docs/COMPLIANCE_AUDIT.md   # Báo cáo đối chiếu đề bài (2026-11-01)
├── tests/                     # Bộ kiểm thử tự động toàn diện (56/56 passed)
│   ├── test_normalizer.py     # Kiểm thử luật chuẩn hóa tiếng Việt
│   ├── test_evaluator.py      # Kiểm thử luật chấm điểm và PA
│   ├── test_temporal.py       # Kiểm thử giải mã mốc thời gian (gồm Tết theo calendar.csv)
│   ├── test_end_to_end.py     # Kiểm thử tích hợp Agent trên mock dataset
│   ├── test_p0_p1_fixes.py    # Hồi quy: data root, cache /tmp, union tháng, alias
│   ├── test_vietnamese_qa_suite.py  # Suite 300 câu tự soạn
│   ├── test_benchmark_300.py  # Regression trên benchmark nội bộ
│   └── test_ui.py             # Smoke test FastAPI UI
├── .clinerules                # Quy chuẩn Commit & Verification Protocol (ExamTrust)
├── Dockerfile                 # Docker submission package chuẩn BTC (offline 100%)
├── requirements.txt           # Thư viện phụ thuộc cho inference
├── requirements-ui.txt        # Thêm FastAPI/uvicorn cho Web UI
├── requirements-benchmark.txt # Thêm DuckDB/tabulate cho benchmark 5M
└── requirements-all.txt       # Gộp cả 3 file trên (dev/benchmark đầy đủ)
```

---

## 🚀 Hướng dẫn Sử dụng

### 1. Cài đặt môi trường
```bash
# Chỉ inference (đủ cho Docker image)
pip install -r requirements.txt

# Môi trường dev đầy đủ (inference + Web UI + benchmark 5M)
pip install -r requirements-all.txt
```

### 2. Khai báo Model (Rule 2 — Zalo AI Challenge 2026)
Bài giải **không sử dụng bất kỳ model học máy nào** (không LLM, không embedding,
không reranker, không classifier). Toàn bộ pipeline là engine luật tất định
(schema inference + temporal resolver + rule compiler + SQLite). Do đó:

- Tổng số tham số sử dụng khi inference: **0** (giới hạn của BTC là 15 tỷ).
- Không cần GPU, không cần tải trọng số, không phụ thuộc mạng.
- Không có fine-tuning, không dùng dữ liệu public/private test để train.

### 3. Chạy toàn bộ Test Suite
```bash
python -m pytest tests/ -v
```

### 4. Chạy suy luận sinh kết quả nộp bài (`submission.jsonl`)
```bash
python -m datamate.cli \
  --data-dir data/public_test \
  --questions data/public_test/questions.jsonl \
  --output submission.jsonl
```

### 5. Đánh giá thử nghiệm với nhãn đối chiếu (nếu có ground truth)
```bash
python -m datamate.cli \
  --data-dir data/public_test \
  --questions data/public_test/questions.jsonl \
  --output submission.jsonl \
  --eval-ref data/public_test/reference.jsonl
```

---

## 🐳 Đóng gói Docker nộp bài

Theo quy chế Zalo AI Challenge 2026:
- Quá trình chạy nghiệm thu chạy offline (`--network none`).
- Dữ liệu kiểm thử được mount tại `/data` (read-only). Agent tự dò data root
  `/data` hoặc `/data/data`, và đọc `calendar.csv` cùng thư mục.
- Cache SQLite ghi ra `/tmp/datamate_cache` — **không** ghi vào `/data` (Rule 5).
- Kết quả xuất ra `/result/submission.jsonl`, ghi streaming từng câu (Rule 7/8).
- Log đối soát xuất ra `/result/submission_log.jsonl` (id, trạng thái, intent, SQL, latency).

```bash
# Build image
docker build -t datamate-solution:latest .

# Chạy thử nghiệm offline mô phỏng máy chủ BTC
docker run --rm --network none \
  -v $(pwd)/data/public_test:/data:ro \
  -v $(pwd)/result:/result \
  datamate-solution:latest
```

> Lưu ý: volume `data/public_test` chứa `questions.jsonl`, `calendar.csv`, `rulebook.md`
> và thư mục `data/` — đúng layout BTC mount.
