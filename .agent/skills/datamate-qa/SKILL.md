---
name: datamate-qa
description: >-
  Vietnamese Natural Language-to-SQL & Data QA Engine for messy, realistic business datasets (Zalo AI Challenge 2026).
  Use when analyzing Vietnamese business queries, handling dialect/teencode variations, resolving solar/lunar dates,
  compiling safe SQL aggregations, and enforcing answerability decisions with penalized accuracy (+1 / 0 / -1).
---

# DataMate — Vietnamese Natural Language Understanding & Data QA Skill

This skill guides the agent in interpreting, compiling, executing, and evaluating Vietnamese natural language queries over messy, realistic small-and-medium enterprise (SME) business data (CSV, Excel, SQLite).

---

## 1. Competition Objectives & Scoring Rules (Zalo AI Challenge 2026)

- **Offline Execution**: 100% offline, zero external cloud APIs, strictly sandboxed container inference ($\le$ 15B parameter models or deterministic semantic compilers).
- **Penalized Accuracy Scoring**:
  $$\text{Score} = \sum_{i} \text{Metric}(y_i, \hat{y}_i)$$
  - **$+1$**: Exactly correct answer (or correctly classified as `unanswerable` / `abstain`).
  - **$0$**: Safe abstention (`abstain`) on answerable queries.
  - **$-1$**: Confidently incorrect answer (or hallucinatory answer on unanswerable queries).
  > [!IMPORTANT]
  > Always prioritize correctness over raw answering rate. When query intent or time frame is ambiguous, safe abstention yields $0$ rather than a $-1$ penalty.

---

## 2. Vietnamese Computational Linguistics & NLU Engine

DataMate features a dedicated Vietnamese NLU preprocessor in `datamate/core/nlp.py`.

### 2.1 Conversational Fluff & Honorific Stripping
Vietnamese queries in real life include polite padding and social fluff that must not be confused with filters:
- **Prefixes to strip**: `Anh/chị xem giúp em`, `Cho mình hỏi`, `Nhờ shop kiểm tra dùm mình`, `Cô/chú coi thử`, `Không biết...`, `Dạ shop ơi`.
- **Suffixes to strip**: `ạ`, `nhé`, `nhỉ`, `nha`, `với`, `vậy shop`, `z shop`, `vậy nè`, `ta`.
- **Business self-references**: `bên mình`, `tiệm mình`, `nhà thuốc mình`, `cửa hàng mình` refer to the current database package, not external entities.

### 2.2 Teencode, Slang & Abbreviation Expansion
- `sp` $\rightarrow$ `sản phẩm`
- `dc`, `đc` $\rightarrow$ `được`
- `bn` $\rightarrow$ `bao nhiêu`
- `ko`, `k`, `hk` $\rightarrow$ `không`
- `nhiu`, `nhìu` $\rightarrow$ `nhiều` / `nhiêu`
- `z` $\rightarrow$ `vậy`
- `sl` $\rightarrow$ `số lượng`
- `dt` $\rightarrow$ `doanh thu`
- `date`, `hsd` $\rightarrow$ `hạn sử dụng`

### 2.3 Regional Dialect Translation
- **Central Dialect (Miền Trung)**:
  - `tháng ni` / `tuần ni` / `ngày ni` $\rightarrow$ `tháng này` / `tuần này` / `ngày này`
  - `đơn mô` / `thuốc mô` / `món mô` $\rightarrow$ `đơn nào` / `thuốc nào` / `món nào`
  - `rứa` $\rightarrow$ `vậy`
  - `răng` $\rightarrow$ `tại sao` (Causal $\rightarrow$ Unanswerable)
  - `chừ` $\rightarrow$ `hiện tại`
- **Northern Dialect (Miền Bắc)**:
  - `to tiền nhất` $\rightarrow$ `giá trị lớn nhất`
  - `bán chậm nhất` $\rightarrow$ `bán ế nhất` (Ranking ASC)
- **Southern Dialect (Miền Nam)**:
  - `nặng tiền nhất` $\rightarrow$ `nhiều tiền nhất`
  - `bán được nhiêu rồi` $\rightarrow$ `doanh thu tích lũy đến hiện tại`

### 2.4 Semantic Intent Disambiguation: Quantity vs. Revenue
- **Volume / Quantity queries** (`is_quantity_query`):
  - Keywords: `bán được bao nhiêu cái/hộp/vỉ/ly/món/sản phẩm`, `số lượng bán`, `sản lượng bán`.
  - Target Measure: `SUM(so_luong)`.
- **Revenue / Financial queries** (`is_revenue_query`):
  - Keywords: `doanh thu`, `doanh số`, `bao nhiêu tiền`, `thu về bao nhiêu`, `bán được bao nhiêu rồi`.
  - Target Measure: `SUM(thanh_tien)`.

---

## 3. Temporal Resolution & Vietnamese Lunar Calendar

Handled strictly by `datamate/temporal/resolver.py`:
- **Strict Anchor**: Never call `datetime.now()`. All calculations anchor to the provided `as_of_date`.
- **Rolling Windows vs. Calendar Weeks**:
  - `7 ngày gần đây`: $[\text{as\_of\_date} - 6\text{ days}, \text{as\_of\_date}]$ (Exactly 7 days).
  - `Tuần rồi`: Monday to Sunday of the previous calendar week.
  - `Cùng kỳ năm ngoái`: Same month of previous calendar year ($Y-1$).
- **Vietnamese Lunar Festival Resolution** (`datamate/data/calendar.py`):
  - `Tết Nguyên Đán (Mùng 1 Tết Bính Ngọ 2026)` $\rightarrow$ `2026-02-17`
  - `Mùng 2 Tết 2026` $\rightarrow$ `2026-02-18`
  - `Rằm tháng Giêng 2026` $\rightarrow$ `2026-03-03`
  - `Từ sau Tết đến nay`: Date range `[2026-02-17, as_of_date]`.
- **Ambiguous Relative Time**:
  - `bữa giờ`, `bữa nay tới giờ` $\rightarrow$ Flagged as ambiguous $\rightarrow$ Triggers `ABSTAIN`.

---

## 4. Answerability Decision Matrix

| Question Pattern | Trigger / Condition | System Decision | Answer Type |
| :--- | :--- | :--- | :--- |
| **Causal Why** | `Tại sao doanh thu giảm?`, `Răng doanh số thấp?` | Transaction logs contain no causal reasons | `unanswerable` |
| **Future Forecast** | `Dự đoán tháng sau bán được bao nhiêu?` | Relational tables record only past events | `unanswerable` |
| **Missing Schema** | Hỏi `lợi nhuận / giá vốn` khi bảng không có `gia_von` | Missing measure | `unanswerable` |
| **Missing Expiry** | Hỏi `thuốc nào hết hạn` khi bảng không có `hsd` | Missing dimension | `unanswerable` |
| **Missing Stock** | Hỏi `kho còn bao nhiêu` khi không có bảng tồn kho | Missing table | `unanswerable` |
| **Ambiguous Time** | `Bữa giờ bán được món nào chạy nhất?` | Unclear interval start | `abstain` |
| **Subjective Quality** | `Tháng này tiệm bán có khá không?` | Qualitative criterion | `abstain` |
| **Valid Metric** | `Doanh thu tháng này là bao nhiêu?` | Supported by schema | `number` / `string` / `list` |

---

## 5. Development & Testing Commands

```powershell
# Run entire test suite (45 unit & regression tests)
python -m pytest

# Run the 350-question Vietnamese QA Benchmark
python -m pytest tests/test_benchmark_300.py

# Evaluate detailed Penalized Accuracy statistics
python scripts/run_benchmark_eval.py

# Execute 5,000,000-row performance benchmark (Vectorized DuckDB/SQLite)
python scripts/benchmark_large_scale.py

# Regenerate 5M dataset if needed
python scripts/generate_5m_dataset.py

# Launch interactive UI playground
python -m datamate.ui.app
```
