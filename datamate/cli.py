from __future__ import annotations
import argparse
import json
import os
import sys
import time
from typing import List
from datamate.core.types import QuestionItem, SubmissionItem
from datamate.engine.agent import DataMateAgent
from datamate.evaluator.metric import compute_penalized_accuracy


def run_pipeline(data_dir: str, questions_file: str, output_file: str, eval_ref_file: str = None) -> None:
    if not os.path.exists(questions_file):
        print(f"Error: Questions file not found at {questions_file}", file=sys.stderr)
        sys.exit(1)

    print(f"Loading DataMate agent with data directory: {data_dir}")
    agent = DataMateAgent(data_root_dir=data_dir)

    # Read questions
    questions: List[QuestionItem] = []
    with open(questions_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            questions.append(QuestionItem(**data))

    print(f"Processing {len(questions)} questions...")
    start_time = time.time()
    results: List[SubmissionItem] = []

    for i, q in enumerate(questions, start=1):
        sub_item = agent.answer_question(q)
        results.append(sub_item)
        if i % 100 == 0 or i == len(questions):
            elapsed = time.time() - start_time
            print(f"[{i}/{len(questions)}] Processed ({elapsed:.1f}s)")

    # Ensure output directory exists
    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)

    # Write submission.jsonl
    with open(output_file, "w", encoding="utf-8") as out:
        for item in results:
            out.write(json.dumps(item.to_dict(), ensure_ascii=False) + "\n")

    total_time = time.time() - start_time
    print(f"Done! Submission saved to {output_file} in {total_time:.2f} seconds.")

    # Optional evaluation
    if eval_ref_file and os.path.exists(eval_ref_file):
        print(f"\nEvaluating against references at {eval_ref_file}...")
        refs = []
        with open(eval_ref_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    refs.append(json.loads(line))
        metrics = compute_penalized_accuracy(results, refs)
        print("=== EVALUATION METRICS ===")
        print(f"Penalized Accuracy (PA): {metrics['pa']:.4f}")
        print(f"Total Questions: {metrics['total']}")
        print(f"Correct (+1): {metrics['correct']}")
        print(f"Abstain (0):  {metrics['abstain']}")
        print(f"Wrong (-1):   {metrics['wrong']}")
        print(f"Accuracy:     {metrics['accuracy']*100:.2f}%")
        print(f"Coverage:     {metrics['coverage']*100:.2f}%")


def main():
    parser = argparse.ArgumentParser(description="DataMate Question Answering CLI")
    parser.add_argument("--data-dir", required=True, help="Directory containing business data packages")
    parser.add_argument("--questions", required=True, help="Path to questions.jsonl")
    parser.add_argument("--output", default="submission.jsonl", help="Path to write submission.jsonl")
    parser.add_argument("--eval-ref", default=None, help="Optional path to reference jsonl for PA evaluation")

    args = parser.parse_args()
    run_pipeline(
        data_dir=args.data_dir,
        questions_file=args.questions,
        output_file=args.output,
        eval_ref_file=args.eval_ref,
    )


if __name__ == "__main__":
    main()
