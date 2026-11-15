import re
import unicodedata


def normalize_text(text):
    """Identical normalization for offline training and online inference."""
    return " ".join(unicodedata.normalize("NFC", text).split())


def is_literal_negative_review(text):
    return re.fullmatch(
        r"phim(?: này)? (?:(?:rất|quá) )?(?:dở|tệ|chán|không hay)(?: (?:quá|lắm|thật))?[.!…]*",
        normalize_text(text).casefold(),
    ) is not None
