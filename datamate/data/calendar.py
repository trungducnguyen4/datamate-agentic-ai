"""Solar-Lunar Calendar and Vietnamese Holiday lookup for DataMate."""
from __future__ import annotations
from datetime import date, datetime
from typing import Dict, Optional, Tuple


# Known Lunar New Year (Tết Mùng 1) and Key Lunar Dates for 2024 - 2027
# Format: (year, month, day) in Solar Calendar
LUNAR_KEY_DATES: Dict[Tuple[int, int, int], str] = {
    # 2024 (Giáp Thìn)
    (2024, 2, 10): "Tết Nguyên Đán (Mùng 1 Tết Giáp Thìn)",
    (2024, 2, 24): "Rằm tháng Giêng",
    (2024, 8, 18): "Rằm tháng Bảy (Vu Lan)",
    (2024, 9, 17): "Tết Trung Thu (Rằm tháng Tám)",

    # 2025 (Ất Tỵ)
    (2025, 1, 29): "Tết Nguyên Đán (Mùng 1 Tết Ất Tỵ)",
    (2025, 2, 12): "Rằm tháng Giêng",
    (2025, 9, 6): "Rằm tháng Bảy (Vu Lan)",
    (2025, 10, 6): "Tết Trung Thu (Rằm tháng Tám)",

    # 2026 (Bính Ngọ - Competition Year)
    (2026, 2, 17): "Tết Nguyên Đán (Mùng 1 Tết Bính Ngọ)",
    (2026, 3, 3): "Rằm tháng Giêng",
    (2026, 8, 27): "Rằm tháng Bảy (Vu Lan)",
    (2026, 9, 25): "Tết Trung Thu (Rằm tháng Tám)",

    # 2027 (Đinh Mùi)
    (2027, 2, 6): "Tết Nguyên Đán (Mùng 1 Tết Đinh Mùi)",
    (2027, 2, 20): "Rằm tháng Giêng",
    (2027, 8, 16): "Rằm tháng Bảy (Vu Lan)",
    (2027, 9, 15): "Tết Trung Thu (Rằm tháng Tám)",
}

# Mapping festival keyword -> (lunar_month, lunar_day)
LUNAR_FESTIVALS = {
    "tet": (1, 1),
    "tết": (1, 1),
    "tết nguyên đán": (1, 1),
    "mùng 1 tết": (1, 1),
    "mùng 2 tết": (1, 2),
    "mùng 3 tết": (1, 3),
    "rằm tháng giêng": (1, 15),
    "vu lan": (7, 15),
    "rằm tháng 7": (7, 15),
    "rằm tháng bảy": (7, 15),
    "trung thu": (8, 15),
    "rằm tháng 8": (8, 15),
    "rằm tháng tám": (8, 15),
}


def get_festival_solar_date(festival_name: str, solar_year: int) -> Optional[str]:
    """Resolve a Vietnamese lunar festival to a solar date YYYY-MM-DD for a given year."""
    fest_key = festival_name.strip().lower()
    
    # Specific lookup for 2025 & 2026
    year_map = {
        2025: {
            "tet": "2025-01-29",
            "tết": "2025-01-29",
            "tết nguyên đán": "2025-01-29",
            "mùng 1 tết": "2025-01-29",
            "mùng 2 tết": "2025-01-30",
            "mùng 3 tết": "2025-01-31",
            "rằm tháng giêng": "2025-02-12",
            "vu lan": "2025-09-06",
            "trung thu": "2025-10-06",
        },
        2026: {
            "tet": "2026-02-17",
            "tết": "2026-02-17",
            "tết nguyên đán": "2026-02-17",
            "mùng 1 tết": "2026-02-17",
            "mùng 2 tết": "2026-02-18",
            "mùng 3 tết": "2026-02-19",
            "rằm tháng giêng": "2026-03-03",
            "vu lan": "2026-08-27",
            "trung thu": "2026-09-25",
        }
    }
    
    if solar_year in year_map and fest_key in year_map[solar_year]:
        return year_map[solar_year][fest_key]
    
    return None
