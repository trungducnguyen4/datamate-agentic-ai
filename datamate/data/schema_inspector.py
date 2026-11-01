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


class TableInfo(BaseModel):
    name: str
    row_count: int
    columns: List[ColumnInfo]


class SchemaInspector:
    """Inspects tables in SQLite and infers semantic roles of columns."""

    CUSTOMER_KEYWORDS = ["khach_hang", "khach", "customer", "client", "nguoi_mua", "ten_khach_hang", "benh_nhan", "doi_tac"]
    DEBT_KEYWORDS = ["cong_no", "tong_no", "con_no", "so_no", "tien_no", "debt", "chua_tra", "no_phai_tra"]
    DATE_KEYWORDS = ["ngay", "date", "created", "time", "thoi_gian", "order_date"]
    STATUS_KEYWORDS = ["trang_thai", "status", "state", "tinh_trang", "ket_qua"]
    TOTAL_AMOUNT_KEYWORDS = ["thanh_tien", "tong_tien", "doanh_thu", "total_amount", "amount", "subtotal", "tong", "tri_gia"]
    QUANTITY_KEYWORDS = ["so_luong", "quantity", "qty", "sl", "quy_ra_dv_le", "so_luong_quy_doi", "so_luong_giao"]
    UNIT_PRICE_KEYWORDS = ["don_gia", "unit_price", "price", "gia_ban", "gia_niem_yet", "don_gia_ban"]
    PRODUCT_KEYWORDS = [
        "san_pham", "sp", "product", "item", "hang_hoa", "mat_hang", "ten_sp", "ma_sp",
        "ten_mon", "mon_an", "mon", "do_uong", "ten_thuoc", "thuoc", "vat_tu", "dich_vu",
        "noi_dung", "hang"
    ]
    ORDER_ID_KEYWORDS = ["ma_hoa_don", "ma_don", "ma_dh", "order_id", "invoice_id", "so_hoa_don", "so_hd", "ma_giao_dich"]
    COST_KEYWORDS = ["gia_von", "cost", "chi_phi", "von", "loi_nhuan", "lai", "gia_nhap"]
    EXPIRY_KEYWORDS = ["han_su_dung", "hsd", "exp_date", "expiry", "ngay_het_han", "han_dung"]
    STOCK_KEYWORDS = ["ton_kho", "stock", "so_luong_ton", "hang_ton", "sl_ton", "tonkho"]
    EMPLOYEE_KEYWORDS = ["nhan_vien", "staff", "seller", "nguoi_ban", "nv"]
    DEBT_DUE_KEYWORDS = ["han_tra", "ngay_den_han", "ngay_no", "ngay_vay", "due_date", "han_thanh_toan"]

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
            for col in cols_meta:
                c_name = col[1]
                c_type = col[2] or "TEXT"
                samples = sample_dict.get(c_name, [])
                role = cls._infer_role(c_name, samples)
                col_infos.append(
                    ColumnInfo(
                        name=c_name,
                        data_type=c_type,
                        sample_values=samples,
                        semantic_role=role,
                    )
                )

            tables[tbl] = TableInfo(name=tbl, row_count=count, columns=col_infos)

        return tables

    @classmethod
    def _infer_role(cls, col_name: str, samples: List[Any]) -> Optional[str]:
        clean_name = strip_accents(col_name)

        # 1. Order ID
        for kw in cls.ORDER_ID_KEYWORDS:
            if kw in clean_name:
                return "order_id"

        # 2. Customer must be checked before Product ("khach_hang" contains "hang")
        for kw in cls.CUSTOMER_KEYWORDS:
            if kw in clean_name:
                return "customer"

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

        # 13. Product
        for kw in cls.PRODUCT_KEYWORDS:
            if kw in clean_name:
                return "product"

        # Check sample values for date patterns
        for s in samples:
            if isinstance(s, str) and (len(s) == 10 and s[4] == "-" and s[7] == "-"):
                return "date"

        return None
