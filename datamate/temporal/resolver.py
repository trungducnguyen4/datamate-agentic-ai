from __future__ import annotations
import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
import re
from typing import Optional, Tuple, List
from datamate.data.calendar import get_festival_solar_date, get_lunar_range
from datamate.data.calendar_csv import get_calendar


@dataclass
class DateRange:
    start_date: str  # YYYY-MM-DD
    end_date: str    # YYYY-MM-DD
    target_month: Optional[str] = None  # YYYY-MM if asking about a specific month
    is_exact_day: bool = False
    is_ambiguous: bool = False
    candidate_months: List[str] = field(default_factory=list)


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
        """Parse as_of_date defensively from multiple date formats (ISO, VN DD/MM/YYYY, etc.)."""
        if not as_of_date_str:
            return date(2026, 3, 4)
        s = str(as_of_date_str).strip()
        # 1. Standard ISO YYYY-MM-DD or YYYY/MM/DD
        m_iso = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", s)
        if m_iso:
            return date(int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3)))
        # 2. Vietnamese DD/MM/YYYY or DD-MM-YYYY
        m_vn = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$", s)
        if m_vn:
            d, m, y = int(m_vn.group(1)), int(m_vn.group(2)), int(m_vn.group(3))
            if m > 12 and d <= 12:  # Swap if MM/DD/YYYY
                d, m = m, d
            return date(y, m, d)
        # 3. Fallback formats
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return date(2026, 3, 4)

    @classmethod
    def normalize_as_of_date_str(cls, as_of_date_str: str) -> str:
        d = cls.parse_as_of_date(as_of_date_str)
        return d.isoformat()

    @staticmethod
    def extract_candidate_months(query: str) -> List[str]:
        """Extract multi-month tokens or ranges from a Vietnamese query (e.g. 3/25, 4/25, 5/25 -> ['2025-03', '2025-04', '2025-05'])."""
        q_norm = query.lower()
        months = set()
        # Pattern 1: M/YYYY or M/YY (e.g. 3/25, 4/25, 11/2025)
        for m in re.finditer(r"(?:tháng\s*|th\s*|t\s*)?(\d{1,2})/(\d{2,4})", q_norm):
            month = int(m.group(1))
            year = int(m.group(2))
            if year < 100:
                year += 2000
            if 1 <= month <= 12:
                months.add(f"{year:04d}-{month:02d}")
        # Pattern 2: Series like th2, th3, th4/2026 or tháng 1, 2, 3/2026
        m_series = re.search(r"(?:th|t|tháng\s*)(\d{1,2})\s*,\s*(?:th|t|tháng\s*)?(\d{1,2})\s*(?:và|,|hay)?\s*(?:th|t|tháng\s*)?(\d{1,2})[/-](\d{2,4})", q_norm)
        if m_series:
            y = int(m_series.group(4))
            if y < 100:
                y += 2000
            for g in range(1, 4):
                months.add(f"{y:04d}-{int(m_series.group(g)):02d}")
        # Pattern 3: Explicit 'tháng X năm Y'
        for m in re.finditer(r"tháng\s*(\d{1,2})\s*năm\s*(\d{4})", q_norm):
            months.add(f"{int(m.group(2)):04d}-{int(m.group(1)):02d}")
        # Pattern 4: Ranges like 'từ th12/2025 đến th2/2026' or 'từ tháng 8/2025 tới tháng 10/2025'
        m_range = re.search(r"(?:từ|tu)\s*(?:tháng\s*|th\s*|t\s*)?(\d{1,2})[/-](\d{2,4})\s*(?:tới|đến|toi|den)\s*(?:tháng\s*|th\s*|t\s*)?(\d{1,2})[/-](\d{2,4})", q_norm)
        if m_range:
            m1, y1 = int(m_range.group(1)), int(m_range.group(2))
            m2, y2 = int(m_range.group(3)), int(m_range.group(4))
            if y1 < 100:
                y1 += 2000
            if y2 < 100:
                y2 += 2000
            cy, cm = y1, m1
            while (cy < y2) or (cy == y2 and cm <= m2):
                months.add(f"{cy:04d}-{cm:02d}")
                cm += 1
                if cm > 12:
                    cm = 1
                    cy += 1
        # If 2 months and range connector
        if len(months) == 2 and any(k in q_norm for k in ["tới", "đến", "toi", "den"]):
            m_list = sorted(list(months))
            y1, m1 = map(int, m_list[0].split("-"))
            y2, m2 = map(int, m_list[1].split("-"))
            cy, cm = y1, m1
            while (cy < y2) or (cy == y2 and cm <= m2):
                months.add(f"{cy:04d}-{cm:02d}")
                cm += 1
                if cm > 12:
                    cm = 1
                    cy += 1
        return sorted(list(months))

    @staticmethod
    def _tet_year(query: str, default_year: int) -> int:
        """Năm âm của dịp Tết được nhắc trong câu (mặc định = năm của as_of)."""
        match = re.search(r"(?:tết|tet)\s*(?:năm|nam)?\s*(\d{4})", query)
        if match:
            return int(match.group(1))
        return default_year

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

        # 1. Lunar expressions (tra lịch bằng calendar.csv của BTC)
        cal = get_calendar()

        # 1a. "Tết Trung Thu" / "Tết Dương lịch" không phải Tết Nguyên Đán
        is_mid_autumn = any(w in q for w in ["trung thu", "trungthu"])
        is_solar_new_year = "dương lịch" in q or "duong lich" in q
        if is_mid_autumn:
            festival = cal.festival(8, 15, year) if cal else None
            if festival:
                return DateRange(start_date=festival.isoformat(), end_date=festival.isoformat(), is_exact_day=True)
        if is_solar_new_year:
            return DateRange(start_date=f"{year}-01-01", end_date=f"{year}-01-01", is_exact_day=True)

        # 1b. "từ mùng 1 đến rằm tháng giêng"
        if any(w in q for w in ["từ mùng 1 đến rằm tháng giêng", "mùng 1 đến rằm tháng giêng", "mung 1 den ram thang gieng"]):
            if cal:
                start = cal.festival(1, 1, year)
                end = cal.festival(1, 15, year)
                if start and end:
                    return DateRange(start_date=start.isoformat(), end_date=end.isoformat())
            r = get_lunar_range("mung_1_den_ram", year)
            if r:
                return DateRange(start_date=r[0], end_date=r[1])

        # 1c. "tháng giêng" / "tháng giêng năm nay"
        if ("tháng giêng" in q or "thang gieng" in q) and not any(w in q for w in ["rằm tháng giêng", "ram thang gieng", "sau tết", "sau tet"]):
            if cal:
                bounds = cal.lunar_month_bounds(year, 1)
                if bounds:
                    return DateRange(start_date=bounds[0].isoformat(), end_date=bounds[1].isoformat())
            r = get_lunar_range("thang_gieng", year)
            if r:
                return DateRange(start_date=r[0], end_date=r[1])

        # 1d. Tết Nguyên Đán: 23 tháng Chạp (năm âm trước) → hết mùng 10 tháng Giêng
        tet_year = cls._tet_year(q, year)
        tet_range = cal.tet_range(tet_year) if cal else None
        if tet_range is None:
            tet_day = get_festival_solar_date("tet", tet_year)
            if tet_day:
                d = date.fromisoformat(tet_day)
                tet_range = (d, d)

        if tet_range:
            tet_start, tet_end = tet_range
            before = tet_start - timedelta(days=1)

            # "mùng 1/2/3 Tết" là một ngày cụ thể, không phải cả dịp Tết
            for day in (1, 2, 3):
                if f"mùng {day} tết" in q or f"mung {day} tet" in q:
                    exact = cal.festival(1, day, tet_year) if cal else None
                    if exact is None:
                        label = f"mùng {day} tết"
                        fallback = get_festival_solar_date(label, tet_year)
                        if fallback:
                            exact = date.fromisoformat(fallback)
                    if exact:
                        return DateRange(start_date=exact.isoformat(), end_date=exact.isoformat(), is_exact_day=True)

            # "trước Tết": cùng số ngày ngay trước 23 tháng Chạp
            if any(w in q for w in ["trước tết", "truoc tet", "trước tết đến", "so với trước tết"]):
                if cal:
                    window = cal.pre_tet_window(tet_year)
                    if window:
                        return DateRange(start_date=window[0].isoformat(), end_date=window[1].isoformat())
                return DateRange(start_date=before.isoformat(), end_date=before.isoformat())

            # "sau Tết đến giờ/nay": BTC không định nghĩa riêng cụm này trong rulebook;
            # giữ quy ước "sau mùng 1 Tết" (ngày kế tiếp mùng 1) như baseline cũ.
            if any(w in q for w in ["sau tết", "sau tet", "từ tết đến giờ", "tu tet den gio", "từ tết đến nay"]):
                start = tet_start + timedelta(days=1)
                return DateRange(start_date=start.isoformat(), end_date=anchor.isoformat())

            # "dịp Tết", "mùa Tết", "tết năm Y", "tết" ...
            if any(w in q for w in ["tết", "tet"]):
                return DateRange(start_date=tet_start.isoformat(), end_date=tet_end.isoformat())

        # Single Lunar festivals (Order from most specific to least specific)
        for fest in ["tết nguyên đán", "mùng 1 tết", "mùng 2 tết", "mùng 3 tết", "mung 1 tet", "mung 2 tet", "mung 3 tet",
                     "rằm tháng giêng", "ram thang gieng", "vu lan", "tết", "tet"]:
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

        # 3. Dynamic rolling "N ngày gần nhất", "N ngày gần đây", "N ngày qua"
        # Rulebook §2 line 28: "N ngày gần nhất: N ngày liền nhau kể cả hôm nay, ngày cuối là hôm nay"
        word_to_num = {
            "một": 1, "mot": 1, "hai": 2, "ba": 3, "bốn": 4, "bon": 4,
            "năm": 5, "nam": 5, "sáu": 6, "sau": 6, "bảy": 7, "bay": 7,
            "tám": 8, "tam": 8, "chín": 9, "chin": 9, "mười": 10, "muoi": 10,
        }
        n_days_match = re.search(
            r"\b(\d+|một|mot|hai|ba|bốn|bon|năm|nam|sáu|sau|bảy|bay|tám|tam|chín|chin|mười|muoi)\s*(?:ngày|ngay)\s*(?:gần nhất|gan nhat|gần đây|gan day|qua|vừa qua|vua qua)\b",
            q,
        )
        if n_days_match:
            raw_n = n_days_match.group(1).lower()
            n = word_to_num.get(raw_n) or int(raw_n)
            if n > 0:
                start_d = anchor - timedelta(days=n - 1)
                return DateRange(
                    start_date=start_d.strftime("%Y-%m-%d"),
                    end_date=anchor.strftime("%Y-%m-%d"),
                )

        # 3b. Dynamic rolling "N tháng gần đây", "ba tháng gần đây", "3 tháng gần đây"
        n_months_match = re.search(
            r"\b(\d+|một|mot|hai|ba|bốn|bon|năm|nam|sáu|sau|bảy|bay|tám|tam|chín|chin|mười|muoi)\s*(?:tháng|thang)\s*(?:gần nhất|gan nhat|gần đây|gan day|qua|vừa qua|vua qua)\b",
            q,
        )
        if n_months_match:
            raw_n = n_months_match.group(1).lower()
            n = word_to_num.get(raw_n) or int(raw_n)
            if n > 0:
                cur_y = year
                cur_m = month - (n - 1)
                while cur_m <= 0:
                    cur_m += 12
                    cur_y -= 1
                return DateRange(
                    start_date=f"{cur_y:04d}-{cur_m:02d}-01",
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

        # 5b. Date Range expressions:
        # e.g., "từ ngày 1/1 đến hết hôm nay", "tính từ ngày 1/1 đến hôm nay", "từ 01/01 đến nay", "từ ngày 1/1 đến nay"
        range_to_today_match = re.search(
            r"(?:từ|tu|tinh tu|tính từ)?\s*(?:ngày|ngay)?\s*(\d{1,2})[\/\-](\d{1,2})(?:[\/\-](\d{4}))?\s*(?:đến|tới|den|toi)\s*(?:hết\s+|het\s+)?(?:hôm nay|hom nay|hnay|nay|bữa nay|bua nay)",
            q
        )
        if range_to_today_match:
            d_day = int(range_to_today_match.group(1))
            d_mon = int(range_to_today_match.group(2))
            d_yr = int(range_to_today_match.group(3)) if range_to_today_match.group(3) else year
            return DateRange(
                start_date=f"{d_yr:04d}-{d_mon:02d}-{d_day:02d}",
                end_date=anchor.strftime("%Y-%m-%d"),
            )

        # e.g., "từ ngày 01/01/2026 đến ngày 15/01/2026", "từ 01/01 đến 15/01", "ngày 01/01 đến 15/01"
        range_between_dates_match = re.search(
            r"(?:từ|tinh tu|tính từ)?\s*(?:ngày|ngay)?\s*(\d{1,2})[\/\-](\d{1,2})(?:[\/\-](\d{4}))?\s*(?:đến|tới|den|toi)\s*(?:ngày|ngay)?\s*(\d{1,2})[\/\-](\d{1,2})(?:[\/\-](\d{4}))?",
            q
        )
        if range_between_dates_match:
            d1_day = int(range_between_dates_match.group(1))
            d1_mon = int(range_between_dates_match.group(2))
            d1_yr = int(range_between_dates_match.group(3)) if range_between_dates_match.group(3) else year
            d2_day = int(range_between_dates_match.group(4))
            d2_mon = int(range_between_dates_match.group(5))
            d2_yr = int(range_between_dates_match.group(6)) if range_between_dates_match.group(6) else (d1_yr or year)
            return DateRange(
                start_date=f"{d1_yr:04d}-{d1_mon:02d}-{d1_day:02d}",
                end_date=f"{d2_yr:04d}-{d2_mon:02d}-{d2_day:02d}",
            )

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

        # 6a. Quarter: "Quý 1", "quý 2", "q1", "q2", "quy 4/2025", "quý 4 năm 2025", "quý 4 năm ngoái", "quý một"
        quarter_match = re.search(r"(?:quý|quy|\bq)\s*([1-4]|i{1,3}|iv|một|mot|hai|ba|bốn|bon)(?:[\s/,-]*(?:năm|nam)?\s*(\d{4}))?\b", q)
        if quarter_match:
            raw_q = quarter_match.group(1).lower()
            if quarter_match.group(2):
                target_yr = int(quarter_match.group(2))
            elif any(w in q for w in ["năm ngoái", "năm trước", "nam ngoai", "nam truoc"]):
                target_yr = year - 1
            else:
                target_yr = year
            roman_map = {
                "1": 1, "i": 1, "một": 1, "mot": 1,
                "2": 2, "ii": 2, "hai": 2,
                "3": 3, "iii": 3, "ba": 3,
                "4": 4, "iv": 4, "bốn": 4, "bon": 4,
            }
            q_num = roman_map.get(raw_q, 1)
            start_m = (q_num - 1) * 3 + 1
            end_m = q_num * 3
            # Rule 34: Tháng M, quý Q không ghi năm: của năm nay nếu không sau hôm nay; sau hôm nay thì của năm trước.
            if not quarter_match.group(2) and not any(w in q for w in ["năm ngoái", "năm trước", "nam ngoai", "nam truoc"]):
                q_start_date = date(target_yr, start_m, 1)
                if q_start_date > anchor:
                    target_yr = year - 1
            last_day = calendar.monthrange(target_yr, end_m)[1]
            return DateRange(
                start_date=f"{target_yr:04d}-{start_m:02d}-01",
                end_date=f"{target_yr:04d}-{end_m:02d}-{last_day:02d}",
            )

        # 6b. Multi-month extraction or Short Month Formats (e.g. 3/25, 4/25, 5/25, th7/2025, 8/2025)
        cand_months = cls.extract_candidate_months(q)
        if len(cand_months) >= 2:
            m_first = cand_months[0]
            m_last = cand_months[-1]
            y_first, m_f_num = map(int, m_first.split("-"))
            y_last, m_l_num = map(int, m_last.split("-"))
            last_day = calendar.monthrange(y_last, m_l_num)[1]
            return DateRange(
                start_date=f"{y_first:04d}-{m_f_num:02d}-01",
                end_date=f"{y_last:04d}-{m_l_num:02d}-{last_day:02d}",
                candidate_months=cand_months,
            )

        # 7. Specific YYYY-MM format in query (e.g., "tháng 3 năm 2026", "tháng 03/2026", "thang 4/2025")
        month_match = re.search(r"(?:tháng|thang)\s*(\d{1,2})(?:[\s/,-]+(?:năm|nam)?\s*|\/)(\d{4})", q)
        if month_match:
            m = int(month_match.group(1))
            y = int(month_match.group(2))
            if 1 <= m <= 12:
                last_day = calendar.monthrange(y, m)[1]
                return DateRange(
                    start_date=f"{y:04d}-{m:02d}-01",
                    end_date=f"{y:04d}-{m:02d}-{last_day:02d}",
                    target_month=f"{y:04d}-{m:02d}",
                )

        if len(cand_months) == 1:
            m_single = cand_months[0]
            y_s, m_s = map(int, m_single.split("-"))
            last_day = calendar.monthrange(y_s, m_s)[1]
            return DateRange(
                start_date=f"{y_s:04d}-{m_s:02d}-01",
                end_date=f"{y_s:04d}-{m_s:02d}-{last_day:02d}",
                target_month=f"{y_s:04d}-{m_s:02d}",
            )

        # 8. Year-to-date: "năm 2026 đến nay", "năm 2026 đến giờ"
        ytd_match = re.search(r"(?:năm|nam)\s*(\d{4})\s*(?:đến nay|đến giờ|tới nay|tới giờ|den nay|den gio)", q)
        if ytd_match:
            y = int(ytd_match.group(1))
            return DateRange(
                start_date=f"{y:04d}-01-01",
                end_date=anchor.strftime("%Y-%m-%d"),
            )

        # Specific YYYY alone: "năm 2025", "năm 2026"
        year_match = re.search(r"(?:năm|nam)\s*(\d{4})", q)
        if year_match and not any(w in q for w in ["năm ngoái", "năm trước", "năm nay", "năm ni", "nam ngoai", "nam truoc", "nam nay", "nam ni"]):
            y = int(year_match.group(1))
            return DateRange(
                start_date=f"{y:04d}-01-01",
                end_date=f"{y:04d}-12-31",
            )

        # Specific single month without year: "tháng 1", "tháng 2", ...
        single_month_match = re.search(r"\bth[aá]ng\s*(\d{1,2})\b", q)
        if single_month_match and not any(w in q for w in ["tháng này", "tháng trước", "tháng rồi", "tháng vừa rồi", "tháng ni", "thang nay", "thang truoc"]):
            m = int(single_month_match.group(1))
            if 1 <= m <= 12:
                # Rule 34: Tháng M, quý Q không ghi năm: của năm nay nếu không sau hôm nay; sau hôm nay thì của năm trước.
                target_yr = year
                m_start_date = date(target_yr, m, 1)
                if m_start_date > anchor:
                    target_yr = year - 1
                last_day = calendar.monthrange(target_yr, m)[1]
                return DateRange(
                    start_date=f"{target_yr:04d}-{m:02d}-01",
                    end_date=f"{target_yr:04d}-{m:02d}-{last_day:02d}",
                    target_month=f"{target_yr:04d}-{m:02d}",
                )

        # 9. Calendar Year: "Năm ngoái", "năm trước", "năm vừa qua", "nam ngoai", "nam truoc"
        if any(w in q for w in ["năm ngoái", "năm trước", "năm vừa qua", "nam ngoai", "nam truoc"]):
            prev_year = year - 1
            return DateRange(
                start_date=f"{prev_year:04d}-01-01",
                end_date=f"{prev_year:04d}-12-31",
            )

        # 10. Year-to-date: "Năm nay", "năm ni", "từ đầu năm", "đầu năm tới nay", "đầu năm tới chừ"
        # Rulebook: "từ đầu năm tới nay" = 01/01 → hết hôm nay (không phải 31/12)
        if any(w in q for w in [
            "năm nay", "năm ni", "nam nay", "nam ni",
            "đầu năm", "dau nam", "từ đầu năm", "tu dau nam",
            "đầu năm tới nay", "đầu năm đến nay", "đầu năm tới chừ", "đầu năm tới bây chừ"
        ]):
            return DateRange(
                start_date=f"{year:04d}-01-01",
                end_date=anchor.strftime("%Y-%m-%d"),
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

        # Month-to-date: "Tháng này", "tháng ni", "từ đầu tháng" (Rulebook Rule 33: Từ ngày 1 đến hết hôm nay)
        if any(w in q for w in ["tháng này", "tháng ni", "thang nay", "thang ni", "đầu tháng", "dau thang", "từ đầu tháng", "tu dau thang"]):
            return DateRange(
                start_date=f"{year:04d}-{month:02d}-01",
                end_date=anchor.strftime("%Y-%m-%d"),
                target_month=f"{year:04d}-{month:02d}",
            )

        # 12. Calendar Week: "Tuần rồi", "tuần trước", "tuần qua"
        if any(w in q for w in ["tuần rồi", "tuần trước", "tuần qua", "tuan roi", "tuan truoc"]):
            current_monday = anchor - timedelta(days=anchor.weekday())
            prev_monday = current_monday - timedelta(days=7)
            prev_sunday = prev_monday + timedelta(days=6)
            return DateRange(
                start_date=prev_monday.strftime("%Y-%m-%d"),
                end_date=prev_sunday.strftime("%Y-%m-%d"),
            )

        # Week-to-date: "Tuần này", "tuần ni" (Rulebook Rule 31: Từ thứ Hai đến hết hôm nay)
        if any(w in q for w in ["tuần này", "tuần ni", "tuan nay", "tuan ni", "đầu tuần", "dau tuan", "từ đầu tuần", "tu dau tuan"]):
            current_monday = anchor - timedelta(days=anchor.weekday())
            return DateRange(
                start_date=current_monday.strftime("%Y-%m-%d"),
                end_date=anchor.strftime("%Y-%m-%d"),
            )

        # 13. Single day: "Hôm qua", "hôm kia", "hôm nay"
        if re.search(r"(?<!\d)\s*\b(?:hôm qua|hom qua|ngày hôm qua|ngay hom qua|ngày qua|ngay qua|hqua|bữa qua|bua qua|hqa)\b", q):
            d_str = (anchor - timedelta(days=1)).strftime("%Y-%m-%d")
            return DateRange(start_date=d_str, end_date=d_str, is_exact_day=True)
        if any(w in q for w in ["hôm kia", "hom kia", "hkia"]):
            d_str = (anchor - timedelta(days=2)).strftime("%Y-%m-%d")
            return DateRange(start_date=d_str, end_date=d_str, is_exact_day=True)
        if any(w in q for w in ["hôm nay", "ngày này", "ngày ni", "hôm ni", "hom ni", "hom nay", "ngay nay", "ngay ni", "hnay", "bữa nay", "bua nay"]):
            d_str = anchor.strftime("%Y-%m-%d")
            return DateRange(start_date=d_str, end_date=d_str, is_exact_day=True)

        return None

    @classmethod
    def resolve_comparison_periods(cls, query: str, as_of_date_str: str) -> Optional[Tuple[DateRange, DateRange]]:
        """Resolve current and comparison baseline period according to Rulebook §1 Rule 19 & §2 Rule 32.

        Example:
        - "Tháng này so với tháng trước":
          Period 1 (Current): 1st to as_of_date
          Period 2 (Comparison): 1st of prev month to min(day of as_of_date, last day of prev month)
        - "Tuần này so với tuần trước":
          Period 1: Monday of this week to as_of_date
          Period 2: Monday of last week to same day of last week
        """
        q = query.lower()
        anchor = cls.parse_as_of_date(as_of_date_str)
        year, month, day = anchor.year, anchor.month, anchor.day

        # Compare month vs previous month
        if any(w in q for w in ["tháng này", "tháng ni", "thang nay"]) and any(w in q for w in ["tháng trước", "tháng rồi", "cùng kỳ", "thang truoc", "thang roi"]):
            cur_start = f"{year:04d}-{month:02d}-01"
            cur_end = anchor.strftime("%Y-%m-%d")
            cur_range = DateRange(start_date=cur_start, end_date=cur_end)

            prev_y = year if month > 1 else year - 1
            prev_m = month - 1 if month > 1 else 12
            last_day_prev = calendar.monthrange(prev_y, prev_m)[1]
            prev_day = min(day, last_day_prev)
            prev_start = f"{prev_y:04d}-{prev_m:02d}-01"
            prev_end = f"{prev_y:04d}-{prev_m:02d}-{prev_day:02d}"
            prev_range = DateRange(start_date=prev_start, end_date=prev_end)
            return cur_range, prev_range

        # Specific month comparison: e.g. "tháng 2/2026 so cùng kỳ năm trước" or "03/2025 so với tháng liền trước"
        m_match = re.search(r"(?:tháng|th|t)\s*(\d{1,2})(?:[\/\-\s]|(?:\s*năm\s*))(\d{2,4})", q)
        if m_match:
            tgt_m = int(m_match.group(1))
            tgt_y = int(m_match.group(2))
            if tgt_y < 100:
                tgt_y += 2000
            if 1 <= tgt_m <= 12 and 2000 <= tgt_y <= 2030:
                last_d = calendar.monthrange(tgt_y, tgt_m)[1]
                cur_range = DateRange(start_date=f"{tgt_y:04d}-{tgt_m:02d}-01", end_date=f"{tgt_y:04d}-{tgt_m:02d}-{last_d:02d}")

                # Compare vs previous year (cùng kỳ năm ngoái / cùng kỳ năm trước / năm rồi)
                if any(w in q for w in ["năm ngoái", "nam ngoai", "năm trước", "nam truoc", "năm rồi", "nam roi", "cùng tháng năm", "cung thang nam"]):
                    prev_y = tgt_y - 1
                    prev_last_d = calendar.monthrange(prev_y, tgt_m)[1]
                    prev_range = DateRange(start_date=f"{prev_y:04d}-{tgt_m:02d}-01", end_date=f"{prev_y:04d}-{tgt_m:02d}-{prev_last_d:02d}")
                    return cur_range, prev_range

                # Compare vs previous month (tháng trước / tháng liền trước)
                if any(w in q for w in ["tháng trước", "thang truoc", "tháng liền trước", "thang lien truoc", "tháng rồi", "thang roi"]):
                    prev_y = tgt_y if tgt_m > 1 else tgt_y - 1
                    prev_m = tgt_m - 1 if tgt_m > 1 else 12
                    prev_last_d = calendar.monthrange(prev_y, prev_m)[1]
                    prev_range = DateRange(start_date=f"{prev_y:04d}-{prev_m:02d}-01", end_date=f"{prev_y:04d}-{prev_m:02d}-{prev_last_d:02d}")
                    return cur_range, prev_range

        return None
