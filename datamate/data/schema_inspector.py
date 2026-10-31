from __future__ import annotations
import re
import sqlite3
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


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

    CUSTOMER_KEYWORDS = ["khach_hang", "khach", "customer", "client", "nguoi_mua", "ten_khach_hang", "benh_nhan"]
    DEBT_KEYWORDS = ["cong_no", "tong_no", "con_no", "so_no", "tien_no", "debt", "chua_tra", "no_phai_tra"]
    DATE_KEYWORDS = ["ngay", "date", "created", "time", "thoi_gian", "order_date"]
    STATUS_KEYWORDS = ["trang_thai", "status", "state", "tinh_trang"]
    TOTAL_AMOUNT_KEYWORDS = ["thanh_tien", "tong_tien", "doanh_thu", "total_amount", "amount", "subtotal", "tong", "tri_gia"]
    UNIT_PRICE_KEYWORDS = ["don_gia", "unit_price", "price", "gia_ban", "gia"]
    QUANTITY_KEYWORDS = ["so_luong", "quantity", "qty", "sl"]
    PRODUCT_KEYWORDS = [
        "san_pham", "sp", "product", "item", "hang_hoa", "mat_hang", "ten_sp", "ma_sp",
        "ten_mon", "mon_an", "mon", "do_uong", "ten_thuoc", "thuoc", "vat_tu", "dich_vu"
    ]
    COST_KEYWORDS = ["gia_von", "cost", "chi_phi", "von", "loi_nhuan", "lai", "gia_nhap"]
    EXPIRY_KEYWORDS = ["han_su_dung", "hsd", "exp_date", "expiry", "ngay_het_han", "han_dung"]
    STOCK_KEYWORDS = ["ton_kho", "stock", "so_luong_ton", "hang_ton", "sl_ton", "tonkho"]
    EMPLOYEE_KEYWORDS = ["nhan_vien", "staff", "seller", "nguoi_ban", "nv"]
    DEBT_DUE_KEYWORDS = ["han_tra", "ngay_den_han", "ngay_no", "ngay_vay", "due_date", "han_thanh_toan"]

    @classmethod
    def inspect(cls, conn: sqlite3.Connection) -> Dict[str, TableInfo]:
        tables: Dict[str, TableInfo] = {}
        cursor = conn.cursor()

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tbl_names = [row[0] for row in cursor.fetchall()]

        for tbl in tbl_names:
            cursor.execute(f"SELECT COUNT(*) FROM `{tbl}`;")
            count = cursor.fetchone()[0]

            cursor.execute(f"PRAGMA table_info(`{tbl}`);")
            cols_meta = cursor.fetchall()

            col_infos = []
            for col in cols_meta:
                c_name = col[1]
                c_type = col[2] or "TEXT"

                # Fetch non-null sample values
                try:
                    cursor.execute(f"SELECT `{c_name}` FROM `{tbl}` WHERE `{c_name}` IS NOT NULL LIMIT 3;")
                    samples = [r[0] for r in cursor.fetchall()]
                except Exception:
                    samples = []

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
        name_lower = col_name.lower()

        # 1. Customer must be checked before Product ("khach_hang" contains "hang")
        for kw in cls.CUSTOMER_KEYWORDS:
            if kw in name_lower:
                return "customer"

        # 2. Debt must be checked before Stock ("tong_no" starts with "tong" not "ton")
        for kw in cls.DEBT_KEYWORDS:
            if kw in name_lower or name_lower == "no":
                return "debt"

        # 3. Debt due date
        for kw in cls.DEBT_DUE_KEYWORDS:
            if kw in name_lower:
                return "debt_due"

        # 4. Expiry
        for kw in cls.EXPIRY_KEYWORDS:
            if kw in name_lower:
                return "expiry"

        # 5. Cost
        for kw in cls.COST_KEYWORDS:
            if kw in name_lower:
                return "cost"

        # 6. Stock
        for kw in cls.STOCK_KEYWORDS:
            if kw in name_lower or name_lower == "ton":
                return "stock"

        # 7. Employee
        for kw in cls.EMPLOYEE_KEYWORDS:
            if kw in name_lower:
                return "employee"

        # 8. Date
        for kw in cls.DATE_KEYWORDS:
            if kw in name_lower:
                return "date"

        # 9. Status
        for kw in cls.STATUS_KEYWORDS:
            if kw in name_lower:
                return "status"

        # 10. Financial amounts & quantities
        for kw in cls.TOTAL_AMOUNT_KEYWORDS:
            if kw in name_lower:
                return "total_amount"
        for kw in cls.UNIT_PRICE_KEYWORDS:
            if kw in name_lower:
                return "unit_price"
        for kw in cls.QUANTITY_KEYWORDS:
            if kw in name_lower:
                return "quantity"

        # 11. Product
        for kw in cls.PRODUCT_KEYWORDS:
            if kw in name_lower:
                return "product"

        # Check sample values for date patterns
        for s in samples:
            if isinstance(s, str) and (len(s) == 10 and s[4] == "-" and s[7] == "-"):
                return "date"

        return None
