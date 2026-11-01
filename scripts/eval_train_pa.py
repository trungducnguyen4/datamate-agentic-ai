"""Evaluate the DataMate pipeline against the organizers' labelled train split.

Chấm theo đúng định nghĩa Penalized Accuracy của Zalo AI Challenge 2026:
    s_i = +1 correct, 0 abstain, -1 wrong
và dùng cả `alias` (các dạng tên/mã được chấp nhận) như BTC.

Ví dụ:
    python -m scripts.eval_train_pa --data-dir data/train/data
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import time
from typing import Any, Dict, List

from datamate.core.normalizer import normalize_string
from datamate.core.types import QuestionItem
from datamate.engine.agent import DataMateAgent
from datamate.evaluator.metric import evaluate_single_answer


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def score(pred: Dict[str, Any], ref: Dict[str, Any]) -> str:
    """Official-style scoring, accepting every alias form for string answers."""
    if ref.get("type") == "string":
        if pred.get("type") == "abstain":
            return "abstain"
        if pred.get("type") != "string":
            return "wrong"
        forms = [ref.get("answer")] + list(ref.get("alias") or [])
        candidate = normalize_string(pred.get("answer"))
        return "correct" if any(candidate == normalize_string(f) for f in forms) else "wrong"
    return evaluate_single_answer(pred, ref).value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data/train/data")
    parser.add_argument("--questions", default="data/train/questions.jsonl")
    parser.add_argument("--answers", default="data/train/answers.jsonl")
    parser.add_argument("--out", default=".cache/train_predictions.jsonl")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    questions = load_jsonl(args.questions)
    if args.limit:
        questions = questions[: args.limit]
    refs = {r["id"]: r for r in load_jsonl(args.answers)}

    agent = DataMateAgent(args.data_dir)
    preds: List[Dict[str, Any]] = []
    start = time.time()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as out:
        for q in questions:
            item = agent.answer_question(QuestionItem(**q)).to_dict()
            preds.append(item)
            out.write(json.dumps(item, ensure_ascii=False) + "\n")

    elapsed = time.time() - start
    stats = collections.Counter()
    per_type: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for pred in preds:
        ref = refs.get(pred["id"])
        if ref is None:
            continue
        result = score(pred, ref)
        stats[result] += 1
        per_type[ref["type"]][result] += 1

    total = sum(stats.values())
    print(f"questions={total} elapsed={elapsed:.1f}s ({elapsed / total * 1000:.0f} ms/câu)")
    print(f"PA = {(stats['correct'] - stats['wrong']) / total:+.4f}")
    print(f"correct={stats['correct']} wrong={stats['wrong']} abstain={stats['abstain']}")
    for ref_type, counter in sorted(per_type.items()):
        n = sum(counter.values())
        print(
            f"  {ref_type:<13} n={n:<5} correct={counter['correct']:<4} "
            f"wrong={counter['wrong']:<5} abstain={counter['abstain']:<5} "
            f"pa={(counter['correct'] - counter['wrong']) / n:+.3f}"
        )


if __name__ == "__main__":
    main()
