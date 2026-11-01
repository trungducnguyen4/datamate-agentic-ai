from __future__ import annotations
import argparse
import io
import json
import os
import sys
import time
from typing import List, Optional

from datamate.core.types import QuestionItem, SubmissionItem
from datamate.engine.agent import DataMateAgent
from datamate.evaluator.metric import compute_penalized_accuracy

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def run_pipeline(
    data_dir: str,
    questions_file: str,
    output_file: str,
    eval_ref_file: Optional[str] = None,
    limit: Optional[int] = None,
    log_file: Optional[str] = None,
) -> None:
    if not os.path.exists(questions_file):
        print(f"Error: Questions file not found at {questions_file}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading DataMate agent with data directory: {data_dir}", flush=True)
    agent = DataMateAgent(data_root_dir=data_dir)
    print(f"Resolved data root: {agent.data_root_dir}", flush=True)

    # Read questions
    questions: List[QuestionItem] = []
    with open(questions_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            questions.append(QuestionItem(**data))

    if limit and limit > 0:
        questions = questions[:limit]

    print(f"Processing {len(questions)} questions...", flush=True)
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    if log_file is None:
        log_file = os.path.join(
            os.path.dirname(os.path.abspath(output_file)), "submission_log.jsonl"
        )
    os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)

    start_time = time.time()
    results: List[SubmissionItem] = []

    # Ghi streaming: BTC chỉ chấm những dòng đã có trong /result/submission.jsonl
    # nếu tiến trình bị dừng giữa chừng (Rule 7/8).
    with open(output_file, "w", encoding="utf-8") as out, open(
        log_file, "w", encoding="utf-8"
    ) as log:
        for i, q in enumerate(questions, start=1):
            sub_item, trace = agent.answer_question_with_trace(q)
            results.append(sub_item)
            out.write(json.dumps(sub_item.to_dict(), ensure_ascii=False) + "\n")
            out.flush()
            log.write(
                json.dumps(
                    {
                        "id": trace.id,
                        "status": trace.status,
                        "intent": trace.intent,
                        "sql": trace.sql,
                        "error_phase": trace.error_phase,
                        "error_message": trace.error_message,
                        "latency_ms": round(trace.latency_ms, 3),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            log.flush()
            if i % 25 == 0 or i == len(questions):
                elapsed = time.time() - start_time
                print(f"[{i}/{len(questions)}] Processed ({elapsed:.1f}s)", flush=True)

    total_time = time.time() - start_time
    print(f"Done! Submission saved to {output_file} in {total_time:.2f} seconds.", flush=True)
    print(f"Run log saved to {log_file}", flush=True)

    # Optional evaluation
    if eval_ref_file and os.path.exists(eval_ref_file):
        print(f"\nEvaluating against references at {eval_ref_file}...")
        refs_map = {}
        with open(eval_ref_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    item = json.loads(line)
                    refs_map[item["id"]] = item

        matching_refs = [refs_map[r.id] for r in results if r.id in refs_map]
        matching_results = [r for r in results if r.id in refs_map]

        metrics = compute_penalized_accuracy(matching_results, matching_refs)
        print("\n" + "=" * 35)
        print("     PENALIZED ACCURACY REPORT     ")
        print("=" * 35)
        print(f"Penalized Accuracy (PA): {metrics['pa']:.4f}")
        print(f"Total Questions:         {metrics['total']}")
        print(f"Correct (+1):            {metrics['correct']}")
        print(f"Abstain (0):             {metrics['abstain']}")
        print(f"Wrong (-1):              {metrics['wrong']}")
        print(f"Accuracy:                {metrics['accuracy']*100:.2f}%")
        print(f"Coverage:                {metrics['coverage']*100:.2f}%")
        print("=" * 35)


def main():
    parser = argparse.ArgumentParser(description="DataMate Question Answering CLI")
    parser.add_argument("--data-dir", required=True, help="Directory containing business data packages")
    parser.add_argument("--questions", required=True, help="Path to questions.jsonl")
    parser.add_argument("--output", default="submission.jsonl", help="Path to write submission.jsonl")
    parser.add_argument("--eval-ref", default=None, help="Optional path to reference jsonl for PA evaluation")
    parser.add_argument("--limit", type=int, default=None, help="Optional question limit")
    parser.add_argument("--log", default=None, help="Optional path for run log (JSONL)")

    args = parser.parse_args()
    run_pipeline(
        data_dir=args.data_dir,
        questions_file=args.questions,
        output_file=args.output,
        eval_ref_file=args.eval_ref,
        limit=args.limit,
        log_file=args.log,
    )


if __name__ == "__main__":
    main()
