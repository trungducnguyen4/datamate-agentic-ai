from __future__ import annotations
import re
import sqlite3
import time
from typing import Any, List, Optional, Tuple


class SafeSQLExecutor:
    """Execute SQL queries safely in read-only mode with timeout and limits."""

    BLOCKED_KEYWORDS = ["insert", "update", "delete", "drop", "alter", "create", "truncate", "attach", "detach"]

    @classmethod
    def execute_query(
        cls,
        conn: sqlite3.Connection,
        sql: str,
        params: Optional[Tuple[Any, ...]] = None,
        max_rows: int = 1000,
        max_opcodes: int = 20_000_000,
        timeout_seconds: float = 10.0,
    ) -> Tuple[List[str], List[List[Any]]]:
        """Execute a SELECT query and return (columns, rows) safely."""
        clean_sql = sql.strip().rstrip(";")
        first_word = clean_sql.split()[0].lower() if clean_sql else ""

        if first_word not in ("select", "with", "pragma"):
            raise ValueError(f"Forbidden query type: {first_word}")

        # Check for harmful statements
        for kw in cls.BLOCKED_KEYWORDS:
            if re.search(rf"\b{kw}\b", clean_sql, re.IGNORECASE):
                raise ValueError(f"Dangerous keyword detected: {kw}")

        # Enforce read-only at database level
        try:
            conn.execute("PRAGMA query_only = ON;")
        except Exception:
            pass

        # Progress handler for execution timeout / infinite loop protection
        step_counter = [0]
        deadline = time.monotonic() + timeout_seconds

        def progress_limit():
            step_counter[0] += 1
            if step_counter[0] > max_opcodes or time.monotonic() > deadline:
                return 1  # Aborts execution with sqlite3.OperationalError: interrupted
            return 0

        conn.set_progress_handler(progress_limit, 1000)
        try:
            cursor = conn.cursor()
            cursor.execute(clean_sql, params or ())
            
            cols = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchmany(max_rows)
            # Convert tuples to lists
            rows_list = [list(r) for r in rows]
            return cols, rows_list
        finally:
            conn.set_progress_handler(None, 0)
