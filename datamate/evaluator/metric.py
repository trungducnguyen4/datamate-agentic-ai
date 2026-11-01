from __future__ import annotations
import math
import re
from typing import Any, Dict, List, Optional, Set, Union
from datamate.core.types import AnswerType, EvaluationResult, SubmissionItem
from datamate.core.normalizer import normalize_string, match_string


def match_number(pred: Any, ref: Any) -> bool:
    """Exact match for numbers (integers or rounded to 2 decimals).

    Per Rule 9:
    - Number format must be JSON number.
    - Money is integer VND.
    - Floats rounded to 2 decimal places.
    - Ignore floating point precision differences.
    """
    if isinstance(pred, bool) or isinstance(ref, bool):
        return False
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
    if isinstance(pred, bool) or isinstance(ref, bool):
        return False
    try:
        p_val = float(pred)
        r_val = float(ref)
        if math.isnan(p_val) or math.isnan(r_val):
            return False
        # Sign check
        if (p_val < -1e-9 and r_val > 1e-9) or (p_val > 1e-9 and r_val < -1e-9):
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
    if isinstance(pred, bool) and isinstance(ref, bool):
        return pred is ref
    if isinstance(pred, str):
        pred = pred.strip().lower() in ("true", "1", "yes")
    if isinstance(ref, str):
        ref = ref.strip().lower() in ("true", "1", "yes")
    return bool(pred) is bool(ref)


def match_element(pred: Any, ref: Any) -> bool:
    """Match an individual element (string or number)."""
    if isinstance(ref, bool) or isinstance(pred, bool):
        return bool(pred) is bool(ref)
    # Try number match
    if isinstance(ref, (int, float)):
        if isinstance(pred, (int, float)):
            return match_number(pred, ref)
        elif isinstance(pred, str) and pred.replace(".", "", 1).replace("-", "", 1).isdigit():
            return match_number(pred, ref)
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
    """Collect all accepted forms for a string answer (answer, alias, accepted_forms)."""
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

    # Deduplicate while preserving order
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
    """List match considering per-element alias (BTC alias is list-of-lists)."""
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

    if len(ref_rows) == 0:
        return True

    # Column mapping: try matching normalized column names
    col_mapping = {}
    ref_norm_cols = [normalize_string(c) for c in ref_cols]
    pred_norm_cols = [normalize_string(c) for c in pred_cols]

    if set(ref_norm_cols) == set(pred_norm_cols) and len(ref_norm_cols) == len(set(ref_norm_cols)):
        for r_idx, r_name in enumerate(ref_norm_cols):
            p_idx = pred_norm_cols.index(r_name)
            col_mapping[p_idx] = r_idx
    else:
        for i in range(len(ref_cols)):
            col_mapping[i] = i

    matched_ref_indices: Set[int] = set()
    for p_row in pred_rows:
        row_found = False
        reordered_p_row = [None] * len(ref_cols)
        for p_idx, val in enumerate(p_row):
            if p_idx in col_mapping:
                reordered_p_row[col_mapping[p_idx]] = val

        for r_idx, r_row in enumerate(ref_rows):
            if r_idx in matched_ref_indices:
                continue
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


def _normalize_type_str(t: Any) -> Optional[str]:
    if t is None:
        return None
    if hasattr(t, "value"):
        t = t.value
    return str(t).strip().lower()


def evaluate_single_answer(
    pred: Union[SubmissionItem, Dict[str, Any]],
    ref: Dict[str, Any],
) -> EvaluationResult:
    """Evaluate a single prediction against ground truth reference.

    Implements official scoring rules of Zalo AI Challenge 2026:
    - Abstain prediction (or missing) -> ABSTAIN (0 points)
    - If reference expects abstain -> ABSTAIN (0 points)
    - If reference is unanswerable:
        - pred unanswerable -> CORRECT (+1 point)
        - pred abstain -> ABSTAIN (0 points)
        - pred answers anything -> WRONG (-1 point)
    - If question is answerable:
        - pred unanswerable -> WRONG (-1 point)
        - pred wrong type or invalid format -> WRONG (-1 point)
        - pred correct type and value matches -> CORRECT (+1 point)
        - otherwise -> WRONG (-1 point)
    """
    if isinstance(pred, dict):
        pred_type = pred.get("type")
        pred_ans = pred.get("answer")
    elif pred is not None:
        pred_type = pred.type
        pred_ans = pred.answer
    else:
        return EvaluationResult.ABSTAIN

    pred_type_str = _normalize_type_str(pred_type)
    ref_type_str = _normalize_type_str(ref.get("type"))
    ref_ans = ref.get("answer")

    # If reference expects abstain: per spec, scored as abstain regardless
    if ref_type_str == AnswerType.ABSTAIN.value:
        return EvaluationResult.ABSTAIN

    # Type abstain or missing answer is an abstain (scores 0, avoids penalty)
    if pred_type_str == AnswerType.ABSTAIN.value or pred_type_str is None:
        return EvaluationResult.ABSTAIN

    # If question is unanswerable:
    if ref_type_str == AnswerType.UNANSWERABLE.value:
        if pred_type_str == AnswerType.UNANSWERABLE.value:
            return EvaluationResult.CORRECT
        return EvaluationResult.WRONG

    # If predicted unanswerable on an answerable question: wrong (-1)
    if pred_type_str == AnswerType.UNANSWERABLE.value:
        return EvaluationResult.WRONG

    # Any other answer is correct only if its type equals reference type
    if pred_type_str != ref_type_str:
        return EvaluationResult.WRONG

    # Enforce strict format per Rule 9 ("Mỗi type có một format duy nhất; sai format là sai"):
    if ref_type_str == AnswerType.NUMBER.value:
        if isinstance(pred_ans, bool) or not isinstance(pred_ans, (int, float)):
            return EvaluationResult.WRONG
        return EvaluationResult.CORRECT if match_number(pred_ans, ref_ans) else EvaluationResult.WRONG

    elif ref_type_str == AnswerType.PERCENT.value:
        if isinstance(pred_ans, bool) or not isinstance(pred_ans, (int, float)):
            return EvaluationResult.WRONG
        return EvaluationResult.CORRECT if match_percent(pred_ans, ref_ans) else EvaluationResult.WRONG

    elif ref_type_str == AnswerType.STRING.value:
        if not isinstance(pred_ans, str):
            return EvaluationResult.WRONG
        forms = _string_forms(ref)
        if not forms:
            return EvaluationResult.WRONG
        return EvaluationResult.CORRECT if match_string(str(pred_ans), forms) else EvaluationResult.WRONG

    elif ref_type_str == AnswerType.DATE.value:
        if not isinstance(pred_ans, str):
            return EvaluationResult.WRONG
        clean_date = pred_ans.strip()
        if not re.match(r"^\d{4}-\d{2}(-\d{2})?$", clean_date):
            return EvaluationResult.WRONG
        return EvaluationResult.CORRECT if match_date(clean_date, ref_ans) else EvaluationResult.WRONG

    elif ref_type_str == AnswerType.BOOLEAN.value:
        if not isinstance(pred_ans, bool):
            return EvaluationResult.WRONG
        return EvaluationResult.CORRECT if match_boolean(pred_ans, ref_ans) else EvaluationResult.WRONG

    elif ref_type_str == AnswerType.LIST.value:
        if not isinstance(pred_ans, list):
            return EvaluationResult.WRONG
        if match_list_with_alias(pred_ans, ref_ans, ref.get("alias")):
            return EvaluationResult.CORRECT
        return EvaluationResult.CORRECT if match_list(pred_ans, ref_ans) else EvaluationResult.WRONG

    elif ref_type_str == AnswerType.TABLE.value:
        if not isinstance(pred_ans, dict):
            return EvaluationResult.WRONG
        if "columns" not in pred_ans or "rows" not in pred_ans:
            return EvaluationResult.WRONG
        if not isinstance(pred_ans["columns"], list) or not isinstance(pred_ans["rows"], list):
            return EvaluationResult.WRONG
        return EvaluationResult.CORRECT if match_table(pred_ans, ref_ans) else EvaluationResult.WRONG

    return EvaluationResult.WRONG


def compute_penalized_accuracy(
    predictions: List[Union[SubmissionItem, Dict[str, Any]]],
    references: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compute Penalized Accuracy (PA) metric over N questions of the test set:

    PA = (correct_count - wrong_count) / total_questions

    Scoring Table:
    - Correct answer: +1
    - Wrong answer: -1
    - Abstain: 0
    - Missing answer: 0
    - Correct unanswerable: +1
    - Answering an unanswerable question: -1
    - Abstain is NEVER treated as a correct unanswerable answer (scores 0).

    Duplicate predictions in `predictions` keep the first occurrence and are counted.
    """
    n_total = len(references)
    if n_total == 0:
        return {
            "pa": 0.0,
            "correct": 0,
            "abstain": 0,
            "wrong": 0,
            "total": 0,
            "accuracy": 0.0,
            "coverage": 0.0,
            "duplicate_count": 0,
            "extra_count": 0,
        }

    ref_map = {r["id"]: r for r in references}

    # Deduplicate predictions safely, preserving first occurrence
    pred_map = {}
    duplicates = []
    for p in predictions:
        pid = p.id if hasattr(p, "id") else p.get("id")
        if pid in pred_map:
            duplicates.append(pid)
        else:
            pred_map[pid] = p

    extra_count = sum(1 for pid in pred_map if pid not in ref_map)

    correct_count = 0
    abstain_count = 0
    wrong_count = 0
    total_score = 0

    # Every reference in references MUST be evaluated against total_questions
    for qid, ref in ref_map.items():
        pred = pred_map.get(qid)
        if pred is None:
            # Missing answer is an abstain (0 points)
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
        "duplicate_count": len(duplicates),
        "extra_count": extra_count,
    }
