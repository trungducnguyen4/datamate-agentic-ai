import sys
import io
import json
from datamate.engine.agent import DataMateAgent
from datamate.core.types import QuestionItem

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

agent = DataMateAgent("data/train/data")

test_cases = [
    ("q_0cb7c9b93048", "Cho tôi biết số đơn hôm qua.", "2025-09-24", 37, "number"),
    ("q_1af02cd5fe06", "Cho tôi biết số đơn hqua", "2026-04-14", 44, "number"),
    ("q_26ec390f37d7", "hqua cua hang ban duoc may don", "2025-08-26", 40, "number"),
    ("q_1cc70c12aa27", "Hôm nay cửa hàng bán được bao nhiêu tiền?", "2026-02-22", 13479900, "number"),
    ("q_2a3019504577", "doanh thu hqua cua cua hang la bao nhiu", "2026-01-12", 3530400, "number"),
]

for qid, q_text, as_of, exp_ans, exp_type in test_cases:
    q_item = QuestionItem(id=qid, business_id="biz_101", question=q_text, as_of_date=as_of)
    result = agent.answer_question(q_item)
    print(f"\n--- {qid} ---")
    print(f"Q: {q_text} (as_of: {as_of})")
    print(f"Agent -> Type: {result.type}, Answer: {result.answer}")
    print(f"Expected -> Type: {exp_type}, Answer: {exp_ans}")
    match = (result.type.value == exp_type and result.answer == exp_ans)
    print(f"Match: {match}")
