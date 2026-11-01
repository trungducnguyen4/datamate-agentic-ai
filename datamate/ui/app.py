from __future__ import annotations
import os
import time
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from datamate.core.types import AnswerType, QuestionItem, SubmissionItem
from datamate.core.nlp import VietnameseNLP
from datamate.data.loader import BusinessDataLoader
from datamate.data.schema_inspector import SchemaInspector
from datamate.engine.agent import DataMateAgent
from datamate.engine.rule_compiler import BusinessRuleCompiler
from datamate.evaluator.metric import compute_penalized_accuracy
from datamate.temporal.resolver import TemporalResolver

app = FastAPI(title="DataMate Interactive Playground", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Directories
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

DATASET_DIRS = {
    "public_test": os.path.abspath("data/public_test/data"),
    "train": os.path.abspath("data/train/data"),
    "5m": os.path.abspath("data/5m"),
    "sample": os.path.abspath("data/sample"),
}

agents_cache: Dict[str, DataMateAgent] = {}


def get_data_dir(dataset: str = "public_test") -> str:
    if dataset == "public_test" and os.path.exists(DATASET_DIRS["public_test"]):
        return DATASET_DIRS["public_test"]
    if dataset == "train" and os.path.exists(DATASET_DIRS["train"]):
        return DATASET_DIRS["train"]
    if dataset == "5m" and os.path.exists(DATASET_DIRS["5m"]):
        return DATASET_DIRS["5m"]
    return DATASET_DIRS["sample"]


def get_agent(dataset: str = "public_test") -> DataMateAgent:
    key = dataset if dataset in DATASET_DIRS and os.path.exists(DATASET_DIRS[dataset]) else "sample"
    if key not in agents_cache:
        agents_cache[key] = DataMateAgent(DATASET_DIRS[key])
    return agents_cache[key]


class AskRequest(BaseModel):
    business_id: str
    question: str
    as_of_date: str = "2026-03-04"
    dataset: str = "public_test"


@app.get("/api/datasets")
def get_datasets():
    return [
        {
            "id": "public_test",
            "name": "🔥 Public Test Zalo 2026 (14 doanh nghiệp, 1.000 câu)",
            "available": os.path.exists(DATASET_DIRS["public_test"]),
            "default": os.path.exists(DATASET_DIRS["public_test"]),
        },
        {
            "id": "train",
            "name": "🏆 Zalo 2026 Train (30 doanh nghiệp, 3.000 câu)",
            "available": os.path.exists(DATASET_DIRS["train"]),
            "default": False,
        },
        {
            "id": "5m",
            "name": "🚀 Siêu Dữ Liệu 5 Triệu Dòng (datamate_vietnamese_qa_5m.csv - 1.2GB)",
            "available": os.path.exists("datamate_vietnamese_qa_5m.csv"),
            "default": False,
        },
        {
            "id": "sample",
            "name": "🧪 Sample Mock Data (4 doanh nghiệp demo)",
            "available": os.path.exists(DATASET_DIRS["sample"]),
            "default": False,
        },
    ]


@app.get("/api/businesses")
def get_businesses(dataset: str = "public_test"):
    data_dir = get_data_dir(dataset)
    if not os.path.exists(data_dir):
        return []
    biz_list = []
    for d in sorted(os.listdir(data_dir)):
        if d.startswith("."):
            continue
        full_p = os.path.join(data_dir, d)
        if os.path.isdir(full_p):
            readme_p = os.path.join(full_p, "README.md")
            readme_content = ""
            if os.path.exists(readme_p):
                with open(readme_p, "r", encoding="utf-8", errors="replace") as f:
                    readme_content = f.read()
            biz_list.append({"id": d, "readme": readme_content})
    return biz_list


@app.get("/api/business/{biz_id}/tables")
def get_business_tables(biz_id: str, dataset: str = "public_test"):
    agent_inst = get_agent(dataset)
    data_dir = get_data_dir(dataset)
    biz_dir = os.path.join(data_dir, biz_id)
    if not os.path.exists(biz_dir):
        raise HTTPException(status_code=404, detail="Business not found")

    loader = agent_inst.get_or_load_business(biz_id)
    tables_meta = agent_inst.get_tables(biz_id, loader.conn)

    res = {}
    for t_name, t_info in tables_meta.items():
        cursor = loader.conn.cursor()
        cursor.execute(f"SELECT * FROM `{t_name}` LIMIT 10;")
        col_names = [d[0] for d in cursor.description]
        rows = cursor.fetchall()

        res[t_name] = {
            "row_count": t_info.row_count,
            "columns": [c.model_dump() for c in t_info.columns],
            "preview_cols": col_names,
            "preview_rows": [list(r) for r in rows],
        }
    return res


@app.post("/api/ask")
def ask_question(req: AskRequest):
    t_start = time.time()
    agent_inst = get_agent(req.dataset)

    q_item = QuestionItem(
        id=f"q_{int(time.time() * 1000)}",
        business_id=req.business_id,
        question=req.question,
        as_of_date=req.as_of_date,
    )

    # 1. NLP Analysis
    nlp_info = VietnameseNLP.process_query(req.question)

    # 2. Resolve temporal
    temp_range = TemporalResolver.resolve(nlp_info.clean_query, req.as_of_date)
    if not temp_range:
        temp_range = TemporalResolver.resolve(req.question, req.as_of_date)

    temp_info = (
        {
            "start_date": temp_range.start_date,
            "end_date": temp_range.end_date,
            "target_month": temp_range.target_month,
            "is_exact_day": temp_range.is_exact_day,
            "is_ambiguous": temp_range.is_ambiguous,
        }
        if temp_range
        else None
    )

    # 3. Get business schema
    loader = agent_inst.get_or_load_business(req.business_id)
    tables = agent_inst.get_tables(req.business_id, loader.conn)

    # 4. Plan compilation
    plan = BusinessRuleCompiler.compile(req.question, req.as_of_date, tables)

    # 5. Agent answer
    sub_item = agent_inst.answer_question(q_item)
    latency_ms = round((time.time() - t_start) * 1000, 2)

    return {
        "submission": sub_item.to_dict(),
        "temporal": temp_info,
        "nlp": {
            "clean_query": nlp_info.clean_query,
            "is_quantity_query": nlp_info.is_quantity_query,
            "is_revenue_query": nlp_info.is_revenue_query,
            "is_profit_cost_query": nlp_info.is_profit_cost_query,
            "is_expiration_query": nlp_info.is_expiration_query,
            "is_stock_query": nlp_info.is_stock_query,
            "is_why_causal": nlp_info.is_why_causal,
            "is_future": nlp_info.is_future,
            "is_ambiguous_time": nlp_info.is_ambiguous_time,
        },
        "plan": {
            "intent": plan.intent,
            "expected_type": plan.expected_type.value,
            "sql": plan.sql,
            "confidence": plan.confidence,
            "unanswerable_reason": plan.unanswerable_reason,
        },
        "trace": agent_inst.last_trace.model_dump() if agent_inst.last_trace else None,
        "latency_ms": latency_ms,
    }


PRIORITY_QA_CASES = [
    {"id": "VN-02", "biz": "biz_099", "q": "Tháng này mặt hàng nào bán chạy nhất?", "desc": "Câu tự nhiên, chuẩn (Số lượng)", "date": "2026-03-04", "expected_type": "string", "expected_answer": "Panadol Extra đỏ vỉ"},
    {"id": "VN-03", "biz": "biz_099", "q": "Anh/chị xem giúp em tháng này thuốc nào bán chạy nhất với.", "desc": "Xưng hô và lịch sự", "date": "2026-03-04", "expected_type": "string", "expected_answer": "Panadol Extra đỏ vỉ"},
    {"id": "CHAT-01", "biz": "biz_099", "q": "sp bán dc nhiều nhất tuần rồi là gì", "desc": "Viết tắt, benchmark", "date": "2026-03-04", "expected_type": "string", "expected_answer": "Panadol Extra đỏ vỉ"},
    {"id": "CHAT-06", "biz": "biz_099", "q": "thang nay mat hang nao ban chay nhat", "desc": "Tiếng Việt không dấu", "date": "2026-03-04", "expected_type": "string", "expected_answer": "Panadol Extra đỏ vỉ"},
    {"id": "CHAT-07", "biz": "biz_099", "q": "sp nào bán dc nhìu nhất tuần rùi z shop", "desc": "Teencode, tiếng lóng", "date": "2026-03-04", "expected_type": "string", "expected_answer": "Panadol Extra đỏ vỉ"},
    {"id": "DIA-04", "biz": "biz_099", "q": "Bữa giờ thuốc nào bán chạy nhất vậy?", "desc": "Phương ngữ Nam, thời gian mơ hồ -> ABSTAIN", "date": "2026-03-04", "expected_type": "abstain", "expected_answer": None},
    {"id": "DIA-06", "biz": "biz_099", "q": "Tháng ni thuốc mô bán chạy nhất rứa?", "desc": "Phương ngữ Trung", "date": "2026-03-04", "expected_type": "string", "expected_answer": "Panadol Extra đỏ vỉ"},
    {"id": "SEM-01", "biz": "biz_fixture_probe", "q": "Sản phẩm nào bán được nhiều nhất?", "desc": "Số lượng (Sản phẩm A)", "date": "2026-03-04", "expected_type": "string", "expected_answer": "Sản phẩm A"},
    {"id": "SEM-02", "biz": "biz_fixture_probe", "q": "Sản phẩm nào thu về nhiều tiền nhất?", "desc": "Doanh thu (Sản phẩm B)", "date": "2026-03-04", "expected_type": "string", "expected_answer": "Sản phẩm B"},
    {"id": "SEM-03", "biz": "biz_fixture_probe", "q": "Sản phẩm nào có lợi nhuận cao nhất?", "desc": "Cần giá vốn -> UNANSWERABLE", "date": "2026-03-04", "expected_type": "unanswerable", "expected_answer": None},
    {"id": "SEM-04", "biz": "biz_099", "q": "Panadol đỏ còn hạn sử dụng đến khi nào?", "desc": "Cần HSD -> UNANSWERABLE", "date": "2026-03-04", "expected_type": "unanswerable", "expected_answer": None},
    {"id": "NEG-04", "biz": "biz_099", "q": "Tại sao tuần rồi doanh số giảm?", "desc": "Câu hỏi Why/Nguyên nhân -> UNANSWERABLE", "date": "2026-03-04", "expected_type": "unanswerable", "expected_answer": None},
    {"id": "NEG-05", "biz": "biz_099", "q": "Tháng sau dự đoán bán được bao nhiêu cái nhiệt kế?", "desc": "Dự đoán tương lai -> UNANSWERABLE", "date": "2026-03-04", "expected_type": "unanswerable", "expected_answer": None},
    {"id": "LUNAR-01", "biz": "biz_099", "q": "Từ sau Tết đến giờ bán được bao nhiêu tiền?", "desc": "Lịch âm (Sau Tết Bính Ngọ)", "date": "2026-03-04", "expected_type": "number", "expected_answer": 6425000},
    {"id": "EMPTY-01", "biz": "biz_empty_sales", "q": "Mặt hàng nào bán chạy nhất tháng này?", "desc": "Tiệm mới mở 0 đơn -> ABSTAIN", "date": "2026-03-04", "expected_type": "abstain", "expected_answer": None},
]

qa_env_dir = None


def get_qa_agent() -> DataMateAgent:
    global qa_env_dir
    if not qa_env_dir or not os.path.exists(qa_env_dir):
        from scripts.run_benchmark_eval import setup_benchmark_env
        qa_env_dir = setup_benchmark_env()
    return DataMateAgent(data_root_dir=qa_env_dir)


@app.get("/api/qa-checklist")
def get_qa_checklist():
    """Return the 15 priority evaluation cases with ground truth references."""
    return PRIORITY_QA_CASES


@app.post("/api/run-all-tests")
def run_all_qa_tests():
    """Execute all 15 QA Priority Cases automatically and return scorecard with diffs."""
    from datamate.evaluator.metric import evaluate_single_answer
    from datamate.core.types import EvaluationResult

    agent_inst = get_qa_agent()
    results = []
    correct_count = 0
    abstain_count = 0
    wrong_count = 0
    total_score = 0.0
    total_latency = 0.0

    for item in PRIORITY_QA_CASES:
        t0 = time.perf_counter()
        q_item = QuestionItem(
            id=item["id"],
            business_id=item["biz"],
            question=item["q"],
            as_of_date=item["date"],
        )
        sub_item, trace = agent_inst.answer_question_with_trace(q_item)
        latency = round((time.perf_counter() - t0) * 1000, 2)
        total_latency += latency

        ref = {
            "id": item["id"],
            "type": item["expected_type"],
            "answer": item["expected_answer"],
        }
        # BTC không phát hành reference kiểu "abstain" (abstain là kiểu dự đoán),
        # nên các case demo "kỳ vọng abstain" được chấm riêng ở đây.
        if item["expected_type"] == "abstain":
            if sub_item.type.value == "abstain":
                status = "PASS"
                correct_count += 1
                total_score += 1.0
            else:
                status = "FAIL"
                wrong_count += 1
                total_score -= 1.0
        else:
            eval_res = evaluate_single_answer(sub_item, ref)
            if eval_res == EvaluationResult.CORRECT:
                status = "PASS"
                correct_count += 1
                total_score += 1.0
            elif eval_res == EvaluationResult.ABSTAIN:
                status = "ABSTAIN"
                abstain_count += 1
            else:
                status = "FAIL"
                wrong_count += 1
                total_score -= 1.0

        results.append({
            "id": item["id"],
            "biz": item["biz"],
            "q": item["q"],
            "desc": item["desc"],
            "expected_type": item["expected_type"],
            "expected_answer": item["expected_answer"],
            "actual_type": sub_item.type.value if hasattr(sub_item.type, "value") else str(sub_item.type),
            "actual_answer": sub_item.answer,
            "status": status,
            "latency_ms": latency,
            "trace": trace.model_dump() if trace else None,
        })

    n = len(PRIORITY_QA_CASES)
    return {
        "summary": {
            "total": n,
            "passed": correct_count,
            "abstain": abstain_count,
            "failed": wrong_count,
            "penalized_score": round(total_score, 1),
            "accuracy_pct": round((correct_count / n) * 100, 1),
            "avg_latency_ms": round(total_latency / n, 2),
        },
        "results": results,
    }


@app.get("/api/sample-questions")
def get_sample_questions(dataset: str = "public_test", business_id: Optional[str] = None):
    if dataset == "public_test":
        q_file = os.path.abspath("data/public_test/questions.jsonl")
    elif dataset == "train":
        q_file = os.path.abspath("data/train/questions.jsonl")
    elif dataset == "5m":
        q_file = os.path.abspath("data/5m/questions.jsonl")
    else:
        q_file = os.path.abspath("data/sample/questions.jsonl")

    if not os.path.exists(q_file):
        return []
    items = []
    with open(q_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                import json
                try:
                    obj = json.loads(line)
                    if not business_id or obj.get("business_id") == business_id:
                        items.append(obj)
                        if len(items) >= 30:
                            break
                except Exception:
                    continue
    return items


@app.get("/", response_class=FileResponse)
def index_html():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"message": "DataMate API is running. index.html not found."}, status_code=404)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting DataMate Web UI on http://127.0.0.1:{port} ...")
    uvicorn.run("datamate.ui.app:app", host="127.0.0.1", port=port, reload=False)
