import unicodedata


def normalize_text(text):
    """Identical normalization for offline training and online inference."""
    return " ".join(unicodedata.normalize("NFC", text).split())
