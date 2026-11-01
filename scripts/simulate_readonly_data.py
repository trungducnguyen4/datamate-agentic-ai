"""Mô phỏng mount /data ở chế độ read-only của BTC (Rule 5).

Loader của DataMate ghi cache SQLite vào `dirname(business_dir)` — tức chính thư mục
dữ liệu. Khi /data được mount `:ro`, lệnh ghi này ném OSError(EROFS) và agent trả
`abstain` cho mọi câu. Script này tái hiện điều kiện đó bằng cách chặn os.makedirs
với đường dẫn `.cache_sqlite`, rồi in ra loại đáp án + trace.

    python -m scripts.simulate_readonly_data --data-dir data/public_test/data --business dev_001
"""
from __future__ import annotations

import argparse
import errno
import os
import shutil
import sys
import tempfile

from datamate.core.types import QuestionItem
from datamate.engine.agent import DataMateAgent


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data/public_test/data")
    parser.add_argument("--business", default="dev_001")
    parser.add_argument("--question", default="Tổng doanh thu tháng này là bao nhiêu?")
    parser.add_argument("--as-of", default="2026-03-04")
    args = parser.parse_args()

    src = os.path.join(args.data_dir, args.business)
    if not os.path.isdir(src):
        sys.exit(f"Không tìm thấy {src}")

    root = tempfile.mkdtemp()
    biz = os.path.join(root, args.business)
    os.makedirs(biz, exist_ok=True)
    for name in os.listdir(src):
        path = os.path.join(src, name)
        if os.path.isfile(path):
            shutil.copy(path, biz)

    real_makedirs = os.makedirs

    def read_only_makedirs(path, *a, **kw):
        text = str(path)
        if ".cache_sqlite" in text or "datamate_cache" in text:
            raise OSError(errno.EROFS, "Read-only file system", text)
        return real_makedirs(path, *a, **kw)

    os.makedirs = read_only_makedirs
    try:
        agent = DataMateAgent(root)
        question = QuestionItem(
            id="readonly_probe",
            business_id=args.business,
            question=args.question,
            as_of_date=args.as_of,
        )
        answer, trace = agent.answer_question_with_trace(question)
    finally:
        os.makedirs = real_makedirs

    print(f"type   = {answer.type.value}")
    print(f"status = {trace.status}")
    print(f"phase  = {trace.error_phase}")
    print(f"error  = {trace.error_message}")
    shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
