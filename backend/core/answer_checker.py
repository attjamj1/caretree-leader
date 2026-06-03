from rapidfuzz import fuzz


FUZZY_THRESHOLD = 85  # % match required (0-100)


def check_answer(submitted: str, correct: str, fuzzy: bool = True) -> bool:
    """
    Compare submitted answer to correct answer.
    - Always case-insensitive
    - Strips punctuation and extra spaces
    - Optional fuzzy matching for typo tolerance
    """
    sub = _normalize(submitted)
    cor = _normalize(correct)

    if sub == cor:
        return True

    if fuzzy:
        ratio = fuzz.ratio(sub, cor)
        return ratio >= FUZZY_THRESHOLD

    return False


def _normalize(text: str) -> str:
    import re
    text = text.upper().strip()
    text = re.sub(r"[^\w\s]", "", text)   # remove punctuation
    text = re.sub(r"\s+", " ", text)       # collapse spaces
    return text