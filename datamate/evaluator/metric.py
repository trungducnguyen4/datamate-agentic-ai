from __future__ import annotations
import math
from typing import Any, Dict, List, Optional, Union
from datamate.core.types import AnswerType, EvaluationResult, SubmissionItem
from datamate.core.normalizer import normalize_string, match_string


def match_number(pred: Any, ref: Any) -> bool:
    """Exact match for numbers (integers or rounded to 2 decimals)."""
    try:
        p_val = float(pred)
        r_val = float(ref)
        if math.isnan(p_val) or math.isnan(r_val):
            return False
        return abs(round(p_val, 2) - round(r_val, 2)) < 1e-9
    except (ValueError, TypeError):
        return False


def match_percent(pred: Any, ref: Any) -> bool:
    """Exact match for percent after rounding to 2 decimals; sign must match."""
    try:
        p_val = float(pred)
        r_val = float(ref)
        if math.isnan(p_val) or math.isnan(r_val):
            return False
        return abs(round(p_val, 2) - round(r_val, 2)) < 1e-9
    except (ValueError, TypeError):
        return False


def match_date(pred: Any, ref: Any) -> bool:
    """Exact match for date (YYYY-MM-DD or YYYY-MM)."""
    p_str = str(pred).strip()
    r_str = str(ref).strip()
    return p_str == r_str


def match_boolean(pred: Any, ref: Any) -> bool:
    """Exact match for boolean."""
    if isinstance(pred, str):
        pred = pred.strip().lower() in ("true", "1", "yes")
    if isinstance(ref, str):
        ref = ref.strip().lower() in ("true", "1", "yes")
    return bool(pred) is bool(ref)


def match_element(pred: Any, ref: Any) -> bool:
    """Match an individual element (string or number)."""
    # Try number first
    if isinstance(ref, (int, float)) or (isinstance(ref, str) and ref.replace(".", "", 1).replace("-", "", 1).isdigit()):
        if match_number(pred, ref):
            return True
    # Fallback to string match
    if isinstance(ref, (list, tuple, set)):
        return match_string(str(pred), [str(x) for x in ref])
    return match_string(str(pred), str(ref))


def match_list(pred: Any, ref: Any) -> bool:
    """Ordered list match, position by position."""
    if not isinstance(pred, (list, tuple)) or not isinstance(ref, (list, tuple)):
        return False
    if len(pred) != len(ref):
        return False
    for p_elem, r_elem in zip(pred, ref):
        if not match_element(p_elem, r_elem):
            return False
    return True


def _string_forms(ref: Dict[str, Any]) -> List[str]:
    """Gom mọi dạng được chấp nhận của một đáp án string.

    BTC dùng khoá ``alias`` trong `answers.jsonl`; một số công cụ nội bộ dùng
    ``accepted_forms``. Hỗ trợ cả hai.
    """
    forms: List[str] = []
    answer = ref.get("answer")
    if answer is not None:
        forms.append(str(answer))

    alias = ref.get("alias")
    if isinstance(alias, list):
        for item in alias:
            if isinstance(item, list):
                forms.extend(str(x) for x in item)
            elif item is not None:
                forms.append(str(item))
    elif alias:
        forms.append(str(alias))

    accepted = ref.get("accepted_forms")
    if isinstance(accepted, list):
        forms.extend(str(x) for x in accepted)
    elif accepted:
        forms.append(str(accepted))

    # bỏ trùng, giữ thứ tự
    seen = set()
    unique = []
    for form in forms:
        if form not in seen:
            seen.add(form)
            unique.append(form)
    return unique


def _element_forms(ref_answer: List[Any], alias: Any, index: int) -> List[Any]:
    forms: List[Any] = []
    if index < len(ref_answer):
        forms.append(ref_answer[index])
    if isinstance(alias, list) and index < len(alias):
        item = alias[index]
        if isinstance(item, list):
            forms.extend(item)
        else:
            forms.append(item)
    return forms


def match_list_with_alias(pred: Any, ref: List[Any], alias: Any) -> bool:
    """List match có xét ``alias`` cho từng phần tử (BTC: alias là list-of-list)."""
    if not isinstance(pred, (list, tuple)) or not isinstance(ref, (list, tuple)):
        return False
    if len(pred) != len(ref):
        return False
    for index, (p_elem, r_elem) in enumerate(zip(pred, ref)):
        forms = _element_forms(list(ref), alias, index)
        if not any(match_element(p_elem, form) for form in forms):
            return False
    return True


def match_table(pred: Any, ref: Any) -> bool:
    """Match table according to DataMate specification:

    Columns matched by normalized name (or position if names don't match).
    Rows matched as a set.
    """
    if not isinstance(pred, dict) or not isinstance(ref, dict):
        return False
    pred_cols = pred.get("columns", [])
    ref_cols = ref.get("columns", [])
    pred_rows = pred.get("rows", [])
    ref_rows = ref.get("rows", [])

    if len(pred_rows) != len(ref_rows):
        return False
    if len(pred_cols) != len(ref_cols):
        return False

    # Check row counts 0
    if len(ref_rows) == 0:
        return True

    # Column mapping
    # Try matching normalized column names
    col_mapping = {}
    ref_norm_cols = [normalize_string(c) for c in ref_cols]
    pred_norm_cols = [normalize_string(c) for c in pred_cols]

    if set(ref_norm_cols) == set(pred_norm_cols) and len(ref_norm_cols) == len(set(ref_norm_cols)):
        for r_idx, r_name in enumerate(ref_norm_cols):
            p_idx = pred_norm_cols.index(r_name)
            col_mapping[p_idx] = r_idx
    else:
        # Fallback to position
        for i in range(len(ref_cols)):
            col_mapping[i] = i

    # Rows matched as a set
    matched_ref_indices = set()
    for p_row in pred_rows:
        row_found = False
        reordered_p_row = [None] * len(ref_cols)
        for p_idx, val in enumerate(p_row):
            if p_idx in col_mapping:
                reordered_p_row[col_mapping[p_idx]] = val

        for r_idx, r_row in enumerate(ref_rows):
            if r_idx in matched_ref_indices:
                continue
            # Compare reordered_p_row with r_row
            row_match = True
            for c_val, r_val in zip(reordered_p_row, r_row):
                if not match_element(c_val, r_val):
                    row_match = False
                    break
            if row_match:
                matched_ref_indices.add(r_idx)
                row_found = True
                break
        if not row_found:
            return False

    return len(matched_ref_indices) == len(ref_rows)


def evaluate_single_answer(
    pred: Union[SubmissionItem, Dict[str, Any]],
    ref: Dict[str, Any],
) -> EvaluationResult:
    """Evaluate a single prediction against ground truth reference.

    ref format:
    {
        "id": "...",
        "type": "number" | "string" | "unanswerable" | ...,
        "answer": ...,
        "accepted_forms": [...] # optional for string/entities
    }
    """
    if isinstance(pred, dict):
        pred_type = pred.get("type")
        pred_ans = pred.get("answer")
    else:
        pred_type = pred.type.value if hasattr(pred.type, "value") else str(pred.type)
        pred_ans = pred.answer

    ref_type = ref.get("type")
    ref_ans = ref.get("answer")

    # If reference expects abstain: theo đề, abstain luôn được tính là abstain
    # ("Scored as abstain regardless of the reference"), không phải correct/wrong.
    if ref_type == AnswerType.ABSTAIN.value:
        return EvaluationResult.ABSTAIN

    # Rule: type abstain or missing answer is an abstain (scores 0, avoids penalty)
    if pred_type == AnswerType.ABSTAIN.value or pred_type is None:
        return EvaluationResult.ABSTAIN

    # If question is unanswerable:
    if ref_type == AnswerType.UNANSWERABLE.value:
        if pred_type == AnswerType.UNANSWERABLE.value:
            return EvaluationResult.CORRECT
        return EvaluationResult.WRONG

    # Any other answer is correct only if its type equals reference type
    if pred_type != ref_type:
        return EvaluationResult.WRONG

    # Evaluate by type
    if ref_type == AnswerType.NUMBER.value:
        return EvaluationResult.CORRECT if match_number(pred_ans, ref_ans) else EvaluationResult.WRONG
    elif ref_type == AnswerType.PERCENT.value:
        return EvaluationResult.CORRECT if match_percent(pred_ans, ref_ans) else EvaluationResult.WRONG
    elif ref_type == AnswerType.STRING.value:
        forms = _string_forms(ref)
        if not forms:
            return EvaluationResult.WRONG
        return EvaluationResult.CORRECT if match_string(str(pred_ans), forms) else EvaluationResult.WRONG
    elif ref_type == AnswerType.DATE.value:
        return EvaluationResult.CORRECT if match_date(pred_ans, ref_ans) else EvaluationResult.WRONG
    elif ref_type == AnswerType.BOOLEAN.value:
        return EvaluationResult.CORRECT if match_boolean(pred_ans, ref_ans) else EvaluationResult.WRONG
    elif ref_type == AnswerType.LIST.value:
        if match_list_with_alias(pred_ans, ref_ans, ref.get("alias")):
            return EvaluationResult.CORRECT
        return EvaluationResult.CORRECT if match_list(pred_ans, ref_ans) else EvaluationResult.WRONG
    elif ref_type == AnswerType.TABLE.value:
        return EvaluationResult.CORRECT if match_table(pred_ans, ref_ans) else EvaluationResult.WRONG

    return EvaluationResult.WRONG


def compute_penalized_accuracy(
    predictions: List[Union[SubmissionItem, Dict[str, Any]]],
    references: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute Penalized Accuracy (PA) metric over N questions:

    PA = 1/N * sum(s_i)
    where:
      s_i = 1 for correct
      s_i = 0 for abstain
      s_i = -1 for wrong
    """
    ref_map = {r["id"]: r for r in references}
    pred_map = {p.id if hasattr(p, "id") else p["id"]: p for p in predictions}

    n_total = len(references)
    if n_total == 0:
        return {"pa": 0.0, "correct": 0, "abstain": 0, "wrong": 0, "total": 0}

    correct_count = 0
    abstain_count = 0
    wrong_count = 0
    total_score = 0

    for qid, ref in ref_map.items():
        pred = pred_map.get(qid)
        if pred is None:
            # Missing answer is an abstain
            res = EvaluationResult.ABSTAIN
        else:
            res = evaluate_single_answer(pred, ref)

        if res == EvaluationResult.CORRECT:
            correct_count += 1
            total_score += 1
        elif res == EvaluationResult.ABSTAIN:
            abstain_count += 1
            total_score += 0
        else:
            wrong_count += 1
            total_score -= 1

    pa = total_score / n_total

    return {
        "pa": round(pa, 5),
        "total": n_total,
        "correct": correct_count,
        "abstain": abstain_count,
        "wrong": wrong_count,
        "accuracy": round(correct_count / n_total, 4),
        "coverage": round((correct_count + wrong_count) / n_total, 4),
    }
