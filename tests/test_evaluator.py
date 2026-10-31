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

    # Wrong type
    pred_type = {"id": "q1", "type": "string", "answer": "1250000"}
    assert evaluate_single_answer(pred_type, ref) == EvaluationResult.WRONG


def test_evaluate_single_percent():
    ref = {"id": "q2", "type": "percent", "answer": -12.45}
    pred_correct = {"id": "q2", "type": "percent", "answer": -12.451}
    pred_wrong_sign = {"id": "q2", "type": "percent", "answer": 12.45}
    
    assert evaluate_single_answer(pred_correct, ref) == EvaluationResult.CORRECT
    assert evaluate_single_answer(pred_wrong_sign, ref) == EvaluationResult.WRONG


def test_evaluate_single_string_with_aliases():
    ref = {
        "id": "q3",
        "type": "string",
        "answer": "Xi măng Hà Tiên PCB40 bao 50kg",
        "accepted_forms": ["xm_hatien_50kg", "Xi măng Hà Tiên PCB40"]
    }
    pred1 = {"id": "q3", "type": "string", "answer": "xi măng hà tiên pcb40 bao 50kg"}
    pred2 = {"id": "q3", "type": "string", "answer": "XM_HATIEN_50KG"}
    pred_wrong = {"id": "q3", "type": "string", "answer": "Xi măng Nghi Sơn"}

    assert evaluate_single_answer(pred1, ref) == EvaluationResult.CORRECT
    assert evaluate_single_answer(pred2, ref) == EvaluationResult.CORRECT
    assert evaluate_single_answer(pred_wrong, ref) == EvaluationResult.WRONG


def test_evaluate_unanswerable_and_abstain():
    ref_unans = {"id": "q4", "type": "unanswerable", "answer": None}
    ref_normal = {"id": "q5", "type": "number", "answer": 100}

    # Correctly answered unanswerable
    assert evaluate_single_answer({"id": "q4", "type": "unanswerable"}, ref_unans) == EvaluationResult.CORRECT
    # Wrongly answered an unanswerable question
    assert evaluate_single_answer({"id": "q4", "type": "number", "answer": 10}, ref_unans) == EvaluationResult.WRONG

    # Abstain is always abstain regardless of reference
    assert evaluate_single_answer({"id": "q4", "type": "abstain"}, ref_unans) == EvaluationResult.ABSTAIN
    assert evaluate_single_answer({"id": "q5", "type": "abstain"}, ref_normal) == EvaluationResult.ABSTAIN


def test_compute_penalized_accuracy():
    refs = [
        {"id": "q1", "type": "number", "answer": 10},      # Correct (+1)
        {"id": "q2", "type": "number", "answer": 20},      # Abstain (0)
        {"id": "q3", "type": "number", "answer": 30},      # Wrong (-1)
        {"id": "q4", "type": "string", "answer": "sữa"},   # Correct (+1)
    ]
    preds = [
        {"id": "q1", "type": "number", "answer": 10},
        {"id": "q2", "type": "abstain"},
        {"id": "q3", "type": "number", "answer": 999},
        {"id": "q4", "type": "string", "answer": "Sữa"},
    ]
    # Total score = 1 + 0 - 1 + 1 = 1. Total questions = 4. PA = 1 / 4 = 0.25
    metrics = compute_penalized_accuracy(preds, refs)
    assert metrics["pa"] == 0.25
    assert metrics["correct"] == 2
    assert metrics["abstain"] == 1
    assert metrics["wrong"] == 1
