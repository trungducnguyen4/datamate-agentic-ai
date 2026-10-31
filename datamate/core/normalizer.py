import re
import unicodedata
from typing import Iterable, Union


def normalize_string(text: Union[str, any]) -> str:
    """Normalize a string according to official DataMate specification:

    1. Unicode NFC
    2. Lowercase
    3. Every character that is not a letter, a digit, or whitespace is replaced by a space
       (Diacritics are preserved).
    4. Leading/trailing whitespace removed and runs of whitespace collapsed to one space.
    """
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)

    # 1. Unicode NFC
    text = unicodedata.normalize("NFC", text)

    # 2. Lowercase
    text = text.lower()

    # 3. Replace anything that is not a letter, digit, or whitespace with space
    chars = []
    for c in text:
        if c.isalnum() or c.isspace():
            chars.append(c)
        else:
            chars.append(" ")
    text = "".join(chars)

    # 4. Collapse runs of whitespace and strip
    text = re.sub(r"\s+", " ", text).strip()

    # Re-normalize NFC just in case
    return unicodedata.normalize("NFC", text)


def match_string(candidate: str, accepted_forms: Union[str, Iterable[str]]) -> bool:
    """Check if candidate matches any of the accepted forms after normalization.

    Accepted forms include every spelling variant and product/item codes.
    """
    norm_cand = normalize_string(candidate)
    if not norm_cand:
        return False

    if isinstance(accepted_forms, str):
        return norm_cand == normalize_string(accepted_forms)

    for form in accepted_forms:
        if norm_cand == normalize_string(form):
            return True
    return False
