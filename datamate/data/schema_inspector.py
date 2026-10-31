from __future__ import annotations
import sqlite3
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ColumnInfo(BaseModel):
    name: str
    data_type: str
    sample_values: List[Any] = []
    semantic_role: Optional[str] = None  # "date", "status", "product", "customer", "amount", "quantity", "debt"


class TableInfo(BaseModel):
    name: str
    row_count: int
    columns: List[ColumnInfo]


class SchemaInspector:
    """Inspects tables in SQLite and infers semantic roles of columns."""

    DATE_KEYWORDS = ["ngay", "date", "created", "time", "thoi_gian"]
    STATUS_KEYWORDS = ["trang_thai", "status", "state", "tinh_trang"]
    TOTAL_AMOUNT_KEYWORDS = ["thanh_tien", "tong_tien", "doanh_thu", "total_amount", "amount", "subtotal"]
    UNIT_PRICE_KEYWORDS = ["don_gia", "unit_price", "price", "gia_ban", "gia"]
    QUANTITY_KEYWORDS = ["so_luong", "quantity", "qty", "sl"]
    PRODUCT_KEYWORDS = ["san_pham", "sp", "product", "item", "hang_hoa", "mat_hang", "ten_sp", "ma_sp"]
    CUSTOMER_KEYWORDS = ["khach_hang", "kh", "customer", "client", "nguoi_mua"]
    DEBT_KEYWORDS = ["cong_no", "con_no", "no", "debt", "chua_tra"]

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

                # Fetch 3 non-null sample values
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
        for kw in cls.DATE_KEYWORDS:
            if kw in name_lower:
                return "date"
        for kw in cls.STATUS_KEYWORDS:
            if kw in name_lower:
                return "status"
        for kw in cls.DEBT_KEYWORDS:
            if kw in name_lower:
                return "debt"
        for kw in cls.TOTAL_AMOUNT_KEYWORDS:
            if kw in name_lower:
                return "total_amount"
        for kw in cls.UNIT_PRICE_KEYWORDS:
            if kw in name_lower:
                return "unit_price"
        for kw in cls.QUANTITY_KEYWORDS:
            if kw in name_lower:
                return "quantity"
        for kw in cls.PRODUCT_KEYWORDS:
            if kw in name_lower:
                return "product"
        for kw in cls.CUSTOMER_KEYWORDS:
            if kw in name_lower:
                return "customer"

        # Check sample values for date patterns
        for s in samples:
            if isinstance(s, str) and (len(s) == 10 and s[4] == "-" and s[7] == "-"):
                return "date"

        return None
