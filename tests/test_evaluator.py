import pytest
from datamate.core.types import AnswerType, SubmissionItem
from datamate.evaluator.metric import (
    evaluate_single_answer,
    compute_penalized_accuracy,
    EvaluationResult,
)


def test_evaluate_single_number():
    ref = {"id": "q1", "type": "number", "answer": 1250000}
    
    # Exact match
    pred_correct = {"id": "q1", "type": "number", "answer": 1250000}
    assert evaluate_single_answer(pred_correct, ref) == EvaluationResult.CORRECT

    # Rounding 2 decimals
    pred_round = {"id": "q1", "type": "number", "answer": 1250000.001}
    assert evaluate_single_answer(pred_round, ref) == EvaluationResult.CORRECT

    # Wrong number
    pred_wrong = {"id": "q1", "type": "number", "answer": 1250001}
    assert evaluate_single_answer(pred_wrong, ref) == EvaluationResult.WRONG

    # Format check: String representation is WRONG per Rule 9
    pred_str_num = {"id": "q1", "type": "number", "answer": "1250000"}
    assert evaluate_single_answer(pred_str_num, ref) == EvaluationResult.WRONG

    # Format check: Boolean is not a valid number
    pred_bool_num = {"id": "q1", "type": "number", "answer": True}
    assert evaluate_single_answer(pred_bool_num, ref) == EvaluationResult.WRONG

    # Wrong type
    pred_type = {"id": "q1", "type": "string", "answer": "1250000"}
    assert evaluate_single_answer(pred_type, ref) == EvaluationResult.WRONG


def test_evaluate_single_percent():
    ref = {"id": "q2", "type": "percent", "answer": -12.45}
    pred_correct = {"id": "q2", "type": "percent", "answer": -12.451}
    pred_wrong_sign = {"id": "q2", "type": "percent", "answer": 12.45}
    pred_str = {"id": "q2", "type": "percent", "answer": "-12.45"}
    
    assert evaluate_single_answer(pred_correct, ref) == EvaluationResult.CORRECT
    assert evaluate_single_answer(pred_wrong_sign, ref) == EvaluationResult.WRONG
    assert evaluate_single_answer(pred_str, ref) == EvaluationResult.WRONG


def test_evaluate_single_boolean():
    ref_true = {"id": "qb1", "type": "boolean", "answer": True}
    ref_false = {"id": "qb2", "type": "boolean", "answer": False}

    assert evaluate_single_answer({"id": "qb1", "type": "boolean", "answer": True}, ref_true) == EvaluationResult.CORRECT
    assert evaluate_single_answer({"id": "qb1", "type": "boolean", "answer": False}, ref_true) == EvaluationResult.WRONG
    assert evaluate_single_answer({"id": "qb2", "type": "boolean", "answer": False}, ref_false) == EvaluationResult.CORRECT

    # Format check: integers (1/0) or strings ("true"/"có") are invalid per Rule 9
    assert evaluate_single_answer({"id": "qb1", "type": "boolean", "answer": 1}, ref_true) == EvaluationResult.WRONG
    assert evaluate_single_answer({"id": "qb1", "type": "boolean", "answer": "true"}, ref_true) == EvaluationResult.WRONG
    assert evaluate_single_answer({"id": "qb1", "type": "boolean", "answer": "có"}, ref_true) == EvaluationResult.WRONG


def test_evaluate_single_date():
    ref_day = {"id": "qd1", "type": "date", "answer": "2026-03-04"}
    ref_month = {"id": "qd2", "type": "date", "answer": "2026-03"}

    assert evaluate_single_answer({"id": "qd1", "type": "date", "answer": "2026-03-04"}, ref_day) == EvaluationResult.CORRECT
    assert evaluate_single_answer({"id": "qd2", "type": "date", "answer": "2026-03"}, ref_month) == EvaluationResult.CORRECT

    # Non-ISO format is WRONG per Rule 9
    assert evaluate_single_answer({"id": "qd1", "type": "date", "answer": "04/03/2026"}, ref_day) == EvaluationResult.WRONG
    assert evaluate_single_answer({"id": "qd2", "type": "date", "answer": "tháng 3/2026"}, ref_month) == EvaluationResult.WRONG


def test_evaluate_single_string_with_aliases():
    ref = {
        "id": "q3",
        "type": "string",
        "answer": "Xi măng Hà Tiên PCB40 bao 50kg",
        "accepted_forms": ["xm_hatien_50kg", "Xi măng Hà Tiên PCB40"],
        "alias": ["SP0001"],
    }
    pred1 = {"id": "q3", "type": "string", "answer": "xi măng hà tiên pcb40 bao 50kg"}
    pred2 = {"id": "q3", "type": "string", "answer": "XM_HATIEN_50KG"}
    pred3 = {"id": "q3", "type": "string", "answer": "sp0001"}
    pred_wrong = {"id": "q3", "type": "string", "answer": "Xi măng Nghi Sơn"}

    assert evaluate_single_answer(pred1, ref) == EvaluationResult.CORRECT
    assert evaluate_single_answer(pred2, ref) == EvaluationResult.CORRECT
    assert evaluate_single_answer(pred3, ref) == EvaluationResult.CORRECT
    assert evaluate_single_answer(pred_wrong, ref) == EvaluationResult.WRONG

    # Format check: List is WRONG for string type
    assert evaluate_single_answer({"id": "q3", "type": "string", "answer": ["SP0001"]}, ref) == EvaluationResult.WRONG


def test_evaluate_unanswerable_and_abstain_matrix():
    ref_unans = {"id": "q4", "type": "unanswerable", "answer": None}
    ref_normal = {"id": "q5", "type": "number", "answer": 100}
    ref_abstain = {"id": "q6", "type": "abstain", "answer": None}

    # 1. Correct unanswerable -> +1 (CORRECT)
    assert evaluate_single_answer({"id": "q4", "type": "unanswerable"}, ref_unans) == EvaluationResult.CORRECT

    # 2. Answering an unanswerable question -> -1 (WRONG)
    assert evaluate_single_answer({"id": "q4", "type": "number", "answer": 10}, ref_unans) == EvaluationResult.WRONG
    assert evaluate_single_answer({"id": "q4", "type": "string", "answer": "có"}, ref_unans) == EvaluationResult.WRONG

    # 3. Unanswerable prediction on an answerable question -> -1 (WRONG)
    assert evaluate_single_answer({"id": "q5", "type": "unanswerable"}, ref_normal) == EvaluationResult.WRONG

    # 4. Abstaining on an unanswerable question -> 0 (ABSTAIN, not correct)
    assert evaluate_single_answer({"id": "q4", "type": "abstain"}, ref_unans) == EvaluationResult.ABSTAIN

    # 5. Abstaining on a normal question -> 0 (ABSTAIN)
    assert evaluate_single_answer({"id": "q5", "type": "abstain"}, ref_normal) == EvaluationResult.ABSTAIN

    # 6. Reference expects abstain -> always ABSTAIN
    assert evaluate_single_answer({"id": "q6", "type": "number", "answer": 100}, ref_abstain) == EvaluationResult.ABSTAIN
    assert evaluate_single_answer({"id": "q6", "type": "abstain"}, ref_abstain) == EvaluationResult.ABSTAIN


def test_compute_penalized_accuracy_all_cases():
    refs = [
        {"id": "q1", "type": "number", "answer": 10},           # Correct (+1)
        {"id": "q2", "type": "number", "answer": 20},           # Abstain (0)
        {"id": "q3", "type": "number", "answer": 30},           # Wrong (-1)
        {"id": "q4", "type": "string", "answer": "sữa"},        # Correct (+1)
        {"id": "q5", "type": "unanswerable", "answer": None},   # Correct Unanswerable (+1)
        {"id": "q6", "type": "unanswerable", "answer": None},   # Wrong answer on unanswerable (-1)
        {"id": "q7", "type": "unanswerable", "answer": None},   # Abstain on unanswerable (0)
        {"id": "q8", "type": "number", "answer": 50},           # Missing answer -> Abstain (0)
    ]
    preds = [
        {"id": "q1", "type": "number", "answer": 10},
        {"id": "q2", "type": "abstain"},
        {"id": "q3", "type": "number", "answer": 999},
        {"id": "q4", "type": "string", "answer": "Sữa"},
        {"id": "q5", "type": "unanswerable"},
        {"id": "q6", "type": "number", "answer": 42},
        {"id": "q7", "type": "abstain"},
        # q8 is missing from preds!
        {"id": "q1", "type": "number", "answer": 999},          # Duplicate of q1 (should be ignored)
        {"id": "q_extra", "type": "number", "answer": 123},     # Extra prediction not in refs
    ]
    # Total score = (+1) + (0) + (-1) + (+1) + (+1) + (-1) + (0) + (0) = 1
    # Total questions = 8
    # PA = 1 / 8 = 0.125
    metrics = compute_penalized_accuracy(preds, refs)
    assert metrics["total"] == 8
    assert metrics["correct"] == 3
    assert metrics["wrong"] == 2
    assert metrics["abstain"] == 3
    assert metrics["pa"] == 0.125
    assert metrics["duplicate_count"] == 1
    assert metrics["extra_count"] == 1
