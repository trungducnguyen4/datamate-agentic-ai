"""Regression tests cho cụm P0 + P1 (2026-11-01).

Bao phủ:
- tự dò data root (`<root>/data` vs `<root>`);
- cache SQLite không ghi vào thư mục dữ liệu (mô phỏng /data read-only);
- union các bảng fact chia theo tháng;
- metric dùng `alias` và xử lý ref `abstain` đúng đề.
"""
import json
import os

import pandas as pd
import pytest

from datamate.core.types import QuestionItem
from datamate.data.loader import BusinessDataLoader
from datamate.engine.agent import DataMateAgent
from datamate.evaluator.metric import EvaluationResult, evaluate_single_answer


def _make_business(root, business_id, files):
    biz_dir = os.path.join(root, business_id)
    os.makedirs(biz_dir, exist_ok=True)
    with open(os.path.join(biz_dir, "README.md"), "w", encoding="utf-8") as fh:
        fh.write("# Cửa hàng thử nghiệm\n")
    for name, rows in files.items():
        pd.DataFrame(rows).to_csv(os.path.join(biz_dir, name), index=False, encoding="utf-8")
    return biz_dir


MONTH_JAN = {
    "ngay": ["2026-01-05", "2026-01-20"],
    "ten_san_pham": ["Trà sữa", "Cà phê"],
    "so_luong": [2, 3],
    "thanh_tien": [100, 200],
    "trang_thai": ["Hoàn thành", "Hoàn thành"],
}

MONTH_FEB = {
    "ngay": ["2026-02-03"],
    "ten_san_pham": ["Trà sữa"],
    "so_luong": [5],
    "thanh_tien": [250],
    "trang_thai": ["Hoàn thành"],
}


@pytest.fixture
def monthly_split_env(tmp_path):
    """Gói dữ liệu có thư mục `data/` lồng bên trong, bán hàng chia 2 tháng."""
    split_root = tmp_path / "split"
    data_root = split_root / "data"
    os.makedirs(data_root)
    _make_business(
        str(data_root),
        "biz_monthly",
        {"SoBanHang_T01_2026.csv": MONTH_JAN, "SoBanHang_T02_2026.csv": MONTH_FEB},
    )
    with open(split_root / "questions.jsonl", "w", encoding="utf-8") as fh:
        fh.write("")
    return str(split_root)


def test_auto_detect_data_root(monthly_split_env):
    agent = DataMateAgent(monthly_split_env)
    assert agent.data_root_dir == os.path.join(monthly_split_env, "data")


def test_monthly_shards_are_unioned(monthly_split_env):
    agent = DataMateAgent(monthly_split_env)
    question = QuestionItem(
        id="q_jan",
        business_id="biz_monthly",
        question="doanh thu tháng 1 là bao nhiêu",
        as_of_date="2026-03-04",
    )
    answer = agent.answer_question(question)
    assert answer.type.value == "number"
    assert answer.answer == 300

    feb = QuestionItem(
        id="q_feb",
        business_id="biz_monthly",
        question="doanh thu tháng 2 là bao nhiêu",
        as_of_date="2026-03-04",
    )
    answer = agent.answer_question(feb)
    assert answer.type.value == "number"
    assert answer.answer == 250


def test_cache_never_written_into_data_dir(monthly_split_env, monkeypatch):
    """Mô phỏng /data read-only: loader phải fallback in-memory thay vì crash."""
    real_makedirs = os.makedirs

    def readonly_makedirs(path, *args, **kwargs):
        if "datamate_cache" in str(path):
            raise OSError(30, "Read-only file system", str(path))
        return real_makedirs(path, *args, **kwargs)

    monkeypatch.setattr(os, "makedirs", readonly_makedirs)
    monkeypatch.delenv("DATAMATE_CACHE_DIR", raising=False)

    loader = BusinessDataLoader(os.path.join(monthly_split_env, "data", "biz_monthly"))
    loader.load()
    assert loader.table_names, "loader phải nạp được dữ liệu khi FS read-only"
    loader.close()


def test_missing_business_abstains(tmp_path):
    agent = DataMateAgent(str(tmp_path))
    answer = agent.answer_question(
        QuestionItem(
            id="q_missing",
            business_id="biz_khong_ton_tai",
            question="doanh thu tháng này là bao nhiêu",
            as_of_date="2026-03-04",
        )
    )
    assert answer.type.value == "abstain"


def test_metric_accepts_alias_for_string():
    ref = {
        "id": "q1",
        "type": "string",
        "answer": "Xi măng Hà Tiên PCB40 bao 50kg",
        "alias": ["SP0001"],
    }
    pred = {"id": "q1", "type": "string", "answer": "sp0001"}
    assert evaluate_single_answer(pred, ref) == EvaluationResult.CORRECT


def test_metric_accepts_alias_for_list():
    ref = {
        "id": "q2",
        "type": "list",
        "answer": ["Cà phê sữa (M)", "Trà đào cam sả (M)"],
        "alias": [["SP0003"], ["SP0017"]],
    }
    pred = {"id": "q2", "type": "list", "answer": ["SP0003", "SP0017"]}
    assert evaluate_single_answer(pred, ref) == EvaluationResult.CORRECT


def test_metric_reference_abstain_is_always_abstain():
    ref = {"id": "q3", "type": "abstain"}
    for pred in (
        {"id": "q3", "type": "abstain"},
        {"id": "q3", "type": "number", "answer": 1},
        {"id": "q3", "type": "unanswerable"},
    ):
        assert evaluate_single_answer(pred, ref) == EvaluationResult.ABSTAIN
