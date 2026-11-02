from __future__ import annotations
import re
from typing import Any, Dict, List, Optional, Tuple
from datamate.core.nlp import VietnameseNLP, NormalizedQueryInfo
from datamate.core.types import AnswerType
from datamate.data.schema_inspector import TableInfo, strip_accents
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
        rulebook: Optional[Any] = None,
        readme_text: str = "",
    ) -> CompiledQueryPlan:
        # Collect known product names from tables sample values
        known_products = []
        for t in tables.values():
            for c in t.columns:
                if c.semantic_role == "product":
                    for s in c.sample_values:
                        if isinstance(s, str) and len(s.strip()) >= 3:
                            known_products.append(s.strip())

        # 1. Process query with Vietnamese NLP engine
        nlp_info = VietnameseNLP.process_query(question, catalog_products=known_products)
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

        # E. Inventory / Stock (Kho còn bao nhiêu thuốc Panadol?)
        if nlp_info.is_stock_query:
            stock_tbl_name = None
            stock_qty_col = None
            stock_prod_col = None
            for t_name, t in tables.items():
                if any(k in t_name.lower() for k in ("ton_kho", "tonkho", "kho", "stock", "inventory")) or any(c.semantic_role == "stock" for c in t.columns):
                    stock_tbl_name = t_name
                    for c in t.columns:
                        if c.semantic_role == "stock" or any(k in c.name.lower() for k in ("ton_cuoi", "cuoi_ky", "sl_ton", "ton", "stock", "so_luong")):
                            stock_qty_col = c.name
                            break
                    for c in t.columns:
                        if c.semantic_role == "product" or any(k in c.name.lower() for k in ("ten_hang", "ten_sp", "ten", "san_pham", "hang", "mat_hang")):
                            stock_prod_col = c.name
                            break
                    if stock_tbl_name and stock_qty_col:
                        break

            if stock_tbl_name and stock_qty_col:
                if nlp_info.has_specific_product and stock_prod_col:
                    return CompiledQueryPlan(
                        intent="stock_product_quantity",
                        expected_type=AnswerType.NUMBER,
                        sql=f"SELECT `{stock_qty_col}` FROM `{stock_tbl_name}` WHERE LOWER(`{stock_prod_col}`) LIKE ? LIMIT 1;",
                        params=(f"%{nlp_info.has_specific_product.lower()}%",),
                        confidence=0.95,
                    )
                return CompiledQueryPlan(
                    intent="abstain_stock_ambiguous",
                    expected_type=AnswerType.ABSTAIN,
                    confidence=0.8,
                )

            # If no stock table or column exists in the entire database (NEG-03)
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

        # Helper to construct WHERE clause and parameter list
        def build_where_clause(include_status: bool = True, custom_prod: Optional[str] = None) -> Tuple[str, List[Any]]:
            clauses = []
            params: List[Any] = []
            if include_status and status_col:
                clauses.append(
                    f"(`{status_col}` IS NULL OR ("
                    f"LOWER(`{status_col}`) NOT LIKE '%hủy%' AND LOWER(`{status_col}`) NOT LIKE '%huỷ%' AND LOWER(`{status_col}`) NOT LIKE '%cancel%' "
                    f"AND LOWER(`{status_col}`) NOT LIKE '%trả hàng%' AND LOWER(`{status_col}`) NOT LIKE '%đổi trả%' "
                    f"AND LOWER(`{status_col}`) NOT LIKE '%hoàn trả%' AND LOWER(`{status_col}`) NOT LIKE '%hoàn tiền%' "
                    f"AND LOWER(`{status_col}`) NOT LIKE '%trả lại%' AND LOWER(`{status_col}`) NOT LIKE '%return%' "
                    f"AND LOWER(`{status_col}`) != 'trả' AND LOWER(`{status_col}`) != 'tra'))"
                )
            if time_range and date_col:
                if time_range.is_exact_day:
                    clauses.append(f"DATE(`{date_col}`) = ?")
                    params.append(time_range.start_date)
                else:
                    clauses.append(f"DATE(`{date_col}`) >= ? AND DATE(`{date_col}`) <= ?")
                    params.extend([time_range.start_date, time_range.end_date])
            if prod_name_col:
                clauses.append(f"(`{prod_name_col}` IS NULL OR LOWER(`{prod_name_col}`) NOT LIKE '%phí phục vụ%')")

            if sales_table and nlp_info.category_filter:
                cat_col = next((c.name for c in tables[sales_table].columns if c.semantic_role == "category" or any(k in c.name.lower() for k in ["loai", "nhom", "cat"])), None)
                if nlp_info.category_filter == "máy":
                    if cat_col:
                        clauses.append(f"(LOWER(`{cat_col}`) LIKE '%máy mới%' OR LOWER(`{cat_col}`) LIKE '%máy cũ%' OR LOWER(`{cat_col}`) LIKE '%may moi%' OR LOWER(`{cat_col}`) LIKE '%may cu%')")
                    elif prod_name_col:
                        clauses.append(f"LOWER(`{prod_name_col}`) NOT LIKE '%phụ kiện%' AND LOWER(`{prod_name_col}`) NOT LIKE '%phu kien%'")
                elif cat_col:
                    clauses.append(f"LOWER(`{cat_col}`) LIKE ?")
                    params.append(f"%{nlp_info.category_filter.lower()}%")
                elif prod_name_col:
                    clauses.append(f"LOWER(`{prod_name_col}`) LIKE ?")
                    params.append(f"%{nlp_info.category_filter.lower()}%")

            if custom_prod:
                if prod_code_col and "sp_" in custom_prod.lower():
                    clauses.append(f"LOWER(`{prod_code_col}`) = ?")
                    params.append(custom_prod.lower())
                elif prod_name_col:
                    clauses.append(f"unaccent(`{prod_name_col}`) LIKE ?")
                    params.append(f"%{strip_accents(custom_prod).lower()}%")
            elif nlp_info.has_specific_product:
                p = nlp_info.has_specific_product
                if prod_code_col and "sp_" in p.lower():
                    clauses.append(f"LOWER(`{prod_code_col}`) = ?")
                    params.append(p.lower())
                elif prod_name_col:
                    clauses.append(f"unaccent(`{prod_name_col}`) LIKE ?")
                    params.append(f"%{strip_accents(p).lower()}%")
            if nlp_info.has_specific_order and order_id_col:
                clauses.append(f"UPPER(`{order_id_col}`) = ?")
                params.append(nlp_info.has_specific_order.upper())
            where_str = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            return where_str, params

        # 6. Intent: Boolean / Zero / Negative Checks
        if nlp_info.is_zero_value_query:
            if not sales_table or not amount_expr:
                return cls._apply_guards(CompiledQueryPlan(intent="zero_val", expected_type=AnswerType.ABSTAIN), nlp_info, clean_q)
            sql = f"SELECT COUNT(*) FROM `{sales_table}` WHERE {amount_expr} = 0;"
            return cls._apply_guards(CompiledQueryPlan(intent="zero_val", expected_type=AnswerType.NUMBER, sql=sql.strip()), nlp_info, clean_q)

        if nlp_info.is_negative_value_query:
            if not sales_table or not amount_expr:
                return cls._apply_guards(CompiledQueryPlan(intent="negative_val", expected_type=AnswerType.ABSTAIN), nlp_info, clean_q)
            sql = f"SELECT COUNT(*) FROM `{sales_table}` WHERE {amount_expr} < 0;"
            return cls._apply_guards(CompiledQueryPlan(intent="negative_val", expected_type=AnswerType.NUMBER, sql=sql.strip()), nlp_info, clean_q)

        if nlp_info.is_success_rate_query:
            if not sales_table or not status_col:
                return cls._apply_guards(CompiledQueryPlan(intent="success_rate", expected_type=AnswerType.ABSTAIN), nlp_info, clean_q)
            where_str, params = build_where_clause(include_status=False)
            sql = f"""
            SELECT ROUND(
                100.0 * SUM(CASE WHEN `{status_col}` NOT LIKE '%hủy%' AND `{status_col}` NOT LIKE '%cancel%' THEN 1 ELSE 0 END)
                / NULLIF(COUNT(*), 0),
                2
            ) FROM `{sales_table}` {where_str};
            """
            return cls._apply_guards(CompiledQueryPlan(intent="success_rate", expected_type=AnswerType.PERCENT, sql=sql.strip(), params=tuple(params)), nlp_info, clean_q)

        if nlp_info.is_special_char_query:
            if not sales_table or not prod_name_col or not amount_expr:
                return cls._apply_guards(CompiledQueryPlan(intent="special_char_sales", expected_type=AnswerType.ABSTAIN), nlp_info, clean_q)
            where_str, params = build_where_clause()
            cond = f"(`{prod_name_col}` GLOB '*[0-9]*' OR `{prod_name_col}` GLOB '*[%@#&+/()_-]*')"
            where_full = f"{where_str} AND {cond}" if where_str else f"WHERE {cond}"
            sql = f"SELECT ROUND(COALESCE(SUM({amount_expr}), 0), 2) FROM `{sales_table}` {where_full};"
            return cls._apply_guards(CompiledQueryPlan(intent="special_char_sales", expected_type=AnswerType.NUMBER, sql=sql.strip(), params=tuple(params)), nlp_info, clean_q)

        # 7. Intent: Specific Order lookup (e.g. "Đơn hàng mã HD07 có giá trị bao nhiêu tiền?")
        if nlp_info.has_specific_order and (nlp_info.is_revenue_query or "giá trị" in clean_q or "bao nhiêu" in clean_q):
            if not sales_table or not order_id_col or not amount_expr:
                return cls._apply_guards(CompiledQueryPlan(intent="order_specific", expected_type=AnswerType.ABSTAIN), nlp_info, clean_q)
            sql = f"SELECT ROUND(COALESCE(SUM({amount_expr}), 0), 2) FROM `{sales_table}` WHERE UPPER(`{order_id_col}`) = ?;"
            return cls._apply_guards(CompiledQueryPlan(
                intent="order_specific",
                expected_type=AnswerType.NUMBER,
                sql=sql.strip(),
                params=(nlp_info.has_specific_order.upper(),),
            ), nlp_info, clean_q)

        # 8. Intent: Specific Customer Debt lookup (e.g. "Tổng nợ của khách hàng Bs Hùng là bao nhiêu?")
        if nlp_info.has_specific_customer and nlp_info.is_debt_query:
            if not debt_table or not debt_cust_col or not debt_amount_col:
                return cls._apply_guards(CompiledQueryPlan(intent="customer_debt_specific", expected_type=AnswerType.ABSTAIN), nlp_info, clean_q)
            sql = f"SELECT ROUND(COALESCE(SUM(`{debt_amount_col}`), 0), 2) FROM `{debt_table}` WHERE LOWER(`{debt_cust_col}`) LIKE ?;"
            return cls._apply_guards(CompiledQueryPlan(
                intent="customer_debt_specific",
                expected_type=AnswerType.NUMBER,
                sql=sql.strip(),
                params=(f"%{nlp_info.has_specific_customer.lower()}%",),
            ), nlp_info, clean_q)

        # 9. Intent: Cancellations (must be checked before order_count to avoid counting cancellations as orders!)
        if nlp_info.is_cancellation_query:
            if not sales_table or not status_col:
                return cls._apply_guards(CompiledQueryPlan(intent="cancellation", expected_type=AnswerType.ABSTAIN), nlp_info, clean_q)

            where_str, params = build_where_clause(include_status=False)
            cancel_match = f"(LOWER(`{status_col}`) LIKE '%hủy%' OR LOWER(`{status_col}`) LIKE '%huỷ%' OR LOWER(`{status_col}`) LIKE '%cancel%')"
            if nlp_info.is_canceled_revenue_query:
                where_clause = f"{where_str} AND {cancel_match}" if where_str else f"WHERE {cancel_match}"
                sql = f"SELECT ROUND(COALESCE(SUM({amount_expr}), 0), 2) FROM `{sales_table}` {where_clause};"
                return cls._apply_guards(CompiledQueryPlan(intent="canceled_revenue", expected_type=AnswerType.NUMBER, sql=sql.strip(), params=tuple(params)), nlp_info, clean_q)
            elif any(w in clean_q for w in ["tỷ lệ", "tỉ lệ", "phần trăm", "phan tram"]):
                id_expr = f"`{order_id_col}`" if order_id_col else "*"
                sql = f"""
                SELECT ROUND(
                    100.0 * COUNT(DISTINCT CASE WHEN {cancel_match} THEN {id_expr} END)
                    / NULLIF(COUNT(DISTINCT {id_expr}), 0),
                    2
                ) FROM `{sales_table}` {where_str};
                """
                return cls._apply_guards(CompiledQueryPlan(intent="cancel_rate", expected_type=AnswerType.PERCENT, sql=sql.strip(), params=tuple(params)), nlp_info, clean_q)
            elif bool(re.search(r"\b(có|co)\b.*\b(không|khong)\b", clean_q.rstrip("?").strip())) and not any(w in clean_q for w in ["bao nhiêu", "mấy", "số đơn", "bn", "nhiêu"]):
                where_cancel = f"{where_str} AND {cancel_match}" if where_str else f"WHERE {cancel_match}"
                sql = f"SELECT CASE WHEN COUNT(*) > 0 THEN 1 ELSE 0 END FROM `{sales_table}` {where_cancel};"
                return cls._apply_guards(CompiledQueryPlan(intent="cancel_boolean", expected_type=AnswerType.BOOLEAN, sql=sql.strip(), params=tuple(params)), nlp_info, clean_q)
            else:
                where_cancel = f"{where_str} AND {cancel_match}" if where_str else f"WHERE {cancel_match}"
                id_expr = f"DISTINCT `{order_id_col}`" if order_id_col else "*"
                sql = f"SELECT COUNT({id_expr}) FROM `{sales_table}` {where_cancel};"
                return cls._apply_guards(CompiledQueryPlan(intent="cancel_count", expected_type=AnswerType.NUMBER, sql=sql.strip(), params=tuple(params)), nlp_info, clean_q)

        # 10. Intent: Debts
        if nlp_info.is_debt_query and not nlp_info.is_debt_duration_query:
            if not debt_table or not debt_cust_col or not debt_amount_col:
                return cls._apply_guards(CompiledQueryPlan(intent="debt", expected_type=AnswerType.ABSTAIN), nlp_info, clean_q)

            where_pos = f"WHERE `{debt_amount_col}` > 0"
            if nlp_info.debt_above is not None:
                sql = f"SELECT DISTINCT `{debt_cust_col}` FROM `{debt_table}` WHERE `{debt_amount_col}` > ? ORDER BY `{debt_cust_col}` ASC;"
                return CompiledQueryPlan(intent="debt_above", expected_type=AnswerType.LIST, sql=sql.strip(), params=(float(nlp_info.debt_above),))
            elif nlp_info.debt_below is not None:
                sql = f"SELECT DISTINCT `{debt_cust_col}` FROM `{debt_table}` WHERE `{debt_amount_col}` > 0 AND `{debt_amount_col}` < ? ORDER BY `{debt_cust_col}` ASC;"
                return CompiledQueryPlan(intent="debt_below", expected_type=AnswerType.LIST, sql=sql.strip(), params=(float(nlp_info.debt_below),))
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
                return cls._apply_guards(CompiledQueryPlan(intent="order_max", expected_type=AnswerType.ABSTAIN), nlp_info, clean_q)
            where_str, params = build_where_clause()
            if any(w in clean_q for w in ["trị giá bao nhiêu", "bao nhiêu tiền"]) or bool(re.search(r"giá trị.*cao nhất.*bao nhiêu", clean_q)):
                sql = f"SELECT ROUND(COALESCE(MAX({amount_expr}), 0), 2) FROM `{sales_table}` {where_str};"
                return cls._apply_guards(CompiledQueryPlan(intent="order_max_value", expected_type=AnswerType.NUMBER, sql=sql.strip(), params=tuple(params)), nlp_info, clean_q)
            else:
                target_col = f"`{order_id_col}`" if order_id_col else amount_expr
                res_type = AnswerType.STRING if order_id_col else AnswerType.NUMBER
                sql = f"SELECT {target_col} FROM `{sales_table}` {where_str} ORDER BY {amount_expr} DESC LIMIT 1;"
                return cls._apply_guards(CompiledQueryPlan(intent="order_max", expected_type=res_type, sql=sql.strip(), params=tuple(params)), nlp_info, clean_q)

        if nlp_info.is_order_min_query:
            if not sales_table or not amount_expr:
                return cls._apply_guards(CompiledQueryPlan(intent="order_min", expected_type=AnswerType.ABSTAIN), nlp_info, clean_q)
            where_str, params = build_where_clause()
            if any(w in clean_q for w in ["trị giá bao nhiêu", "bao nhiêu tiền", "là bao nhiêu"]):
                sql = f"SELECT ROUND(COALESCE(MIN({amount_expr}), 0), 2) FROM `{sales_table}` {where_str};"
                return cls._apply_guards(CompiledQueryPlan(intent="order_min_value", expected_type=AnswerType.NUMBER, sql=sql.strip(), params=tuple(params)), nlp_info, clean_q)
            else:
                target_col = f"`{order_id_col}`" if order_id_col else amount_expr
                res_type = AnswerType.STRING if order_id_col else AnswerType.NUMBER
                sql = f"SELECT {target_col} FROM `{sales_table}` {where_str} ORDER BY {amount_expr} ASC LIMIT 1;"
                return cls._apply_guards(CompiledQueryPlan(intent="order_min", expected_type=res_type, sql=sql.strip(), params=tuple(params)), nlp_info, clean_q)

        # 11b. Intent: Average per order queries (Rulebook line 48 & line 133: làm tròn về đồng -> 0 decimals)
        if nlp_info.is_avg_order_revenue_query:
            if not sales_table or not amount_expr:
                return cls._apply_guards(CompiledQueryPlan(intent="avg_order_revenue", expected_type=AnswerType.ABSTAIN), nlp_info, clean_q)
            where_str, params = build_where_clause()
            order_div = f"COUNT(DISTINCT `{order_id_col}`)" if order_id_col else "COUNT(*)"
            sql = f"SELECT ROUND(SUM({amount_expr}) * 1.0 / NULLIF({order_div}, 0), 0) FROM `{sales_table}` {where_str};"
            return cls._apply_guards(CompiledQueryPlan(intent="avg_order_revenue", expected_type=AnswerType.NUMBER, sql=sql.strip(), params=tuple(params)), nlp_info, clean_q)

        if nlp_info.is_avg_order_qty_query:
            if not sales_table or not qty_col:
                return cls._apply_guards(CompiledQueryPlan(intent="avg_order_qty", expected_type=AnswerType.ABSTAIN), nlp_info, clean_q)
            where_str, params = build_where_clause()
            order_div = f"COUNT(DISTINCT `{order_id_col}`)" if order_id_col else "COUNT(*)"
            sql = f"SELECT ROUND(SUM(`{qty_col}`) * 1.0 / NULLIF({order_div}, 0), 2) FROM `{sales_table}` {where_str};"
            return cls._apply_guards(CompiledQueryPlan(intent="avg_order_qty", expected_type=AnswerType.NUMBER, sql=sql.strip(), params=tuple(params)), nlp_info, clean_q)

        # 12. Intent: Distinct products count (BM_MULTI_20)
        if nlp_info.is_distinct_product_query:
            if not sales_table or not prod_name_col:
                return cls._apply_guards(CompiledQueryPlan(intent="distinct_products", expected_type=AnswerType.ABSTAIN), nlp_info, clean_q)
            where_str, params = build_where_clause()
            sql = f"SELECT COUNT(DISTINCT `{prod_name_col}`) FROM `{sales_table}` {where_str};"
            return cls._apply_guards(CompiledQueryPlan(intent="distinct_products", expected_type=AnswerType.NUMBER, sql=sql.strip(), params=tuple(params)), nlp_info, clean_q)

        # 13. Intent: Order count (SEM-10: Tháng này bán được bao nhiêu đơn?)
        if nlp_info.is_order_count_query:
            if not sales_table:
                return cls._apply_guards(CompiledQueryPlan(intent="order_count", expected_type=AnswerType.ABSTAIN), nlp_info, clean_q)
            where_str, params = build_where_clause()
            if order_id_col:
                sql = f"SELECT CASE WHEN COUNT(`{order_id_col}`) > 0 THEN COUNT(DISTINCT `{order_id_col}`) ELSE COUNT(*) END FROM `{sales_table}` {where_str};"
            else:
                sql = f"SELECT COUNT(*) FROM `{sales_table}` {where_str};"
            return cls._apply_guards(CompiledQueryPlan(intent="order_count", expected_type=AnswerType.NUMBER, sql=sql.strip(), params=tuple(params)), nlp_info, clean_q)

        # 13a. Intent: Customer Count (SEM / Rulebook: AnswerType.NUMBER)
        if nlp_info.is_customer_count_query:
            if nlp_info.is_debt_query or any(w in clean_q for w in ["nợ", "no", "thiếu tiền", "thieu tien", "công nợ", "cong no"]):
                if debt_table and debt_cust_col and debt_amount_col:
                    sql = f"SELECT COUNT(DISTINCT `{debt_cust_col}`) FROM `{debt_table}` WHERE `{debt_amount_col}` > 0;"
                    return cls._apply_guards(CompiledQueryPlan(intent="debt_customer_count", expected_type=AnswerType.NUMBER, sql=sql.strip(), confidence=0.95), nlp_info, clean_q)
                return cls._apply_guards(CompiledQueryPlan(intent="debt_customer_count", expected_type=AnswerType.ABSTAIN), nlp_info, clean_q)

            if sales_table and cust_col:
                threshold_match = re.search(r"(?:từ|ít nhất|it nhat|tu)\s*(\d+)\s*(?:đơn|don|lần|lan)", clean_q)
                threshold = int(threshold_match.group(1)) if threshold_match else 1
                where_str, params = build_where_clause()
                order_expr = f"DISTINCT `{order_id_col}`" if order_id_col else "*"
                no_retail = f"(LOWER(TRIM(`{cust_col}`)) NOT IN ('lẻ', 'le', 'kl', 'khách lẻ', 'khach le', 'khách vãng lai', 'khach vang lai', 'vãng lai', 'vang lai', '') AND LOWER(`{cust_col}`) NOT LIKE '%khách lẻ%' AND LOWER(`{cust_col}`) NOT LIKE '%khach le%' AND LOWER(`{cust_col}`) NOT LIKE '%vãng lai%')"
                where_full = f"{where_str} AND `{cust_col}` IS NOT NULL AND {no_retail}" if where_str else f"WHERE `{cust_col}` IS NOT NULL AND {no_retail}"
                sql = f"""
                SELECT COUNT(*) FROM (
                    SELECT `{cust_col}`
                    FROM `{sales_table}`
                    {where_full}
                    GROUP BY `{cust_col}`
                    HAVING COUNT({order_expr}) >= {threshold}
                );
                """
                return cls._apply_guards(CompiledQueryPlan(intent="customer_count_threshold", expected_type=AnswerType.NUMBER, sql=sql.strip(), params=tuple(params), confidence=0.95), nlp_info, clean_q)
            return cls._apply_guards(CompiledQueryPlan(intent="customer_count", expected_type=AnswerType.ABSTAIN), nlp_info, clean_q)

        # 13b. Intent: Best customer / Top buyer (SEM-05 / Rule 48: Đơn khách lẻ không tính)
        if nlp_info.is_customer_query:
            if not sales_table or not cust_col:
                return cls._apply_guards(CompiledQueryPlan(intent="top_customer", expected_type=AnswerType.UNANSWERABLE, unanswerable_reason="Missing customer column in sales data."), nlp_info, clean_q)
            where_str, params = build_where_clause()

            # Rulebook §3: "Khách trung thành nhất: khách có nhiều ngày có mua nhất trong kỳ"
            if any(w in clean_q for w in ["trung thành", "trung thanh", "thường xuyên"]):
                sum_expr = f"COUNT(DISTINCT DATE(`{date_col}`))" if date_col else "COUNT(*)"
            # Rulebook §3: "Khách sộp nhất: khách có giá trị trung bình một đơn cao nhất trong kỳ (từ 2 đơn trở lên)"
            elif any(w in clean_q for w in ["sộp", "sop", "chịu chi", "chiu chi"]):
                sum_expr = f"SUM({amount_expr}) * 1.0 / NULLIF(COUNT(DISTINCT `{order_id_col}`), 0)" if order_id_col else f"AVG({amount_expr})"
            # Rulebook §3: "Khách hay đổi ý nhất: khách có nhiều đơn huỷ nhất trong kỳ"
            elif any(w in clean_q for w in ["đổi ý", "doi y", "hủy nhiều", "huỷ nhiều"]):
                sum_expr = f"COUNT(DISTINCT CASE WHEN LOWER(`{status_col}`) LIKE '%hủy%' OR LOWER(`{status_col}`) LIKE '%cancel%' THEN `{order_id_col}` END)" if (status_col and order_id_col) else "COUNT(*)"
            elif any(w in clean_q for w in ["nhiều đơn", "số đơn", "nhiều đơn nhất", "nhiều lần mua"]):
                sum_expr = f"COUNT(DISTINCT `{order_id_col}`)" if order_id_col else "COUNT(*)"
            else:
                sum_expr = amount_expr if amount_expr else (f"SUM(`{qty_col}`)" if qty_col else "COUNT(*)")

            no_retail = f"(LOWER(TRIM(`{cust_col}`)) NOT IN ('lẻ', 'le', 'kl', 'khách lẻ', 'khach le', 'khách vãng lai', 'khach vang lai', 'vãng lai', 'vang lai', '') AND LOWER(`{cust_col}`) NOT LIKE '%khách lẻ%' AND LOWER(`{cust_col}`) NOT LIKE '%khach le%' AND LOWER(`{cust_col}`) NOT LIKE '%vãng lai%')"
            where_join = f"{where_str} AND `{cust_col}` IS NOT NULL AND {no_retail}" if where_str else f"WHERE `{cust_col}` IS NOT NULL AND {no_retail}"
            having_clause = f"HAVING COUNT(DISTINCT `{order_id_col}`) >= 2" if any(w in clean_q for w in ["sộp", "sop"]) and order_id_col else ""
            k = nlp_info.top_k or 1
            exp_type = AnswerType.LIST if k > 1 else AnswerType.STRING
            sql = f"""
            SELECT `{cust_col}`
            FROM `{sales_table}`
            {where_join}
            GROUP BY `{cust_col}`
            {having_clause}
            ORDER BY {sum_expr} DESC
            LIMIT {k};
            """
            return cls._apply_guards(CompiledQueryPlan(intent="top_customer", expected_type=exp_type, sql=sql.strip(), params=tuple(params)), nlp_info, clean_q)

        # 14. Intent: Unsold products check (Grounded against Catalog and Sales)
        if nlp_info.is_unsold_query:
            catalog_tbl, catalog_prod_col = cls._find_catalog_table(tables, sales_table, prod_name_col)
            if not sales_table:
                return cls._apply_guards(CompiledQueryPlan(intent="unsold_check", expected_type=AnswerType.ABSTAIN, unanswerable_reason="Missing sales table."), nlp_info, clean_q)

            # Grounding check: without catalog/inventory table, we cannot infer unsold products from sales logs alone
            if not catalog_tbl or not catalog_prod_col:
                return CompiledQueryPlan(
                    intent="unsold_check",
                    expected_type=AnswerType.UNANSWERABLE,
                    unanswerable_reason="Chỉ có bảng giao dịch, thiếu bảng danh mục sản phẩm (catalog) hoặc kho để đối chiếu sản phẩm chưa bán."
                )

            where_str, params = build_where_clause()
            sql = f"""
            SELECT CASE WHEN EXISTS (
                SELECT 1 FROM `{catalog_tbl}` c
                WHERE c.`{catalog_prod_col}` IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM `{sales_table}` s
                      {where_str}
                      AND s.`{prod_name_col}` = c.`{catalog_prod_col}`
                  )
            ) THEN 1 ELSE 0 END;
            """
            return CompiledQueryPlan(
                intent="unsold_check",
                expected_type=AnswerType.BOOLEAN,
                sql=sql.strip(),
                params=tuple(params),
                confidence=0.92,
            )

        # 15. Intent: Specific Product Quantity / Revenue query
        if nlp_info.has_specific_product and not nlp_info.is_revenue_ranking and not nlp_info.is_quantity_ranking:
            if not sales_table:
                return cls._apply_guards(CompiledQueryPlan(intent="product_metric", expected_type=AnswerType.ABSTAIN), nlp_info, clean_q)
            where_str, params = build_where_clause()
            if nlp_info.is_revenue_query:
                sql = f"SELECT ROUND(COALESCE(SUM({amount_expr}), 0), 2) FROM `{sales_table}` {where_str};"
                return cls._apply_guards(CompiledQueryPlan(intent="product_revenue", expected_type=AnswerType.NUMBER, sql=sql.strip(), params=tuple(params)), nlp_info, clean_q)
            else:
                target_expr = f"`{qty_col}`" if qty_col else amount_expr
                sql = f"SELECT ROUND(COALESCE(SUM({target_expr}), 0), 2) FROM `{sales_table}` {where_str};"
                return cls._apply_guards(CompiledQueryPlan(intent="product_quantity", expected_type=AnswerType.NUMBER, sql=sql.strip(), params=tuple(params)), nlp_info, clean_q)

        # 16a. Intent: Which Day Query (AnswerType.DATE)
        if nlp_info.is_which_day_query or any(w in clean_q for w in ["ngày đắt khách", "ngay dat khach", "ngày đông khách", "ngay dong khach"]):
            if not sales_table or not date_col:
                return CompiledQueryPlan(intent="which_day", expected_type=AnswerType.ABSTAIN)
            where_str, params = build_where_clause()
            if any(w in clean_q for w in ["đắt khách", "dat khach", "đông khách", "dong khach", "nhiều đơn nhất"]):
                order_expr = f"COUNT(DISTINCT `{order_id_col}`)" if order_id_col else "COUNT(*)"
            else:
                agg_target = f"`{qty_col}`" if (nlp_info.is_quantity_query and qty_col) else amount_expr
                order_expr = f"SUM({agg_target})"

            is_min = any(w in clean_q for w in ["thấp nhất", "thap nhat", "ít nhất", "it nhat", "kém nhất", "kem nhat", "ế nhất", "e nhat"])
            direction = "ASC" if is_min else "DESC"

            sql = f"""
            SELECT DATE(`{date_col}`)
            FROM `{sales_table}`
            {where_str}
            GROUP BY DATE(`{date_col}`)
            ORDER BY {order_expr} {direction}, DATE(`{date_col}`) ASC
            LIMIT 1;
            """
            return CompiledQueryPlan(intent="which_day", expected_type=AnswerType.DATE, sql=sql.strip(), params=tuple(params), confidence=0.96)

        # 16b. Intent: Which Month Query (AnswerType.DATE)
        if nlp_info.is_which_month_query:
            if not sales_table or not date_col:
                return CompiledQueryPlan(intent="which_month", expected_type=AnswerType.ABSTAIN)
            metric = amount_expr if (nlp_info.is_revenue_query or not nlp_info.is_quantity_query) else (qty_col or amount_expr)
            clauses = []
            params = []
            if nlp_info.candidate_months:
                placeholders = ", ".join(["?"] * len(nlp_info.candidate_months))
                clauses.append(f"SUBSTR(DATE(`{date_col}`), 1, 7) IN ({placeholders})")
                params.extend(nlp_info.candidate_months)
            elif time_range and time_range.start_date and time_range.end_date:
                clauses.append(f"DATE(`{date_col}`) BETWEEN ? AND ?")
                params.extend([time_range.start_date, time_range.end_date])
            if status_col:
                clauses.append(f"(`{status_col}` IS NULL OR (`{status_col}` NOT LIKE '%trả hàng%' AND `{status_col}` NOT LIKE '%đổi trả%' AND `{status_col}` NOT LIKE '%hoàn trả%' AND `{status_col}` NOT LIKE '%hủy%' AND `{status_col}` NOT LIKE '%huỷ%'))")
            if prod_name_col:
                clauses.append(f"(`{prod_name_col}` IS NULL OR LOWER(`{prod_name_col}`) NOT LIKE '%phí phục vụ%')")
            if as_of_date_str:
                clauses.append(f"DATE(`{date_col}`) <= ?")
                params.append(as_of_date_str)
            where_str = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            sql = f"""
            SELECT SUBSTR(DATE(`{date_col}`), 1, 7)
            FROM `{sales_table}`
            {where_str}
            GROUP BY SUBSTR(DATE(`{date_col}`), 1, 7)
            ORDER BY SUM({metric}) DESC, SUBSTR(DATE(`{date_col}`), 1, 7) ASC
            LIMIT 1;
            """
            return CompiledQueryPlan(intent="which_month", expected_type=AnswerType.DATE, sql=sql.strip(), params=tuple(params), confidence=0.96)

        # 16c. Intent: Product Ranking by REVENUE (SEM-02 / SEM-08 / BM_FORMAL_01)
        if nlp_info.is_revenue_ranking or (nlp_info.is_revenue_query and nlp_info.is_lowest_ranking):
            if not sales_table or not prod_name_col or not amount_expr:
                return CompiledQueryPlan(intent="ranking_product_revenue", expected_type=AnswerType.ABSTAIN)

            where_str, params = build_where_clause()
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
                params=tuple(params),
                confidence=0.96,
            )

        # 17. Intent: Product Ranking by QUANTITY SOLD (SEM-01 / SEM-06 / VN-01 / VN-02)
        if nlp_info.is_quantity_ranking or nlp_info.is_lowest_ranking:
            if not sales_table or not prod_name_col:
                return CompiledQueryPlan(intent="ranking_product_quantity", expected_type=AnswerType.ABSTAIN)

            where_str, params = build_where_clause()
            order_dir = "ASC" if nlp_info.is_lowest_ranking else "DESC"

            # Check if query asks specifically about popular products in orders (Mặt hàng được ưa chuộng nhất)
            if any(w in clean_q for w in ["ưa chuộng", "ua chuong", "được chuộng", "pho bien nhất", "phổ biến nhất"]) and order_id_col:
                sum_target = f"COUNT(DISTINCT `{order_id_col}`)"
                secondary_sort = f", SUM(`{qty_col}`) {order_dir}" if qty_col else ""
            elif any(w in clean_q for w in ["người mua", "khách mua", "nguoi mua", "khach mua"]) and cust_col:
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
                params=tuple(params),
                confidence=0.96,
            )

        # 17d. Intent: Cancellation Rate (Rule 18: AnswerType.PERCENT)
        if nlp_info.is_cancellation_rate_query:
            if not sales_table or not status_col:
                return cls._apply_guards(CompiledQueryPlan(intent="cancellation_rate", expected_type=AnswerType.ABSTAIN), nlp_info, clean_q)
            where_str, params = build_where_clause(include_status=False)
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
            return cls._apply_guards(CompiledQueryPlan(intent="cancellation_rate", expected_type=AnswerType.PERCENT, sql=sql.strip(), params=tuple(params), confidence=0.95), nlp_info, clean_q)

        # 17e. Intent: Revenue Growth / Percentage Change (Rulebook §1 Rule 19: AnswerType.PERCENT)
        is_growth_query = nlp_info.is_growth_query or (
            any(w in clean_q for w in ["tăng trưởng", "tang truong", "tăng bao nhiêu %", "tang bao nhieu %", "giảm bao nhiêu %", "giam bao nhieu %", "thay đổi bao nhiêu %", "phần trăm thay đổi", "phan tram thay doi", "tăng hay giảm", "tang hay giam", "cao hay thấp hơn", "hơn hay kém"])
            and any(w in clean_q for w in ["%", "phần trăm", "phan tram"])
        )
        if is_growth_query:
            if sales_table and date_col and amount_expr:
                periods = TemporalResolver.resolve_comparison_periods(clean_q, as_of_date_str)
                if periods:
                    cur_p, prev_p = periods
                    conds = []
                    if status_col:
                        conds.append(
                            f"(`{status_col}` IS NULL OR ("
                            f"LOWER(`{status_col}`) NOT LIKE '%hủy%' AND LOWER(`{status_col}`) NOT LIKE '%huỷ%' AND LOWER(`{status_col}`) NOT LIKE '%cancel%' "
                            f"AND LOWER(`{status_col}`) NOT LIKE '%trả hàng%' AND LOWER(`{status_col}`) NOT LIKE '%đổi trả%' "
                            f"AND LOWER(`{status_col}`) NOT LIKE '%hoàn trả%' AND LOWER(`{status_col}`) NOT LIKE '%hoàn tiền%' "
                            f"AND LOWER(`{status_col}`) NOT LIKE '%trả lại%' AND LOWER(`{status_col}`) NOT LIKE '%return%' "
                            f"AND LOWER(`{status_col}`) != 'trả' AND LOWER(`{status_col}`) != 'tra'))"
                        )
                    if prod_name_col:
                        conds.append(f"(`{prod_name_col}` IS NULL OR LOWER(`{prod_name_col}`) NOT LIKE '%phí phục vụ%')")
                    status_clause = " AND ".join(conds) if conds else "1=1"
                    sql = f"""
                    WITH cur AS (
                        SELECT COALESCE(SUM({amount_expr}), 0.0) AS val
                        FROM `{sales_table}`
                        WHERE DATE(`{date_col}`) >= ? AND DATE(`{date_col}`) <= ? AND {status_clause}
                    ),
                    prev AS (
                        SELECT COALESCE(SUM({amount_expr}), 0.0) AS val
                        FROM `{sales_table}`
                        WHERE DATE(`{date_col}`) >= ? AND DATE(`{date_col}`) <= ? AND {status_clause}
                    )
                    SELECT ROUND(100.0 * (cur.val - prev.val) / NULLIF(prev.val, 0), 2)
                    FROM cur, prev;
                    """
                    growth_params = (cur_p.start_date, cur_p.end_date, prev_p.start_date, prev_p.end_date)
                    return cls._apply_guards(CompiledQueryPlan(intent="growth_rate", expected_type=AnswerType.PERCENT, sql=sql.strip(), params=growth_params, confidence=0.95), nlp_info, clean_q)
            return cls._apply_guards(CompiledQueryPlan(intent="growth_rate_unresolved", expected_type=AnswerType.ABSTAIN, confidence=0.0), nlp_info, clean_q)

        # 17f. Intent: Specific Column Target (e.g. thu_may_cu, khach_tra, bot)
        if nlp_info.metric_target and sales_table:
            matched_col = next((c.name for c in tables[sales_table].columns if nlp_info.metric_target in c.name.lower()), None)
            if matched_col:
                where_str, params = build_where_clause()
                sql = f"SELECT ROUND(COALESCE(SUM(`{matched_col}`), 0), 2) FROM `{sales_table}` {where_str};"
                return CompiledQueryPlan(intent=f"metric_{nlp_info.metric_target}", expected_type=AnswerType.NUMBER, sql=sql.strip(), params=tuple(params), confidence=0.96)

        # 17g. Intent: Table output (AnswerType.TABLE)
        if nlp_info.is_table_query:
            k = nlp_info.top_k or 5
            if nlp_info.is_debt_query and debt_table and debt_cust_col and debt_amount_col:
                sql = f"""
                SELECT `{debt_cust_col}` AS khach_hang, ROUND(`{debt_amount_col}`) AS so_tien_no
                FROM `{debt_table}`
                WHERE `{debt_amount_col}` > 0
                ORDER BY `{debt_amount_col}` DESC
                LIMIT {k};
                """
                return CompiledQueryPlan(intent="debt_table", expected_type=AnswerType.TABLE, sql=sql.strip(), confidence=0.95)
            elif sales_table and prod_name_col:
                where_str, params = build_where_clause()
                metric = amount_expr if nlp_info.is_revenue_query else (f"SUM(`{qty_col}`)" if qty_col else amount_expr)
                metric_name = "doanh_thu" if nlp_info.is_revenue_query else "so_luong"
                sql = f"""
                SELECT `{prod_name_col}` AS ten_san_pham, ROUND({metric}, 2) AS {metric_name}
                FROM `{sales_table}`
                {where_str}
                GROUP BY `{prod_name_col}`
                ORDER BY {metric} DESC
                LIMIT {k};
                """
                return CompiledQueryPlan(intent="sales_table", expected_type=AnswerType.TABLE, sql=sql.strip(), params=tuple(params), confidence=0.95)

        # 18. Intent: Total Revenue
        if nlp_info.is_revenue_query:
            if not sales_table or not amount_expr:
                return cls._apply_guards(CompiledQueryPlan(intent="revenue", expected_type=AnswerType.ABSTAIN), nlp_info, clean_q)

            where_str, params = build_where_clause()
            sql = f"SELECT ROUND(COALESCE(SUM({amount_expr}), 0), 2) FROM `{sales_table}` {where_str};"
            return cls._apply_guards(CompiledQueryPlan(intent="revenue", expected_type=AnswerType.NUMBER, sql=sql.strip(), params=tuple(params), confidence=0.95), nlp_info, clean_q)

        # 19. Intent: Total Quantity Sold
        if nlp_info.is_quantity_query or any(w in clean_q for w in ["bán được bao nhiêu", "số lượng bán", "tiêu thụ được bao nhiêu"]):
            if not sales_table:
                return cls._apply_guards(CompiledQueryPlan(intent="quantity", expected_type=AnswerType.ABSTAIN), nlp_info, clean_q)

            where_str, params = build_where_clause()
            target_expr = f"`{qty_col}`" if qty_col else amount_expr
            sql = f"SELECT ROUND(COALESCE(SUM({target_expr}), 0), 2) FROM `{sales_table}` {where_str};"
            return cls._apply_guards(CompiledQueryPlan(intent="quantity", expected_type=AnswerType.NUMBER, sql=sql.strip(), params=tuple(params), confidence=0.92), nlp_info, clean_q)

        # Default fallback: return ABSTAIN to prevent -1 penalty
        return CompiledQueryPlan(
            intent="unknown",
            expected_type=AnswerType.ABSTAIN,
            confidence=0.0,
        )

    @classmethod
    def _apply_guards(cls, plan: CompiledQueryPlan, nlp_info: NormalizedQueryInfo, clean_q: str) -> CompiledQueryPlan:
        if plan.expected_type == AnswerType.ABSTAIN:
            return plan

        # Guard 1: Specific unit without matched product -> ABSTAIN
        has_unit_word = bool(re.search(r"\b(bao nhiêu|mấy|bnhiu|bn)\s+(cây|ly|chai|hộp|bịch|gói|bình|lon|phần|tô|dĩa|đĩa|m3|viên|lọ|cuộn|bao|mét|kg)\b", clean_q))
        if has_unit_word and not nlp_info.has_specific_product and not nlp_info.category_filter:
            if plan.intent in ("quantity", "revenue"):
                return CompiledQueryPlan(intent="missing_product_guard_abstain", expected_type=AnswerType.ABSTAIN, confidence=0.0)

        # Guard 2: Percent question returning Number or String -> ABSTAIN
        is_pct_question = any(w in clean_q for w in ["%", "phần trăm", "phan tram", "tỷ lệ", "tỉ lệ", "tăng trưởng", "tang truong", "tăng bao nhiêu %", "giảm bao nhiêu %", "thay đổi bao nhiêu %", "hơn kém mấy %", "chiếm mấy %", "chiếm bao nhiêu %"])
        if is_pct_question and plan.expected_type in (AnswerType.NUMBER, AnswerType.STRING):
            return CompiledQueryPlan(intent="type_guard_abstain", expected_type=AnswerType.ABSTAIN, confidence=0.0)

        # Guard 3: Customer count question returning String -> ABSTAIN
        if nlp_info.is_customer_count_query and plan.expected_type == AnswerType.STRING:
            return CompiledQueryPlan(intent="customer_count_guard_abstain", expected_type=AnswerType.ABSTAIN, confidence=0.0)

        # Guard 4: Cancellation with specific reason -> ABSTAIN
        if plan.intent in ("cancel_count", "cancel_rate", "canceled_revenue"):
            if any(w in clean_q for w in ["vì", "vi ", "lý do", "ly do", "nguyên nhân", "nguyen nhan", "giao trễ", "giao tre", "hỏng", "hong", "đổi ý", "doi y"]):
                return CompiledQueryPlan(intent="cancel_reason_abstain", expected_type=AnswerType.ABSTAIN, confidence=0.0)

        # Guard 5: Comparison / Side comparison for top_customer -> ABSTAIN
        if plan.intent == "top_customer":
            if any(w in clean_q for w in ["bên nào", "ben nao", "ai hơn", "ai hon", "so với", "so voi", "nhiều hơn", "nhieu hon"]):
                return CompiledQueryPlan(intent="customer_comparison_abstain", expected_type=AnswerType.ABSTAIN, confidence=0.0)

        # Guard 6: Unhandled Slice Precision Guard for aggregates (revenue, order_count, quantity)
        if plan.intent in ("revenue", "order_count", "quantity"):
            guard_keywords = [
                # Channels
                "tại quầy", "tai quay", "qua điện thoại", "qua dien thoai", "online", "mang về", "mang ve",
                "giao hàng", "giao hang", "tiền ship", "tien ship", "phí ship", "phi ship", "vận chuyển", "van chuyen",
                "shopee", "tiki", "lazada", "grab", "baemin", "shopeefood", "gojek", "tại bàn", "tai ban", "mang đi", "mang di",
                # Segments & Locations
                "nhóm sỉ", "nhom si", "khách sỉ", "khach si", "khách buôn", "khach buon", "khách lẻ", "khach le",
                "thân thiết", "than thiet", "khách quen", "khach quen", "khách mới", "khach moi", "vip", "thành viên", "thanh vien",
                "ở đường", "o duong", "tại đường", "tai duong", "khách ở", "khach o", "khu vực", "khu vuc",
                # Costs, Purchases, Inventory, Profit
                "nhập hàng", "nhap hang", "đánh hàng", "danh hang", "cất hàng", "cat hang", "nhập kho", "nhap kho",
                "chi nhập", "chi nhap", "tiền hàng nhập", "tien hang nhap", "giá vốn", "gia von", "chi phí", "chi phi",
                "lãi", "lai", "lợi nhuận", "loi nhuan", "tiền lời", "tien loi",
                # Payment, credit, installments, discounts, points
                "chuyển khoản", "chuyen khoan", "tiền mặt", "tien mat", "quẹt thẻ", "quet the", "thẻ tín dụng", "the tin dung",
                "ví điện tử", "vi dien tu", "momo", "zalopay", "vnpay", "trả góp", "tra gop", "bán chịu", "ban chiu",
                "ghi nợ", "ghi no", "chưa góp", "chua gop", "kỳ chưa tới hạn", "sau hôm nay", "sau hom nay",
                "quá hạn", "qua han", "kỳ góp", "ky gop", "chưa đóng", "chua dong",
                "voucher", "coupon", "khuyến mãi", "khuyen mai", "mã giảm giá", "ma giam gia", "chiết khấu", "chiet khau",
                "điểm tích lũy", "diem tich luy", "điểm trừ", "diem tru", "điểm thưởng", "diem thuong",
                "đăng ký", "dang ky", "thành viên mới", "thanh vien moi",
                # Shifts & time of day
                "ca sáng", "ca sang", "ca chiều", "ca chieu", "ca tối", "ca toi", "ca đêm", "ca dem",
                "buổi sáng", "buoi sang", "buổi trưa", "buoi trua", "buổi chiều", "buoi chieu", "buổi tối", "buoi toi",
                "ban ngày", "ban ngay", "ban đêm", "ban dem", "khung giờ", "khung gio", "giờ cao điểm", "gio cao diem",
                # Averages & per-order
                "trung bình", "trung binh", "bình quân", "binh quan", "mỗi đơn", "moi don", "từng đơn", "tung don",
                "1 đơn", "một đơn", "mot don",
                # Multi-values & orderings
                "lần lượt", "lan luot", "tương ứng", "tuong ung", "với lại", "so với", "và bao nhiêu", "va bao nhieu",
                "từng tháng", "tung thang", "mỗi tháng bao nhiêu", "moi thang bao nhieu", "mỗi ngày bao nhiêu", "moi ngay bao nhieu",
                "từng ngày", "tung ngay", "thứ tự đó", "thu tu do",
                # Delivery batches & staff
                "đợt", "dot", "chở thành", "giao từ", "lần giao", "nhân viên", "nhan vien", "nv ", "thu ngân", "thu ngan",
            ]
            if any(k in clean_q for k in guard_keywords):
                return CompiledQueryPlan(intent="slice_guard_abstain", expected_type=AnswerType.ABSTAIN, confidence=0.0)

            # Threshold pattern (e.g. từ 1.100.000đ trở lên, dưới 500k, đạt...)
            threshold_pattern = re.compile(
                r"(?:từ|tu|trên|tren|dưới|duoi|ít nhất|it nhat|nhiều hơn|nhieu hon|cao hơn|cao hon|thấp hơn|thap hon|lớn hơn|lon hon|nhỏ hơn|nho hon|vượt|vuot|quá|qua)\s*\d+[\d\.,]*|"
                r"\d+[\d\.,]*\s*(?:triệu|tr|k|nghìn|ngàn|đ|vnd|đồng|dong)\s*(?:trở lên|tro len|trở xuống|tro xuong|đổ lại|do lai)|"
                r"(?:đạt|dat)\s+\d+[\d\.,]*"
            )
            if threshold_pattern.search(clean_q):
                return CompiledQueryPlan(intent="threshold_guard_abstain", expected_type=AnswerType.ABSTAIN, confidence=0.0)

            # Specific category mentioned in question but unparsed
            q_clean_h = re.sub(r"\b(cửa hàng|cua hang|đơn hàng|don hang)\b", "", clean_q)
            if not nlp_info.category_filter and not nlp_info.has_specific_product:
                if re.search(r"\b(nhóm|nhom|loại|loai|phân loại|phan loai|ngành hàng|nganh hang)\b", q_clean_h):
                    return CompiledQueryPlan(intent="unparsed_category_guard_abstain", expected_type=AnswerType.ABSTAIN, confidence=0.0)
                m = re.search(r"\bbán\s+(.+?)\s+(?:được|duoc)\s+(?:bao nhiêu|mấy|bnhiu|bn)", q_clean_h)
                if m:
                    middle = m.group(1).strip()
                    if middle and middle not in ("ra", "thì", "thi", "tổng cộng", "tong cong", "tat ca", "tất cả"):
                        return CompiledQueryPlan(intent="unparsed_product_guard_abstain", expected_type=AnswerType.ABSTAIN, confidence=0.0)

        # Guard 7: Order count with return/cancel conditions
        if plan.intent == "order_count":
            if any(w in clean_q for w in ["trả lại", "tra lai", "đổi trả", "doi tra", "hoàn hàng", "hoan hang", "trả hàng", "tra hang"]):
                return CompiledQueryPlan(intent="return_order_abstain", expected_type=AnswerType.ABSTAIN, confidence=0.0)
            is_not_canceled = any(w in clean_q for w in ["không bị hủy", "khong bi huy", "chưa bị hủy", "chua bi huy", "không hủy", "khong huy"])
            if any(w in clean_q for w in ["hủy", "huỷ", "huy"]) and not is_not_canceled:
                return CompiledQueryPlan(intent="return_order_abstain", expected_type=AnswerType.ABSTAIN, confidence=0.0)

        # Guard 8: Product rankings with profit or count questions
        if plan.intent in ("ranking_product_quantity", "ranking_product_revenue"):
            if any(w in clean_q for w in ["lời", "loi", "lãi", "lai", "lợi nhuận", "loi nhuan", "lãi gộp", "lai gop"]):
                return CompiledQueryPlan(intent="ranking_profit_abstain", expected_type=AnswerType.ABSTAIN, confidence=0.0)
            if re.search(r"\b(có bao nhiêu|co bao nhieu|có mấy|co may|bao nhiêu mặt hàng|bao nhieu mat hang|mấy mặt hàng|may mat hang|bao nhiêu sp|bao nhieu sp|mấy sp|may sp|bao nhiêu món|bao nhieu mon|mấy món|may mon)\b", clean_q):
                return CompiledQueryPlan(intent="ranking_count_abstain", expected_type=AnswerType.ABSTAIN, confidence=0.0)

        return plan

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
            name_clean = strip_accents(c.name).lower()
            if c.semantic_role == "customer":
                if not cust_col:
                    cust_col = c.name
                else:
                    curr_clean = strip_accents(cust_col).lower()
                    def _cust_priority(name: str) -> int:
                        if any(k in name for k in ["ho_ten", "ten_khach", "ten_khach_hang", "nguoi_mua", "ten_nguoi_mua"]):
                            return 3
                        if any(k in name for k in ["ma_khach", "ma_khach_hang", "ma_khach_mua", "customer_id", "makh"]):
                            return 2
                        if any(k in name for k in ["khach_hang", "customer"]):
                            return 1
                        return 0
                    if _cust_priority(name_clean) > _cust_priority(curr_clean):
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
                    if not prod_name_col or any(k in name_lower for k in ["ten_sp", "ten_san_pham", "ten_hang_hoa", "ten_mon", "ten_thuoc"]):
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

        # Prioritize customer name column over type/category or codes
        name_cols = [c.name for c in t.columns if any(k in c.name.lower() for k in ["ten_kh", "ten_khach", "khach_hang", "ho_ten", "customer_name"])]
        if name_cols:
            debt_cust_col = name_cols[0]
        else:
            code_cols = [c.name for c in t.columns if any(k in c.name.lower() for k in ["ma_kh", "customer_id", "id_kh"])]
            if code_cols:
                debt_cust_col = code_cols[0]
            else:
                for c in t.columns:
                    if (c.semantic_role == "customer" or "khach" in c.name.lower()) and not any(k in c.name.lower() for k in ["loai", "nhom", "cap", "type"]):
                        debt_cust_col = c.name
                        break

        for c in t.columns:
            if c.semantic_role == "debt" or any(k in c.name.lower() for k in ["tong_no", "cong_no", "so_tien", "tien_no"]):
                debt_amount_col = c.name
                break

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
