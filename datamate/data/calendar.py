"""Solar-Lunar Calendar and Vietnamese Holiday lookup for DataMate."""
from __future__ import annotations
from datetime import date, datetime
from typing import Dict, Optional, Tuple


# Known Lunar New Year (Tết Mùng 1) and Key Lunar Dates for 2024 - 2027
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

# Solar date ranges for Lunar Month 1 (Tháng Giêng âm lịch), Lunar 1-15 (Mùng 1 đến Rằm),
# and the official Rulebook Tết Window (Rule 35: 23 tháng Chạp đến mùng 10 tháng Giêng)
LUNAR_RANGES: Dict[int, Dict[str, Tuple[str, str]]] = {
    2024: {
        "thang_gieng": ("2024-02-10", "2024-03-09"),
        "mung_1_den_ram": ("2024-02-10", "2024-02-24"),
        "tet_mung_1": ("2024-02-10", "2024-02-10"),
        # Rule 35: 23 tháng Chạp 2023 -> mùng 10 tháng Giêng 2024
        "tet_window": ("2024-02-02", "2024-02-19"),
        "tet": ("2024-02-02", "2024-02-19"),
    },
    2025: {
        "thang_gieng": ("2025-01-29", "2025-02-27"),
        "mung_1_den_ram": ("2025-01-29", "2025-02-12"),
        "tet_mung_1": ("2025-01-29", "2025-01-29"),
        # Rule 35: 23 tháng Chạp 2024 -> mùng 10 tháng Giêng 2025
        "tet_window": ("2025-01-22", "2025-02-07"),
        "tet": ("2025-01-22", "2025-02-07"),
    },
    2026: {
        "thang_gieng": ("2026-02-17", "2026-03-18"),
        "mung_1_den_ram": ("2026-02-17", "2026-03-03"),
        "tet_mung_1": ("2026-02-17", "2026-02-17"),
        # Rule 35: 23 tháng Chạp 2025 -> mùng 10 tháng Giêng 2026
        "tet_window": ("2026-02-10", "2026-02-26"),
        "tet": ("2026-02-10", "2026-02-26"),
    },
    2027: {
        "thang_gieng": ("2027-02-06", "2027-03-07"),
        "mung_1_den_ram": ("2027-02-06", "2027-02-20"),
        "tet_mung_1": ("2027-02-06", "2027-02-06"),
        # Rule 35: 23 tháng Chạp 2026 -> mùng 10 tháng Giêng 2027
        "tet_window": ("2027-01-30", "2027-02-16"),
        "tet": ("2027-01-30", "2027-02-16"),
    },
}


def get_festival_solar_date(festival_name: str, solar_year: int) -> Optional[str]:
    """Resolve a Vietnamese lunar festival to a solar date YYYY-MM-DD for a given year."""
    fest_key = festival_name.strip().lower()

    year_map = {
        2024: {
            "tet": "2024-02-10",
            "tết": "2024-02-10",
            "tết nguyên đán": "2024-02-10",
            "mùng 1 tết": "2024-02-10",
            "rằm tháng giêng": "2024-02-24",
            "vu lan": "2024-08-18",
            "trung thu": "2024-09-17",
        },
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
        },
        2027: {
            "tet": "2027-02-06",
            "tết": "2027-02-06",
            "tết nguyên đán": "2027-02-06",
            "mùng 1 tết": "2027-02-06",
            "rằm tháng giêng": "2027-02-20",
            "vu lan": "2027-08-16",
            "trung thu": "2027-09-15",
        },
    }

    if solar_year in year_map and fest_key in year_map[solar_year]:
        return year_map[solar_year][fest_key]

    return None


def get_lunar_range(range_type: str, solar_year: int) -> Optional[Tuple[str, str]]:
    """Get start and end solar dates for specific lunar intervals."""
    if solar_year in LUNAR_RANGES and range_type in LUNAR_RANGES[solar_year]:
        return LUNAR_RANGES[solar_year][range_type]
    return None
