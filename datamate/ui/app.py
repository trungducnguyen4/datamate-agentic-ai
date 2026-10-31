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

DATA_ROOT = os.environ.get("DATAMATE_DATA_DIR", os.path.abspath("data/sample"))
agent = DataMateAgent(DATA_ROOT)


class AskRequest(BaseModel):
    business_id: str
    question: str
    as_of_date: str = "2026-03-04"


@app.get("/api/businesses")
def get_businesses():
    if not os.path.exists(DATA_ROOT):
        return []
    biz_list = []
    for d in sorted(os.listdir(DATA_ROOT)):
        full_p = os.path.join(DATA_ROOT, d)
        if os.path.isdir(full_p):
            readme_p = os.path.join(full_p, "README.md")
            readme_content = ""
            if os.path.exists(readme_p):
                with open(readme_p, "r", encoding="utf-8", errors="replace") as f:
                    readme_content = f.read()
            biz_list.append({"id": d, "readme": readme_content})
    return biz_list


@app.get("/api/business/{biz_id}/tables")
def get_business_tables(biz_id: str):
    biz_dir = os.path.join(DATA_ROOT, biz_id)
    if not os.path.exists(biz_dir):
        raise HTTPException(status_code=404, detail="Business not found")

    loader = agent.get_or_load_business(biz_id)
    tables_meta = SchemaInspector.inspect(loader.conn)

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
    loader = agent.get_or_load_business(req.business_id)
    tables = SchemaInspector.inspect(loader.conn)

    # 4. Plan compilation
    plan = BusinessRuleCompiler.compile(req.question, req.as_of_date, tables)

    # 5. Agent answer
    sub_item = agent.answer_question(q_item)
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
        "latency_ms": latency_ms,
    }


@app.get("/api/sample-questions")
def get_sample_questions():
    q_file = os.path.join(DATA_ROOT, "questions.jsonl")
    if not os.path.exists(q_file):
        return []
    items = []
    with open(q_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                import json
                items.append(json.loads(line))
    return items


@app.get("/", response_class=FileResponse)
def index_html():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"message": "DataMate API is running. index.html not found."}, status_code=404)
