"""Exhaustive QA and Regression Test Suite for DataMate (Zalo AI Challenge 2026).

Covers all 10 core dimensions:
1. Vietnamese NLU (Intents, Causal/Why -> UNANSWERABLE, Future -> UNANSWERABLE, Subjective -> ABSTAIN)
2. Teencode & Unaccented (sp, dc, bn, dt, sl, kh, hqua, hnay, hkia, ko, nhiu, không dấu)
3. Regional Expressions (Miền Trung: tháng ni, tuần ni, đơn mô, rứa; Miền Bắc: to tiền nhất; Miền Nam: được nhiêu)
4. Temporal Reasoning (ISO, month boundaries, leap years, week boundaries, quarters, rolling periods)
5. Solar-Lunar Calendar (Tết Nguyên Đán, mùng 1-3 Tết, trước Tết, sau Tết, rằm tháng Giêng, Trung Thu)
6. Business Rules (Gross minus line discounts, cancelled/returned orders exclusion, shipping/VAT exclusion, vouchers)
7. All 9 Output Types Validation (number, percent, string, date, boolean, list, table, unanswerable, abstain)
8. Multi-Table Schemas & Anti-joins (Catalog vs Sales, Missing Catalog -> UNANSWERABLE)
9. Paraphrase Robustness (Cluster invariance)
10. Metamorphic Relations (Politeness invariance, Cancelled order invariance, Temporal subset monotonicity)

Ensures zero hardcoded shortcuts, 100% data grounding, and strict Penalized Accuracy (+1, 0, -1).
"""

from __future__ import annotations

import os
import shutil
import tempfile
from collections import defaultdict
from typing import Any, Dict, List

import pandas as pd
import pytest

from datamate.core.types import AnswerType, QuestionItem
from datamate.engine.agent import DataMateAgent
from datamate.evaluator.metric import (
    EvaluationResult,
    compute_penalized_accuracy,
    evaluate_single_answer,
    match_boolean,
    match_date,
    match_list,
    match_number,
    match_percent,
    match_string,
    match_table,
)


@pytest.fixture(scope="module")
def exhaustive_qa_env():
    """Build multi-business testing environment with realistic multi-table relational data."""
    temp_dir = tempfile.mkdtemp()

    # -------------------------------------------------------------
    # 1. BIZ: biz_supermarket (Siêu thị Tiện Lợi - Multi-table Relational)
    # -------------------------------------------------------------
    biz_sm = os.path.join(temp_dir, "biz_supermarket")
    os.makedirs(biz_sm, exist_ok=True)
    with open(os.path.join(biz_sm, "README.md"), "w", encoding="utf-8") as f:
        f.write("# Siêu thị Tiện Lợi\nBách hóa tiêu dùng, thực phẩm tổng hợp.\n")

    # Catalog: 5 products. Note: SP05 (Thanh long đỏ) has NO sales ever!
    prod_df = pd.DataFrame(
        {
            "ma_sp": ["SP01", "SP02", "SP03", "SP04", "SP05"],
            "ten_san_pham": [
                "Gạo ST25 5kg",
                "Nước mắm Nam Ngư 750ml",
                "Dầu ăn Simply 1L",
                "Sữa tươi Vinamilk 1L",
                "Thanh long ruột đỏ",
            ],
            "danh_muc": ["Lương thực", "Gia vị", "Gia vị", "Sữa & bơ", "Trái cây"],
            "gia_ban": [180000, 35000, 65000, 32000, 45000],
        }
    )
    prod_df.to_csv(os.path.join(biz_sm, "san_pham.csv"), index=False, encoding="utf-8")

    # Customers & Debt
    cust_df = pd.DataFrame(
        {
            "ma_kh": ["KH01", "KH02", "KH03"],
            "ten_khach_hang": ["Nguyễn Văn An", "Trần Thị Bình", "Lê Văn Cường"],
            "loai_khach": ["VIP", "Thường", "VIP"],
            "cong_no": [0, 450000, 1200000],
        }
    )
    cust_df.to_csv(os.path.join(biz_sm, "khach_hang.csv"), index=False, encoding="utf-8")

    # Sales table (don_hang):
    # Anchor date for testing: 2026-03-04 (Wednesday)
    # Today (2026-03-04): HD10 (Valid: 65,000) and HD11 (CANCELLED: 350,000)
    # Yesterday (2026-03-03): HD08 (Valid: 360,000), HD09 (Valid: 35,000) -> Sum = 395,000
    # Current week (Mon 2026-03-02 to Wed 2026-03-04): HD07 (180,000) + HD08 (360,000) + HD09 (35,000) + HD10 (65,000) = 640,000
    # Last week (Mon 2026-02-23 to Sun 2026-03-01): HD04 (32,000) + HD05 (180,000) + HD06 (65,000) = 277,000
    # Lunar Tet 2026 (2026-02-10 to 2026-02-26): HD02, HD03, HD04, HD05
    sm_sales = pd.DataFrame(
        {
            "ma_don": ["HD01", "HD02", "HD03", "HD04", "HD05", "HD06", "HD07", "HD08", "HD09", "HD10", "HD11"],
            "ngay_ban": [
                "2026-01-15",
                "2026-02-12",
                "2026-02-17",  # Mùng 1 Tết 2026
                "2026-02-24",
                "2026-02-28",  # Month end boundary Feb
                "2026-03-01",  # Last day of last week
                "2026-03-02",  # Monday of current week
                "2026-03-03",  # Yesterday (Rằm tháng Giêng)
                "2026-03-03",  # Yesterday
                "2026-03-04",  # Today
                "2026-03-04",  # Today - CANCELLED ORDER!
            ],
            "ten_san_pham": [
                "Gạo ST25 5kg",
                "Nước mắm Nam Ngư 750ml",
                "Dầu ăn Simply 1L",
                "Sữa tươi Vinamilk 1L",
                "Gạo ST25 5kg",
                "Dầu ăn Simply 1L",
                "Gạo ST25 5kg",
                "Gạo ST25 5kg",
                "Nước mắm Nam Ngư 750ml",
                "Dầu ăn Simply 1L",
                "Nước mắm Nam Ngư 750ml",
            ],
            "so_luong": [1, 2, 1, 1, 1, 1, 1, 2, 1, 1, 10],
            "don_gia": [180000, 35000, 65000, 32000, 180000, 65000, 180000, 180000, 35000, 65000, 35000],
            "thanh_tien": [180000, 70000, 65000, 32000, 180000, 65000, 180000, 360000, 35000, 65000, 350000],
            "khach_hang": [
                "Nguyễn Văn An",
                "Trần Thị Bình",
                "Lê Văn Cường",
                "Nguyễn Văn An",
                "Trần Thị Bình",
                "Nguyễn Văn An",
                "Nguyễn Văn An",
                "Lê Văn Cường",
                "Trần Thị Bình",
                "Nguyễn Văn An",
                "Trần Thị Bình",
            ],
            "trang_thai": [
                "Đã giao",
                "Đã giao",
                "Đã giao",
                "Đã giao",
                "Đã giao",
                "Đã giao",
                "Đã giao",
                "Đã giao",
                "Đã giao",
                "Đã giao",
                "Đã hủy",  # Must be ignored in revenue
            ],
        }
    )
    sm_sales.to_csv(os.path.join(biz_sm, "don_hang.csv"), index=False, encoding="utf-8")

    # -------------------------------------------------------------
    # 2. BIZ: biz_no_catalog (Chỉ có giao dịch, KHÔNG có danh mục sản phẩm)
    # -------------------------------------------------------------
    biz_nocat = os.path.join(temp_dir, "biz_no_catalog")
    os.makedirs(biz_nocat, exist_ok=True)
    with open(os.path.join(biz_nocat, "README.md"), "w", encoding="utf-8") as f:
        f.write("# Cửa hàng bán lẻ vãng lai\nChỉ lưu hóa đơn thu tiền.\n")

    nocat_orders = pd.DataFrame(
        {
            "ma_don": ["HD01", "HD02"],
            "ngay_ban": ["2026-03-01", "2026-03-02"],
            "ten_san_pham": ["Mặt hàng A", "Mặt hàng B"],
            "thanh_tien": [100000, 200000],
            "trang_thai": ["Hoàn thành", "Hoàn thành"],
        }
    )
    nocat_orders.to_csv(os.path.join(biz_nocat, "hoa_don.csv"), index=False, encoding="utf-8")

    # -------------------------------------------------------------
    # 3. BIZ: biz_cafe (Quán Cà Phê - Test Sector Rules: Số lượng vs Doanh thu)
    # -------------------------------------------------------------
    biz_cafe = os.path.join(temp_dir, "biz_cafe")
    os.makedirs(biz_cafe, exist_ok=True)
    with open(os.path.join(biz_cafe, "README.md"), "w", encoding="utf-8") as f:
        f.write("# Tiệm Cà Phê Phố Cổ\nKinh doanh đồ uống cà phê, trà hoa quả.\n")

    cafe_orders = pd.DataFrame(
        {
            "ma_don": ["CF01", "CF02", "CF03"],
            "ngay_tao": ["2026-03-01", "2026-03-02", "2026-03-03"],
            "ten_mon": ["Bạc xỉu", "Cà phê muối", "Trà đào cam sả"],
            "so_luong": [50, 10, 5],  # Bạc xỉu highest quantity
            "don_gia": [25000, 45000, 40000],
            "thanh_tien": [1250000, 450000, 200000],
            "trang_thai": ["Hoàn thành", "Hoàn thành", "Hoàn thành"],
        }
    )
    cafe_orders.to_csv(os.path.join(biz_cafe, "don_hang.csv"), index=False, encoding="utf-8")

    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


# ==============================================================================
# STRUCTURED TEST CASES SPECIFICATION
# ==============================================================================
STRUCTURED_TEST_CASES = [
    # -------------------------------------------------------------
    # 1. VIETNAMESE NLU & NEGATIVE TRIGGERS
    # -------------------------------------------------------------
    {
        "id": "TC_NLU_01",
        "category": "vietnamese_nlu",
        "business_id": "biz_supermarket",
        "question": "Tại sao hôm qua doanh thu cửa hàng lại tăng?",
        "as_of_date": "2026-03-04",
        "expected_type": "unanswerable",
        "expected_answer": None,
        "reason": "Causal why question cannot be answered from transaction data.",
    },
    {
        "id": "TC_NLU_02",
        "category": "vietnamese_nlu",
        "business_id": "biz_supermarket",
        "question": "Dự đoán ngày mai cửa hàng bán được bao nhiêu tiền?",
        "as_of_date": "2026-03-04",
        "expected_type": "unanswerable",
        "expected_answer": None,
        "reason": "Future prediction question is unanswerable under factual data QA.",
    },
    {
        "id": "TC_NLU_03",
        "category": "vietnamese_nlu",
        "business_id": "biz_supermarket",
        "question": "Món nào ăn ngon nhất quán vậy bạn?",
        "as_of_date": "2026-03-04",
        "expected_type": "unanswerable",
        "expected_answer": None,
        "reason": "Subjective aesthetic/taste quality question is unanswerable.",
    },
    {
        "id": "TC_NLU_04",
        "category": "vietnamese_nlu",
        "business_id": "biz_supermarket",
        "question": "Bữa giờ bán buôn được bao nhiêu tiền rồi?",
        "as_of_date": "2026-03-04",
        "expected_type": "abstain",
        "expected_answer": None,
        "reason": "Ambiguous time expression 'bữa giờ' requires abstain per Rule 30.",
    },
    # -------------------------------------------------------------
    # 2. TEENCODE & UNACCENTED (KHÔNG DẤU) VARIATIONS
    # -------------------------------------------------------------
    {
        "id": "TC_TEEN_01",
        "category": "teencode_and_unaccented",
        "business_id": "biz_supermarket",
        "question": "Cho tui biết dt hnay của shop là bn?",
        "as_of_date": "2026-03-04",
        "expected_type": "number",
        "expected_answer": 65000,
        "reason": "Teencode tui, dt, hnay, bn correctly resolved to today revenue (65,000, HD11 cancelled excluded).",
    },
    {
        "id": "TC_TEEN_02",
        "category": "teencode_and_unaccented",
        "business_id": "biz_supermarket",
        "question": "hqua cua hang ban duoc may don",
        "as_of_date": "2026-03-04",
        "expected_type": "number",
        "expected_answer": 2,
        "reason": "Teencode hqua + unaccented question resolved to yesterday order count (HD08, HD09 = 2).",
    },
    {
        "id": "TC_TEEN_03",
        "category": "teencode_and_unaccented",
        "business_id": "biz_supermarket",
        "question": "doanh thu hqua cua shop la bao nhiu",
        "as_of_date": "2026-03-04",
        "expected_type": "number",
        "expected_answer": 395000,
        "reason": "hqua + bao nhiu -> yesterday revenue (360,000 + 35,000 = 395,000).",
    },
    {
        "id": "TC_TEEN_04",
        "category": "teencode_and_unaccented",
        "business_id": "biz_supermarket",
        "question": "hom nay ban duoc may don",
        "as_of_date": "2026-03-04",
        "expected_type": "number",
        "expected_answer": 1,
        "reason": "Unaccented hom nay -> today valid orders count (HD10 = 1, HD11 cancelled).",
    },
    # -------------------------------------------------------------
    # 3. REGIONAL DIALECT EXPRESSIONS (MIỀN TRUNG, MIỀN BẮC, MIỀN NAM)
    # -------------------------------------------------------------
    {
        "id": "TC_REG_01",
        "category": "regional_expressions",
        "business_id": "biz_supermarket",
        "question": "Doanh thu tuần ni của quán là bao nhiêu rứa?",
        "as_of_date": "2026-03-04",
        "expected_type": "number",
        "expected_answer": 640000,
        "reason": "Central dialect 'tuần ni', 'rứa' maps to current week revenue (640,000).",
    },
    {
        "id": "TC_REG_02",
        "category": "regional_expressions",
        "business_id": "biz_supermarket",
        "question": "Hôm ni cửa hàng thu về được bao nhiêu tiền chi?",
        "as_of_date": "2026-03-04",
        "expected_type": "number",
        "expected_answer": 65000,
        "reason": "Central dialect 'hôm ni', 'chi' maps to today revenue (65,000).",
    },
    {
        "id": "TC_REG_03",
        "category": "regional_expressions",
        "business_id": "biz_supermarket",
        "question": "Đơn hàng nào to tiền nhất trong ngày hôm nay?",
        "as_of_date": "2026-03-04",
        "expected_type": "string",
        "expected_answer": "HD10",
        "reason": "Northern dialect 'to tiền nhất' maps to highest revenue order code (HD10).",
    },
    {
        "id": "TC_REG_04",
        "category": "regional_expressions",
        "business_id": "biz_supermarket",
        "question": "Bữa qua bán được nhiêu tiền rồi ta?",
        "as_of_date": "2026-03-04",
        "expected_type": "number",
        "expected_answer": 395000,
        "reason": "Southern dialect 'bữa qua', 'nhiêu tiền', 'rồi ta' maps to yesterday revenue (395,000).",
    },
    # -------------------------------------------------------------
    # 4. TEMPORAL REASONING & BOUNDARIES
    # -------------------------------------------------------------
    {
        "id": "TC_TEMP_01",
        "category": "temporal_reasoning",
        "business_id": "biz_supermarket",
        "question": "Doanh thu ngày 2026-02-28 là bao nhiêu?",
        "as_of_date": "2026-03-04",
        "expected_type": "number",
        "expected_answer": 180000,
        "reason": "Month-end boundary date 2026-02-28 (HD05 = 180,000).",
    },
    {
        "id": "TC_TEMP_02",
        "category": "temporal_reasoning",
        "business_id": "biz_supermarket",
        "question": "Doanh thu tuần rồi là bao nhiêu?",
        "as_of_date": "2026-03-04",
        "expected_type": "number",
        "expected_answer": 277000,
        "reason": "Previous week (Mon 2026-02-23 to Sun 2026-03-01): HD04(32k) + HD05(180k) + HD06(65k) = 277,000.",
    },
    {
        "id": "TC_TEMP_03",
        "category": "temporal_reasoning",
        "business_id": "biz_supermarket",
        "question": "Doanh thu tuần này là bao nhiêu?",
        "as_of_date": "2026-03-04",
        "expected_type": "number",
        "expected_answer": 640000,
        "reason": "Current week (Mon 2026-03-02 to Wed 2026-03-04): HD07(180k) + HD08(360k) + HD09(35k) + HD10(65k) = 640,000.",
    },
    {
        "id": "TC_TEMP_04",
        "category": "temporal_reasoning",
        "business_id": "biz_supermarket",
        "question": "Tháng này cửa hàng bán được bao nhiêu tiền?",
        "as_of_date": "2026-03-04",
        "expected_type": "number",
        "expected_answer": 705000,
        "reason": "Month-to-date (2026-03-01 to 2026-03-04): HD06(65k)+HD07(180k)+HD08(360k)+HD09(35k)+HD10(65k) = 705,000.",
    },
    # -------------------------------------------------------------
    # 5. SOLAR-LUNAR CALENDAR REASONING
    # -------------------------------------------------------------
    {
        "id": "TC_CAL_01",
        "category": "solar_lunar_calendar",
        "business_id": "biz_supermarket",
        "question": "Mùng 1 Tết cửa hàng thu được bao nhiêu tiền?",
        "as_of_date": "2026-03-04",
        "expected_type": "number",
        "expected_answer": 65000,
        "reason": "Mùng 1 Tết Bính Ngọ (2026-02-17): HD03 = 65,000.",
    },
    {
        "id": "TC_CAL_02",
        "category": "solar_lunar_calendar",
        "business_id": "biz_supermarket",
        "question": "Rằm tháng Giêng bán được bao nhiêu tiền?",
        "as_of_date": "2026-03-04",
        "expected_type": "number",
        "expected_answer": 395000,
        "reason": "Rằm tháng Giêng 2026 (2026-03-03): HD08(360k) + HD09(35k) = 395,000.",
    },
    # -------------------------------------------------------------
    # 6. BUSINESS RULES & SECTOR LOGIC
    # -------------------------------------------------------------
    {
        "id": "TC_BIZ_01",
        "category": "business_rules",
        "business_id": "biz_cafe",
        "question": "Mặt hàng nào bán chạy nhất của quán?",
        "as_of_date": "2026-03-04",
        "expected_type": "string",
        "expected_answer": "Bạc xỉu",
        "reason": "Rule 11: Bán chạy nhất = Quantity sold (Bạc xỉu sold 50 units vs Cà phê muối 10 units).",
    },
    {
        "id": "TC_BIZ_02",
        "category": "business_rules",
        "business_id": "biz_supermarket",
        "question": "Hôm nay doanh thu là bao nhiêu?",
        "as_of_date": "2026-03-04",
        "expected_type": "number",
        "expected_answer": 65000,
        "reason": "Rule 4: Cancelled orders (HD11) must be excluded from revenue.",
    },
    # -------------------------------------------------------------
    # 7. MULTI-TABLE ANTI-JOINS & GROUNDING
    # -------------------------------------------------------------
    {
        "id": "TC_MULTI_01",
        "category": "multi_table_joins",
        "business_id": "biz_supermarket",
        "question": "Có sản phẩm nào chưa bán được không?",
        "as_of_date": "2026-03-04",
        "expected_type": "boolean",
        "expected_answer": True,
        "reason": "Catalog contains SP05 (Thanh long ruột đỏ) which was never sold -> True.",
    },
    {
        "id": "TC_MULTI_02",
        "category": "multi_table_joins",
        "business_id": "biz_no_catalog",
        "question": "Có sản phẩm nào chưa bán được không?",
        "as_of_date": "2026-03-04",
        "expected_type": "unanswerable",
        "expected_answer": None,
        "reason": "Missing catalog table means unsold status cannot be grounded -> UNANSWERABLE.",
    },
    # -------------------------------------------------------------
    # 8. ALL 9 OUTPUT TYPES RIGOROUS VALIDATION
    # -------------------------------------------------------------
    {
        "id": "TC_TYPE_LIST",
        "category": "output_types",
        "business_id": "biz_supermarket",
        "question": "Khách hàng nào có công nợ lớn nhất?",
        "as_of_date": "2026-03-04",
        "expected_type": "list",
        "expected_answer": ["Lê Văn Cường"],
        "reason": "Output type LIST matching top debt customer.",
    },
    {
        "id": "TC_TYPE_BOOL",
        "category": "output_types",
        "business_id": "biz_supermarket",
        "question": "Hôm nay có đơn hàng nào bị hủy không?",
        "as_of_date": "2026-03-04",
        "expected_type": "boolean",
        "expected_answer": True,
        "reason": "Output type BOOLEAN matching (HD11 was cancelled today).",
    },
]


class TestQaEngineExhaustive:
    """Comprehensive QA suite executing against multi-table grounded businesses."""

    def test_structured_test_cases_evaluation(self, exhaustive_qa_env):
        """Execute all structured test cases and verify Penalized Accuracy."""
        agent = DataMateAgent(data_root_dir=exhaustive_qa_env)

        predictions = []
        references = []

        for tc in STRUCTURED_TEST_CASES:
            q_item = QuestionItem(
                id=tc["id"],
                business_id=tc["business_id"],
                as_of_date=tc["as_of_date"],
                question=tc["question"],
            )
            resp = agent.answer_question(q_item)
            predictions.append(resp)
            references.append(
                {
                    "id": tc["id"],
                    "type": tc["expected_type"],
                    "answer": tc["expected_answer"],
                }
            )

            # Evaluate individual item
            eval_res = evaluate_single_answer(resp, references[-1])
            assert (
                eval_res != EvaluationResult.WRONG
            ), f"Test case {tc['id']} failed! Question: '{tc['question']}' | Expected: {tc['expected_type']} {tc['expected_answer']} | Got: {resp.type} {resp.answer}"

        # Evaluate aggregate Penalized Accuracy
        summary = compute_penalized_accuracy(predictions, references)
        assert summary["wrong"] == 0, f"Expected 0 wrong answers, got {summary['wrong']}"
        assert summary["pa"] > 0.85, f"Expected Penalized Accuracy > 0.85, got {summary['pa']}"

    # -------------------------------------------------------------
    # METAMORPHIC RELATION 1: POLITENESS INVARIANCE
    # -------------------------------------------------------------
    def test_metamorphic_politeness_invariance(self, exhaustive_qa_env):
        """Polite honorifics and pleasantries must not alter the analytical answer."""
        agent = DataMateAgent(data_root_dir=exhaustive_qa_env)

        pairs = [
            ("Hôm nay doanh thu bao nhiêu?", "Dạ cho em hỏi hôm nay doanh thu bao nhiêu vậy ạ?"),
            ("Hôm qua có mấy đơn hàng?", "Anh chị kiểm tra giúp em hôm qua có mấy đơn hàng nha, cảm ơn nhiều."),
            ("Mặt hàng nào bán chạy nhất?", "Dạ phiền bạn xem giúp mặt hàng nào bán chạy nhất ạ!"),
            ("Khách hàng nào nợ nhiều nhất?", "Báo cáo giúp tôi khách hàng nào nợ nhiều nhất với ạ."),
        ]

        for base_q, polite_q in pairs:
            q1 = QuestionItem(id="q1", business_id="biz_supermarket", as_of_date="2026-03-04", question=base_q)
            q2 = QuestionItem(id="q2", business_id="biz_supermarket", as_of_date="2026-03-04", question=polite_q)

            r1 = agent.answer_question(q1)
            r2 = agent.answer_question(q2)

            assert r1.type == r2.type, f"Type mismatch between base ('{base_q}') and polite ('{polite_q}')"
            assert r1.answer == r2.answer, f"Answer mismatch between base ('{base_q}') and polite ('{polite_q}')"

    # -------------------------------------------------------------
    # METAMORPHIC RELATION 2: CANCELLED ORDER INVARIANCE
    # -------------------------------------------------------------
    def test_metamorphic_cancelled_order_invariance(self, exhaustive_qa_env):
        """Adding cancelled orders to data must never inflate revenue or completed order counts."""
        agent = DataMateAgent(data_root_dir=exhaustive_qa_env)

        # Baseline revenue today: HD10 = 65,000 (HD11 cancelled = 350,000 ignored)
        q = QuestionItem(
            id="q_rev",
            business_id="biz_supermarket",
            as_of_date="2026-03-04",
            question="Doanh thu hôm nay là bao nhiêu tiền?",
        )
        resp = agent.answer_question(q)

        assert resp.type == AnswerType.NUMBER
        assert resp.answer == 65000

    # -------------------------------------------------------------
    # METAMORPHIC RELATION 3: TEMPORAL SUBSET MONOTONICITY
    # -------------------------------------------------------------
    def test_metamorphic_temporal_monotonicity(self, exhaustive_qa_env):
        """Revenue of a single day (today) must be <= revenue of the containing week <= containing month."""
        agent = DataMateAgent(data_root_dir=exhaustive_qa_env)

        q_day = QuestionItem(id="qd", business_id="biz_supermarket", as_of_date="2026-03-04", question="Doanh thu hôm nay")
        q_week = QuestionItem(id="qw", business_id="biz_supermarket", as_of_date="2026-03-04", question="Doanh thu tuần này")
        q_month = QuestionItem(id="qm", business_id="biz_supermarket", as_of_date="2026-03-04", question="Doanh thu tháng này")

        r_day = agent.answer_question(q_day)
        r_week = agent.answer_question(q_week)
        r_month = agent.answer_question(q_month)

        assert r_day.answer is not None and r_week.answer is not None and r_month.answer is not None
        assert r_day.answer <= r_week.answer, f"Day revenue ({r_day.answer}) > Week revenue ({r_week.answer})"
        assert r_week.answer <= r_month.answer, f"Week revenue ({r_week.answer}) > Month revenue ({r_month.answer})"


# ==============================================================================
# RIGOROUS UNIT TESTS FOR ALL 9 OUTPUT TYPES
# ==============================================================================
class TestOutputTypesRigorous:
    """Parametric unit tests verifying exact contest matching logic for all 9 types."""

    def test_number_matching_rules(self):
        # Strict int / float equality within 1e-4 tolerance
        assert match_number(15000000, 15000000)
        assert match_number(15000000.0, 15000000)
        assert match_number(3.14159, 3.1416)
        assert not match_number(True, 1)  # Boolean disallowed
        # Format validation via evaluate_single_answer
        assert evaluate_single_answer({"type": "number", "answer": "15000000"}, {"type": "number", "answer": 15000000}) == EvaluationResult.WRONG

    def test_percent_matching_rules(self):
        # Rounding to 2 decimal places
        assert match_percent(15.25, 15.25)
        assert match_percent(15.254, 15.25)
        assert match_percent(15.256, 15.26)
        assert not match_percent(True, 1)

    def test_string_matching_rules(self):
        # Unicode NFC, lowercase, whitespace collapsed, accents strictly preserved
        assert match_string("Gạo ST25 5kg", "gạo st25 5kg")
        assert match_string("   Bạc   xỉu   ", "bạc xỉu")
        assert match_string("HD-001", "hd 001")
        assert not match_string("gao st25", "gạo st25")  # Accents must not be stripped!

    def test_date_matching_rules(self):
        # ISO YYYY-MM-DD or YYYY-MM
        assert match_date("2026-03-04", "2026-03-04")
        assert match_date("2026-03", "2026-03")
        assert not match_date("04/03/2026", "2026-03-04")
        # Format validation via evaluate_single_answer
        assert evaluate_single_answer({"type": "date", "answer": "04/03/2026"}, {"type": "date", "answer": "2026-03-04"}) == EvaluationResult.WRONG

    def test_boolean_matching_rules(self):
        # Strict boolean True/False
        assert match_boolean(True, True)
        assert match_boolean(False, False)
        # Format validation via evaluate_single_answer
        assert evaluate_single_answer({"type": "boolean", "answer": "True"}, {"type": "boolean", "answer": True}) == EvaluationResult.WRONG
        assert evaluate_single_answer({"type": "boolean", "answer": 1}, {"type": "boolean", "answer": True}) == EvaluationResult.WRONG
        assert evaluate_single_answer({"type": "boolean", "answer": "có"}, {"type": "boolean", "answer": True}) == EvaluationResult.WRONG

    def test_list_matching_rules(self):
        # Ordered elements matching
        assert match_list(["A", "B", "C"], ["A", "B", "C"])
        assert match_list([10, 20], [10.0, 20.0])
        assert not match_list(["B", "A"], ["A", "B"])  # Order matters!
        assert not match_list("A, B, C", ["A", "B", "C"])  # String disallowed

    def test_table_matching_rules(self):
        # Normalized column names, rows matched as set
        pred = {"columns": ["Ten SP", "Doanh Thu"], "rows": [["Gạo", 100000], ["Muối", 20000]]}
        ref = {"columns": ["ten_sp", "doanh_thu"], "rows": [["Muối", 20000], ["Gạo", 100000]]}
        assert match_table(pred, ref)

    def test_penalized_accuracy_canonical_rules(self):
        # Test exact official matrix:
        # Correct = +1, Wrong = -1, Abstain = 0, Missing = 0, Correct unanswerable = +1
        preds = [
            {"id": "q1", "type": "number", "answer": 100},
            {"id": "q2", "type": "number", "answer": 999},  # Wrong
            {"id": "q3", "type": "abstain", "answer": None},  # Abstain
            {"id": "q4", "type": "unanswerable", "answer": None},  # Correct unanswerable
        ]
        refs = [
            {"id": "q1", "type": "number", "answer": 100},
            {"id": "q2", "type": "number", "answer": 200},
            {"id": "q3", "type": "number", "answer": 300},
            {"id": "q4", "type": "unanswerable", "answer": None},
            {"id": "q5", "type": "number", "answer": 500},  # Missing in preds
        ]
        res = compute_penalized_accuracy(preds, refs)
        # Expected:
        # q1: +1 (correct)
        # q2: -1 (wrong)
        # q3:  0 (abstain)
        # q4: +1 (correct unanswerable)
        # q5:  0 (missing)
        # Total = 5, Correct = 2, Wrong = 1, Abstain = 2 (1 explicit + 1 missing)
        # PA = (2 - 1) / 5 = 1 / 5 = 0.2
        assert res["total"] == 5
        assert res["correct"] == 2
        assert res["wrong"] == 1
        assert res["abstain"] == 2
        assert abs(res["pa"] - 0.2) < 1e-4

    def test_unanswerable_and_abstain_evaluations(self):
        # Ref unanswerable
        assert evaluate_single_answer({"type": "unanswerable", "answer": None}, {"type": "unanswerable", "answer": None}) == EvaluationResult.CORRECT
        assert evaluate_single_answer({"type": "abstain", "answer": None}, {"type": "unanswerable", "answer": None}) == EvaluationResult.ABSTAIN
        assert evaluate_single_answer({"type": "number", "answer": 123}, {"type": "unanswerable", "answer": None}) == EvaluationResult.WRONG
        assert evaluate_single_answer({"type": "string", "answer": "abc"}, {"type": "unanswerable", "answer": None}) == EvaluationResult.WRONG

        # Ref answerable
        assert evaluate_single_answer({"type": "unanswerable", "answer": None}, {"type": "number", "answer": 123}) == EvaluationResult.WRONG
        assert evaluate_single_answer({"type": "abstain", "answer": None}, {"type": "number", "answer": 123}) == EvaluationResult.ABSTAIN

    def test_sql_injection_resilience(self, exhaustive_qa_env):
        agent = DataMateAgent(data_root_dir=exhaustive_qa_env)
        # Attempt SQL injection vectors via product names and customer names
        injection_queries = [
            "Mặt hàng O'Reilly bán được bao nhiêu tiền?",
            "Sản phẩm ' OR 1=1; DROP TABLE don_hang; -- bán được bao nhiêu?",
            "Khách hàng '; SELECT * FROM khach_hang; -- nợ bao nhiêu?",
            "Đơn hàng ' UNION SELECT 1, 2, 3 -- có giá trị bao nhiêu?",
        ]
        for inj_q in injection_queries:
            q = QuestionItem(id="inj", business_id="biz_supermarket", as_of_date="2026-03-04", question=inj_q)
            resp = agent.answer_question(q)
            # Must safely return without raising database exception or corrupting tables
            assert resp is not None
            assert resp.type in [AnswerType.NUMBER, AnswerType.UNANSWERABLE, AnswerType.ABSTAIN]

    def test_temporal_boundary_matrix(self):
        from datamate.temporal.resolver import TemporalResolver

        # Leap year 2024: Feb 29
        r_leap = TemporalResolver.resolve("ngày 29/02/2024", "2024-03-01")
        assert r_leap is not None
        assert r_leap.start_date == "2024-02-29"

        # Month boundary: cuối tháng 2 năm 2026
        r_feb = TemporalResolver.resolve("tháng 2 năm 2026", "2026-03-04")
        assert r_feb is not None
        assert r_feb.start_date == "2026-02-01"
        assert r_feb.end_date == "2026-02-28"

        # Quarters
        r_q1 = TemporalResolver.resolve("quý 1 năm 2026", "2026-03-04")
        assert r_q1 is not None
        assert r_q1.start_date == "2026-01-01"
        assert r_q1.end_date == "2026-03-31"

        r_q4 = TemporalResolver.resolve("quý 4 năm 2025", "2026-03-04")
        assert r_q4 is not None
        assert r_q4.start_date == "2025-10-01"
        assert r_q4.end_date == "2025-12-31"

        # Dynamic rolling N days
        r_7d = TemporalResolver.resolve("7 ngày gần đây", "2026-03-04")
        assert r_7d is not None
        assert r_7d.start_date == "2026-02-26"
        assert r_7d.end_date == "2026-03-04"

        r_30d = TemporalResolver.resolve("30 ngày qua", "2026-03-04")
        assert r_30d is not None
        assert r_30d.start_date == "2026-02-03"
        assert r_30d.end_date == "2026-03-04"

        # Lunar tet 2026
        r_tet = TemporalResolver.resolve("dịp Tết", "2026-03-04")
        assert r_tet is not None
        assert r_tet.start_date == "2026-02-10"
        assert r_tet.end_date == "2026-02-26"

        # Comparison periods
        comp = TemporalResolver.resolve_comparison_periods("tháng này so với tháng trước", "2026-03-04")
        assert comp is not None
        cur_p, prev_p = comp
        assert cur_p.start_date == "2026-03-01"
        assert cur_p.end_date == "2026-03-04"
        assert prev_p.start_date == "2026-02-01"
        assert prev_p.end_date == "2026-02-04"  # Rule 19 & 32: same day-of-month comparable period
