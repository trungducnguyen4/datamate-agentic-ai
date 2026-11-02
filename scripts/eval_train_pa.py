"""Evaluate the DataMate pipeline against the organizers' labelled train split.

Chấm theo đúng định nghĩa Penalized Accuracy của Zalo AI Challenge 2026:
    s_i = +1 correct, 0 abstain, -1 wrong
và dùng một hàm evaluator duy nhất (canonical evaluator trong `datamate.evaluator.metric`).

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

from datamate.core.types import QuestionItem
from datamate.engine.agent import DataMateAgent
from datamate.evaluator.metric import compute_penalized_accuracy, evaluate_single_answer


def load_jsonl(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


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
    all_refs = load_jsonl(args.answers)
    refs_map = {r["id"]: r for r in all_refs}
    # Limit references to the questions being evaluated
    q_ids = {q["id"] for q in questions}
    refs = [r for r in all_refs if r["id"] in q_ids]

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
    metrics = compute_penalized_accuracy(preds, refs)

    per_type: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    pred_dict = {p["id"]: p for p in preds}
    for r in refs:
        p = pred_dict.get(r["id"])
        res = evaluate_single_answer(p, r) if p is not None else EvaluationResult.ABSTAIN
        per_type[r["type"]][res.value] += 1

    total = metrics["total"]
    print(f"questions={total} elapsed={elapsed:.1f}s ({elapsed / max(total, 1) * 1000:.0f} ms/câu)")
    print(f"PA = {metrics['pa']:+.4f}")
    print(f"correct={metrics['correct']} wrong={metrics['wrong']} abstain={metrics['abstain']}")
    for ref_type, counter in sorted(per_type.items()):
        n = sum(counter.values())
        print(
            f"  {ref_type:<13} n={n:<5} correct={counter['correct']:<4} "
            f"wrong={counter['wrong']:<5} abstain={counter['abstain']:<5} "
            f"pa={(counter['correct'] - counter['wrong']) / max(n, 1):+.3f}"
        )


if __name__ == "__main__":
    main()
