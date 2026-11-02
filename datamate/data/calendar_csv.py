"""Đọc lịch Âm - Dương do BTC cung cấp (`calendar.csv`).

Rulebook DataMate: "Tra lịch âm trong `calendar.csv` cùng thư mục". Module này thay
cho bảng hard-code 2024-2027 trong `datamate/data/calendar.py`, và bổ sung các phép
tính cần cho rulebook: khoảng Tết (23 tháng Chạp → hết mùng 10 tháng Giêng), khoảng
một tháng âm, đổi ngày âm ↔ dương.
"""
from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class LunarDay:
    lunar_day: int
    lunar_month: int
    lunar_year: int
    is_leap: bool
    holiday: str


class LunarCalendar:
    """Bảng tra lịch âm dương nạp từ `calendar.csv`."""

    def __init__(self, rows: Iterable[Tuple[date, LunarDay]]):
        self._solar_to_lunar: Dict[date, LunarDay] = {}
        self._lunar_to_solar: Dict[Tuple[int, int, int, bool], date] = {}
        for solar, lunar in rows:
            self._solar_to_lunar[solar] = lunar
            key = (lunar.lunar_year, lunar.lunar_month, lunar.lunar_day, lunar.is_leap)
            self._lunar_to_solar.setdefault(key, solar)

    # ------------------------------------------------------------------ load
    @classmethod
    def from_csv(cls, path: str) -> "LunarCalendar":
        rows: List[Tuple[date, LunarDay]] = []
        with open(path, "r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                solar_raw = (row.get("date") or "").strip()
                if not solar_raw:
                    continue
                try:
                    year, month, day = (int(x) for x in solar_raw.split("-"))
                    solar = date(year, month, day)
                    lunar = LunarDay(
                        lunar_day=int(row["lunar_day"]),
                        lunar_month=int(row["lunar_month"]),
                        lunar_year=int(row["lunar_year"]),
                        is_leap=str(row.get("lunar_leap", "")).strip().lower() == "true",
                        holiday=(row.get("holiday") or "").strip(),
                    )
                except (ValueError, KeyError):
                    continue
                rows.append((solar, lunar))
        return cls(rows)

    def __bool__(self) -> bool:
        return bool(self._solar_to_lunar)

    def __len__(self) -> int:
        return len(self._solar_to_lunar)

    @property
    def solar_bounds(self) -> Optional[Tuple[date, date]]:
        if not self._solar_to_lunar:
            return None
        return min(self._solar_to_lunar), max(self._solar_to_lunar)

    # --------------------------------------------------------------- convert
    def to_lunar(self, solar: date) -> Optional[LunarDay]:
        return self._solar_to_lunar.get(solar)

    def to_solar(self, lunar_year: int, lunar_month: int, lunar_day: int) -> Optional[date]:
        return self._lunar_to_solar.get((lunar_year, lunar_month, lunar_day, False))

    def lunar_month_bounds(self, lunar_year: int, lunar_month: int) -> Optional[Tuple[date, date]]:
        days = [
            solar
            for solar, lunar in self._solar_to_lunar.items()
            if lunar.lunar_year == lunar_year
            and lunar.lunar_month == lunar_month
            and not lunar.is_leap
        ]
        if not days:
            return None
        return min(days), max(days)

    # ------------------------------------------------------------- rulebook
    def tet_range(self, lunar_year: int) -> Optional[Tuple[date, date]]:
        """Dịp Tết năm âm `lunar_year`: 23 tháng Chạp (năm trước) → hết mùng 10 tháng Giêng."""
        start = self.to_solar(lunar_year - 1, 12, 23)
        end = self.to_solar(lunar_year, 1, 10)
        if not start or not end:
            return None
        return start, end

    def pre_tet_window(self, lunar_year: int) -> Optional[Tuple[date, date]]:
        """Cùng số ngày ngay trước ngày 23 tháng Chạp (dùng cho "so với trước Tết")."""
        tet = self.tet_range(lunar_year)
        if not tet:
            return None
        start, end = tet
        length = (end - start).days + 1
        return start - timedelta(days=length), start - timedelta(days=1)

    def festival(self, lunar_month: int, lunar_day: int, lunar_year: int) -> Optional[date]:
        return self.to_solar(lunar_year, lunar_month, lunar_day)


_CALENDAR: Optional[LunarCalendar] = None


def find_calendar_csv(*roots: str) -> Optional[str]:
    """Tìm `calendar.csv` trong data root, thư mục cha, hoặc /data."""
    candidates: List[str] = []
    for root in roots:
        if not root:
            continue
        root = os.path.abspath(root)
        candidates += [
            os.path.join(root, "calendar.csv"),
            os.path.join(os.path.dirname(root), "calendar.csv"),
        ]
    candidates.append(os.path.join(os.sep, "data", "calendar.csv"))
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def configure_calendar(*roots: str) -> Optional[LunarCalendar]:
    """Nạp lịch từ CSV và đặt làm lịch dùng chung cho tiến trình."""
    global _CALENDAR
    path = find_calendar_csv(*roots)
    if not path:
        return None
    try:
        calendar = LunarCalendar.from_csv(path)
    except OSError:
        return None
    if calendar:
        _CALENDAR = calendar
        return calendar
    return None


def get_calendar() -> Optional[LunarCalendar]:
    """Trả về lịch đang dùng; tự nạp từ vị trí quen thuộc nếu chưa cấu hình."""
    global _CALENDAR
    if _CALENDAR is None:
        candidates = [
            os.environ.get("DATAMATE_CALENDAR", ""),
            os.path.join(os.getcwd(), "calendar.csv"),
            os.path.join(os.getcwd(), "data", "train", "calendar.csv"),
            os.path.join(os.getcwd(), "data", "public_test", "calendar.csv"),
            os.path.join(os.sep, "data", "calendar.csv"),
            os.path.join(os.sep, "app", "calendar.csv"),
        ]
        for path in candidates:
            if not path or not os.path.isfile(path):
                continue
            try:
                calendar = LunarCalendar.from_csv(path)
            except OSError:
                continue
            if calendar:
                _CALENDAR = calendar
                break
    return _CALENDAR
