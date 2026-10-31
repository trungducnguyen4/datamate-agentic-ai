import json
import os
import shutil
import tempfile
import pandas as pd
import pytest

from datamate.core.types import AnswerType, QuestionItem
from datamate.engine.agent import DataMateAgent
from datamate.evaluator.metric import evaluate_single_answer, compute_penalized_accuracy


@pytest.fixture
def mock_dataset_dir():
    temp_dir = tempfile.mkdtemp()
    biz_dir = os.path.join(temp_dir, "biz_118")
    os.makedirs(biz_dir, exist_ok=True)

    # 1. README.md
    with open(os.path.join(biz_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write("# Cửa hàng vật liệu xây dựng Thành Đạt\nChuyên cung cấp xi măng, cát, đá, sắt thép.\n")

    # 2. Orders CSV
    # As of date: 2026-03-04 (Wednesday)
    # Previous week: 2026-02-23 to 2026-03-01
    orders_data = {
        "ngay_ban": [
            "2026-02-24",  # Previous week
            "2026-02-25",  # Previous week
            "2026-02-26",  # Previous week (Cancelled)
            "2026-03-02",  # Current week (March)
            "2026-03-03",  # Current week (March)
        ],
        "ma_sp": ["SP01", "SP02", "SP03", "SP01", "SP02"],
        "ten_san_pham": [
            "Xi măng Hà Tiên PCB40 bao 50kg",
            "Cát vàng xây tô m3",
            "Gạch tuynel 4 lỗ",
            "Xi măng Hà Tiên PCB40 bao 50kg",
            "Cát vàng xây tô m3",
        ],
        "so_luong": [50, 10, 1000, 20, 5],
        "don_gia": [90000, 300000, 1200, 90000, 300000],
        "thanh_tien": [4500000, 3000000, 1200000, 1800000, 1500000],
        "trang_thai": [
            "Hoàn thành",
            "Hoàn thành",
            "Đã hủy",
            "Hoàn thành",
            "Hoàn thành",
        ],
    }
    df_orders = pd.DataFrame(orders_data)
    df_orders.to_csv(os.path.join(biz_dir, "don_hang.csv"), index=False, encoding="utf-8")

    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_agent_contest_example(mock_dataset_dir):
    agent = DataMateAgent(mock_dataset_dir)

    # 1. Best seller in previous week (Contest's official example!)
    q1 = QuestionItem(
        id="q_06de33fa21cc",
        business_id="biz_118",
        question="sp bán dc nhiều nhất tuần rồi là gì",
        as_of_date="2026-03-04",
    )
    ans1 = agent.answer_question(q1)
    assert ans1.id == "q_06de33fa21cc"
    assert ans1.type == AnswerType.STRING
    assert ans1.answer == "Xi măng Hà Tiên PCB40 bao 50kg"

    # Evaluate against official reference
    ref1 = {
        "id": "q_06de33fa21cc",
        "type": "string",
        "answer": "Xi măng Hà Tiên PCB40 bao 50kg",
    }
    assert evaluate_single_answer(ans1, ref1) == "correct"


def test_agent_monthly_revenue(mock_dataset_dir):
    agent = DataMateAgent(mock_dataset_dir)

    # 2. Revenue in March 2026: March 2nd (1,800,000) + March 3rd (1,500,000) = 3,300,000
    q2 = QuestionItem(
        id="q_rev_01",
        business_id="biz_118",
        question="doanh thu tháng này là bao nhiêu",
        as_of_date="2026-03-04",
    )
    ans2 = agent.answer_question(q2)
    assert ans2.type == AnswerType.NUMBER
    assert ans2.answer == 3300000


def test_agent_unanswerable_missing_columns(mock_dataset_dir):
    agent = DataMateAgent(mock_dataset_dir)

    # 3. Question asking for profit / cost which does not exist in schema
    q3 = QuestionItem(
        id="q_unans_01",
        business_id="biz_118",
        question="lợi nhuận ròng của cửa hàng tuần rồi là bao nhiêu",
        as_of_date="2026-03-04",
    )
    ans3 = agent.answer_question(q3)
    assert ans3.type == AnswerType.UNANSWERABLE


def test_agent_abstain_on_unknown(mock_dataset_dir):
    agent = DataMateAgent(mock_dataset_dir)

    # 4. Out of domain / ambiguous question -> should safely abstain
    q4 = QuestionItem(
        id="q_abs_01",
        business_id="biz_118",
        question="thời tiết tuần này thế nào",
        as_of_date="2026-03-04",
    )
    ans4 = agent.answer_question(q4)
    assert ans4.type == AnswerType.ABSTAIN
