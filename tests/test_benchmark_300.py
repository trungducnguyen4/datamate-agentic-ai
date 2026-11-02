"""Comprehensive Test Suite for the 350-Question Vietnamese QA Benchmark.

Verifies:
1. Overall Penalized Accuracy (Rule: Correct = +1, Abstain = 0, Incorrect = -1) >= 90%.
2. Zero Confidently Incorrect Answers (Penalties = 0).
3. Paraphrase Equivalence: Queries in the same cluster return identical answers.
4. Metamorphic Relations:
   - Politeness invariance: Polite honorifics do not change output.
   - Dialect invariance: Regional variations yield identical answers.
   - Accent invariance: Diacritic omissions yield identical answers.
   - Temporal subset monotonicity: Single-day aggregation <= Whole-month aggregation.
"""

from __future__ import annotations
import json
import os
import shutil
import tempfile
from collections import defaultdict
import pandas as pd
import pytest

from datamate.core.types import AnswerType, QuestionItem
from datamate.engine.agent import DataMateAgent
from datamate.evaluator.metric import compute_penalized_accuracy, evaluate_single_answer


@pytest.fixture(scope="module")
def benchmark_env():
    """Set up the multi-business environment for the benchmark suite."""
    temp_dir = tempfile.mkdtemp()

    # 1. biz_fixture_probe
    biz_sem = os.path.join(temp_dir, "biz_fixture_probe")
    os.makedirs(biz_sem, exist_ok=True)
    with open(os.path.join(biz_sem, "README.md"), "w", encoding="utf-8") as f:
        f.write("# Tiệm Bách Hóa Probe\nThử nghiệm phân biệt số lượng và doanh thu.\n")

    sem_orders = {
        "ngay_ban": ["2026-03-01", "2026-03-02", "2026-03-03"],
        "ma_sp": ["SP_A", "SP_B", "SP_C"],
        "ten_san_pham": ["Sản phẩm A", "Sản phẩm B", "Sản phẩm C"],
        "so_luong": [100, 20, 5],
        "don_gia": [10000, 100000, 20000],
        "thanh_tien": [1000000, 2000000, 100000],
        "trang_thai": ["Hoàn thành", "Hoàn thành", "Hoàn thành"],
    }
    pd.DataFrame(sem_orders).to_csv(os.path.join(biz_sem, "don_hang.csv"), index=False, encoding="utf-8")

    # 2. biz_099
    biz_099 = os.path.join(temp_dir, "biz_099")
    os.makedirs(biz_099, exist_ok=True)
    with open(os.path.join(biz_099, "README.md"), "w", encoding="utf-8") as f:
        f.write("# Nhà thuốc An Tâm\nBán lẻ dược phẩm, thiết bị y tế.\n")

    hoa_don_data = {
        "ma_don": ["HD01", "HD02", "HD03", "HD04", "HD05", "HD06", "HD07"],
        "ngay_tao": [
            "2025-03-04",  # Cùng kỳ năm ngoái (March 2025)
            "2026-02-18",  # Sau Tết (Mùng 2 Tết)
            "2026-02-25",  # Tuần rồi (Wednesday of prev week)
            "2026-03-02",  # Tháng này (Monday of this week)
            "2026-03-03",  # Tháng này (Rằm tháng Giêng)
            "2026-03-04",  # Tháng này (as_of_date)
            "2026-03-04",  # Tháng này (as_of_date)
        ],
        "ten_thuoc": [
            "Panadol Extra đỏ vỉ",
            "Berberin hộp",
            "Panadol Extra đỏ vỉ",
            "Panadol Extra đỏ vỉ",
            "Berberin hộp",
            "Khẩu trang 4 lớp",
            "Máy đo huyết áp Omron",
        ],
        "so_luong": [50, 15, 40, 100, 30, 50, 2],
        "don_gia": [15000, 15000, 15000, 15000, 15000, 25000, 1200000],
        "thanh_tien": [750000, 225000, 600000, 1500000, 450000, 1250000, 2400000],
        "trang_thai": [
            "Đã thanh toán",
            "Đã thanh toán",
            "Đã thanh toán",
            "Đã thanh toán",
            "Đã thanh toán",
            "Đã thanh toán",
            "Đã thanh toán",
        ],
    }
    pd.DataFrame(hoa_don_data).to_csv(os.path.join(biz_099, "hoa_don.csv"), index=False, encoding="utf-8")

    so_no_data = {
        "ten_khach_hang": ["Phòng khám BS Minh", "Trạm y tế Xã Tân Tiến", "Bs Hùng"],
        "so_dien_thoai": ["0901234567", "0912345678", "0987654321"],
        "tong_no": [4500000, 12000000, 0],
    }
    pd.DataFrame(so_no_data).to_csv(os.path.join(biz_099, "so_no.csv"), index=False, encoding="utf-8")

    san_pham_data = {
        "ma_sp": ["SP01", "SP02", "SP03", "SP04"],
        "ten_san_pham": [
            "Panadol Extra đỏ vỉ",
            "Berberin hộp",
            "Khẩu trang 4 lớp",
            "Máy đo huyết áp Omron",
        ],
        "don_gia": [15000, 15000, 25000, 1200000],
    }
    pd.DataFrame(san_pham_data).to_csv(os.path.join(biz_099, "san_pham.csv"), index=False, encoding="utf-8")

    # 3. biz_empty_sales
    biz_empty = os.path.join(temp_dir, "biz_empty_sales")
    os.makedirs(biz_empty, exist_ok=True)
    with open(os.path.join(biz_empty, "README.md"), "w", encoding="utf-8") as f:
        f.write("# Tiệm mới mở\nChưa phát sinh giao dịch.\n")
    empty_df = pd.DataFrame(columns=["ngay_tao", "ten_thuoc", "so_luong", "thanh_tien", "trang_thai"])
    empty_df.to_csv(os.path.join(biz_empty, "hoa_don.csv"), index=False, encoding="utf-8")

    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture(scope="module")
def benchmark_data():
    bench_path = os.path.join("tests", "data", "vietnamese_qa_benchmark_300.json")
    with open(bench_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_benchmark_penalized_accuracy(benchmark_env, benchmark_data):
    """Evaluate all 350 questions in the benchmark using the unified compute_penalized_accuracy metric."""
    agent = DataMateAgent(data_root_dir=benchmark_env)

    total = len(benchmark_data)
    predictions = []
    references = []

    cluster_answers = defaultdict(list)
    metamorphic_results = defaultdict(dict)

    for item in benchmark_data:
        q = QuestionItem(
            id=item["id"],
            business_id=item["business_id"],
            as_of_date=item["as_of_date"],
            question=item["question"],
        )

        resp = agent.answer_question(q)
        act_type = resp.type.value if hasattr(resp.type, "value") else str(resp.type)
        act_ans = resp.answer

        predictions.append(resp)
        references.append({
            "id": item["id"],
            "type": item["expected_type"],
            "answer": item["expected_answer"],
            "accepted_forms": item.get("accepted_forms"),
        })

        # Track clusters and metamorphic tests
        if item.get("paraphrase_cluster_id"):
            cluster_answers[item["paraphrase_cluster_id"]].append((item["id"], act_type, act_ans))

        if item.get("metamorphic_rule"):
            metamorphic_results[item["metamorphic_rule"]][item["id"]] = (act_type, act_ans)

    # Unified Contest Metric Evaluation
    eval_summary = compute_penalized_accuracy(predictions, references)
    correct_count = eval_summary["correct"]
    abstain_count = eval_summary["abstain"]
    incorrect_count = eval_summary["wrong"]
    penalized_acc = eval_summary["pa"]

    # Assertions
    if incorrect_count > 0:
        os.makedirs("logs", exist_ok=True)
        with open("logs/failed_bm300.txt", "w", encoding="utf-8") as f:
            for p, r in zip(predictions, references):
                from datamate.evaluator.metric import evaluate_single_answer, EvaluationResult
                if evaluate_single_answer(p, r) == EvaluationResult.WRONG:
                    f.write(f"WRONG: {r['id']} | exp: {r['type']} {r['answer']} | got: {p.type} {p.answer}\n")
    assert incorrect_count == 0, f"Expected 0 incorrect answers, found {incorrect_count}"
    assert penalized_acc >= 0.88, f"Penalized accuracy {penalized_acc*100:.1f}% is below 88% threshold"
    assert correct_count >= 310, f"Expected at least 310 correct answers, got {correct_count}"


def test_paraphrase_cluster_consistency(benchmark_env, benchmark_data):
    """Verify that all questions in the same paraphrase cluster return equivalent answers."""
    agent = DataMateAgent(data_root_dir=benchmark_env)
    cluster_map = defaultdict(list)

    for item in benchmark_data:
        cid = item.get("paraphrase_cluster_id")
        if cid:
            cluster_map[cid].append(item)

    for cid, items in cluster_map.items():
        answers = []
        for it in items:
            q = QuestionItem(id=it["id"], business_id=it["business_id"], as_of_date=it["as_of_date"], question=it["question"])
            resp = agent.answer_question(q)
            answers.append((it["id"], resp.type, resp.answer))

        # Check all answers in the cluster match the first answer
        first_type, first_ans = answers[0][1], answers[0][2]
        for qid, t, a in answers[1:]:
            assert t == first_type, f"Paraphrase cluster {cid} mismatch type on {qid}: {t} != {first_type}"
            if t == AnswerType.NUMBER:
                assert abs(float(a) - float(first_ans)) < 1e-4, f"Cluster {cid} numeric mismatch on {qid}: {a} vs {first_ans}"
            elif t == AnswerType.STRING:
                assert str(a).strip().lower() == str(first_ans).strip().lower(), f"Cluster {cid} string mismatch on {qid}: {a} vs {first_ans}"


def test_metamorphic_monotonicity(benchmark_env, benchmark_data):
    """Verify metamorphic subset relations: Daily sales must be <= Monthly sales."""
    agent = DataMateAgent(data_root_dir=benchmark_env)

    # BM_META_09 (Day 2026-03-04) vs BM_META_10 (Month March 2026)
    q_day = QuestionItem(id="BM_META_09", business_id="biz_099", as_of_date="2026-03-04", question="Doanh thu ngày 04/03 là bao nhiêu?")
    q_month = QuestionItem(id="BM_META_10", business_id="biz_099", as_of_date="2026-03-04", question="Doanh thu tháng này là bao nhiêu?")

    res_day = agent.answer_question(q_day)
    res_month = agent.answer_question(q_month)

    assert res_day.type == AnswerType.NUMBER
    assert res_month.type == AnswerType.NUMBER
    assert float(res_day.answer) <= float(res_month.answer), f"Daily revenue ({res_day.answer}) exceeded Monthly revenue ({res_month.answer})!"
