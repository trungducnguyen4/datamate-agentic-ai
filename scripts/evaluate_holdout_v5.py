import json
import os
import sys
import time
from collections import Counter, defaultdict

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.abspath("."))

from datamate.core.types import QuestionItem
from datamate.engine.agent import DataMateAgent
from datamate.evaluator.metric import evaluate_single_answer, EvaluationResult, compute_penalized_accuracy

HOLDOUT_BIZ_IDS = {
    "biz_101", # flat file single table
    "biz_103", # header + detail line items
    "biz_105", # monthly multi-sheet
    "biz_106", # POS export
    "biz_111", # relational multi-file
    "biz_120", # multi-file pharmacy with batch/lot
    "biz_124", # heterogeneous sources
    "biz_128", # multi-file departments
}

def main():
    print("Loading train questions and answers...")
    answers_map = {}
    with open("data/train/answers.jsonl", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            answers_map[item["id"]] = item

    questions = []
    with open("data/train/questions.jsonl", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            if item["business_id"] in HOLDOUT_BIZ_IDS:
                questions.append(item)

    print(f"Total holdout questions selected: {len(questions)} across {len(HOLDOUT_BIZ_IDS)} businesses.")

    agent = DataMateAgent(data_root_dir="data/train/data")

    predictions = []
    references = []
    results_detail = []

    start_time = time.perf_counter()
    for idx, q_item in enumerate(questions):
        qid = q_item["id"]
        q_obj = QuestionItem(
            id=qid,
            business_id=q_item["business_id"],
            as_of_date=q_item.get("as_of_date", "2026-03-04"),
            question=q_item["question"]
        )

        resp, trace = agent.answer_question_with_trace(q_obj)
        ref = answers_map[qid]

        predictions.append(resp)
        references.append(ref)

        eval_res = evaluate_single_answer(resp, ref)

        results_detail.append({
            "id": qid,
            "business_id": q_item["business_id"],
            "question": q_item["question"],
            "as_of_date": q_item.get("as_of_date"),
            "expected_type": ref.get("type"),
            "expected_answer": ref.get("answer"),
            "actual_type": resp.type.value if hasattr(resp.type, "value") else str(resp.type),
            "actual_answer": resp.answer,
            "eval_result": eval_res.value,
            "status": trace.status,
            "intent": trace.intent,
            "sql": trace.sql,
            "params": trace.params,
            "error_phase": trace.error_phase,
            "error_message": trace.error_message,
        })

        if (idx + 1) % 100 == 0 or (idx + 1) == len(questions):
            elapsed = time.perf_counter() - start_time
            print(f"[{idx+1}/{len(questions)}] Processed in {elapsed:.1f}s...", flush=True)

    # Compute overall metric
    overall_summary = compute_penalized_accuracy(predictions, references)
    out_lines = []
    out_lines.append("=======================================================")
    out_lines.append("HOLDOUT VALIDATION BENCHMARK RESULTS (Candidate)")
    out_lines.append("=======================================================")
    out_lines.append(f"Total Questions: {overall_summary['total']}")
    out_lines.append(f"Correct:         {overall_summary['correct']}  ({overall_summary['correct']/overall_summary['total']*100:.2f}%)")
    out_lines.append(f"Wrong:           {overall_summary['wrong']}  ({overall_summary['wrong']/overall_summary['total']*100:.2f}%)")
    out_lines.append(f"Abstain:         {overall_summary['abstain']}  ({overall_summary['abstain']/overall_summary['total']*100:.2f}%)")
    out_lines.append(f"Penalized Acc:   {overall_summary['pa']:+.5f}")

    # Breakdown by business
    by_biz = defaultdict(list)
    for r in results_detail:
        by_biz[r["business_id"]].append(r)

    out_lines.append("\n--- Breakdown By Business ---")
    for biz_id, items in sorted(by_biz.items()):
        preds = [{"id": x["id"], "type": x["actual_type"], "answer": x["actual_answer"]} for x in items]
        refs = [answers_map[x["id"]] for x in items]
        summary = compute_penalized_accuracy(preds, refs)
        out_lines.append(f"  {biz_id:8s}: Total={summary['total']:3d} | Correct={summary['correct']:3d} | Wrong={summary['wrong']:3d} | Abstain={summary['abstain']:3d} | PA={summary['pa']:+.4f}")

    # Breakdown by intent
    by_intent = defaultdict(list)
    for r in results_detail:
        by_intent[r["intent"]].append(r)

    out_lines.append("\n--- Breakdown By Intent (Top 15) ---")
    sorted_intents = sorted(by_intent.items(), key=lambda kv: len(kv[1]), reverse=True)
    for intent, items in sorted_intents[:15]:
        preds = [{"id": x["id"], "type": x["actual_type"], "answer": x["actual_answer"]} for x in items]
        refs = [answers_map[x["id"]] for x in items]
        summary = compute_penalized_accuracy(preds, refs)
        out_lines.append(f"  {intent:26s}: Total={summary['total']:3d} | Correct={summary['correct']:3d} | Wrong={summary['wrong']:3d} | Abstain={summary['abstain']:3d} | PA={summary['pa']:+.4f}")

    # Save detailed evaluation log
    os.makedirs("logs", exist_ok=True)
    with open("logs/holdout_validation_v5.jsonl", "w", encoding="utf-8") as f:
        for r in results_detail:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    with open("logs/holdout_summary_v5.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines))

    print("\n".join(out_lines), flush=True)

if __name__ == "__main__":
    main()
