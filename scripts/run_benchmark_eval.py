import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import json
import tempfile
import shutil
import pandas as pd
from collections import defaultdict
from datamate.core.types import QuestionItem, AnswerType, EvaluationResult
from datamate.engine.agent import DataMateAgent
from datamate.evaluator.metric import evaluate_single_answer, compute_penalized_accuracy

def setup_benchmark_env():
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

    return temp_dir

def run_benchmark():
    sys.stdout.reconfigure(encoding='utf-8')
    temp_dir = setup_benchmark_env()
    agent = DataMateAgent(data_root_dir=temp_dir)

    with open("tests/data/vietnamese_qa_benchmark_300.json", "r", encoding="utf-8") as f:
        benchmarks = json.load(f)

    total = len(benchmarks)
    results = []
    category_stats = defaultdict(lambda: {"total": 0, "correct": 0, "incorrect": 0, "abstain": 0, "score": 0.0})
    mismatches = []

    print(f"Running Benchmark Suite on {total} questions...")

    for item in benchmarks:
        cat = item["category"]
        category_stats[cat]["total"] += 1

        q = QuestionItem(
            id=item["id"],
            business_id=item["business_id"],
            as_of_date=item["as_of_date"],
            question=item["question"],
        )

        resp = agent.answer_question(q)
        actual_type = resp.type.value if hasattr(resp.type, "value") else str(resp.type)
        actual_ans = resp.answer

        exp_type = item["expected_type"]
        exp_ans = item["expected_answer"]

        # Evaluate score using unified evaluate_single_answer
        ref = {
            "id": item["id"],
            "type": exp_type,
            "answer": exp_ans,
            "accepted_forms": item.get("accepted_forms"),
        }
        eval_res = evaluate_single_answer(resp, ref)
        if eval_res == EvaluationResult.CORRECT:
            score = 1.0
            category_stats[cat]["correct"] += 1
        elif eval_res == EvaluationResult.ABSTAIN:
            score = 0.0
            category_stats[cat]["abstain"] += 1
        else:
            score = -1.0
            category_stats[cat]["incorrect"] += 1
            mismatches.append({
                "id": item["id"],
                "cat": cat,
                "q": item["question"],
                "exp_type": exp_type,
                "exp_ans": exp_ans,
                "act_type": actual_type,
                "act_ans": actual_ans,
            })

        category_stats[cat]["score"] += score
        results.append({
            "id": item["id"],
            "score": score,
            "actual_type": actual_type,
            "actual_ans": actual_ans,
        })

    total_score = sum(r["score"] for r in results)
    total_correct = sum(1 for r in results if r["score"] > 0)
    total_abstain = sum(1 for r in results if r["score"] == 0)
    total_incorrect = sum(1 for r in results if r["score"] < 0)

    print("\n" + "="*80)
    print(f"BENCHMARK RESULTS: {total} Questions")
    print(f"Correct (+1): {total_correct} ({total_correct/total*100:.1f}%)")
    print(f"Abstain ( 0): {total_abstain} ({total_abstain/total*100:.1f}%)")
    print(f"Incorrect (-1): {total_incorrect} ({total_incorrect/total*100:.1f}%)")
    print(f"Total Penalized Score: {total_score:.1f} / {total} ({total_score/total*100:.1f}%)")
    print("="*80)

    print("\nCategory Breakdown:")
    print(f"{'Category':<30} | {'Total':<6} | {'Correct':<8} | {'Abstain':<8} | {'Incorrect':<10} | {'Score':<6}")
    print("-" * 80)
    for cat, stats in sorted(category_stats.items()):
        print(f"{cat:<30} | {stats['total']:<6} | {stats['correct']:<8} | {stats['abstain']:<8} | {stats['incorrect']:<10} | {stats['score']:<6.1f}")

    if mismatches:
        print("\n" + "="*80)
        print(f"Sample Mismatches (showing top {min(len(mismatches), 15)} of {len(mismatches)}):")
        for m in mismatches[:15]:
            print(f"- [{m['id']}] ({m['cat']}) Q: {m['q']}")
            print(f"    Expected: {m['exp_type']} -> {m['exp_ans']}")
            print(f"    Actual:   {m['act_type']} -> {m['act_ans']}")

    shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    run_benchmark()
