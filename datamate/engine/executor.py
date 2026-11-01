from __future__ import annotations
import re
import sqlite3
import time
from typing import Any, List, Optional, Tuple


class SQLExecutionError(Exception):
    """Base class for SQL execution errors."""
    pass


class SQLSecurityError(SQLExecutionError):
    """Raised when dangerous SQL keywords or multi-statements are detected."""
    pass


class SQLTimeoutError(SQLExecutionError):
    """Raised when query execution exceeds the allowed timeout or opcode limit."""
    pass


class SQLSyntaxError(SQLExecutionError):
    """Raised when query syntax or schema validation fails."""
    pass


class SafeSQLExecutor:
    """Execute SQL queries safely in read-only mode with timeout and limits."""

    BLOCKED_KEYWORDS = ["insert", "update", "delete", "drop", "alter", "create", "truncate", "attach", "detach"]

    @staticmethod
    def _has_unquoted_semicolon(sql: str) -> bool:
        """Check if SQL contains semicolons outside string literals."""
        in_single = False
        in_double = False
        for c in sql:
            if c == "'" and not in_double:
                in_single = not in_single
            elif c == '"' and not in_single:
                in_double = not in_double
            elif c == ';' and not in_single and not in_double:
                return True
        return False

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
        if not clean_sql:
            raise SQLSyntaxError("Empty SQL query")

        # Disallow multi-statement execution
        if cls._has_unquoted_semicolon(clean_sql):
            raise SQLSecurityError("Multi-statement queries are strictly forbidden")

        first_word = clean_sql.split()[0].lower() if clean_sql else ""
        if first_word not in ("select", "with", "pragma"):
            raise SQLSecurityError(f"Forbidden query type: {first_word}")

        # Check for harmful statements
        for kw in cls.BLOCKED_KEYWORDS:
            if re.search(rf"\b{kw}\b", clean_sql, re.IGNORECASE):
                raise SQLSecurityError(f"Dangerous keyword detected: {kw}")

        # Register Unicode-aware LOWER and UPPER functions for Vietnamese text
        try:
            conn.create_function("lower", 1, lambda s: str(s).lower() if s is not None else None)
            conn.create_function("upper", 1, lambda s: str(s).upper() if s is not None else None)
        except Exception:
            pass

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
        except sqlite3.OperationalError as e:
            err_msg = str(e).lower()
            if "interrupted" in err_msg:
                raise SQLTimeoutError(f"Query exceeded timeout of {timeout_seconds}s or {max_opcodes} opcodes") from e
            elif "syntax" in err_msg or "no such" in err_msg:
                raise SQLSyntaxError(f"SQL syntax or schema error: {e}") from e
            raise SQLExecutionError(f"Database operational error: {e}") from e
        except Exception as e:
            raise SQLExecutionError(f"SQL execution error: {e}") from e
        finally:
            conn.set_progress_handler(None, 0)
