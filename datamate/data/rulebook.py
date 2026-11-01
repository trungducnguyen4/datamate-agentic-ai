"""Đọc và nạp Rulebook động (`rulebook.md`) do BTC cung cấp theo từng split.

Quy chế Zalo AI Challenge 2026:
"The rulebook is provided per split. The system MUST load and apply the actual
rulebook for the current execution. Never assume the training rulebook is valid
for every split."

Module này nạp file `rulebook.md` tại runtime, phân tích các bảng quy tắc
(Doanh thu, Thời gian, Xếp hạng, Công nợ, Kho bãi, và Quy tắc theo ngành)
để cung cấp cho BusinessRuleCompiler và Agent.
"""
from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Tuple


class Rulebook:
    """Parsed in-memory rulebook."""

    def __init__(self, raw_text: str, source_path: str = ""):
        self.raw_text = raw_text
        self.source_path = source_path
        self.sections: Dict[str, Dict[str, str]] = {}
        self.domain_rules: Dict[str, Dict[str, str]] = {}
        self._parse()

    def _parse(self) -> None:
        """Parse markdown tables in rulebook sections."""
        current_section = "general"
        current_domain = None
        lines = self.raw_text.splitlines()

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            # Section header: ## 1. Đơn hàng và doanh thu
            if line.startswith("## "):
                sec_title = line[3:].strip()
                current_section = sec_title
                current_domain = None
                self.sections.setdefault(current_section, {})
                i += 1
                continue

            # Sub-section header: ### Cà phê, ### Sửa xe, ### Mẹ và bé
            if line.startswith("### "):
                current_domain = line[4:].strip()
                self.domain_rules.setdefault(current_domain, {})
                i += 1
                continue

            # Table header detection: | Luật | Mặc định | or | Cách nói | Nghĩa |
            if line.startswith("|") and line.endswith("|"):
                parts = [p.strip() for p in line.split("|")[1:-1]]
                # Check if next line is table divider: |--|--|
                if i + 1 < len(lines) and re.match(r"^\|(\s*[-:]+\s*\|)+$", lines[i + 1].strip()):
                    # Skip divider
                    i += 2
                    # Read table rows
                    while i < len(lines):
                        row_line = lines[i].strip()
                        if not (row_line.startswith("|") and row_line.endswith("|")):
                            break
                        cells = [c.strip() for c in row_line.split("|")[1:-1]]
                        if len(cells) >= 2:
                            rule_key = cells[0].strip("*_ ")
                            rule_val = cells[1].strip()
                            if current_domain:
                                self.domain_rules[current_domain][rule_key] = rule_val
                            else:
                                self.sections[current_section][rule_key] = rule_val
                        i += 1
                    continue
            i += 1

    def get_rule(self, rule_key: str, section: Optional[str] = None) -> Optional[str]:
        """Look up a rule by key across sections."""
        key_lower = rule_key.lower()
        if section and section in self.sections:
            for k, v in self.sections[section].items():
                if key_lower in k.lower():
                    return v
        for sec, rules in self.sections.items():
            for k, v in rules.items():
                if key_lower in k.lower():
                    return v
        return None

    def get_domain_rules(self, domain: str) -> Dict[str, str]:
        """Get rules specific to a business sector (e.g. Sửa xe, Mẹ và bé)."""
        dom_lower = domain.lower()
        for d_name, rules in self.domain_rules.items():
            if dom_lower in d_name.lower():
                return rules
        return {}

    def detect_business_domain(self, readme_text: str) -> Optional[str]:
        """Infer business domain from README.md content."""
        r_low = readme_text.lower()
        if any(w in r_low for w in ["sửa xe", "gara", "tiệm sửa xe", "bảo dưỡng xe", "xe máy", "ô tô"]):
            return "Sửa xe"
        if any(w in r_low for w in ["mẹ và bé", "me va be", "bỉm", "sữa trẻ em", "sơ sinh"]):
            return "Mẹ và bé"
        if any(w in r_low for w in ["điện thoại", "smartphone", "di động", "phụ kiện điện thoại", "iphone", "samsung"]):
            return "Cửa hàng điện thoại"
        if any(w in r_low for w in ["nhà thuốc", "dược phẩm", "quầy thuốc", "thuốc tây"]):
            return "Nhà thuốc"
        if any(w in r_low for w in ["cà phê", "cafe", "trà sữa", "nước giải khát"]):
            return "Cà phê"
        if any(w in r_low for w in ["vật liệu xây dựng", "xi măng", "cát đá", "vlxd"]):
            return "Vật liệu xây dựng"
        return None


_RULEBOOK: Optional[Rulebook] = None


def find_rulebook_path(*roots: str) -> Optional[str]:
    """Find rulebook.md searching supplied roots and standard paths."""
    candidates = []
    for root in roots:
        if not root:
            continue
        r = os.path.abspath(root)
        candidates.extend([
            os.path.join(r, "rulebook.md"),
            os.path.join(os.path.dirname(r), "rulebook.md"),
            os.path.join(os.path.dirname(os.path.dirname(r)), "rulebook.md"),
        ])
    candidates.extend([
        os.path.join(os.getcwd(), "rulebook.md"),
        os.path.join(os.getcwd(), "data", "train", "rulebook.md"),
        os.path.join(os.getcwd(), "data", "public_test", "rulebook.md"),
        os.path.join(os.sep, "data", "rulebook.md"),
        os.path.join(os.sep, "app", "rulebook.md"),
    ])
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


def configure_rulebook(*roots: str) -> Optional[Rulebook]:
    """Load rulebook from markdown and set as active global instance."""
    global _RULEBOOK
    path = find_rulebook_path(*roots)
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        rulebook = Rulebook(text, source_path=path)
        _RULEBOOK = rulebook
        return rulebook
    except OSError:
        return None


def get_rulebook() -> Optional[Rulebook]:
    """Return currently active rulebook or auto-discover from environment."""
    global _RULEBOOK
    if _RULEBOOK is None:
        configure_rulebook(os.getcwd())
    return _RULEBOOK
