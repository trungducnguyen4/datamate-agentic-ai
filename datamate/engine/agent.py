from __future__ import annotations
import os
from typing import Any, Dict, List, Optional
from datamate.core.types import AnswerType, QuestionItem, SubmissionItem
from datamate.data.loader import BusinessDataLoader
from datamate.data.schema_inspector import SchemaInspector
from datamate.engine.executor import SafeSQLExecutor
from datamate.engine.rule_compiler import BusinessRuleCompiler, CompiledQueryPlan


class DataMateAgent:
    """Agentic AI engine for DataMate question answering over business data."""

    def __init__(self, data_root_dir: str):
        self.data_root_dir = os.path.abspath(data_root_dir)
        self._loaders_cache: Dict[str, BusinessDataLoader] = {}
        self._tables_cache: Dict[str, Any] = {}

    def get_or_load_business(self, business_id: str) -> BusinessDataLoader:
        if business_id in self._loaders_cache:
            return self._loaders_cache[business_id]

        biz_dir = os.path.join(self.data_root_dir, business_id)
        loader = BusinessDataLoader(biz_dir).load()
        self._loaders_cache[business_id] = loader
        return loader

    def get_tables(self, business_id: str, conn) -> Any:
        if business_id not in self._tables_cache:
            self._tables_cache[business_id] = SchemaInspector.inspect(conn)
        return self._tables_cache[business_id]

    def answer_question(self, item: QuestionItem) -> SubmissionItem:
        """Process a single question and return a valid SubmissionItem."""
        try:
            loader = self.get_or_load_business(item.business_id)
            tables = self.get_tables(item.business_id, loader.conn)

            # If no tables exist for this business
            if not tables:
                return SubmissionItem(id=item.id, type=AnswerType.UNANSWERABLE)

            plan: CompiledQueryPlan = BusinessRuleCompiler.compile(
                question=item.question,
                as_of_date_str=item.as_of_date,
                tables=tables,
            )

            # If explicitly unanswerable
            if plan.expected_type == AnswerType.UNANSWERABLE:
                return SubmissionItem(id=item.id, type=AnswerType.UNANSWERABLE)

            # If abstain
            if plan.expected_type == AnswerType.ABSTAIN or not plan.sql:
                return SubmissionItem(id=item.id, type=AnswerType.ABSTAIN)

            # Execute SQL
            cols, rows = SafeSQLExecutor.execute_query(loader.conn, plan.sql)

            if not rows or len(rows) == 0:
                # No rows found
                return SubmissionItem(id=item.id, type=AnswerType.ABSTAIN)

            # Format answer
            formatted_ans = self._format_answer(plan.expected_type, cols, rows)
            if formatted_ans is None:
                return SubmissionItem(id=item.id, type=AnswerType.ABSTAIN)

            return SubmissionItem(
                id=item.id,
                type=plan.expected_type,
                answer=formatted_ans,
            )

        except Exception as e:
            # Fallback to abstain on runtime error to avoid -1 score!
            return SubmissionItem(id=item.id, type=AnswerType.ABSTAIN)

    def _format_answer(self, ans_type: AnswerType, cols: List[str], rows: List[List[Any]]) -> Any:
        if ans_type == AnswerType.STRING:
            val = rows[0][0]
            return str(val).strip() if val is not None else None

        elif ans_type == AnswerType.NUMBER:
            val = rows[0][0]
            if val is None:
                return None
            f_val = float(val)
            return int(f_val) if f_val.is_integer() else round(f_val, 2)

        elif ans_type == AnswerType.PERCENT:
            val = rows[0][0]
            if val is None:
                return None
            return round(float(val), 2)

        elif ans_type == AnswerType.BOOLEAN:
            val = rows[0][0]
            return bool(val)

        elif ans_type == AnswerType.DATE:
            val = rows[0][0]
            return str(val).strip()

        elif ans_type == AnswerType.LIST:
            # Flatten column 0 into a list
            res_list = []
            for r in rows:
                if r and r[0] is not None:
                    res_list.append(r[0])
            return res_list

        elif ans_type == AnswerType.TABLE:
            return {
                "columns": cols,
                "rows": rows,
            }

        return None
