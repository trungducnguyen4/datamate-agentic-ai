from __future__ import annotations
import hashlib
import os
import re
import sqlite3
import tempfile
import unicodedata
from typing import Any, Dict, List, Optional, Tuple
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
        return None
    text = value.strip()
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


def clean_dataframe_vectorized(df: pd.DataFrame) -> pd.DataFrame:
    """Fast vectorized cleaning for dates, numbers, currency in DataFrame."""
    if df.empty:
        return df

    for col in df.columns:
        if df[col].dtype == object:
            # Check non-null values
            s = df[col].dropna().astype(str).str.strip()
            if len(s) == 0:
                continue

            # 0. Ngày ở nhiều định dạng trộn lẫn (Excel hay trộn '01/01/2026' với
            #    '2025-03-01' và '9 thg 8 2026'). Chuẩn hoá theo TỪNG giá trị.
            parsed_dates = s.map(parse_date_token)
            if parsed_dates.notna().sum() >= max(3, int(len(s) * 0.8)):
                df[col] = parsed_dates.reindex(df.index)
                continue

            first_val = s.iloc[0]

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

            # 3. Numeric values with commas/dots/currency (e.g. '560,000', '65,000.0000', '25.000đ')
            if re.search(r"[\d]", first_val) and not re.search(r"[a-zA-Z\u00C0-\u024F\u1EA0-\u1EF9]", first_val):
                clean_s = s.str.replace(r"[\sđĐ₫]", "", regex=True).str.replace(",", "", regex=False)
                # Check for Vietnamese dot thousand separator
                if "." in first_val and clean_s.str.contains(r"^\d+\.\d{3}$").any():
                    clean_s = clean_s.str.replace(".", "", regex=False)
                converted = pd.to_numeric(clean_s, errors="coerce")
                if converted.notna().sum() > len(s) * 0.7:
                    df[col] = converted

    return df


def find_header_row(df: pd.DataFrame) -> int:
    """Detect if table has top title/metadata rows and identify real header row."""
    keywords = ["ngay", "ma", "ten", "don", "gia", "so luong", "thanh tien", "khach", "trang thai", "date", "name", "id", "status"]
    for i in range(min(10, len(df))):
        row_str = strip_accents(" ".join([str(x).lower() for x in df.iloc[i].dropna().values]))
        matches = sum(1 for kw in keywords if kw in row_str)
        if matches >= 2:
            return i
    return 0


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
        entries = ["cache_v2"]
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
        # Special high-performance handler for 5-Million-Row Dataset
        if self.business_id == "biz_mega_5m":
            csv_path = os.path.abspath("datamate_vietnamese_qa_5m.csv")
            if os.path.exists(csv_path):
                import duckdb
                self.conn = duckdb.connect(":memory:")
                self.conn.execute(f"CREATE VIEW sales_5m AS SELECT * FROM read_csv_auto('{csv_path}');")
                self.table_names = ["sales_5m"]
                readme_path = os.path.join(self.business_dir, "README.md")
                if os.path.exists(readme_path):
                    with open(readme_path, "r", encoding="utf-8", errors="replace") as f:
                        self.readme_text = f.read()
                return self

        if not os.path.exists(self.business_dir):
            self.conn = sqlite3.connect(":memory:")
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
                    return self
                # Cache dở dang (bị kill giữa chừng) → xoá và build lại
                self.conn.close()
                self.conn = None
                os.remove(self.cache_file)
            except Exception:
                pass

        # Build vào file tạm rồi rename nguyên tử: tránh cache dở dang.
        build_path = f"{self.cache_file}.building" if self.cache_file else None
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
                pass

        return self

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
