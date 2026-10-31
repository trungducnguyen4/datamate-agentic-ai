from __future__ import annotations
import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re
from typing import Optional, Tuple
from datamate.data.calendar import get_festival_solar_date


@dataclass
class DateRange:
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    target_month: Optional[str] = None  # YYYY-MM if asking about a specific month
    is_exact_day: bool = False


class TemporalResolver:
    """Resolve Vietnamese relative and absolute time expressions against as_of_date."""

    @staticmethod
    def parse_as_of_date(as_of_date_str: str) -> date:
        return datetime.strptime(as_of_date_str.strip(), "%Y-%m-%d").date()

    @classmethod
    def resolve(cls, query: str, as_of_date_str: str) -> Optional[DateRange]:
        q = query.lower()
        anchor = cls.parse_as_of_date(as_of_date_str)
        year = anchor.year
        month = anchor.month
        day = anchor.day

        # 1. Lunar festivals
        for fest in ["tết nguyên đán", "tết", "rằm tháng giêng", "vu lan", "trung thu", "mùng 1 tết"]:
            if fest in q:
                s_date = get_festival_solar_date(fest, year)
                if s_date:
                    return DateRange(start_date=s_date, end_date=s_date, is_exact_day=True)

        # 2. Specific YYYY-MM format in query (e.g., "tháng 3 năm 2026", "tháng 03/2026")
        month_match = re.search(r"tháng\s*(\d{1,2})(?:[\s/,-]+năm\s*|\/)(\d{4})", q)
        if month_match:
            m = int(month_match.group(1))
            y = int(month_match.group(2))
            last_day = calendar.monthrange(y, m)[1]
            return DateRange(
                start_date=f"{y:04d}-{m:02d}-01",
                end_date=f"{y:04d}-{m:02d}-{last_day:02d}",
                target_month=f"{y:04d}-{m:02d}",
            )

        # Specific single month without year: "tháng 1", "tháng 2", ...
        # Assume anchor year
        single_month_match = re.search(r"\btháng\s*(\d{1,2})\b", q)
        if single_month_match and "tháng này" not in q and "tháng trước" not in q and "tháng rồi" not in q:
            m = int(single_month_match.group(1))
            if 1 <= m <= 12:
                last_day = calendar.monthrange(year, m)[1]
                return DateRange(
                    start_date=f"{year:04d}-{m:02d}-01",
                    end_date=f"{year:04d}-{m:02d}-{last_day:02d}",
                    target_month=f"{year:04d}-{m:02d}",
                )

        # 3. "Hôm nay", "hôm qua", "hôm kia"
        if "hôm nay" in q or "ngày này" in q:
            d_str = anchor.strftime("%Y-%m-%d")
            return DateRange(start_date=d_str, end_date=d_str, is_exact_day=True)
        if "hôm qua" in q or "ngày qua" in q:
            d_str = (anchor - timedelta(days=1)).strftime("%Y-%m-%d")
            return DateRange(start_date=d_str, end_date=d_str, is_exact_day=True)
        if "hôm kia" in q:
            d_str = (anchor - timedelta(days=2)).strftime("%Y-%m-%d")
            return DateRange(start_date=d_str, end_date=d_str, is_exact_day=True)

        # 4. "Tuần rồi", "tuần trước", "tuần qua"
        if any(w in q for w in ["tuần rồi", "tuần trước", "tuần qua"]):
            # Monday of current week
            current_monday = anchor - timedelta(days=anchor.weekday())
            prev_monday = current_monday - timedelta(days=7)
            prev_sunday = prev_monday + timedelta(days=6)
            return DateRange(
                start_date=prev_monday.strftime("%Y-%m-%d"),
                end_date=prev_sunday.strftime("%Y-%m-%d"),
            )

        # "Tuần này"
        if "tuần này" in q:
            current_monday = anchor - timedelta(days=anchor.weekday())
            current_sunday = current_monday + timedelta(days=6)
            return DateRange(
                start_date=current_monday.strftime("%Y-%m-%d"),
                end_date=current_sunday.strftime("%Y-%m-%d"),
            )

        # 5. "Tháng rồi", "tháng trước"
        if any(w in q for w in ["tháng rồi", "tháng trước", "tháng vừa qua"]):
            if month == 1:
                prev_month = 12
                prev_year = year - 1
            else:
                prev_month = month - 1
                prev_year = year
            last_day = calendar.monthrange(prev_year, prev_month)[1]
            return DateRange(
                start_date=f"{prev_year:04d}-{prev_month:02d}-01",
                end_date=f"{prev_year:04d}-{prev_month:02d}-{last_day:02d}",
                target_month=f"{prev_year:04d}-{prev_month:02d}",
            )

        # "Tháng này"
        if "tháng này" in q:
            last_day = calendar.monthrange(year, month)[1]
            return DateRange(
                start_date=f"{year:04d}-{month:02d}-01",
                end_date=f"{year:04d}-{month:02d}-{last_day:02d}",
                target_month=f"{year:04d}-{month:02d}",
            )

        # 6. "Năm ngoái", "năm trước"
        if any(w in q for w in ["năm ngoái", "năm trước", "năm vừa qua"]):
            prev_year = year - 1
            return DateRange(
                start_date=f"{prev_year:04d}-01-01",
                end_date=f"{prev_year:04d}-12-31",
            )

        # "Năm nay"
        if "năm nay" in q:
            return DateRange(
                start_date=f"{year:04d}-01-01",
                end_date=f"{year:04d}-12-31",
            )

        # 7. Quý ("quý 1", "quý 2", "quý 3", "quý 4", "quý này", "quý trước")
        quarter_match = re.search(r"quý\s*([1-4]|i{1,3}|iv)", q)
        if quarter_match:
            raw_q = quarter_match.group(1)
            roman_map = {"1": 1, "i": 1, "2": 2, "ii": 2, "3": 3, "iii": 3, "4": 4, "iv": 4}
            q_num = roman_map.get(raw_q, 1)
            start_m = (q_num - 1) * 3 + 1
            end_m = q_num * 3
            last_day = calendar.monthrange(year, end_m)[1]
            return DateRange(
                start_date=f"{year:04d}-{start_m:02d}-01",
                end_date=f"{year:04d}-{end_m:02d}-{last_day:02d}",
            )

        return None
