import pytest
from datamate.core.normalizer import normalize_string, match_string


def test_normalize_string_basic():
    # Test lowercase, punctuation replacement, whitespace collapse
    raw = "  Sting-dâu,  330ml!!  "
    expected = "sting dâu 330ml"
    assert normalize_string(raw) == expected


def test_normalize_diacritics_preserved():
    raw = "Xi măng Hà Tiên PCB40 (bao 50kg)"
    expected = "xi măng hà tiên pcb40 bao 50kg"
    assert normalize_string(raw) == expected


def test_match_string_with_aliases():
    accepted_forms = ["Sting dâu 330ml", "SP0042", "Nước ngọt Sting dâu chai 330ml"]
    
    # Matching exact normalized name
    assert match_string("sting dâu 330ml", accepted_forms) is True
    # Matching with punctuation difference
    assert match_string("Sting dâu (330ml)", accepted_forms) is True
    # Matching code
    assert match_string("sp0042", accepted_forms) is True
    assert match_string("SP0042", accepted_forms) is True
    
    # Non matching
    assert match_string("Coca Cola 330ml", accepted_forms) is False
