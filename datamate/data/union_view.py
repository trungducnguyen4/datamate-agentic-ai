"""Gộp các bảng fact bán hàng bị chia theo tháng/quý/năm thành một view chung.

Dữ liệu DataMate thường lưu mỗi tháng một file/sheet (``SoBanHang_T01_2025.xlsx``,
``BanHang_Thang03_2026.xlsx``, ``so_chi_tiet_ban_hang_t02_2025`` ...). Engine cũ chỉ
chọn đúng một bảng nên mọi câu hỏi về tháng khác đều trả rỗng.

Module này dò các bảng cùng "schema bán hàng" (ngày, sản phẩm, số lượng, thành tiền,
trạng thái, khách, mã đơn) rồi tạo ``VIEW _sales_unified`` bằng UNION ALL, chuẩn hoá
tên cột về một bộ tên chung. Nhờ đó compiler chỉ cần đọc một bảng duy nhất.
"""
from __future__ import annotations

import re
import sqlite3
from typing import Dict, List, Optional, Tuple

from datamate.data.schema_inspector import ColumnInfo, TableInfo

UNIFIED_VIEW = "_sales_unified"

SALES_NAME_TOKENS = (
    "ban_hang", "banhang", "ban_h", "ban_lt", "hoa_don", "hoadon",
    "don_hang", "donhang", "chi_tiet_ban", "chitietban", "sales", "orders",
    "giao_dich",
)

EXCLUDE_NAME_TOKENS = (
    "nhap", "phieu_thu", "phieuthu", "thu_tien", "thutien",
    "chi_phi", "chiphi", "cong_no", "hanno", "so_no", "khachhang", "khach_hang",
    "hanghoa", "san_pham", "sanpham", "lohang", "lo_hang", "ton_kho", "tonkho",
    "ton_cuoi", "ton_dau", "bang_gia", "banggia", "lich_su_gia", "lichsugia",
    "danh_muc", "danhmuc", "khuyen_mai", "khuyenmai", "baocao", "danh_gia",
    "danhgia", "nha_cung_cap", "nhacungcap", "quy_doi", "quydoi", "don_vi",
    "donvi", "donhang_lo", "don_hang_lo", "chitietlo", "chi_tiet_lo",
)

CANON_ROLES = (
    "date", "product", "quantity", "total_amount", "unit_price",
    "status", "customer", "order_id", "discount",
)

_SHORT_SEGMENTS = {"ton", "kho", "lo", "gia", "no", "thu", "nhap", "giao"}


def _is_excluded_name(clean: str) -> bool:
    is_cash_journal = "giao_dich" in clean
    if not is_cash_journal:
        for token in ("giao", "tra_hang", "trahang", "huy"):
            if token in clean:
                return True
    for token in EXCLUDE_NAME_TOKENS:
        if token in clean:
            return True
    segments = [s for s in re.split(r"[^a-z0-9]+", clean) if s]
    for segment in segments:
        if is_cash_journal and segment in ("giao", "dich"):
            continue
        if segment in _SHORT_SEGMENTS:
            return True
    return False


def _is_sales_table(name: str, info: TableInfo) -> bool:
    clean = name.lower()
    if clean == UNIFIED_VIEW.lower() or clean.startswith("_"):
        return False
    roles = {c.semantic_role for c in info.columns if c.semantic_role}

    if _is_excluded_name(clean):
        return False

    if not any(token in clean for token in SALES_NAME_TOKENS):
        return False

    if "date" not in roles or "product" not in roles:
        return False
    return bool({"quantity", "total_amount", "unit_price"} & roles)


def _product_columns(info: TableInfo) -> Tuple[Optional[str], Optional[str]]:
    """Trả về (cột tên sản phẩm, cột mã sản phẩm)."""
    name_column: Optional[str] = None
    code_column: Optional[str] = None
    for column in info.columns:
        if column.semantic_role != "product":
            continue
        lowered = column.name.lower()
        if any(key in lowered for key in ("ma_", "code", "id")) and not code_column:
            code_column = column.name
        elif not name_column:
            name_column = column.name
    if not name_column and code_column:
        name_column, code_column = code_column, None
    return name_column, code_column


def _role_columns(info: TableInfo) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for column in info.columns:
        role = column.semantic_role
        if role and role in CANON_ROLES and role not in mapping:
            mapping[role] = column.name
    name, code = _product_columns(info)
    if name:
        mapping["product"] = name
    mapping["product_code"] = code or ""
    return mapping


def _signature(mapping: Dict[str, str]) -> Tuple[Tuple[str, Optional[str]], ...]:
    return tuple((role, mapping.get(role) or None) for role in CANON_ROLES) + (
        ("product_code", mapping.get("product_code") or None),
    )


def _amount_expression(mapping: Dict[str, str]) -> str:
    if "total_amount" in mapping:
        return f"CAST(`{mapping['total_amount']}` AS REAL)"
    if "quantity" in mapping and "unit_price" in mapping:
        discount = (
            f" - COALESCE(CAST(`{mapping['discount']}` AS REAL), 0)"
            if "discount" in mapping
            else ""
        )
        return (
            f"CAST(`{mapping['quantity']}` AS REAL) * "
            f"CAST(`{mapping['unit_price']}` AS REAL){discount}"
        )
    return "NULL"


def _expr(column: Optional[str], alias: str, cast: str = "TEXT") -> str:
    if not column:
        return f"NULL AS {alias}"
    return f"CAST(`{column}` AS {cast}) AS {alias}"


def _select_for_table(table: str, mapping: Dict[str, str]) -> str:
    return (
        f"SELECT {_expr(mapping.get('date'), 'ngay')}, "
        f"{_expr(mapping.get('product'), 'ten_san_pham')}, "
        f"{_expr(mapping.get('product_code'), 'ma_san_pham')}, "
        f"{_expr(mapping.get('quantity'), 'so_luong', 'REAL')}, "
        f"{_amount_expression(mapping)} AS thanh_tien, "
        f"{_expr(mapping.get('status'), 'trang_thai')}, "
        f"{_expr(mapping.get('customer'), 'khach_hang')}, "
        f"{_expr(mapping.get('order_id'), 'ma_hoa_don')}, "
        f"{_expr(mapping.get('unit_price'), 'don_gia', 'REAL')}, "
        f"{_expr(mapping.get('discount'), 'giam_gia', 'REAL')} "
        f"FROM `{table}`"
    )


def _ensure_indexes(conn: sqlite3.Connection, tables: Dict[str, TableInfo]) -> None:
    """Tạo index trên khóa join/ngày/sản phẩm để tránh nested-loop join bậc N×M."""
    for name, info in tables.items():
        if not (
            _is_sales_table(name, info)
            or _is_header_table(name, info)
            or _is_detail_table(name, info)
        ):
            continue
        for role in ("order_id", "date", "customer"):
            column = next((c.name for c in info.columns if c.semantic_role == role), None)
            if not column:
                continue
            index_name = f"idx_{name}_{column}"[:120]
            try:
                conn.execute(
                    f'CREATE INDEX IF NOT EXISTS "{index_name}" ON `{name}`(`{column}`)'
                )
            except sqlite3.Error:
                continue
    conn.commit()


def build_sales_union(conn: sqlite3.Connection, tables: Dict[str, TableInfo]) -> Optional[str]:
    """Tạo `_sales_unified` nếu gộp được nhiều bảng fact bán hàng.

    Ưu tiên 2 kiểu dữ liệu phổ biến của DataMate:
    1. Nhiều bảng dòng hàng chia theo tháng/quý/năm (UNION ALL).
    2. Bảng header hóa đơn + bảng chi tiết dòng hàng (JOIN theo mã hóa đơn).
    """
    _ensure_indexes(conn, tables)
    groups: Dict[Tuple[Tuple[str, Optional[str]], ...], List[Tuple[str, TableInfo, Dict[str, str]]]] = {}
    for name, info in tables.items():
        if not _is_sales_table(name, info):
            continue
        mapping = _role_columns(info)
        groups.setdefault(_signature(mapping), []).append((name, info, mapping))

    best: Optional[List[Tuple[str, TableInfo, Dict[str, str]]]] = None
    best_rows = -1
    for members in groups.values():
        if len(members) < 2:
            continue
        total_rows = sum(info.row_count for _, info, _ in members)
        if total_rows > best_rows:
            best_rows = total_rows
            best = members

    if best:
        conn.execute(f"DROP VIEW IF EXISTS `{UNIFIED_VIEW}`")
        selects = [_select_for_table(name, mapping) for name, _, mapping in best]
        conn.execute(f"CREATE VIEW `{UNIFIED_VIEW}` AS " + " UNION ALL ".join(selects))
        conn.commit()
        return UNIFIED_VIEW

    return _build_header_detail_union(conn, tables)


# --------------------------------------------------------------- header/detail
def _is_header_table(name: str, info: TableInfo) -> bool:
    clean = name.lower()
    if clean == UNIFIED_VIEW.lower() or clean.startswith("_"):
        return False
    if not any(token in clean for token in ("hoa_don", "hoadon", "don_hang", "donhang", "ban_hang", "banhang")):
        return False
    if any(token in clean for token in ("chi_tiet", "chitiet", "nhap", "phieu_thu", "phieuthu", "giao")):
        return False
    roles = {c.semantic_role for c in info.columns if c.semantic_role}
    return {"date", "order_id", "total_amount"} <= roles and "product" not in roles


def _is_detail_table(name: str, info: TableInfo) -> bool:
    clean = name.lower()
    if not any(token in clean for token in ("chi_tiet", "chitiet")):
        return False
    if any(token in clean for token in ("lo", "nhap", "giao")):
        return False
    roles = {c.semantic_role for c in info.columns if c.semantic_role}
    return {"order_id", "product"} <= roles and bool({"quantity", "total_amount"} & roles)


def _header_mapping(info: TableInfo) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for column in info.columns:
        role = column.semantic_role
        if role in ("date", "order_id", "status", "customer") and role not in mapping:
            mapping[role] = column.name
    for column in info.columns:
        if column.semantic_role == "total_amount":
            mapping["total_amount"] = column.name
    return mapping


def _detail_mapping(info: TableInfo) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for column in info.columns:
        role = column.semantic_role
        if role in ("order_id", "quantity", "unit_price", "discount") and role not in mapping:
            mapping[role] = column.name
    for column in info.columns:
        if column.semantic_role == "total_amount":
            mapping["total_amount"] = column.name
    name, code = _product_columns(info)
    mapping["product"] = name or ""
    mapping["product_code"] = code or ""
    return mapping


def _best_group(members_by_sig, minimum: int = 1):
    best = None
    best_rows = -1
    for members in members_by_sig.values():
        if len(members) < minimum:
            continue
        rows = sum(info.row_count for _, info, _ in members)
        if rows > best_rows:
            best_rows = rows
            best = members
    return best


def _build_header_detail_union(conn: sqlite3.Connection, tables: Dict[str, TableInfo]) -> Optional[str]:
    header_groups: Dict[Tuple, List[Tuple[str, TableInfo, Dict[str, str]]]] = {}
    detail_groups: Dict[Tuple, List[Tuple[str, TableInfo, Dict[str, str]]]] = {}

    for name, info in tables.items():
        if _is_header_table(name, info):
            mapping = _header_mapping(info)
            header_groups.setdefault(
                tuple((r, mapping.get(r)) for r in ("date", "order_id", "status", "customer")),
                [],
            ).append((name, info, mapping))
        elif _is_detail_table(name, info):
            mapping = _detail_mapping(info)
            detail_groups.setdefault(
                tuple((r, mapping.get(r)) for r in ("order_id", "quantity", "total_amount")),
                [],
            ).append((name, info, mapping))

    headers = _best_group(header_groups)
    details = _best_group(detail_groups)
    if not headers or not details:
        return None

    header_selects = []
    for name, _, mapping in headers:
        header_selects.append(
            f"SELECT {_expr(mapping.get('order_id'), 'ma_hoa_don')}, "
            f"{_expr(mapping.get('date'), 'ngay')}, "
            f"{_expr(mapping.get('status'), 'trang_thai')}, "
            f"{_expr(mapping.get('customer'), 'khach_hang')} FROM `{name}`"
        )
    detail_selects = []
    for name, _, mapping in details:
        detail_selects.append(
            f"SELECT {_expr(mapping.get('order_id'), 'ma_hoa_don')}, "
            f"{_expr(mapping.get('product'), 'ten_san_pham')}, "
            f"{_expr(mapping.get('product_code'), 'ma_san_pham')}, "
            f"{_expr(mapping.get('quantity'), 'so_luong', 'REAL')}, "
            f"{_amount_expression(mapping)} AS thanh_tien, "
            f"{_expr(mapping.get('unit_price'), 'don_gia', 'REAL')}, "
            f"{_expr(mapping.get('discount'), 'giam_gia', 'REAL')} FROM `{name}`"
        )

    sql = (
        f"CREATE VIEW `{UNIFIED_VIEW}` AS "
        f"SELECT h.ngay AS ngay, d.ten_san_pham AS ten_san_pham, "
        f"d.ma_san_pham AS ma_san_pham, d.so_luong AS so_luong, "
        f"d.thanh_tien AS thanh_tien, h.trang_thai AS trang_thai, "
        f"h.khach_hang AS khach_hang, d.ma_hoa_don AS ma_hoa_don, "
        f"d.don_gia AS don_gia, d.giam_gia AS giam_gia "
        f"FROM ({' UNION ALL '.join(detail_selects)}) d "
        f"JOIN ({' UNION ALL '.join(header_selects)}) h "
        f"ON d.ma_hoa_don = h.ma_hoa_don"
    )
    conn.execute(f"DROP VIEW IF EXISTS `{UNIFIED_VIEW}`")
    conn.execute(sql)
    conn.commit()
    return UNIFIED_VIEW


def build_unified_table_info(conn: sqlite3.Connection, view: str = UNIFIED_VIEW) -> TableInfo:
    """Mô tả view dưới dạng TableInfo để compiler dùng như bảng thường."""
    columns = [
        ColumnInfo(name="ngay", data_type="TEXT", semantic_role="date"),
        ColumnInfo(name="ten_san_pham", data_type="TEXT", semantic_role="product"),
        ColumnInfo(name="ma_san_pham", data_type="TEXT", semantic_role="product"),
        ColumnInfo(name="so_luong", data_type="REAL", semantic_role="quantity"),
        ColumnInfo(name="thanh_tien", data_type="REAL", semantic_role="total_amount"),
        ColumnInfo(name="trang_thai", data_type="TEXT", semantic_role="status"),
        ColumnInfo(name="khach_hang", data_type="TEXT", semantic_role="customer"),
        ColumnInfo(name="ma_hoa_don", data_type="TEXT", semantic_role="order_id"),
        ColumnInfo(name="don_gia", data_type="REAL", semantic_role="unit_price"),
        ColumnInfo(name="giam_gia", data_type="REAL", semantic_role="discount"),
    ]
    row_count = int(conn.execute(f"SELECT COUNT(*) FROM `{view}`").fetchone()[0])
    return TableInfo(
        name=view,
        row_count=row_count,
        columns=columns,
        primary_key="ma_hoa_don",
        table_kind="fact_sales",
        grain="transaction_item",
        relations=[],
    )


def ensure_sales_union(conn: sqlite3.Connection, tables: Dict[str, TableInfo]) -> Optional[str]:
    """Tạo view (nếu cần) và trả về tên view; None nếu không gộp được."""
    view = build_sales_union(conn, tables)
    if view:
        tables[view] = build_unified_table_info(conn, view)
    return view
