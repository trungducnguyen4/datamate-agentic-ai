from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Tuple
from datamate.core.types import AnswerType
from datamate.data.schema_inspector import TableInfo
from datamate.temporal.resolver import DateRange, TemporalResolver


class CompiledQueryPlan:
    def __init__(
        self,
        intent: str,
        expected_type: AnswerType,
        sql: Optional[str] = None,
        confidence: float = 1.0,
        unanswerable_reason: Optional[str] = None,
    ):
        self.intent = intent
        self.expected_type = expected_type
        self.sql = sql
        self.confidence = confidence
        self.unanswerable_reason = unanswerable_reason


class BusinessRuleCompiler:
    """Compiles Vietnamese natural language questions into safe SQL query plans."""

    @classmethod
    def compile(
        cls,
        question: str,
        as_of_date_str: str,
        tables: Dict[str, TableInfo],
    ) -> CompiledQueryPlan:
        q_lower = question.lower()
        time_range = TemporalResolver.resolve(question, as_of_date_str)

        # 1. Check for Unanswerable signals
        # If question asks for cost/profit but no cost column exists
        if any(w in q_lower for w in ["lợi nhuận", "lãi ròng", "giá vốn", "chi phí nhập"]):
            has_cost = any(
                any("gia_von" in c.name or "cost" in c.name or "chi_phi" in c.name for c in t.columns)
                for t in tables.values()
            )
            if not has_cost:
                return CompiledQueryPlan(
                    intent="unanswerable_missing_cost",
                    expected_type=AnswerType.UNANSWERABLE,
                    confidence=1.0,
                    unanswerable_reason="Question asks for profit/cost but no cost column exists in tables.",
                )

        # Find primary table for orders / sales
        sales_table, date_col, prod_name_col, prod_code_col, qty_col, amount_col, status_col, cust_col = (
            cls._find_sales_columns(tables)
        )

        # 2. Ranking / Best-selling product or item ("bán chạy nhất", "món bán chạy", "nhiều nhất", etc.)
        ranking_keywords = [
            "bán chạy", "bán dc", "bán được", "bán nhiều", "bán ít",
            "mua nhiều nhất", "được mua nhiều nhất", "chạy nhất", "nhiều nhất",
            "ít nhất", "thấp nhất", "cao nhất", "top"
        ]
        if any(w in q_lower for w in ranking_keywords) and not any(w in q_lower for w in ["tỷ lệ", "phần trăm", "ai nợ"]):
            if not sales_table or not prod_name_col:
                return CompiledQueryPlan(
                    intent="ranking_product",
                    expected_type=AnswerType.UNANSWERABLE,
                    unanswerable_reason="Missing sales table or product column.",
                )

            # Build where clause with date range and valid order filter
            where_clauses = []
            if status_col:
                where_clauses.append(f"`{status_col}` NOT LIKE '%hủy%' AND `{status_col}` NOT LIKE '%cancel%'")
            if time_range and date_col:
                where_clauses.append(f"`{date_col}` >= '{time_range.start_date}' AND `{date_col}` <= '{time_range.end_date}'")

            where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            order_dir = "ASC" if any(w in q_lower for w in ["ít nhất", "thấp nhất"]) else "DESC"
            
            # Ranking criterion: revenue vs quantity
            if any(w in q_lower for w in ["doanh thu", "doanh số", "tiền"]) and amount_col:
                sum_target = f"SUM({amount_col})"
            else:
                sum_target = f"SUM(`{qty_col}`)" if qty_col else "COUNT(*)"

            tie_breaker = f", `{prod_code_col}` ASC" if prod_code_col else f", `{prod_name_col}` ASC"

            sql = f"""
            SELECT `{prod_name_col}`
            FROM `{sales_table}`
            {where_str}
            GROUP BY `{prod_name_col}`
            ORDER BY {sum_target} {order_dir} {tie_breaker}
            LIMIT 1;
            """
            return CompiledQueryPlan(
                intent="ranking_product_top1",
                expected_type=AnswerType.STRING,
                sql=sql.strip(),
                confidence=0.95,
            )

        # 3. Total Revenue ("doanh thu", "tổng tiền", "doanh số")
        if any(w in q_lower for w in ["doanh thu", "tổng tiền", "doanh số", "thu được bao nhiêu"]):
            if not sales_table or not amount_col:
                return CompiledQueryPlan(
                    intent="revenue",
                    expected_type=AnswerType.UNANSWERABLE,
                    unanswerable_reason="Missing sales table or amount column.",
                )

            where_clauses = []
            if status_col:
                where_clauses.append(f"`{status_col}` NOT LIKE '%hủy%' AND `{status_col}` NOT LIKE '%cancel%'")
            if time_range and date_col:
                where_clauses.append(f"`{date_col}` >= '{time_range.start_date}' AND `{date_col}` <= '{time_range.end_date}'")

            where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            sql = f"SELECT ROUND(COALESCE(SUM({amount_col}), 0), 2) FROM `{sales_table}` {where_str};"
            return CompiledQueryPlan(
                intent="revenue",
                expected_type=AnswerType.NUMBER,
                sql=sql.strip(),
                confidence=0.95,
            )

        # 4. Total Quantity ("bán được bao nhiêu", "số lượng bán")
        if any(w in q_lower for w in ["bán được bao nhiêu ly", "bán được bao nhiêu cái", "số lượng bán", "bán được bao nhiêu"]):
            if not sales_table:
                return CompiledQueryPlan(
                    intent="quantity",
                    expected_type=AnswerType.UNANSWERABLE,
                )

            where_clauses = []
            if status_col:
                where_clauses.append(f"`{status_col}` NOT LIKE '%hủy%' AND `{status_col}` NOT LIKE '%cancel%'")
            if time_range and date_col:
                where_clauses.append(f"`{date_col}` >= '{time_range.start_date}' AND `{date_col}` <= '{time_range.end_date}'")

            where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
            target_expr = f"`{qty_col}`" if qty_col else amount_col
            sql = f"SELECT ROUND(COALESCE(SUM({target_expr}), 0), 2) FROM `{sales_table}` {where_str};"
            return CompiledQueryPlan(
                intent="quantity",
                expected_type=AnswerType.NUMBER,
                sql=sql.strip(),
                confidence=0.9,
            )

        # 5. Cancellations ("bao nhiêu đơn hủy", "tỷ lệ hủy")
        if any(w in q_lower for w in ["hủy", "cancel"]):
            if not sales_table or not status_col:
                return CompiledQueryPlan(
                    intent="cancellation",
                    expected_type=AnswerType.UNANSWERABLE,
                )

            where_clauses = []
            if time_range and date_col:
                where_clauses.append(f"`{date_col}` >= '{time_range.start_date}' AND `{date_col}` <= '{time_range.end_date}'")
            where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            if "tỷ lệ" in q_lower or "phần trăm" in q_lower:
                sql = f"""
                SELECT ROUND(
                    100.0 * SUM(CASE WHEN `{status_col}` LIKE '%hủy%' OR `{status_col}` LIKE '%cancel%' THEN 1 ELSE 0 END)
                    / NULLIF(COUNT(*), 0),
                    2
                ) FROM `{sales_table}` {where_str};
                """
                return CompiledQueryPlan(
                    intent="cancel_rate",
                    expected_type=AnswerType.PERCENT,
                    sql=sql.strip(),
                    confidence=0.92,
                )
            else:
                sql = f"""
                SELECT SUM(CASE WHEN `{status_col}` LIKE '%hủy%' OR `{status_col}` LIKE '%cancel%' THEN 1 ELSE 0 END)
                FROM `{sales_table}` {where_str};
                """
                return CompiledQueryPlan(
                    intent="cancel_count",
                    expected_type=AnswerType.NUMBER,
                    sql=sql.strip(),
                    confidence=0.92,
                )

        # 6. Debts / Unpaid customers ("còn ai nợ tiền", "ai nợ tiền chưa trả")
        if any(w in q_lower for w in ["nợ", "còn ai nợ", "chưa trả"]):
            debt_table, debt_cust_col, debt_amount_col = cls._find_debt_columns(tables)
            if not debt_table or not debt_cust_col:
                return CompiledQueryPlan(
                    intent="debt_customers",
                    expected_type=AnswerType.UNANSWERABLE,
                    unanswerable_reason="No debt table or customer column found.",
                )

            where_clause = f"WHERE `{debt_amount_col}` > 0" if debt_amount_col else ""
            if "tổng nợ" in q_lower or "bao nhiêu tiền nợ" in q_lower:
                sql = f"SELECT ROUND(COALESCE(SUM(`{debt_amount_col}`), 0), 2) FROM `{debt_table}` {where_clause};"
                return CompiledQueryPlan(
                    intent="total_debt",
                    expected_type=AnswerType.NUMBER,
                    sql=sql.strip(),
                    confidence=0.9,
                )
            else:
                sql = f"SELECT DISTINCT `{debt_cust_col}` FROM `{debt_table}` {where_clause} ORDER BY `{debt_cust_col}` ASC;"
                return CompiledQueryPlan(
                    intent="debt_customers_list",
                    expected_type=AnswerType.LIST,
                    sql=sql.strip(),
                    confidence=0.88,
                )

        # Default fallback: When intent cannot be identified with high confidence,
        # return ABSTAIN to prevent -1 penalty!
        return CompiledQueryPlan(
            intent="unknown",
            expected_type=AnswerType.ABSTAIN,
            confidence=0.0,
        )

    @classmethod
    def _find_sales_columns(
        cls, tables: Dict[str, TableInfo]
    ) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
        for tbl_name, tbl_info in tables.items():
            date_col = None
            prod_name_col = None
            prod_code_col = None
            qty_col = None
            total_amount_col = None
            unit_price_col = None
            status_col = None
            cust_col = None

            for col in tbl_info.columns:
                c_name = col.name
                c_lower = c_name.lower()
                role = col.semantic_role

                if role == "date" and not date_col:
                    date_col = c_name
                elif role == "product":
                    if "ma" in c_lower or "code" in c_lower:
                        prod_code_col = c_name
                    else:
                        prod_name_col = c_name
                elif role == "quantity" and not qty_col:
                    qty_col = c_name
                elif role == "total_amount" and not total_amount_col:
                    total_amount_col = c_name
                elif role == "unit_price" and not unit_price_col:
                    unit_price_col = c_name
                elif role == "status" and not status_col:
                    status_col = c_name
                elif role == "customer" and not cust_col:
                    cust_col = c_name

            # If prod_name_col was not matched by keyword, try fallback text column
            if not prod_name_col:
                for col in tbl_info.columns:
                    if col.name not in (date_col, status_col, cust_col, qty_col, total_amount_col, unit_price_col):
                        if "text" in col.data_type.lower() or not col.semantic_role:
                            prod_name_col = col.name
                            break

            # Determine best amount expression
            if total_amount_col:
                amount_expr = f"`{total_amount_col}`"
            elif unit_price_col and qty_col:
                amount_expr = f"(`{unit_price_col}` * `{qty_col}`)"
            elif unit_price_col:
                amount_expr = f"`{unit_price_col}`"
            else:
                amount_expr = None

            if amount_expr or qty_col or prod_name_col:
                return tbl_name, date_col, prod_name_col, prod_code_col, qty_col, amount_expr, status_col, cust_col

        return None, None, None, None, None, None, None, None

    @classmethod
    def _find_debt_columns(
        cls, tables: Dict[str, TableInfo]
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        for tbl_name, tbl_info in tables.items():
            cust_col = None
            debt_col = None
            for col in tbl_info.columns:
                c_lower = col.name.lower()
                if "khach" in c_lower or "customer" in c_lower or "ten" in c_lower:
                    cust_col = col.name
                if "no" in c_lower or "debt" in c_lower or "con_lai" in c_lower:
                    debt_col = col.name
            if debt_col and cust_col:
                return tbl_name, cust_col, debt_col
        return None, None, None
