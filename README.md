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
│   │   ├── loader.py          # Load CSV, multi-sheet Excel, SQLite
│   │   ├── calendar.py        # Solar-Lunar Calendar cho các năm 2024 - 2027
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
├── tests/                     # Bộ kiểm thử tự động toàn diện (16/16 passed)
│   ├── test_normalizer.py     # Kiểm thử luật chuẩn hóa tiếng Việt
│   ├── test_evaluator.py      # Kiểm thử luật chấm điểm và PA
│   ├── test_temporal.py       # Kiểm thử giải mã mốc thời gian
│   └── test_end_to_end.py     # Kiểm thử tích hợp Agent trên mock dataset
├── .clinerules                # Quy chuẩn Commit & Verification Protocol (ExamTrust)
├── Dockerfile                 # Docker submission package chuẩn BTC (offline 100%)
└── requirements.txt           # Thư viện phụ thuộc
```

---

## 🚀 Hướng dẫn Sử dụng

### 1. Cài đặt môi trường
```bash
pip install -r requirements.txt
```

### 2. Chạy toàn bộ Test Suite
```bash
python -m pytest tests/ -v
```

### 3. Chạy suy luận sinh kết quả nộp bài (`submission.jsonl`)
```bash
python -m datamate.cli \
  --data-dir data/public_test \
  --questions data/public_test/questions.jsonl \
  --output submission.jsonl
```

### 4. Đánh giá thử nghiệm với nhãn đối chiếu (nếu có ground truth)
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
- Dữ liệu kiểm thử được mount tại `/data`.
- Kết quả xuất ra `/result/submission.jsonl`.

```bash
# Build image
docker build -t datamate-solution:latest .

# Chạy thử nghiệm offline mô phỏng máy chủ BTC
docker run --rm --network none \
  -v $(pwd)/data/public_test:/data:ro \
  -v $(pwd)/result:/result \
  datamate-solution:latest
```
