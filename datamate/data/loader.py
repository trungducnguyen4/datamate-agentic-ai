from __future__ import annotations
import os
import re
import sqlite3
from typing import Dict, List, Optional, Tuple
import pandas as pd


def sanitize_table_name(name: str) -> str:
    """Sanitize filename/sheet name into a safe SQL table name."""
    clean = re.sub(r"[^\w]", "_", name.strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    if clean and clean[0].isdigit():
        clean = "t_" + clean
    return clean or "table"


def sanitize_column_name(col: str) -> str:
    """Sanitize column name for SQLite."""
    clean = str(col).strip().lower()
    clean = re.sub(r"[^\w]", "_", clean)
    clean = re.sub(r"_+", "_", clean).strip("_")
    if clean and clean[0].isdigit():
        clean = "c_" + clean
    return clean or "col"


class BusinessDataLoader:
    """Load business data package (.csv, .xlsx, .sqlite, README.md) into an in-memory SQLite DB."""

    def __init__(self, business_dir: str):
        self.business_dir = os.path.abspath(business_dir)
        self.business_id = os.path.basename(self.business_dir)
        self.readme_text = ""
        self.table_names: List[str] = []
        self.column_mappings: Dict[str, Dict[str, str]] = {}  # table -> {orig_col: safe_col}
        self.conn = sqlite3.connect(":memory:")

    def load(self) -> BusinessDataLoader:
        """Scan directory and load all data files."""
        if not os.path.exists(self.business_dir):
            return self

        # Read README.md if present
        readme_path = os.path.join(self.business_dir, "README.md")
        if os.path.exists(readme_path):
            with open(readme_path, "r", encoding="utf-8", errors="replace") as f:
                self.readme_text = f.read()

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
            # Try utf-8 first, fallback to utf-8-sig or latin1
            try:
                df = pd.read_csv(fpath, encoding="utf-8")
            except UnicodeDecodeError:
                df = pd.read_csv(fpath, encoding="utf-8-sig")
            self._save_df_to_sqlite(df, table_name)
        except Exception as e:
            print(f"Warning: Failed to load CSV {fname}: {e}")

    def _load_excel(self, fpath: str, fname: str) -> None:
        base_name = sanitize_table_name(os.path.splitext(fname)[0])
        try:
            excel_file = pd.ExcelFile(fpath)
            for sheet in excel_file.sheet_names:
                df = excel_file.parse(sheet)
                sheet_sanitized = sanitize_table_name(sheet)
                table_name = f"{base_name}_{sheet_sanitized}" if len(excel_file.sheet_names) > 1 else base_name
                self._save_df_to_sqlite(df, table_name)
        except Exception as e:
            print(f"Warning: Failed to load Excel {fname}: {e}")

    def _load_sqlite(self, fpath: str) -> None:
        try:
            disk_conn = sqlite3.connect(fpath)
            # Copy tables from disk sqlite to in-memory sqlite
            disk_conn.backup(self.conn)
            cursor = self.conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            self.table_names.extend([row[0] for row in cursor.fetchall()])
            disk_conn.close()
        except Exception as e:
            print(f"Warning: Failed to load SQLite {fpath}: {e}")

    def _save_df_to_sqlite(self, df: pd.DataFrame, table_name: str) -> None:
        if df.empty and len(df.columns) == 0:
            return

        orig_cols = list(df.columns)
        safe_cols = [sanitize_column_name(c) for c in orig_cols]
        # Resolve any duplicates in safe_cols
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
            self.conn.close()
        except Exception:
            pass
