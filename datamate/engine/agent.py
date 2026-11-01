from __future__ import annotations
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple
from datamate.core.types import AnswerType, QuestionItem, SubmissionItem, ExecutionTrace
from datamate.data.calendar_csv import configure_calendar
from datamate.data.rulebook import configure_rulebook
from datamate.data.loader import BusinessDataLoader
from datamate.data.schema_inspector import SchemaInspector
from datamate.data.union_view import ensure_sales_union
from datamate.engine.executor import SafeSQLExecutor
from datamate.engine.rule_compiler import BusinessRuleCompiler, CompiledQueryPlan
from datamate.temporal.resolver import TemporalResolver

logger = logging.getLogger("datamate.agent")

DATA_SUFFIXES = (".csv", ".xlsx", ".xls", ".sqlite", ".db")


class DataMateAgent:
    """Agentic AI engine for DataMate question answering over business data."""

    def __init__(self, data_root_dir: str):
        raw_root = os.path.abspath(data_root_dir)
        self.split_root_dir = raw_root
        self.data_root_dir = self._resolve_data_root(raw_root)
        self._calendar = configure_calendar(raw_root, self.data_root_dir)
        self._rulebook = configure_rulebook(raw_root, self.data_root_dir)
        self._loaders_cache: Dict[str, BusinessDataLoader] = {}
        self._tables_cache: Dict[str, Any] = {}
        self.last_trace: Optional[ExecutionTrace] = None

    # ------------------------------------------------------------- data root
    @staticmethod
    def _has_data_package(path: str) -> bool:
        if not os.path.isdir(path):
            return False
        try:
            entries = os.listdir(path)
        except OSError:
            return False
        for name in entries:
            if name.startswith("."):
                continue
            sub = os.path.join(path, name)
            if not os.path.isdir(sub):
                continue
            try:
                files = os.listdir(sub)
            except OSError:
                continue
            if any(f.lower().endswith(DATA_SUFFIXES) for f in files):
                return True
        return False

    @classmethod
    def _resolve_data_root(cls, raw_root: str) -> str:
        """Chấp nhận cả `/data` và `/data/data` (layout của BTC)."""
        candidates = [raw_root, os.path.join(raw_root, "data")]
        for candidate in candidates:
            if cls._has_data_package(candidate):
                return candidate
        return raw_root

    def _business_dir(self, business_id: str) -> Optional[str]:
        for root in (self.data_root_dir, self.split_root_dir):
            candidate = os.path.join(root, business_id)
            if os.path.isdir(candidate):
                return candidate
        return None

    # ----------------------------------------------------------------- data
    def get_or_load_business(self, business_id: str) -> BusinessDataLoader:
        if business_id in self._loaders_cache:
            return self._loaders_cache[business_id]

        biz_dir = self._business_dir(business_id)
        loader = BusinessDataLoader(biz_dir or os.path.join(self.data_root_dir, business_id)).load()
        self._loaders_cache[business_id] = loader
        return loader

    def get_tables(self, business_id: str, conn) -> Any:
        if business_id not in self._tables_cache:
            tables = SchemaInspector.inspect(conn)
            if tables:
                ensure_sales_union(conn, tables)
            self._tables_cache[business_id] = tables
        return self._tables_cache[business_id]

    # ------------------------------------------------------------- question
    def answer_question(self, item: QuestionItem) -> SubmissionItem:
        """Process a single question and return a valid SubmissionItem."""
        submission, trace = self.answer_question_with_trace(item)
        self.last_trace = trace
        return submission

    def answer_question_with_trace(self, item: QuestionItem) -> Tuple[SubmissionItem, ExecutionTrace]:
        """Process question and return both SubmissionItem and detailed ExecutionTrace."""
        start_time = time.perf_counter()
        trace = ExecutionTrace(id=item.id, status="SUCCESS")

        phase = "LOADER"
        try:
            business_dir = self._business_dir(item.business_id)
            if business_dir is None:
                # Không có gói dữ liệu: đây là lỗi hệ thống, abstain an toàn hơn
                # unanswerable (tránh bị trừ điểm oan).
                trace.status = "MISSING_BUSINESS"
                trace.error_phase = "LOADER"
                trace.error_message = f"business package not found: {item.business_id}"
                trace.latency_ms = (time.perf_counter() - start_time) * 1000
                return SubmissionItem(id=item.id, type=AnswerType.ABSTAIN), trace

            loader = self.get_or_load_business(item.business_id)

            phase = "SCHEMA"
            tables = self.get_tables(item.business_id, loader.conn)

            # If no tables exist for this business
            if not tables:
                trace.status = "NO_TABLES"
                trace.error_phase = "SCHEMA"
                trace.latency_ms = (time.perf_counter() - start_time) * 1000
                return SubmissionItem(id=item.id, type=AnswerType.ABSTAIN), trace

            phase = "COMPILER"
            norm_as_of = TemporalResolver.normalize_as_of_date_str(item.as_of_date) if item.as_of_date else "2026-03-04"
            plan: CompiledQueryPlan = BusinessRuleCompiler.compile(
                question=item.question,
                as_of_date_str=norm_as_of,
                tables=tables,
                rulebook=self._rulebook,
                readme_text=loader.readme_text,
            )
            trace.intent = plan.intent
            trace.sql = plan.sql
            trace.params = list(getattr(plan, "params", ()))

            # If explicitly unanswerable
            if plan.expected_type == AnswerType.UNANSWERABLE:
                trace.status = "UNANSWERABLE"
                trace.error_message = plan.unanswerable_reason
                trace.latency_ms = (time.perf_counter() - start_time) * 1000
                return SubmissionItem(id=item.id, type=AnswerType.UNANSWERABLE), trace

            # If abstain decided by business rules
            if plan.expected_type == AnswerType.ABSTAIN or not plan.sql:
                trace.status = "ABSTAIN_BUSINESS_RULE"
                trace.latency_ms = (time.perf_counter() - start_time) * 1000
                return SubmissionItem(id=item.id, type=AnswerType.ABSTAIN), trace

            # Execute SQL safely
            phase = "SQL_EXECUTION"
            plan_params = getattr(plan, "params", ())
            cols, rows = SafeSQLExecutor.execute_query(loader.conn, plan.sql, params=plan_params)

            if not rows or len(rows) == 0:
                # No rows found
                trace.status = "ABSTAIN_EMPTY_RESULT"
                trace.latency_ms = (time.perf_counter() - start_time) * 1000
                return SubmissionItem(id=item.id, type=AnswerType.ABSTAIN), trace

            # Format answer
            phase = "FORMATTER"
            formatted_ans = self._format_answer(plan.expected_type, cols, rows)
            if formatted_ans is None:
                trace.status = "ABSTAIN_NULL_FORMAT"
                trace.latency_ms = (time.perf_counter() - start_time) * 1000
                return SubmissionItem(id=item.id, type=AnswerType.ABSTAIN), trace

            # Penalized Accuracy Safeguard: In business analytics queries (revenue, product quantity, growth, counts, debt),
            # an answer of 0 or empty list almost always indicates unmatched WHERE conditions or missing dimensions.
            # Returning 0 on non-zero reality yields -1 penalty, whereas ABSTAIN yields 0.
            if plan.expected_type == AnswerType.LIST and (formatted_ans is None or len(formatted_ans) == 0):
                trace.status = "ABSTAIN_EMPTY_LIST"
                trace.latency_ms = (time.perf_counter() - start_time) * 1000
                return SubmissionItem(id=item.id, type=AnswerType.ABSTAIN), trace

            if formatted_ans in (0, 0.0) and plan.intent in (
                "revenue", "product_revenue", "quantity", "product_quantity",
                "which_day", "which_month", "avg_order_revenue", "growth_rate",
                "ranking_product_revenue", "ranking_product_quantity",
                "debt_max"
            ):
                trace.status = "ABSTAIN_ZERO_SAFEGUARD"
                trace.latency_ms = (time.perf_counter() - start_time) * 1000
                return SubmissionItem(id=item.id, type=AnswerType.ABSTAIN), trace

            trace.status = "SUCCESS"
            trace.latency_ms = (time.perf_counter() - start_time) * 1000
            return (
                SubmissionItem(
                    id=item.id,
                    type=plan.expected_type,
                    answer=formatted_ans,
                ),
                trace,
            )

        except Exception as e:
            # Fallback to abstain on runtime error to avoid -1 score in contest submissions,
            # but preserve exact failure trace for observability and engineering.
            trace.status = "EXECUTION_ERROR"
            trace.error_phase = phase
            trace.error_message = f"{type(e).__name__}: {str(e)}"
            trace.latency_ms = (time.perf_counter() - start_time) * 1000
            logger.warning("Execution error in phase %s for question %s: %s", phase, item.id, e)
            return SubmissionItem(id=item.id, type=AnswerType.ABSTAIN), trace

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
            if val is None:
                return None
            if isinstance(val, str):
                return val.strip().lower() in ("true", "1", "yes", "t")
            if isinstance(val, (int, float)):
                return bool(val != 0)
            return bool(val)

        elif ans_type == AnswerType.DATE:
            val = rows[0][0]
            if val is None:
                return None
            s_val = str(val).strip()
            # Normalize timestamp to date if present (e.g. 2026-03-01 00:00:00 -> 2026-03-01)
            date_part = s_val.split()[0] if " " in s_val else s_val
            import re
            if re.match(r"^\d{4}-\d{2}(-\d{2})?$", date_part):
                return date_part
            return s_val

        elif ans_type == AnswerType.LIST:
            # Flatten column 0 into a formatted list
            res_list = []
            for r in rows:
                if r and r[0] is not None:
                    item_val = r[0]
                    if isinstance(item_val, float) and item_val.is_integer():
                        item_val = int(item_val)
                    elif isinstance(item_val, str):
                        item_val = item_val.strip()
                    res_list.append(item_val)
            return res_list

        elif ans_type == AnswerType.TABLE:
            cleaned_rows = []
            for r in rows:
                cleaned_row = []
                for cell in r:
                    if cell is not None and not isinstance(cell, (int, float, bool)):
                        cell_str = str(cell).strip().replace(",", "")
                        try:
                            f = float(cell_str)
                            cell = int(f) if f.is_integer() else round(f, 2)
                        except (ValueError, TypeError):
                            cell = str(cell).strip()
                    elif isinstance(cell, float) and cell.is_integer():
                        cell = int(cell)
                    cleaned_row.append(cell)
                cleaned_rows.append(cleaned_row)
            return {
                "columns": cols,
                "rows": cleaned_rows,
            }

        return None
