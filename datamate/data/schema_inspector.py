from __future__ import annotations
import re
import sqlite3
import unicodedata
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


def strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "d").lower()


class ColumnInfo(BaseModel):
    name: str
    data_type: str
    sample_values: List[Any] = []
    semantic_role: Optional[str] = None
    is_primary_key: bool = False
    is_unique: bool = False


class TableRelation(BaseModel):
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    relation_type: str = "MANY_TO_ONE"  # "MANY_TO_ONE", "ONE_TO_MANY", "ONE_TO_ONE"
    confidence: float = 1.0


class TableInfo(BaseModel):
    name: str
    row_count: int
    columns: List[ColumnInfo]
    primary_key: Optional[str] = None
    table_kind: str = "unknown"  # "fact_sales", "fact_debt", "dim_product", "dim_customer", "dim_inventory", "unknown"
    grain: Optional[str] = None
    relations: List[TableRelation] = []


class SchemaInspector:
    """Inspects tables in SQLite and infers semantic roles of columns."""

    CUSTOMER_KEYWORDS = ["khach_hang", "khach", "customer", "client", "nguoi_mua", "ten_khach_hang", "benh_nhan", "doi_tac"]
    DEBT_KEYWORDS = ["cong_no", "tong_no", "con_no", "so_no", "tien_no", "debt", "chua_tra", "no_phai_tra"]
    DATE_KEYWORDS = ["ngay", "date", "created", "time", "thoi_gian", "order_date", "gio"]
    STATUS_KEYWORDS = ["trang_thai", "status", "state", "tinh_trang", "ket_qua"]
    TOTAL_AMOUNT_KEYWORDS = ["thanh_tien", "tong_tien", "doanh_thu", "total_amount", "amount", "subtotal", "tong", "tri_gia", "tong_tien_hang", "tong_sau_giam_gia", "t_tien", "ttien"]
    QUANTITY_KEYWORDS = ["so_luong", "quantity", "qty", "sl", "quy_ra_dv_le", "so_luong_quy_doi", "so_luong_giao"]
    UNIT_PRICE_KEYWORDS = ["don_gia", "unit_price", "price", "gia_ban", "gia_niem_yet", "don_gia_ban", "gia_don_vi", "gia_le", "gia_moi", "gia_cu"]
    PRODUCT_KEYWORDS = [
        "san_pham", "sp", "product", "item", "hang_hoa", "mat_hang", "ten_sp", "ma_sp",
        "ten_mon", "mon_an", "mon", "do_uong", "ten_thuoc", "thuoc", "vat_tu", "dich_vu",
        "noi_dung", "hang_hoa", "mat_hang", "ghi_tat", "viet_tat",
        "ten_hang", "ma_hang", "id_sp", "hang", "thuoc_tinh",
    ]
    ORDER_ID_KEYWORDS = [
        "ma_hoa_don", "ma_don", "ma_dh", "order_id", "invoice_id", "so_hoa_don", "so_hd", "ma_giao_dich",
        "stt", "so_tt", "so_thu_tu", "ma_chung_tu", "chung_tu", "so_chung_tu", "so_phieu"
    ]
    COST_KEYWORDS = ["gia_von", "cost", "chi_phi", "von", "loi_nhuan", "lai", "gia_nhap"]
    EXPIRY_KEYWORDS = ["han_su_dung", "hsd", "exp_date", "expiry", "ngay_het_han", "han_dung"]
    STOCK_KEYWORDS = ["ton_kho", "stock", "so_luong_ton", "hang_ton", "sl_ton", "tonkho", "ton_cuoi", "ton_cuoi_ky"]
    EMPLOYEE_KEYWORDS = ["nhan_vien", "staff", "seller", "nguoi_ban", "nv"]
    DEBT_DUE_KEYWORDS = ["han_tra", "ngay_den_han", "ngay_no", "ngay_vay", "due_date", "han_thanh_toan"]
    CATEGORY_KEYWORDS = ["loai", "loai_hang", "nhom", "nhom_hang", "nganh_hang", "category", "phan_loai"]
    ADJUSTMENT_KEYWORDS = {
        "khach_tra": "customer_payment",
        "khach_da_tra": "customer_payment",
        "khach_phai_tra": "customer_payment",
        "tien_khach_tra": "customer_payment",
        "da_tra": "customer_payment",
        "con_phai_thu": "customer_payment",
        "phai_thu": "customer_payment",
        "thu_may_cu": "trade_in_amount",
        "thu_cu": "trade_in_amount",
        "bot": "discount_amount",
        "giam_gia": "discount_amount",
        "chiet_khau": "discount_amount",
    }

    # Viết tắt rất phổ biến trong bảng tính Việt Nam (tt = thành tiền, dg = đơn giá ...).
    SHORT_ROLE_NAMES = {
        "tt": "total_amount",
        "ttien": "total_amount",
        "thanhtien": "total_amount",
        "dg": "unit_price",
        "dongia": "unit_price",
        "gianiemyet": "unit_price",
        "hd": "order_id",
        "mahd": "order_id",
        "sohd": "order_id",
        "sl": "quantity",
        "soluong": "quantity",
        "nv": "employee",
        "manv": "employee",
    }

    @classmethod
    def inspect(cls, conn: sqlite3.Connection) -> Dict[str, TableInfo]:
        tables: Dict[str, TableInfo] = {}
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%';")
        tbl_names = [row[0] for row in cursor.fetchall()]

        for tbl in tbl_names:
            cursor.execute(f"SELECT COUNT(*) FROM `{tbl}`;")
            count = cursor.fetchone()[0]

            cursor.execute(f"PRAGMA table_info(`{tbl}`);")
            cols_meta = cursor.fetchall()

            sample_dict = {col[1]: [] for col in cols_meta}
            try:
                cursor.execute(f"SELECT * FROM `{tbl}` LIMIT 5;")
                col_names_ordered = [desc[0] for desc in cursor.description]
                sample_rows = cursor.fetchall()
                for row in sample_rows:
                    for c_name, val in zip(col_names_ordered, row):
                        if val is not None and len(sample_dict[c_name]) < 3:
                            sample_dict[c_name].append(val)
            except Exception:
                pass

            col_infos = []
            pk_col = None
            for col in cols_meta:
                c_name = col[1]
                c_type = col[2] or "TEXT"
                is_pk = bool(col[5] > 0)
                samples = sample_dict.get(c_name, [])
                role = cls._infer_role(c_name, samples)

                is_unique = False
                if is_pk:
                    pk_col = c_name
                    is_unique = True
                elif count > 0 and count <= 50000:
                    try:
                        cursor.execute(f"SELECT COUNT(DISTINCT `{c_name}`) FROM `{tbl}`;")
                        dist_cnt = cursor.fetchone()[0]
                        if dist_cnt == count:
                            is_unique = True
                            if not pk_col and any(k in c_name.lower() for k in ["ma_", "id", "code"]):
                                pk_col = c_name
                    except Exception:
                        pass

                col_infos.append(
                    ColumnInfo(
                        name=c_name,
                        data_type=c_type,
                        sample_values=samples,
                        semantic_role=role,
                        is_primary_key=is_pk,
                        is_unique=is_unique,
                    )
                )

            # Infer Table Kind and Grain
            table_kind = "unknown"
            grain = None
            roles_in_table = set(c.semantic_role for c in col_infos if c.semantic_role)
            tbl_clean = strip_accents(tbl)

            if "date" in roles_in_table and ("total_amount" in roles_in_table or "quantity" in roles_in_table):
                table_kind = "fact_sales"
                grain = "transaction_item" if "quantity" in roles_in_table else "order_header"
            elif any(k in tbl_clean for k in ["hoa_don", "don_hang", "ban_hang", "sales", "giao_dich"]):
                table_kind = "fact_sales"
                grain = "transaction_item"
            elif "debt" in roles_in_table or any(k in tbl_clean for k in ["so_no", "cong_no", "debt"]):
                table_kind = "fact_debt"
                grain = "customer_debt_balance"
            elif "category" in roles_in_table or ("product" in roles_in_table and not ("total_amount" in roles_in_table or "date" in roles_in_table)) or any(k in tbl_clean for k in ["san_pham", "hang_hoa", "danh_muc", "catalog", "ghi_tat", "viet_tat"]):
                table_kind = "dim_product"
                grain = "product_catalog"
            elif "customer" in roles_in_table and not ("total_amount" in roles_in_table or "date" in roles_in_table):
                table_kind = "dim_customer"
                grain = "customer_directory"
            elif "stock" in roles_in_table or any(k in tbl_clean for k in ["ton_kho", "kho", "stock"]):
                table_kind = "dim_inventory"
                grain = "inventory_snapshot"

            tables[tbl] = TableInfo(
                name=tbl,
                row_count=count,
                columns=col_infos,
                primary_key=pk_col,
                table_kind=table_kind,
                grain=grain,
                relations=[],
            )

        # Infer Relationships (Explicit FKs & Semantic Joins)
        for tbl, t_info in tables.items():
            # 1. Explicit SQLite foreign keys
            try:
                cursor.execute(f"PRAGMA foreign_key_list(`{tbl}`);")
                for fk_row in cursor.fetchall():
                    target_tbl = fk_row[2]
                    from_c = fk_row[3]
                    to_c = fk_row[4]
                    if target_tbl in tables:
                        t_info.relations.append(
                            TableRelation(
                                from_table=tbl,
                                from_column=from_c,
                                to_table=target_tbl,
                                to_column=to_c,
                                relation_type="MANY_TO_ONE",
                                confidence=1.0,
                            )
                        )
            except Exception:
                pass

            # 2. Semantic FK / Name Overlap Detection
            for other_tbl, other_info in tables.items():
                if tbl == other_tbl:
                    continue

                # Fact-to-Dimension product relationship
                if t_info.table_kind == "fact_sales" and other_info.table_kind in ("dim_product", "dim_inventory"):
                    matched_pair = None
                    code_a = next((c.name for c in t_info.columns if c.semantic_role == "product" and any(k in c.name.lower() for k in ["ma", "code", "id"])), None)
                    code_b = next((c.name for c in other_info.columns if c.semantic_role == "product" and any(k in c.name.lower() for k in ["ma", "code", "id"])), None)
                    if code_a and code_b:
                        matched_pair = (code_a, code_b)
                    else:
                        name_a = next((c.name for c in t_info.columns if c.semantic_role == "product" and any(k in c.name.lower() for k in ["ten", "name"])), None)
                        name_b = next((c.name for c in other_info.columns if c.semantic_role == "product" and any(k in c.name.lower() for k in ["ten", "name"])), None)
                        if name_a and name_b:
                            matched_pair = (name_a, name_b)

                    if not matched_pair:
                        col_a = next((c.name for c in t_info.columns if c.semantic_role == "product"), None)
                        col_b = other_info.primary_key or next((c.name for c in other_info.columns if c.semantic_role == "product"), None)
                        if col_a and col_b:
                            matched_pair = (col_a, col_b)

                    if matched_pair:
                        t_info.relations.append(
                            TableRelation(
                                from_table=tbl,
                                from_column=matched_pair[0],
                                to_table=other_tbl,
                                to_column=matched_pair[1],
                                relation_type="MANY_TO_ONE",
                                confidence=0.95,
                            )
                        )

                # Fact-to-Fact/Dim customer relationship (sales to customer / debt)
                if t_info.table_kind == "fact_sales" and other_info.table_kind in ("fact_debt", "dim_customer"):
                    matched_pair = None
                    code_a = next((c.name for c in t_info.columns if c.semantic_role == "customer" and any(k in c.name.lower() for k in ["ma", "code", "id"])), None)
                    code_b = next((c.name for c in other_info.columns if c.semantic_role == "customer" and any(k in c.name.lower() for k in ["ma", "code", "id"])), None)
                    if code_a and code_b:
                        matched_pair = (code_a, code_b)
                    else:
                        name_a = next((c.name for c in t_info.columns if c.semantic_role == "customer" and any(k in c.name.lower() for k in ["ten", "name", "khach"])), None)
                        name_b = next((c.name for c in other_info.columns if c.semantic_role == "customer" and any(k in c.name.lower() for k in ["ten", "name", "khach"])), None)
                        if name_a and name_b:
                            matched_pair = (name_a, name_b)

                    if not matched_pair:
                        col_a = next((c.name for c in t_info.columns if c.semantic_role == "customer"), None)
                        col_b = other_info.primary_key or next((c.name for c in other_info.columns if c.semantic_role == "customer"), None)
                        if col_a and col_b:
                            matched_pair = (col_a, col_b)

                    if matched_pair:
                        t_info.relations.append(
                            TableRelation(
                                from_table=tbl,
                                from_column=matched_pair[0],
                                to_table=other_tbl,
                                to_column=matched_pair[1],
                                relation_type="MANY_TO_ONE",
                                confidence=0.90,
                            )
                        )

        return tables

    @staticmethod
    def _looks_numeric(value: Any) -> bool:
        if isinstance(value, bool):
            return False
        if isinstance(value, (int, float)):
            return True
        if isinstance(value, str):
            text = (
                value.strip()
                .replace(".", "")
                .replace(",", "")
                .replace("đ", "")
                .replace("₫", "")
                .replace(" ", "")
            )
            if text.startswith("-"):
                text = text[1:]
            return bool(text) and text.isdigit()
        return False

    @classmethod
    def _infer_role(cls, col_name: str, samples: List[Any]) -> Optional[str]:
        clean_name = strip_accents(col_name).lower()
        compact_name = re.sub(r"[^a-z0-9]", "", clean_name)

        # 0. Adjustments & specific payments (e.g. khach_tra, khachdatra, thu_may_cu, bot)
        for kw, role in cls.ADJUSTMENT_KEYWORDS.items():
            kw_compact = re.sub(r"[^a-z0-9]", "", kw)
            if kw == clean_name or kw in clean_name or kw_compact == compact_name or kw_compact in compact_name:
                return role

        # 1. Order ID
        for kw in cls.ORDER_ID_KEYWORDS:
            if kw in clean_name:
                return "order_id"

        # Check guest/cover counts which contain 'khach' but are numbers of guests
        if any(gk in clean_name for gk in ["so_khach", "luong_khach", "so_luong_khach"]) or any(gk in compact_name for gk in ["sokhach", "luongkhach", "soluongkhach"]):
            return "quantity"

        # Check customer groups/segments which contain 'khach' but are categories
        if any(gk in clean_name for gk in ["nhom_khach", "nhom_kh"]) or any(gk in compact_name for gk in ["nhomkhach", "nhomkh"]):
            return "category"

        # 2. Customer must be checked before Product ("khach_hang" contains "hang")
        for kw in cls.CUSTOMER_KEYWORDS:
            if kw in clean_name:
                return "customer"

        # 2b. Category
        for kw in cls.CATEGORY_KEYWORDS:
            if kw in clean_name:
                return "category"

        # 3. Debt must be checked before Stock ("tong_no" starts with "tong" not "ton")
        for kw in cls.DEBT_KEYWORDS:
            if kw in clean_name or clean_name == "no":
                return "debt"

        # 4. Debt due date
        for kw in cls.DEBT_DUE_KEYWORDS:
            if kw in clean_name:
                return "debt_due"

        # 5. Expiry
        for kw in cls.EXPIRY_KEYWORDS:
            if kw in clean_name:
                return "expiry"

        # 6. Cost
        for kw in cls.COST_KEYWORDS:
            if kw in clean_name:
                return "cost"

        # 7. Stock
        for kw in cls.STOCK_KEYWORDS:
            if kw in clean_name or clean_name == "ton":
                return "stock"

        # 8. Employee
        for kw in cls.EMPLOYEE_KEYWORDS:
            if kw in clean_name:
                return "employee"

        # 9. Quantity (check before Unit Price to avoid "giao" matching "gia")
        for kw in cls.QUANTITY_KEYWORDS:
            if kw in clean_name:
                return "quantity"

        # 10. Financial amounts & unit prices
        for kw in cls.TOTAL_AMOUNT_KEYWORDS:
            if kw in clean_name:
                return "total_amount"
        for kw in cls.UNIT_PRICE_KEYWORDS:
            if kw in clean_name:
                return "unit_price"
        if clean_name == "gia" or clean_name.startswith("gia_") or clean_name.endswith("_gia"):
            return "unit_price"

        # 11. Date
        for kw in cls.DATE_KEYWORDS:
            if kw in clean_name:
                return "date"

        # 12. Status
        for kw in cls.STATUS_KEYWORDS:
            if kw in clean_name:
                return "status"

        # 12b. Channel & Store (not product)
        if any(kw in clean_name for kw in ["kenh_ban", "kenh", "channel"]):
            return "channel"
        if any(kw in clean_name for kw in ["cua_hang", "cuahang", "store", "chi_nhanh"]):
            return "store"

        # 13. Product (exclude store, channel, order, customer, delivery)
        if not any(ex in clean_name for ex in ["cua_hang", "kenh", "channel", "don_hang", "khach_hang", "giao_hang", "nhan_vien"]):
            for kw in cls.PRODUCT_KEYWORDS:
                if kw in clean_name:
                    return "product"

        # 14. Viết tắt phổ biến (chỉ nhận khi giá trị mẫu phù hợp)
        compact = re.sub(r"[^a-z0-9]", "", clean_name)
        short_role = cls.SHORT_ROLE_NAMES.get(compact)
        if short_role:
            if short_role in ("total_amount", "unit_price", "quantity"):
                if any(cls._looks_numeric(s) for s in samples):
                    return short_role
            else:
                return short_role

        # Check sample values for date patterns
        for s in samples:
            if isinstance(s, str) and (len(s) >= 10 and s[4] == "-" and s[7] == "-"):
                return "date"

        return None
