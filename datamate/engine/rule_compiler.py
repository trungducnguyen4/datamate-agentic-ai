from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Tuple
from datamate.core.nlp import VietnameseNLP, NormalizedQueryInfo
from datamate.core.types import AnswerType
from datamate.data.schema_inspector import TableInfo
from datamate.temporal.resolver import DateRange, TemporalResolver


class CompiledQueryPlan:
    def __init__(
        self,
        intent: str,
        expected_type: AnswerType,
        sql: Optional[str] = None,
        params: Tuple[Any, ...] = (),
        confidence: float = 1.0,
        unanswerable_reason: Optional[str] = None,
    ):
        self.intent = intent
        self.expected_type = expected_type
        self.sql = sql
        self.params = params
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
        # 1. Process query with Vietnamese NLP engine
        nlp_info = VietnameseNLP.process_query(question)
        clean_q = nlp_info.clean_query

        # 2. Check explicitly unanswerable question classes
        # A. Causal "Why" questions (NEG-04: Tại sao doanh thu giảm? / DIA-07: Răng doanh thu thấp hơn?)
        if nlp_info.is_why_causal:
            return CompiledQueryPlan(
                intent="unanswerable_causal_why",
                expected_type=AnswerType.UNANSWERABLE,
                confidence=1.0,
                unanswerable_reason="Causal/why questions cannot be answered from transaction tables.",
            )

        # B. Future prediction / forecasting (NEG-05 / NEG-10: Dự đoán tháng sau, ngày mai bán được bao nhiêu)
        if nlp_info.is_future:
            return CompiledQueryPlan(
                intent="unanswerable_future_forecast",
                expected_type=AnswerType.UNANSWERABLE,
                confidence=1.0,
                unanswerable_reason="Future forecasts cannot be answered without predictive models.",
            )

        # C. Profit / Cost / ROI (NEG-01 / NEG-07 / SEM-03)
        if nlp_info.is_profit_cost_query:
            has_cost = any(
                any(c.semantic_role == "cost" or "cost" in c.name.lower() or "gia_von" in c.name.lower() or "chi_phi" in c.name.lower() for c in t.columns)
                for t in tables.values()
            )
            if not has_cost:
                return CompiledQueryPlan(
                    intent="unanswerable_missing_cost",
                    expected_type=AnswerType.UNANSWERABLE,
                    confidence=1.0,
                    unanswerable_reason="Question asks for profit/cost/ROI but no cost column exists.",
                )

        # D. Expiration / Shelf life (NEG-02 / CHAT-10: Thuốc nào sắp hết hạn/date)
        if nlp_info.is_expiration_query:
            has_expiry = any(
                any(c.semantic_role == "expiry" or "hsd" in c.name.lower() or "han_su_dung" in c.name.lower() or "exp" in c.name.lower() for c in t.columns)
                for t in tables.values()
            )
            if not has_expiry:
                return CompiledQueryPlan(
                    intent="unanswerable_missing_expiry",
                    expected_type=AnswerType.UNANSWERABLE,
                    confidence=1.0,
                    unanswerable_reason="Question asks for expiry dates but schema does not provide expiry column.",
                )

        # E. Inventory / Stock (NEG-03: Kho còn bao nhiêu thuốc Panadol?)
        if nlp_info.is_stock_query:
            has_stock = any(
                any(
                    c.semantic_role == "stock"
                    or "ton_kho" in c.name.lower()
                    or c.name.lower() == "ton"
                    or "stock" in c.name.lower()
                    for c in t.columns
                )
                for t in tables.values()
            ) or any(
                t_name.lower() in ("ton_kho", "kho", "stock", "inventory")
                or "ton_kho" in t_name.lower()
                for t_name in tables
            )
            if not has_stock:
                return CompiledQueryPlan(
                    intent="unanswerable_missing_stock",
                    expected_type=AnswerType.UNANSWERABLE,
                    confidence=1.0,
                    unanswerable_reason="Question asks for warehouse stock but no inventory table/column exists.",
                )

        # F. Employee sales (NEG-08: Doanh thu của nhân viên Nguyễn Văn A?)
        if nlp_info.is_employee_query:
            has_emp = any(
                any(c.semantic_role == "employee" or "nhan_vien" in c.name.lower() or "staff" in c.name.lower() for c in t.columns)
                for t in tables.values()
            )
            if not has_emp:
                return CompiledQueryPlan(
                    intent="unanswerable_missing_employee",
                    expected_type=AnswerType.UNANSWERABLE,
                    confidence=1.0,
                    unanswerable_reason="Question asks for employee performance but no employee column exists.",
                )

        # G. Customer loyalty tier (NEG-06: Khách hàng thân thiết nhất là ai?)
        if nlp_info.is_customer_loyalty_query:
            has_loyalty = any(
                any("than_thiet" in c.name.lower() or "loyalty" in c.name.lower() or "vip" in c.name.lower() or "hang_khach" in c.name.lower() for c in t.columns)
                for t in tables.values()
            )
            if not has_loyalty:
                return CompiledQueryPlan(
                    intent="unanswerable_missing_loyalty",
                    expected_type=AnswerType.UNANSWERABLE,
                    confidence=1.0,
                    unanswerable_reason="No customer loyalty tier column or definition in schema.",
                )

        # H. Debt duration / overdue aging (SEM-07: Ai đang nợ tiền lâu nhất?)
        if nlp_info.is_debt_duration_query:
            has_debt_date = any(
                any(
                    c.semantic_role == "debt_due"
                    or any(w in c.name.lower() for w in ["ngay_den_han", "han_tra", "ngay_no", "due_date", "han_thanh_toan"])
                    for c in t.columns
                )
                for t_name, t in tables.items()
                if "no" in t_name.lower() or any(c.semantic_role == "debt" for c in t.columns)
            )
            if not has_debt_date:
                return CompiledQueryPlan(
                    intent="unanswerable_missing_debt_duration",
                    expected_type=AnswerType.UNANSWERABLE,
                    confidence=1.0,
                    unanswerable_reason="No debt date or due date column to determine duration.",
                )

        # 3. Check for Abstain conditions (ambiguous time period or subjective qualities)
        if nlp_info.is_ambiguous_time or nlp_info.is_subjective:
            return CompiledQueryPlan(
                intent="abstain_ambiguous_or_subjective",
                expected_type=AnswerType.ABSTAIN,
                confidence=0.0,
                unanswerable_reason="Ambiguous time period ('bữa giờ') or qualitative subjective criterion.",
            )

        # 4. Resolve temporal range strictly against as_of_date
        time_range = TemporalResolver.resolve(clean_q, as_of_date_str)
        if not time_range:
            time_range = TemporalResolver.resolve(question, as_of_date_str)

        if time_range and time_range.is_ambiguous:
            return CompiledQueryPlan(
                intent="abstain_ambiguous_time",
                expected_type=AnswerType.ABSTAIN,
                confidence=0.0,
            )

        # 5. Discover primary sales & debt columns
        (
            sales_table,
            date_col,
            prod_name_col,
            prod_code_col,
            qty_col,
            amount_expr,
            status_col,
            cust_col,
            order_id_col,
        ) = cls._find_sales_columns(tables)

        debt_table, debt_cust_col, debt_amount_col = cls._find_debt_columns(tables)

        # Không thể áp mốc thời gian khi bảng bán hàng không có cột ngày:
        # thà abstain (0 điểm) còn hơn trả số liệu all-time (-1 điểm).
        if time_range and not date_col:
            return CompiledQueryPlan(
                intent="abstain_no_date_column",
                expected_type=AnswerType.ABSTAIN,
                confidence=0.0,
                unanswerable_reason="Time-bounded question but the sales table has no date column.",
            )

        # If table is completely empty (0 rows) and query asks for ranking:
        if sales_table and tables[sales_table].row_count == 0:
            if nlp_info.is_quantity_ranking or nlp_info.is_revenue_ranking:
                return CompiledQueryPlan(intent="empty_table_ranking", expected_type=AnswerType.ABSTAIN)

        # Helper to construct WHERE clause
        def build_where_clause(include_status: bool = True, custom_prod: Optional[str] = None) -> str:
            clauses = []
            if include_status and status_col:
                clauses.append(
                    f"(`{status_col}` IS NULL OR ("
                    f"`{status_col}` NOT LIKE '%hủy%' AND `{status_col}` NOT LIKE '%huỷ%' AND `{status_col}` NOT LIKE '%cancel%' "
                    f"AND `{status_col}` NOT LIKE '%trả hàng%' AND `{status_col}` NOT LIKE '%đổi trả%' "
                    f"AND `{status_col}` NOT LIKE '%hoàn trả%' AND `{status_col}` NOT LIKE '%hoàn tiền%' "
                    f"AND `{status_col}` NOT LIKE '%trả lại%' AND `{status_col}` NOT LIKE '%return%' "
                    f"AND LOWER(`{status_col}`) != 'trả' AND LOWER(`{status_col}`) != 'tra'))"
                )
            if time_range and date_col:
                if time_range.is_exact_day:
                    clauses.append(f"DATE(`{date_col}`) = '{time_range.start_date}'")
                else:
                    clauses.append(f"DATE(`{date_col}`) >= '{time_range.start_date}' AND DATE(`{date_col}`) <= '{time_range.end_date}'")
            if prod_name_col:
                clauses.append(f"LOWER(`{prod_name_col}`) NOT LIKE '%phí phục vụ%'")

            if sales_table and nlp_info.category_filter:
                cat_col = next((c.name for c in tables[sales_table].columns if c.semantic_role == "category" or any(k in c.name.lower() for k in ["loai", "nhom", "cat"])), None)
                if nlp_info.category_filter == "máy":
                    if cat_col:
                        clauses.append(f"(LOWER(`{cat_col}`) LIKE '%máy mới%' OR LOWER(`{cat_col}`) LIKE '%máy cũ%' OR LOWER(`{cat_col}`) LIKE '%may moi%' OR LOWER(`{cat_col}`) LIKE '%may cu%')")
                    elif prod_name_col:
                        clauses.append(f"LOWER(`{prod_name_col}`) NOT LIKE '%phụ kiện%' AND LOWER(`{prod_name_col}`) NOT LIKE '%phu kien%'")
                elif cat_col:
                    clauses.append(f"LOWER(`{cat_col}`) LIKE '%{nlp_info.category_filter.lower()}%'")
                elif prod_name_col:
                    clauses.append(f"LOWER(`{prod_name_col}`) LIKE '%{nlp_info.category_filter.lower()}%'")

            if custom_prod:
                if prod_code_col and "sp_" in custom_prod.lower():
                    clauses.append(f"LOWER(`{prod_code_col}`) = '{custom_prod.lower()}'")
                elif prod_name_col:
                    clauses.append(f"LOWER(`{prod_name_col}`) LIKE '%{custom_prod.lower()}%'")
            elif nlp_info.has_specific_product:
                p = nlp_info.has_specific_product.lower()
                if prod_code_col and "sp_" in p:
                    clauses.append(f"LOWER(`{prod_code_col}`) = '{p}'")
                elif prod_name_col:
                    clauses.append(f"LOWER(`{prod_name_col}`) LIKE '%{p}%'")
            if nlp_info.has_specific_order and order_id_col:
                clauses.append(f"UPPER(`{order_id_col}`) = '{nlp_info.has_specific_order}'")
            return f"WHERE {' AND '.join(clauses)}" if clauses else ""

        # 6. Intent: Boolean / Zero / Negative Checks
        if nlp_info.is_zero_value_query:
            if not sales_table or not amount_expr:
                return CompiledQueryPlan(intent="zero_val", expected_type=AnswerType.UNANSWERABLE)
            sql = f"SELECT COUNT(*) FROM `{sales_table}` WHERE {amount_expr} = 0;"
            return CompiledQueryPlan(intent="zero_val", expected_type=AnswerType.NUMBER, sql=sql.strip())

        if nlp_info.is_negative_value_query:
            if not sales_table or not amount_expr:
                return CompiledQueryPlan(intent="negative_val", expected_type=AnswerType.UNANSWERABLE)
            sql = f"SELECT COUNT(*) FROM `{sales_table}` WHERE {amount_expr} < 0;"
            return CompiledQueryPlan(intent="negative_val", expected_type=AnswerType.NUMBER, sql=sql.strip())

        if nlp_info.is_success_rate_query:
            if not sales_table or not status_col:
                return CompiledQueryPlan(intent="success_rate", expected_type=AnswerType.UNANSWERABLE)
            where_str = build_where_clause(include_status=False)
            sql = f"""
            SELECT ROUND(
                100.0 * SUM(CASE WHEN `{status_col}` NOT LIKE '%hủy%' AND `{status_col}` NOT LIKE '%cancel%' THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0),
                2
            ) FROM `{sales_table}` {where_str};
            """
            return CompiledQueryPlan(intent="success_rate", expected_type=AnswerType.PERCENT, sql=sql.strip())

        if nlp_info.is_special_char_query:
            if not sales_table or not prod_name_col or not amount_expr:
                return CompiledQueryPlan(intent="special_char_sales", expected_type=AnswerType.UNANSWERABLE)
            sql = f"SELECT ROUND(COALESCE(SUM({amount_expr}), 0), 2) FROM `{sales_table}` WHERE `{prod_name_col}` GLOB '*[0-9]*' OR `{prod_name_col}` LIKE '%4 lớp%';"
            return CompiledQueryPlan(intent="special_char_sales", expected_type=AnswerType.NUMBER, sql=sql.strip())

        # 7. Intent: Specific Order lookup (e.g. "Đơn hàng mã HD07 có giá trị bao nhiêu tiền?")
        if nlp_info.has_specific_order and (nlp_info.is_revenue_query or "giá trị" in clean_q or "bao nhiêu" in clean_q):
            if not sales_table or not order_id_col or not amount_expr:
                return CompiledQueryPlan(intent="order_specific", expected_type=AnswerType.UNANSWERABLE)
            sql = f"SELECT ROUND(COALESCE(SUM({amount_expr}), 0), 2) FROM `{sales_table}` WHERE UPPER(`{order_id_col}`) = ?;"
            return CompiledQueryPlan(
                intent="order_specific",
                expected_type=AnswerType.NUMBER,
                sql=sql.strip(),
                params=(nlp_info.has_specific_order.upper(),),
            )

        # 8. Intent: Specific Customer Debt lookup (e.g. "Tổng nợ của khách hàng Bs Hùng là bao nhiêu?")
        if nlp_info.has_specific_customer and nlp_info.is_debt_query:
            if not debt_table or not debt_cust_col or not debt_amount_col:
                return CompiledQueryPlan(intent="customer_debt_specific", expected_type=AnswerType.UNANSWERABLE)
            sql = f"SELECT ROUND(COALESCE(SUM(`{debt_amount_col}`), 0), 2) FROM `{debt_table}` WHERE LOWER(`{debt_cust_col}`) LIKE ?;"
            return CompiledQueryPlan(
                intent="customer_debt_specific",
                expected_type=AnswerType.NUMBER,
                sql=sql.strip(),
                params=(f"%{nlp_info.has_specific_customer.lower()}%",),
            )

        # 9. Intent: Cancellations (must be checked before order_count to avoid counting cancellations as orders!)
        if nlp_info.is_cancellation_query:
            if not sales_table or not status_col:
                return CompiledQueryPlan(intent="cancellation", expected_type=AnswerType.UNANSWERABLE)

            where_str = build_where_clause(include_status=False)
            if nlp_info.is_canceled_revenue_query:
                where_clause = f"{where_str} AND (`{status_col}` LIKE '%hủy%' OR `{status_col}` LIKE '%cancel%')" if where_str else f"WHERE (`{status_col}` LIKE '%hủy%' OR `{status_col}` LIKE '%cancel%')"
                sql = f"SELECT ROUND(COALESCE(SUM({amount_expr}), 0), 2) FROM `{sales_table}` {where_clause};"
                return CompiledQueryPlan(intent="canceled_revenue", expected_type=AnswerType.NUMBER, sql=sql.strip())
            elif any(w in clean_q for w in ["tỷ lệ", "phần trăm", "phan tram"]):
                sql = f"""
                SELECT ROUND(
                    100.0 * SUM(CASE WHEN `{status_col}` LIKE '%hủy%' OR `{status_col}` LIKE '%cancel%' THEN 1 ELSE 0 END)
                    / NULLIF(COUNT(*), 0),
                    2
                ) FROM `{sales_table}` {where_str};
                """
                return CompiledQueryPlan(intent="cancel_rate", expected_type=AnswerType.PERCENT, sql=sql.strip())
            else:
                where_cancel = f"{where_str} AND (`{status_col}` LIKE '%hủy%' OR `{status_col}` LIKE '%cancel%')" if where_str else f"WHERE (`{status_col}` LIKE '%hủy%' OR `{status_col}` LIKE '%cancel%')"
                sql = f"SELECT COUNT(*) FROM `{sales_table}` {where_cancel};"
                return CompiledQueryPlan(intent="cancel_count", expected_type=AnswerType.NUMBER, sql=sql.strip())

        # 10. Intent: Debts
        if nlp_info.is_debt_query and not nlp_info.is_debt_duration_query:
            if not debt_table or not debt_cust_col or not debt_amount_col:
                return CompiledQueryPlan(intent="debt", expected_type=AnswerType.UNANSWERABLE)

            where_pos = f"WHERE `{debt_amount_col}` > 0"
            if nlp_info.debt_above is not None:
                sql = f"SELECT DISTINCT `{debt_cust_col}` FROM `{debt_table}` WHERE `{debt_amount_col}` > {nlp_info.debt_above} ORDER BY `{debt_cust_col}` ASC;"
                return CompiledQueryPlan(intent="debt_above", expected_type=AnswerType.LIST, sql=sql.strip())
            elif nlp_info.debt_below is not None:
                sql = f"SELECT DISTINCT `{debt_cust_col}` FROM `{debt_table}` WHERE `{debt_amount_col}` > 0 AND `{debt_amount_col}` < {nlp_info.debt_below} ORDER BY `{debt_cust_col}` ASC;"
                return CompiledQueryPlan(intent="debt_below", expected_type=AnswerType.LIST, sql=sql.strip())
            elif nlp_info.is_debt_highest:
                sql = f"SELECT `{debt_cust_col}` FROM `{debt_table}` ORDER BY `{debt_amount_col}` DESC LIMIT 1;"
                return CompiledQueryPlan(intent="debt_highest", expected_type=AnswerType.LIST, sql=sql.strip())
            elif nlp_info.is_debt_amount_query:
                sql = f"SELECT ROUND(COALESCE(SUM(`{debt_amount_col}`), 0), 2) FROM `{debt_table}` {where_pos};"
                return CompiledQueryPlan(intent="total_debt", expected_type=AnswerType.NUMBER, sql=sql.strip())
            elif nlp_info.is_debt_count_query:
                sql = f"SELECT COUNT(DISTINCT `{debt_cust_col}`) FROM `{debt_table}` {where_pos};"
                return CompiledQueryPlan(intent="debt_count", expected_type=AnswerType.NUMBER, sql=sql.strip())
            elif nlp_info.is_debt_max_query:
                sql = f"SELECT ROUND(COALESCE(MAX(`{debt_amount_col}`), 0), 2) FROM `{debt_table}`; "
                return CompiledQueryPlan(intent="debt_max", expected_type=AnswerType.NUMBER, sql=sql.strip())
            elif nlp_info.is_debt_min_query:
                sql = f"SELECT ROUND(COALESCE(MIN(`{debt_amount_col}`), 0), 2) FROM `{debt_table}` {where_pos};"
                return CompiledQueryPlan(intent="debt_min", expected_type=AnswerType.NUMBER, sql=sql.strip())
            else:
                sql = f"SELECT DISTINCT `{debt_cust_col}` FROM `{debt_table}` {where_pos} ORDER BY `{debt_cust_col}` ASC;"
                return CompiledQueryPlan(intent="debt_customers_list", expected_type=AnswerType.LIST, sql=sql.strip())

        # 11. Intent: Order Max / Order Min value or ID
        if nlp_info.is_order_max_query:
            if not sales_table or not amount_expr:
                return CompiledQueryPlan(intent="order_max", expected_type=AnswerType.UNANSWERABLE)
            where_str = build_where_clause()
            # If asking specifically about amount/value:
            if any(w in clean_q for w in ["trị giá bao nhiêu", "bao nhiêu tiền"]) or bool(re.search(r"giá trị.*cao nhất.*bao nhiêu", clean_q)):
                sql = f"SELECT ROUND(COALESCE(MAX({amount_expr}), 0), 2) FROM `{sales_table}` {where_str};"
                return CompiledQueryPlan(intent="order_max_value", expected_type=AnswerType.NUMBER, sql=sql.strip())
            else:
                target_col = f"`{order_id_col}`" if order_id_col else amount_expr
                res_type = AnswerType.STRING if order_id_col else AnswerType.NUMBER
                sql = f"SELECT {target_col} FROM `{sales_table}` {where_str} ORDER BY {amount_expr} DESC LIMIT 1;"
                return CompiledQueryPlan(intent="order_max", expected_type=res_type, sql=sql.strip())

        if nlp_info.is_order_min_query:
            if not sales_table or not amount_expr:
                return CompiledQueryPlan(intent="order_min", expected_type=AnswerType.UNANSWERABLE)
            where_str = build_where_clause()
            if any(w in clean_q for w in ["trị giá bao nhiêu", "bao nhiêu tiền", "là bao nhiêu"]):
                sql = f"SELECT ROUND(COALESCE(MIN({amount_expr}), 0), 2) FROM `{sales_table}` {where_str};"
                return CompiledQueryPlan(intent="order_min_value", expected_type=AnswerType.NUMBER, sql=sql.strip())
            else:
                target_col = f"`{order_id_col}`" if order_id_col else amount_expr
                res_type = AnswerType.STRING if order_id_col else AnswerType.NUMBER
                sql = f"SELECT {target_col} FROM `{sales_table}` {where_str} ORDER BY {amount_expr} ASC LIMIT 1;"
                return CompiledQueryPlan(intent="order_min", expected_type=res_type, sql=sql.strip())

        # 11b. Intent: Average per order queries (BM_AGG_01, BM_AGG_05)
        if nlp_info.is_avg_order_revenue_query:
            if not sales_table or not amount_expr:
                return CompiledQueryPlan(intent="avg_order_revenue", expected_type=AnswerType.UNANSWERABLE)
            where_str = build_where_clause()
            order_div = f"COUNT(DISTINCT `{order_id_col}`)" if order_id_col else "COUNT(*)"
            sql = f"SELECT ROUND(SUM({amount_expr}) * 1.0 / NULLIF({order_div}, 0), 2) FROM `{sales_table}` {where_str};"
            return CompiledQueryPlan(intent="avg_order_revenue", expected_type=AnswerType.NUMBER, sql=sql.strip())

        if nlp_info.is_avg_order_qty_query:
            if not sales_table or not qty_col:
                return CompiledQueryPlan(intent="avg_order_qty", expected_type=AnswerType.UNANSWERABLE)
            where_str = build_where_clause()
            order_div = f"COUNT(DISTINCT `{order_id_col}`)" if order_id_col else "COUNT(*)"
            sql = f"SELECT ROUND(SUM(`{qty_col}`) * 1.0 / NULLIF({order_div}, 0), 2) FROM `{sales_table}` {where_str};"
            return CompiledQueryPlan(intent="avg_order_qty", expected_type=AnswerType.NUMBER, sql=sql.strip())

        # 12. Intent: Distinct products count (BM_MULTI_20)
        if nlp_info.is_distinct_product_query:
            if not sales_table or not prod_name_col:
                return CompiledQueryPlan(intent="distinct_products", expected_type=AnswerType.UNANSWERABLE)
            where_str = build_where_clause()
            sql = f"SELECT COUNT(DISTINCT `{prod_name_col}`) FROM `{sales_table}` {where_str};"
            return CompiledQueryPlan(intent="distinct_products", expected_type=AnswerType.NUMBER, sql=sql.strip())

        # 13. Intent: Order count (SEM-10: Tháng này bán được bao nhiêu đơn?)
        if nlp_info.is_order_count_query:
            if not sales_table:
                return CompiledQueryPlan(intent="order_count", expected_type=AnswerType.UNANSWERABLE)
            where_str = build_where_clause()
            if order_id_col:
                sql = f"SELECT COUNT(DISTINCT `{order_id_col}`) FROM `{sales_table}` {where_str};"
            else:
                sql = f"SELECT COUNT(*) FROM `{sales_table}` {where_str};"
            return CompiledQueryPlan(intent="order_count", expected_type=AnswerType.NUMBER, sql=sql.strip())

        # 13. Intent: Best customer / Top buyer (SEM-05 / Rule 48: Đơn khách lẻ không tính)
        if nlp_info.is_customer_query:
            if not sales_table or not cust_col:
                return CompiledQueryPlan(intent="top_customer", expected_type=AnswerType.UNANSWERABLE, unanswerable_reason="Missing customer column in sales data.")
            where_str = build_where_clause()
            if any(w in clean_q for w in ["nhiều đơn", "số đơn", "nhiều đơn nhất", "nhiều lần mua"]):
                sum_expr = f"COUNT(DISTINCT `{order_id_col}`)" if order_id_col else "COUNT(*)"
            else:
                sum_expr = amount_expr if amount_expr else (f"SUM(`{qty_col}`)" if qty_col else "COUNT(*)")
            no_retail = f"(LOWER(TRIM(`{cust_col}`)) NOT IN ('lẻ', 'le', 'kl', 'khách lẻ', 'khach le', 'khách vãng lai', 'khach vang lai', 'vãng lai', 'vang lai', '') AND LOWER(`{cust_col}`) NOT LIKE '%khách lẻ%' AND LOWER(`{cust_col}`) NOT LIKE '%khach le%' AND LOWER(`{cust_col}`) NOT LIKE '%vãng lai%')"
            where_join = f"{where_str} AND `{cust_col}` IS NOT NULL AND {no_retail}" if where_str else f"WHERE `{cust_col}` IS NOT NULL AND {no_retail}"
            sql = f"""
            SELECT `{cust_col}`
            FROM `{sales_table}`
            {where_join}
            GROUP BY `{cust_col}`
            ORDER BY {sum_expr} DESC
            LIMIT 1;
            """
            return CompiledQueryPlan(intent="top_customer", expected_type=AnswerType.STRING, sql=sql.strip())

        # 14. Intent: Unsold products check (Grounded against Catalog and Sales)
        if nlp_info.is_unsold_query:
            catalog_tbl, catalog_prod_col = cls._find_catalog_table(tables, sales_table, prod_name_col)
            if not sales_table:
                return CompiledQueryPlan(intent="unsold_check", expected_type=AnswerType.UNANSWERABLE, unanswerable_reason="Missing sales table.")

            # Grounding check: without catalog/inventory table, we cannot infer unsold products from sales logs alone
            if not catalog_tbl or not catalog_prod_col:
                return CompiledQueryPlan(
                    intent="unsold_check",
                    expected_type=AnswerType.UNANSWERABLE,
                    unanswerable_reason="Chỉ có bảng giao dịch, thiếu bảng danh mục sản phẩm (catalog) hoặc kho để đối chiếu sản phẩm chưa bán."
                )

            where_str = build_where_clause()
            sales_subquery = f"SELECT DISTINCT `{prod_name_col}` FROM `{sales_table}` {where_str}" if prod_name_col else f"SELECT DISTINCT 1 FROM `{sales_table}`"
            sql = f"SELECT CASE WHEN EXISTS (SELECT 1 FROM `{catalog_tbl}` WHERE `{catalog_prod_col}` NOT IN ({sales_subquery})) THEN 1 ELSE 0 END;"
            return CompiledQueryPlan(
                intent="unsold_check",
                expected_type=AnswerType.BOOLEAN,
                sql=sql.strip(),
                confidence=0.92,
            )

        # 15. Intent: Specific Product Quantity / Revenue query
        if nlp_info.has_specific_product and not nlp_info.is_revenue_ranking and not nlp_info.is_quantity_ranking:
            if not sales_table:
                return CompiledQueryPlan(intent="product_metric", expected_type=AnswerType.UNANSWERABLE)
            where_str = build_where_clause()
            if nlp_info.is_revenue_query:
                sql = f"SELECT ROUND(COALESCE(SUM({amount_expr}), 0), 2) FROM `{sales_table}` {where_str};"
                return CompiledQueryPlan(intent="product_revenue", expected_type=AnswerType.NUMBER, sql=sql.strip())
            else:
                target_expr = f"`{qty_col}`" if qty_col else amount_expr
                sql = f"SELECT ROUND(COALESCE(SUM({target_expr}), 0), 2) FROM `{sales_table}` {where_str};"
                return CompiledQueryPlan(intent="product_quantity", expected_type=AnswerType.NUMBER, sql=sql.strip())

        # 16. Intent: Product Ranking by REVENUE (SEM-02 / SEM-08 / BM_FORMAL_01)
        if nlp_info.is_revenue_ranking or (nlp_info.is_revenue_query and nlp_info.is_lowest_ranking):
            if not sales_table or not prod_name_col or not amount_expr:
                return CompiledQueryPlan(intent="ranking_product_revenue", expected_type=AnswerType.UNANSWERABLE)

            where_str = build_where_clause()
            order_dir = "ASC" if nlp_info.is_lowest_ranking else "DESC"
            group_expr = f"`{prod_name_col}`, `{prod_code_col}`" if prod_code_col else f"`{prod_name_col}`"
            tie_breaker = f", `{prod_code_col}` ASC" if prod_code_col else f", `{prod_name_col}` ASC"

            k = nlp_info.top_k or 1
            exp_type = AnswerType.LIST if k > 1 else AnswerType.STRING
            sql = f"""
            SELECT `{prod_name_col}`
            FROM `{sales_table}`
            {where_str}
            GROUP BY {group_expr}
            ORDER BY SUM({amount_expr}) {order_dir} {tie_breaker}
            LIMIT {k};
            """
            return CompiledQueryPlan(
                intent="ranking_product_revenue",
                expected_type=exp_type,
                sql=sql.strip(),
                confidence=0.96,
            )

        # 17. Intent: Product Ranking by QUANTITY SOLD (SEM-01 / SEM-06 / VN-01 / VN-02)
        if nlp_info.is_quantity_ranking or nlp_info.is_lowest_ranking:
            if not sales_table or not prod_name_col:
                return CompiledQueryPlan(intent="ranking_product_quantity", expected_type=AnswerType.UNANSWERABLE)

            where_str = build_where_clause()
            order_dir = "ASC" if nlp_info.is_lowest_ranking else "DESC"

            # Check if query asks specifically about buyers (người mua / khách mua)
            if any(w in clean_q for w in ["người mua", "khách mua", "nguoi mua", "khach mua"]) and cust_col:
                sum_target = f"COUNT(DISTINCT `{cust_col}`)"
                secondary_sort = f", SUM(`{qty_col}`) {order_dir}" if qty_col else ""
            else:
                sum_target = f"SUM(`{qty_col}`)" if qty_col else "COUNT(*)"
                secondary_sort = ""

            tie_breaker = f"{secondary_sort}, `{prod_code_col}` ASC" if prod_code_col else f"{secondary_sort}, `{prod_name_col}` ASC"
            group_expr = f"`{prod_name_col}`, `{prod_code_col}`" if prod_code_col else f"`{prod_name_col}`"

            k = nlp_info.top_k or 1
            exp_type = AnswerType.LIST if k > 1 else AnswerType.STRING
            sql = f"""
            SELECT `{prod_name_col}`
            FROM `{sales_table}`
            {where_str}
            GROUP BY {group_expr}
            ORDER BY {sum_target} {order_dir} {tie_breaker}
            LIMIT {k};
            """
            return CompiledQueryPlan(
                intent="ranking_product_quantity",
                expected_type=exp_type,
                sql=sql.strip(),
                confidence=0.96,
            )

        # 17b. Intent: Which Day Query (AnswerType.DATE)
        if nlp_info.is_which_day_query:
            if not sales_table or not date_col:
                return CompiledQueryPlan(intent="which_day", expected_type=AnswerType.UNANSWERABLE)
            metric = amount_expr if (nlp_info.is_revenue_query or not nlp_info.is_quantity_query) else (qty_col or amount_expr)
            where_str = build_where_clause()
            sql = f"""
            SELECT DATE(`{date_col}`)
            FROM `{sales_table}`
            {where_str}
            GROUP BY DATE(`{date_col}`)
            ORDER BY SUM({metric}) DESC, DATE(`{date_col}`) ASC
            LIMIT 1;
            """
            return CompiledQueryPlan(intent="which_day", expected_type=AnswerType.DATE, sql=sql.strip(), confidence=0.96)

        # 17c. Intent: Which Month Query (AnswerType.DATE)
        if nlp_info.is_which_month_query:
            if not sales_table or not date_col:
                return CompiledQueryPlan(intent="which_month", expected_type=AnswerType.UNANSWERABLE)
            metric = amount_expr if (nlp_info.is_revenue_query or not nlp_info.is_quantity_query) else (qty_col or amount_expr)
            where_str = build_where_clause()
            sql = f"""
            SELECT SUBSTR(DATE(`{date_col}`), 1, 7)
            FROM `{sales_table}`
            {where_str}
            GROUP BY SUBSTR(DATE(`{date_col}`), 1, 7)
            ORDER BY SUM({metric}) DESC, SUBSTR(DATE(`{date_col}`), 1, 7) ASC
            LIMIT 1;
            """
            return CompiledQueryPlan(intent="which_month", expected_type=AnswerType.DATE, sql=sql.strip(), confidence=0.96)

        # 17d. Intent: Cancellation Rate (Rule 18: AnswerType.PERCENT)
        if nlp_info.is_cancellation_rate_query:
            if not sales_table or not status_col:
                return CompiledQueryPlan(intent="cancellation_rate", expected_type=AnswerType.UNANSWERABLE)
            where_str = build_where_clause(include_status=False)
            id_expr = f"`{order_id_col}`" if order_id_col else "*"
            sql = f"""
            SELECT ROUND(
                100.0 * COUNT(DISTINCT CASE WHEN LOWER(`{status_col}`) LIKE '%hủy%' OR LOWER(`{status_col}`) LIKE '%cancel%' OR LOWER(`{status_col}`) LIKE '%trả%' OR LOWER(`{status_col}`) LIKE '%tra%' THEN {id_expr} END)
                / NULLIF(COUNT(DISTINCT {id_expr}), 0),
                2
            )
            FROM `{sales_table}`
            {where_str};
            """
            return CompiledQueryPlan(intent="cancellation_rate", expected_type=AnswerType.PERCENT, sql=sql.strip(), confidence=0.95)

        # 17e. Intent: Specific Column Target (e.g. thu_may_cu, khach_tra, bot)
        if nlp_info.metric_target and sales_table:
            matched_col = next((c.name for c in tables[sales_table].columns if nlp_info.metric_target in c.name.lower()), None)
            if matched_col:
                where_str = build_where_clause()
                sql = f"SELECT ROUND(COALESCE(SUM(`{matched_col}`), 0), 2) FROM `{sales_table}` {where_str};"
                return CompiledQueryPlan(intent=f"metric_{nlp_info.metric_target}", expected_type=AnswerType.NUMBER, sql=sql.strip(), confidence=0.96)

        # 17f. Intent: Debt Table (AnswerType.TABLE)
        if nlp_info.is_table_query and debt_table and debt_cust_col and debt_amount_col:
            k = nlp_info.top_k or 5
            sql = f"""
            SELECT `{debt_cust_col}` AS khach_hang, ROUND(`{debt_amount_col}`) AS so_tien_no
            FROM `{debt_table}`
            WHERE `{debt_amount_col}` > 0
            ORDER BY `{debt_amount_col}` DESC
            LIMIT {k};
            """
            return CompiledQueryPlan(intent="debt_table", expected_type=AnswerType.TABLE, sql=sql.strip(), confidence=0.95)

        # 18. Intent: Total Revenue
        if nlp_info.is_revenue_query:
            if not sales_table or not amount_expr:
                return CompiledQueryPlan(intent="revenue", expected_type=AnswerType.UNANSWERABLE)

            where_str = build_where_clause()
            sql = f"SELECT ROUND(COALESCE(SUM({amount_expr}), 0), 2) FROM `{sales_table}` {where_str};"
            return CompiledQueryPlan(intent="revenue", expected_type=AnswerType.NUMBER, sql=sql.strip(), confidence=0.95)

        # 19. Intent: Total Quantity Sold
        if nlp_info.is_quantity_query or any(w in clean_q for w in ["bán được bao nhiêu", "số lượng bán", "tiêu thụ được bao nhiêu"]):
            if not sales_table:
                return CompiledQueryPlan(intent="quantity", expected_type=AnswerType.UNANSWERABLE)

            where_str = build_where_clause()
            target_expr = f"`{qty_col}`" if qty_col else amount_expr
            sql = f"SELECT ROUND(COALESCE(SUM({target_expr}), 0), 2) FROM `{sales_table}` {where_str};"
            return CompiledQueryPlan(intent="quantity", expected_type=AnswerType.NUMBER, sql=sql.strip(), confidence=0.92)

        # Default fallback: return ABSTAIN to prevent -1 penalty
        return CompiledQueryPlan(
            intent="unknown",
            expected_type=AnswerType.ABSTAIN,
            confidence=0.0,
        )

    @classmethod
    def _find_sales_columns(
        cls, tables: Dict[str, TableInfo]
    ) -> Tuple[
        Optional[str],
        Optional[str],
        Optional[str],
        Optional[str],
        Optional[str],
        Optional[str],
        Optional[str],
        Optional[str],
        Optional[str],
    ]:
        sales_table = None
        if "_sales_unified" in tables:
            sales_table = "_sales_unified"
        else:
            best_score = -1
            for t_name, t_info in tables.items():
                lower = t_name.lower()
                if not any(k in lower for k in ["hoa_don", "don_hang", "ban_hang", "sales", "orders", "giao_dich"]):
                    continue
                roles = {c.semantic_role for c in t_info.columns if c.semantic_role}
                score = (
                    8 * ("date" in roles)
                    + 4 * ("total_amount" in roles)
                    + 2 * ("product" in roles)
                    + 1 * ("quantity" in roles)
                )
                if score > best_score:
                    best_score = score
                    sales_table = t_name
        if not sales_table and tables:
            sales_table = max(tables.keys(), key=lambda k: tables[k].row_count)

        if not sales_table:
            return None, None, None, None, None, None, None, None, None

        t = tables[sales_table]
        date_col = None
        prod_name_col = None
        prod_code_col = None
        qty_col = None
        amount_expr = None
        status_col = None
        cust_col = None
        order_id_col = None

        unit_price_col = None
        discount_col = None

        for c in t.columns:
            name_lower = c.name.lower()
            if c.semantic_role == "customer":
                cust_col = c.name
            elif c.semantic_role == "status":
                status_col = c.name
            elif c.semantic_role == "date" and not date_col:
                date_col = c.name
            elif c.semantic_role == "total_amount":
                amount_expr = f"`{c.name}`"
            elif c.semantic_role == "unit_price":
                unit_price_col = c.name
            elif c.semantic_role == "quantity":
                qty_col = c.name
            elif c.semantic_role == "product":
                if any(k in name_lower for k in ["ma", "code", "id"]):
                    prod_code_col = c.name
                else:
                    prod_name_col = c.name
            elif c.semantic_role == "order_id" or any(k in name_lower for k in ["ma_don", "ma_hd", "ma_hoa_don", "hoa_don", "order_id", "invoice_id", "so_hd", "so_don"]):
                order_id_col = c.name
            elif any(k in name_lower for k in ["giam_gia", "chiet_khau", "discount"]):
                discount_col = c.name

        if not amount_expr and qty_col and unit_price_col:
            disc = f" - COALESCE(`{discount_col}`, 0)" if discount_col else ""
            amount_expr = f"(`{qty_col}` * `{unit_price_col}`{disc})"

        return (
            sales_table,
            date_col,
            prod_name_col,
            prod_code_col,
            qty_col,
            amount_expr,
            status_col,
            cust_col,
            order_id_col,
        )

    @classmethod
    def _find_debt_columns(
        cls, tables: Dict[str, TableInfo]
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        debt_table = None
        for t_name, t_info in tables.items():
            lower = t_name.lower()
            if any(k in lower for k in ["so_no", "cong_no", "debt", "no_phai_thu"]):
                debt_table = t_name
                break

        if not debt_table:
            for t_name, t_info in tables.items():
                if any(c.semantic_role == "debt" for c in t_info.columns):
                    debt_table = t_name
                    break

        if not debt_table:
            return None, None, None

        t = tables[debt_table]
        debt_cust_col = None
        debt_amount_col = None

        for c in t.columns:
            if c.semantic_role == "customer" or "khach" in c.name.lower():
                debt_cust_col = c.name
            elif c.semantic_role == "debt" or any(k in c.name.lower() for k in ["tong_no", "cong_no", "so_tien", "tien_no"]):
                debt_amount_col = c.name

        return debt_table, debt_cust_col, debt_amount_col

    @classmethod
    def _find_catalog_table(
        cls, tables: Dict[str, TableInfo], sales_table: Optional[str], sales_prod_col: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """Find catalog/inventory dimension table and matching product column."""
        for t_name, t_info in tables.items():
            if t_name == sales_table:
                continue
            lower = t_name.lower()
            if any(k in lower for k in ["san_pham", "sp", "hang_hoa", "danh_muc", "kho", "ton_kho", "catalog", "products"]):
                is_sales_code = bool(sales_prod_col and any(k in sales_prod_col.lower() for k in ["ma", "code", "id"]))
                if is_sales_code:
                    for c in t_info.columns:
                        if any(k in c.name.lower() for k in ["ma_sp", "ma_thuoc", "ma_san_pham", "product_id", "code"]):
                            return t_name, c.name
                else:
                    for c in t_info.columns:
                        if any(k in c.name.lower() for k in ["ten_sp", "ten_thuoc", "ten_san_pham", "ten_hang", "name"]):
                            return t_name, c.name

                for c in t_info.columns:
                    if c.semantic_role == "product":
                        return t_name, c.name
                if t_info.columns:
                    return t_name, t_info.columns[0].name
        return None, None
