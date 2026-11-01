from __future__ import annotations
import os
import re
import sqlite3
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
    """Load business data package (.csv, .xlsx, .sqlite, README.md) into SQLite DB with disk caching."""

    def __init__(self, business_dir: str):
        self.business_dir = os.path.abspath(business_dir)
        self.business_id = os.path.basename(self.business_dir)
        self.readme_text = ""
        self.table_names: List[str] = []
        self.column_mappings: Dict[str, Dict[str, str]] = {}
        
        # Disk cache for instant subsequent loading
        cache_dir = os.path.join(os.path.dirname(self.business_dir), ".cache_sqlite")
        os.makedirs(cache_dir, exist_ok=True)
        self.cache_file = os.path.join(cache_dir, f"{self.business_id}.sqlite")
        self.conn: Optional[sqlite3.Connection] = None

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
        if os.path.exists(self.cache_file) and os.path.getsize(self.cache_file) > 1024:
            try:
                self.conn = sqlite3.connect(self.cache_file)
                cursor = self.conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
                self.table_names = [r[0] for r in cursor.fetchall()]
                if len(self.table_names) > 0:
                    return self
            except Exception:
                pass

        # Otherwise build new SQLite database on disk
        self.conn = sqlite3.connect(self.cache_file)

        for fname in os.listdir(self.business_dir):
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

        return self

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
