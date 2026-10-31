from __future__ import annotations
import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import re
from typing import Optional, Tuple
from datamate.data.calendar import get_festival_solar_date, get_lunar_range


@dataclass
class DateRange:
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    target_month: Optional[str] = None  # YYYY-MM if asking about a specific month
    is_exact_day: bool = False
    is_ambiguous: bool = False


class TemporalResolver:
    """Resolve Vietnamese relative and absolute time expressions strictly against as_of_date.

    Guarantees:
    - Never uses machine local time (`datetime.now()`).
    - Distinguishes dynamic rolling intervals ("7 ngày gần đây") from calendar weeks ("tuần rồi").
    - Resolves traditional Vietnamese Lunar calendar expressions (Tết, Rằm tháng Giêng, Tháng Giêng).
    - Flags ambiguous relative expressions ("bữa giờ") for risk-aware abstention.
    """

    @staticmethod
    def parse_as_of_date(as_of_date_str: str) -> date:
        return datetime.strptime(as_of_date_str.strip(), "%Y-%m-%d").date()

    @classmethod
    def resolve(cls, query: str, as_of_date_str: str) -> Optional[DateRange]:
        q = query.lower().strip()
        anchor = cls.parse_as_of_date(as_of_date_str)
        year = anchor.year
        month = anchor.month
        day = anchor.day

        # Check for ambiguous time expression: "bữa giờ"
        if "bữa giờ" in q or "bữa nay tới giờ" in q or "bua gio" in q:
            return DateRange(start_date="", end_date="", is_ambiguous=True)

        # 0. ISO Date Format (e.g., 2026-03-01)
        iso_match = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", q)
        if iso_match:
            iso_d = iso_match.group(0)
            return DateRange(start_date=iso_d, end_date=iso_d, is_exact_day=True)

        # 1. Complex Lunar expressions
        # "từ mùng 1 đến rằm tháng giêng"
        if any(w in q for w in ["từ mùng 1 đến rằm tháng giêng", "mùng 1 đến rằm tháng giêng", "mung 1 den ram thang gieng"]):
            r = get_lunar_range("mung_1_den_ram", year)
            if r:
                return DateRange(start_date=r[0], end_date=r[1])

        # "tháng giêng" / "tháng giêng năm nay"
        if ("tháng giêng" in q or "thang gieng" in q) and not any(w in q for w in ["rằm tháng giêng", "ram thang gieng", "sau tết", "sau tet"]):
            r = get_lunar_range("thang_gieng", year)
            if r:
                return DateRange(start_date=r[0], end_date=r[1])

        # "từ sau tết đến giờ", "từ sau tết đến nay", "sau tết đến giờ", "từ tết đến giờ", "từ tết đến nay"
        if any(w in q for w in ["sau tết đến giờ", "sau tết đến nay", "từ tết đến giờ", "từ tết đến nay", "sau tết",
                                "tu sau tet den gio", "tu sau tet den nay", "sau tet den gio", "tu tet den gio"]):
            tet_date = get_festival_solar_date("tet", year)
            if tet_date:
                return DateRange(start_date=tet_date, end_date=anchor.strftime("%Y-%m-%d"))

        # Single Lunar festivals (Order from most specific to least specific)
        for fest in ["tết nguyên đán", "mùng 1 tết", "mùng 2 tết", "mùng 3 tết", "mung 1 tet", "mung 2 tet", "mung 3 tet",
                     "rằm tháng giêng", "ram thang gieng", "vu lan", "trung thu", "tết", "tet"]:
            if fest in q:
                clean_fest = fest.replace("mung", "mùng").replace("ram thang gieng", "rằm tháng giêng").replace("tet", "tết")
                s_date = get_festival_solar_date(clean_fest, year)
                if s_date:
                    return DateRange(start_date=s_date, end_date=s_date, is_exact_day=True)

        # 2. "Từ đầu tháng đến hết hôm qua"
        if any(w in q for w in ["từ đầu tháng đến hết hôm qua", "đầu tháng đến hôm qua", "tu dau thang den het hom qua", "dau thang den hom qua"]):
            yesterday = anchor - timedelta(days=1)
            start_str = f"{year:04d}-{month:02d}-01"
            end_str = yesterday.strftime("%Y-%m-%d")
            return DateRange(start_date=start_str, end_date=end_str)

        # 3. Dynamic rolling "7 ngày gần đây", "7 ngày qua", "bảy ngày gần đây"
        # Window: [anchor - 6 days, anchor] (Total exactly 7 days including as_of_date)
        if any(w in q for w in ["7 ngày gần đây", "7 ngày qua", "bảy ngày gần đây", "bảy ngày qua", "7 ngay gan day", "7 ngay qua"]):
            start_d = anchor - timedelta(days=6)
            return DateRange(
                start_date=start_d.strftime("%Y-%m-%d"),
                end_date=anchor.strftime("%Y-%m-%d"),
            )

        # 4. "Cùng kỳ năm ngoái", "cùng kỳ năm trước"
        if any(w in q for w in ["cùng kỳ năm ngoái", "cùng kỳ năm trước", "cung ky nam ngoai", "cung ky nam truoc"]):
            prev_year = year - 1
            last_day_prev = calendar.monthrange(prev_year, month)[1]
            return DateRange(
                start_date=f"{prev_year:04d}-{month:02d}-01",
                end_date=f"{prev_year:04d}-{month:02d}-{last_day_prev:02d}",
                target_month=f"{prev_year:04d}-{month:02d}",
            )

        # 5. Invalid Month Check: "tháng 13", "thang 13"
        if re.search(r"\bth[aá]ng\s*(1[3-9]|[2-9]\d)\b", q):
            return DateRange(start_date="9999-12-31", end_date="9999-12-31")

        # 6. Explicit specific date DD/MM or DD/MM/YYYY
        # e.g., "ngày 03/04/2026", "ngày 04/03", "ngay 04/03", "03-04-2026"
        date_explicit_match = re.search(r"(?:ngày|ngay)\s*(\d{1,2})[\/\-](\d{1,2})(?:[\/\-](\d{4}))?", q)
        if date_explicit_match:
            d_day = int(date_explicit_match.group(1))
            d_mon = int(date_explicit_match.group(2))
            d_yr = int(date_explicit_match.group(3)) if date_explicit_match.group(3) else year
            return DateRange(
                start_date=f"{d_yr:04d}-{d_mon:02d}-{d_day:02d}",
                end_date=f"{d_yr:04d}-{d_mon:02d}-{d_day:02d}",
                is_exact_day=True,
            )

        # 7. Specific YYYY-MM format in query (e.g., "tháng 3 năm 2026", "tháng 03/2026")
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

        # 8. Year-to-date: "năm 2026 đến nay", "năm 2026 đến giờ"
        ytd_match = re.search(r"năm\s*(\d{4})\s*(?:đến nay|đến giờ|tới nay|tới giờ|den nay|den gio)", q)
        if ytd_match:
            y = int(ytd_match.group(1))
            return DateRange(
                start_date=f"{y:04d}-01-01",
                end_date=anchor.strftime("%Y-%m-%d"),
            )

        # Specific YYYY alone: "năm 2025", "năm 2026"
        year_match = re.search(r"năm\s*(\d{4})", q)
        if year_match and not any(w in q for w in ["năm ngoái", "năm trước", "năm nay", "năm ni"]):
            y = int(year_match.group(1))
            return DateRange(
                start_date=f"{y:04d}-01-01",
                end_date=f"{y:04d}-12-31",
            )

        # Specific single month without year: "tháng 1", "tháng 2", ... (assuming anchor year)
        single_month_match = re.search(r"\bth[aá]ng\s*(\d{1,2})\b", q)
        if single_month_match and not any(w in q for w in ["tháng này", "tháng trước", "tháng rồi", "tháng vừa rồi", "tháng ni", "thang nay", "thang truoc"]):
            m = int(single_month_match.group(1))
            if 1 <= m <= 12:
                last_day = calendar.monthrange(year, m)[1]
                return DateRange(
                    start_date=f"{year:04d}-{m:02d}-01",
                    end_date=f"{year:04d}-{m:02d}-{last_day:02d}",
                    target_month=f"{year:04d}-{m:02d}",
                )

        # 9. "Hôm nay", "hôm qua", "hôm kia"
        if any(w in q for w in ["hôm nay", "ngày này", "ngày ni", "hom nay", "ngay nay", "ngay ni"]):
            d_str = anchor.strftime("%Y-%m-%d")
            return DateRange(start_date=d_str, end_date=d_str, is_exact_day=True)
        if any(w in q for w in ["hôm qua", "ngày qua", "hom qua", "ngay qua"]):
            d_str = (anchor - timedelta(days=1)).strftime("%Y-%m-%d")
            return DateRange(start_date=d_str, end_date=d_str, is_exact_day=True)
        if any(w in q for w in ["hôm kia", "hom kia"]):
            d_str = (anchor - timedelta(days=2)).strftime("%Y-%m-%d")
            return DateRange(start_date=d_str, end_date=d_str, is_exact_day=True)

        # 10. Calendar Week: "Tuần rồi", "tuần trước", "tuần qua"
        if any(w in q for w in ["tuần rồi", "tuần trước", "tuần qua", "tuan roi", "tuan truoc"]):
            current_monday = anchor - timedelta(days=anchor.weekday())
            prev_monday = current_monday - timedelta(days=7)
            prev_sunday = prev_monday + timedelta(days=6)
            return DateRange(
                start_date=prev_monday.strftime("%Y-%m-%d"),
                end_date=prev_sunday.strftime("%Y-%m-%d"),
            )

        # "Tuần này", "tuần ni"
        if any(w in q for w in ["tuần này", "tuần ni", "tuan nay", "tuan ni"]):
            current_monday = anchor - timedelta(days=anchor.weekday())
            current_sunday = current_monday + timedelta(days=6)
            return DateRange(
                start_date=current_monday.strftime("%Y-%m-%d"),
                end_date=current_sunday.strftime("%Y-%m-%d"),
            )

        # 11. Calendar Month: "Tháng rồi", "tháng trước", "tháng vừa qua", "tháng vừa rồi"
        if any(w in q for w in ["tháng rồi", "tháng trước", "tháng vừa qua", "tháng vừa rồi", "thang roi", "thang truoc", "thang vua roi"]):
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

        # "Tháng này", "tháng ni"
        if any(w in q for w in ["tháng này", "tháng ni", "thang nay", "thang ni"]):
            last_day = calendar.monthrange(year, month)[1]
            return DateRange(
                start_date=f"{year:04d}-{month:02d}-01",
                end_date=f"{year:04d}-{month:02d}-{last_day:02d}",
                target_month=f"{year:04d}-{month:02d}",
            )

        # 12. Year: "Năm ngoái", "năm trước", "năm nay", "năm ni"
        if any(w in q for w in ["năm ngoái", "năm trước", "năm vừa qua", "nam ngoai", "nam truoc"]):
            prev_year = year - 1
            return DateRange(
                start_date=f"{prev_year:04d}-01-01",
                end_date=f"{prev_year:04d}-12-31",
            )

        if any(w in q for w in ["năm nay", "năm ni", "nam nay", "nam ni"]):
            return DateRange(
                start_date=f"{year:04d}-01-01",
                end_date=f"{year:04d}-12-31",
            )

        # 13. Quarter: "Quý 1", "quý 2", "quý 3", "quý 4"
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
