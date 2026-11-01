import sys
import io
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

with open("data/train/questions.jsonl", "r", encoding="utf-8") as fq, \
     open("data/train/answers.jsonl", "r", encoding="utf-8") as fa:
    count = 0
    for q_line, a_line in zip(fq, fa):
        q = json.loads(q_line)
        a = json.loads(a_line)
        if q["business_id"] == "biz_101":
            print(f"[{q['id']}] Q: {q['question']} (as_of: {q['as_of_date']})")
            print(f"   -> Expected: {a['type']} : {a['answer']}")
            count += 1
            if count >= 10:
                break
