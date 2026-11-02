from __future__ import annotations
import hashlib
import os
import re
import sqlite3
import tempfile
import unicodedata
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


def strip_accents(s: str) -> str:
    """Strip Vietnamese accents for safe matching."""
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("đ", "d").replace("Đ", "d")


def sanitize_table_name(name: str) -> str:
    """Sanitize filename/sheet name into a safe SQL table name."""
    clean = strip_accents(name.strip().lower())
    clean = re.sub(r"[^\w]", "_", clean)
    clean = re.sub(r"_+", "_", clean).strip("_")
    if clean and clean[0].isdigit():
        clean = "t_" + clean
    return clean or "table"


def sanitize_column_name(col: str) -> str:
    """Sanitize column name for SQLite."""
    clean = strip_accents(str(col).strip().lower())
    clean = re.sub(r"[^\w]", "_", clean)
    clean = re.sub(r"_+", "_", clean).strip("_")
    if clean and clean[0].isdigit():
        clean = "c_" + clean
    return clean or "col"


_DATE_PATTERNS = (
    (re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$"), "ymd"),
    (re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$"), "dmy"),
    (re.compile(r"^(\d{1,2})\s+thg\s+(\d{1,2})\s+(\d{4})$", re.IGNORECASE), "dmy"),
)


def parse_date_token(value: Any) -> Optional[str]:
    """Chuẩn hoá các định dạng ngày thường gặp về ISO `YYYY-MM-DD`."""
    if not isinstance(value, str):
        if isinstance(value, (int, float)) and 40000 <= value <= 55000:
            dt = pd.to_datetime(value, unit="D", origin="1899-12-30", errors="coerce")
            if pd.notna(dt):
                return dt.strftime("%Y-%m-%d")
        return None
    text = value.strip()
    try:
        fval = float(text)
        if 40000 <= fval <= 55000:
            dt = pd.to_datetime(fval, unit="D", origin="1899-12-30", errors="coerce")
            if pd.notna(dt):
                return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        pass
    for pattern, order in _DATE_PATTERNS:
        match = pattern.match(text)
        if not match:
            continue
        groups = match.groups()
        if order == "ymd":
            year, month, day = (int(g) for g in groups)
        else:
            day, month, year = (int(g) for g in groups)
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"
    return None


def parse_vn_num_val(val: Any) -> float:
    """Parse Vietnamese and informal accounting number formats into float.
    Handles '55.000đ', '25k', '41.5k', '1.5tr', '120,000', '1.250.000', '12,5'.
    """
    if val is None or pd.isna(val):
        return np.nan
    val_str = str(val).strip().lower()
    if not val_str or val_str in ("nan", "none", "null"):
        return np.nan
    multiplier = 1.0
    if val_str.endswith("k"):
        multiplier = 1000.0
        val_str = val_str[:-1]
    elif val_str.endswith("tr") or val_str.endswith("m"):
        multiplier = 1000000.0
        val_str = val_str.rstrip("trm")

    val_str = re.sub(r"[\sđĐ₫]|vnd|dong|đồng", "", val_str)
    if not val_str or not re.search(r"\d", val_str):
        return np.nan

    # Detect separators
    if "," in val_str and "." in val_str:
        if val_str.rfind(".") > val_str.rfind(","):
            val_str = val_str.replace(",", "")
        else:
            val_str = val_str.replace(".", "").replace(",", ".")
    elif "," in val_str:
        parts = val_str.split(",")
        if all(len(p) == 3 for p in parts[1:]):
            val_str = val_str.replace(",", "")
        elif len(parts) == 2 and len(parts[1]) in (1, 2, 4):
            val_str = val_str.replace(",", ".")
        else:
            val_str = val_str.replace(",", "")
    elif "." in val_str:
        parts = val_str.split(".")
        if all(len(p) == 3 for p in parts[1:]):
            val_str = val_str.replace(".", "")

    try:
        return float(val_str) * multiplier
    except Exception:
        return np.nan


def clean_dataframe_vectorized(df: pd.DataFrame) -> pd.DataFrame:
    """Fast vectorized cleaning for dates, numbers, currency in DataFrame."""
    if df.empty:
        return df

    for col in df.columns:
        col_lower = str(col).lower()
        is_date_named = any(k in col_lower for k in ["ngay", "thoi_gian", "date", "time", "hsd", "exp"])
        is_amount_named = any(k in col_lower for k in ["tien", "gia", "amount", "sl", "so_luong", "don_gia", "thanh_tien", "chiet_khau", "tri_gia"])

        # Check numeric Excel serial date (e.g. 40000 to 55000 corresponding to years 2010 to 2050)
        if pd.api.types.is_numeric_dtype(df[col]):
            valid = df[col].dropna()
            if len(valid) > 0 and ((valid >= 40000) & (valid <= 55000)).mean() > 0.8:
                if is_date_named or not is_amount_named:
                    df[col] = pd.to_datetime(df[col], unit="D", origin="1899-12-30", errors="coerce").dt.strftime("%Y-%m-%d")
                    continue

        if df[col].dtype == object:
            # Check non-null values
            s = df[col].dropna().astype(str).str.strip()
            if len(s) == 0:
                continue

            first_val = s.iloc[0]

            # Excel serial number stored as string
            numeric_s = pd.to_numeric(s, errors="coerce")
            if numeric_s.notna().sum() > len(s) * 0.8:
                valid = numeric_s.dropna()
                if len(valid) > 0 and ((valid >= 40000) & (valid <= 55000)).mean() > 0.8:
                    if is_date_named or not is_amount_named:
                        df[col] = pd.to_datetime(numeric_s, unit="D", origin="1899-12-30", errors="coerce").dt.strftime("%Y-%m-%d")
                        continue

            # 0. Ngày ở nhiều định dạng trộn lẫn (Excel hay trộn '01/01/2026' với
            #    '2025-03-01' và '9 thg 8 2026' hoặc số serial 45658). Chuẩn hoá theo TỪNG giá trị nếu có dấu hiệu ngày.
            if any(k in first_val.lower() for k in ["-", "/", "thg", "ngay"]) or (re.search(r"\d", first_val) and is_date_named):
                parsed_dates = s.map(parse_date_token)
                if parsed_dates.notna().sum() >= max(3, int(len(s) * 0.4)):
                    df[col] = parsed_dates.reindex(df.index)
                    continue

            # 1. Date format '1 thg 6 2025' or '01 thg 06 2025'
            if "thg" in first_val.lower():
                extracted = s.str.extract(r"^(\d{1,2})\s+thg\s+(\d{1,2})\s+(\d{4})$", flags=re.IGNORECASE)
                if not extracted[0].isna().all():
                    df[col] = extracted[2].str.zfill(4) + "-" + extracted[1].str.zfill(2) + "-" + extracted[0].str.zfill(2)
                    continue

            # 2. Date format '01/02/2025' or '1/2/2025'
            if "/" in first_val:
                extracted = s.str.extract(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
                if not extracted[0].isna().all():
                    df[col] = extracted[2].str.zfill(4) + "-" + extracted[1].str.zfill(2) + "-" + extracted[0].str.zfill(2)
                    continue

            # 3. Numeric values with commas/dots/currency (e.g. '560,000', '65,000.0000', '25.000đ', '25k', '41.5k')
            if re.search(r"[\d]", first_val) and not is_date_named:
                parsed_nums = s.map(parse_vn_num_val)
                if (parsed_nums.notna().sum() >= max(2, int(len(s) * 0.5))) or is_amount_named:
                    if parsed_nums.notna().sum() > len(s) * 0.4:
                        df[col] = parsed_nums.reindex(df.index)

    return df


def find_header_row(df: pd.DataFrame) -> int:
    """Detect if table has top title/metadata rows and identify real header row."""
    keywords = [
        "ngay", "thoi_gian", "date", "time",
        "ma", "id", "code", "stt",
        "ten", "san_pham", "hang", "mat_hang", "mon",
        "so_luong", "sl", "qty", "quantity",
        "don_gia", "gia", "price", "unit_price",
        "thanh_tien", "tien", "amount", "tri_gia", "tong_tien",
        "khach", "khach_hang", "customer",
        "trang_thai", "status",
        "don_vi", "dvt", "unit",
        "giam_gia", "chiet_khau", "discount",
    ]
    best_row = 0
    best_score = -1.0
    total_cols = len(df.columns)
    if total_cols == 0:
        return 0

    max_check = min(15, len(df))
    for i in range(max_check):
        row = df.iloc[i]
        non_null_count = row.notna().sum()
        if non_null_count == 0:
            continue

        row_cells = [strip_accents(str(x)).strip().lower() for x in row.dropna().values]
        numeric_count = sum(1 for c in row_cells if re.match(r"^[\d\.,\s]+$", c))
        if numeric_count > non_null_count * 0.5:
            continue

        matched_keywords = 0
        for cell in row_cells:
            tokens = re.split(r"[^\w]+", cell)
            for kw in keywords:
                if kw in tokens or kw in cell:
                    matched_keywords += 1
                    break

        coverage_ratio = non_null_count / total_cols
        score = (matched_keywords * 3.0) + (coverage_ratio * 5.0)

        if matched_keywords >= 2 and score > best_score:
            best_score = score
            best_row = i

    return best_row


class BusinessDataLoader:
    """Load business data package (.csv, .xlsx, .sqlite, README.md) into SQLite DB with disk caching.

    Cache KHÔNG bao giờ được ghi vào thư mục dữ liệu: BTC mount `/data` ở chế độ
    read-only (Rule 5). Cache mặc định nằm ở ``<tmp>/datamate_cache`` (hoặc biến môi
    trường ``DATAMATE_CACHE_DIR``); nếu không ghi được thì fallback sang SQLite
    in-memory để pipeline vẫn chạy được.
    """

    def __init__(self, business_dir: str):
        self.business_dir = os.path.abspath(business_dir)
        self.business_id = os.path.basename(self.business_dir)
        self.readme_text = ""
        self.table_names: List[str] = []
        self.column_mappings: Dict[str, Dict[str, str]] = {}
        self.cache_file: Optional[str] = self._cache_path()
        self.conn: Optional[sqlite3.Connection] = None

    # ------------------------------------------------------------------ cache
    def _files_signature(self) -> str:
        entries = ["cache_v3"]
        try:
            for name in sorted(os.listdir(self.business_dir)):
                path = os.path.join(self.business_dir, name)
                if os.path.isfile(path):
                    stat = os.stat(path)
                    entries.append(f"{name}:{stat.st_size}")
        except OSError:
            pass
        digest = hashlib.sha1(
            "|".join([self.business_dir] + entries).encode("utf-8", "replace")
        ).hexdigest()[:16]
        return f"{sanitize_table_name(self.business_id)}_{digest}.sqlite"

    def _cache_path(self) -> Optional[str]:
        base = os.environ.get("DATAMATE_CACHE_DIR") or os.path.join(
            tempfile.gettempdir(), "datamate_cache"
        )
        try:
            os.makedirs(base, exist_ok=True)
            return os.path.join(base, self._files_signature())
        except OSError:
            # Read-only filesystem: dùng in-memory ở load()
            return None

    def load(self) -> BusinessDataLoader:
        """Scan directory and load all data files."""
        if not os.path.exists(self.business_dir):
            self.conn = sqlite3.connect(":memory:")
            self._setup_conn()
            return self

        # Read README.md if present
        readme_path = os.path.join(self.business_dir, "README.md")
        if os.path.exists(readme_path):
            with open(readme_path, "r", encoding="utf-8", errors="replace") as f:
                self.readme_text = f.read()

        # If disk cache already exists, connect directly!
        expected_tables = self._count_source_files()
        if self.cache_file and os.path.exists(self.cache_file) and os.path.getsize(self.cache_file) > 1024:
            try:
                self.conn = sqlite3.connect(self.cache_file)
                cursor = self.conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
                self.table_names = [r[0] for r in cursor.fetchall()]
                if len(self.table_names) >= expected_tables > 0:
                    self._setup_conn()
                    return self
                # Cache dở dang (bị kill giữa chừng) → xoá và build lại
                self.conn.close()
                self.conn = None
                os.remove(self.cache_file)
            except Exception:
                pass

        # Build vào file tạm riêng cho process rồi rename nguyên tử: tránh cache dở dang và xung đột đa tiến trình
        build_path = f"{self.cache_file}.{os.getpid()}.building" if self.cache_file else None
        if build_path and os.path.exists(build_path):
            try:
                os.remove(build_path)
            except OSError:
                build_path = None
        try:
            self.conn = sqlite3.connect(build_path) if build_path else sqlite3.connect(":memory:")
        except Exception:
            build_path = None
            self.conn = sqlite3.connect(":memory:")

        for fname in sorted(os.listdir(self.business_dir)):
            fpath = os.path.join(self.business_dir, fname)
            if os.path.isdir(fpath):
                continue

            lower_name = fname.lower()
            if lower_name.endswith(".csv"):
                self._load_csv(fpath, fname)
            elif lower_name.endswith(".xlsx") or lower_name.endswith(".xls"):
                self._load_excel(fpath, fname)
            elif lower_name.endswith(".sqlite") or lower_name.endswith(".db"):
                self._load_sqlite(fpath)

        if build_path and self.cache_file:
            try:
                self.conn.commit()
                self.conn.close()
                os.replace(build_path, self.cache_file)
                self.conn = sqlite3.connect(self.cache_file)
            except OSError:
                # Nếu bị khoá hoặc xung đột quyền ghi, mở lại file sẵn có hoặc dùng in-memory
                if os.path.exists(self.cache_file):
                    self.conn = sqlite3.connect(self.cache_file)
                elif os.path.exists(build_path):
                    self.conn = sqlite3.connect(build_path)
                else:
                    self.conn = sqlite3.connect(":memory:")

        self._setup_conn()
        return self

    def _setup_conn(self) -> None:
        if self.conn is not None:
            try:
                self.conn.create_function("lower", 1, lambda s: str(s).lower() if s is not None else None)
                self.conn.create_function("upper", 1, lambda s: str(s).upper() if s is not None else None)
                self.conn.create_function("unaccent", 1, lambda s: strip_accents(str(s)).lower() if s is not None else None)
            except Exception:
                pass

    def _count_source_files(self) -> int:
        try:
            return sum(
                1
                for name in os.listdir(self.business_dir)
                if os.path.isfile(os.path.join(self.business_dir, name))
                and name.lower().endswith((".csv", ".xlsx", ".xls", ".sqlite", ".db"))
            )
        except OSError:
            return 0

    @staticmethod
    def _drop_footer_rows(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        def is_footer(row):
            cells = [str(x).strip().lower() for x in row.dropna().values[:3]]
            for c in cells:
                if re.search(r"^(cộng|cong|tổng|tong|tổng cộng|tong cong|ghi chú|ghi chu|note|kết chuyển)\b", c):
                    return True
            return False
        is_f = df.apply(is_footer, axis=1)
        if is_f.any():
            df = df[~is_f].reset_index(drop=True)
        return df

    @staticmethod
    def _forward_fill_merged_order_cells(df: pd.DataFrame, cols: list) -> pd.DataFrame:
        if df.empty or len(cols) < 2:
            return df
        clean_cols = [strip_accents(str(c)).lower() for c in cols]
        id_idx = next(
            (
                i for i, c in enumerate(clean_cols)
                if any(k in c for k in ["ma_don", "ma don", "ma_hoa_don", "ma hoa don", "order_id", "invoice", "so_phieu", "so phieu", "ma_phieu", "ma phieu"])
                or ("ma" in c and not any(k in c for k in ["sp", "san_pham", "san pham", "hang", "mon", "thuoc", "item"]))
            ),
            None,
        )

        prod_keywords = [
            "san_pham", "san pham", "ten hang", "ten_hang", "mat hang", "mat_hang",
            "ten mon", "ten_mon", "item", "product", "ten thuoc", "ten_thuoc", "ten hang hoa", "hang hoa"
        ]
        prod_idx = next((i for i, c in enumerate(clean_cols) if any(k in c for k in prod_keywords)), None)
        if prod_idx is None:
            def is_standalone_hang(c_str: str) -> bool:
                tokens = c_str.replace("_", " ").split()
                for idx, tok in enumerate(tokens):
                    if tok in ("hang", "mon", "sp"):
                        prev = tokens[idx - 1] if idx > 0 else ""
                        if prev not in ("don", "dat", "khach", "giao", "nhan", "tra", "mua", "ban", "nhap", "ma", "cua"):
                            return True
                return False
            prod_idx = next((i for i, c in enumerate(clean_cols) if is_standalone_hang(c)), None)

        if id_idx is not None and prod_idx is not None and id_idx != prod_idx and df.iloc[:, id_idx].isna().sum() > 0:
            fill_keywords = [
                "ma", "don", "hoa don", "hoa_don", "order_id", "invoice", "so phieu", "so_phieu",
                "ngay", "thoi gian", "thoi_gian", "date", "time", "khach", "customer",
                "trang thai", "trang_thai", "status", "nhan vien", "nhan_vien", "nguoi ban", "thu ngan"
            ]
            fill_cols = [
                cols[i] for i, c in enumerate(clean_cols)
                if any(k in c for k in fill_keywords) and not any(p in c for p in [
                    "san_pham", "san pham", "ten hang", "so luong", "so_luong", "don gia", "don_gia",
                    "gia", "tien", "tri_gia", "tri gia", "thanh_tien", "thanh tien"
                ])
            ]
            for fc in fill_cols:
                df[fc] = df[fc].ffill()
        return df

    def _load_csv(self, fpath: str, fname: str) -> None:
        table_name = sanitize_table_name(os.path.splitext(fname)[0])
        try:
            try:
                df = pd.read_csv(fpath, encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(fpath, encoding="utf-8-sig")

            if not df.empty:
                if df.columns[0].startswith("Unnamed") or len(df.columns) < 2:
                    h_idx = find_header_row(df)
                    if h_idx > 0:
                        raw_cols = df.iloc[h_idx].values
                        cols = [str(c).strip() if pd.notna(c) and str(c).strip() else f"col_{j}" for j, c in enumerate(raw_cols)]
                        df = df.iloc[h_idx + 1:].reset_index(drop=True)
                        df.columns = cols
                df = self._drop_footer_rows(df)
                df = self._forward_fill_merged_order_cells(df, list(df.columns))
                df = df.drop_duplicates().reset_index(drop=True)

            self._save_df_to_sqlite(df, table_name)
        except Exception as e:
            print(f"Warning: Failed to load CSV {fname}: {e}")

    def _load_excel(self, fpath: str, fname: str) -> None:
        base_name = sanitize_table_name(os.path.splitext(fname)[0])
        try:
            excel_file = pd.ExcelFile(fpath)
            for sheet in excel_file.sheet_names:
                df = excel_file.parse(sheet, header=None)
                if df.empty or len(df) == 0:
                    continue

                h_idx = find_header_row(df)
                if h_idx > 0 or df.iloc[0].isna().sum() > len(df.columns) / 2:
                    raw_cols = df.iloc[h_idx].values
                    cols = [str(c).strip() if pd.notna(c) and str(c).strip() else f"col_{j}" for j, c in enumerate(raw_cols)]
                    df = df.iloc[h_idx + 1:].reset_index(drop=True)
                    df.columns = cols
                else:
                    raw_cols = df.iloc[0].values
                    cols = [str(c).strip() if pd.notna(c) and str(c).strip() else f"col_{j}" for j, c in enumerate(raw_cols)]
                    df = df.iloc[1:].reset_index(drop=True)
                    df.columns = cols

                sheet_sanitized = sanitize_table_name(sheet)
                table_name = f"{base_name}_{sheet_sanitized}" if len(excel_file.sheet_names) > 1 else base_name

                # Drop summary/footer rows and forward-fill merged order-level cells
                df = self._drop_footer_rows(df)
                df = self._forward_fill_merged_order_cells(df, cols)
                df = df.drop_duplicates().reset_index(drop=True)
                self._save_df_to_sqlite(df, table_name)
        except Exception as e:
            print(f"Warning: Failed to load Excel {fname}: {e}")

    def _load_sqlite(self, fpath: str) -> None:
        try:
            disk_conn = sqlite3.connect(fpath)
            disk_conn.backup(self.conn)
            cursor = self.conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            self.table_names.extend([row[0] for row in cursor.fetchall()])
            disk_conn.close()
        except Exception as e:
            print(f"Warning: Failed to load SQLite {fpath}: {e}")

    def _save_df_to_sqlite(self, df: pd.DataFrame, table_name: str) -> None:
        if df.empty and len(df.columns) == 0:
            return

        # Vectorized clean dates and numbers
        df = clean_dataframe_vectorized(df)

        orig_cols = list(df.columns)
        safe_cols = [sanitize_column_name(c) for c in orig_cols]
        unique_safe = []
        counts = {}
        for c in safe_cols:
            if c not in counts:
                counts[c] = 1
                unique_safe.append(c)
            else:
                counts[c] += 1
                unique_safe.append(f"{c}_{counts[c]}")

        self.column_mappings[table_name] = dict(zip(orig_cols, unique_safe))
        df.columns = unique_safe

        # Store in sqlite
        df.to_sql(table_name, self.conn, if_exists="replace", index=False)
        if table_name not in self.table_names:
            self.table_names.append(table_name)

    def close(self) -> None:
        try:
            if self.conn:
                self.conn.close()
        except Exception:
            pass
