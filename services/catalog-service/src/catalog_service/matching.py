"""Resolve explicit titles without mistaking common words for film selections."""
import re
import unicodedata


def folded(value):
    value = unicodedata.normalize('NFD', value.lower().replace('đ', 'd'))
    return ''.join(c for c in value if unicodedata.category(c) != 'Mn')


def title_mentioned(message, title):
    content, name = folded(message).strip(), folded(title).strip()
    if not name:
        return False
    pattern = re.escape(name)
    if not re.search(r'(?<!\w)'+pattern+r'(?!\w)', content):
        return False
    if len(name.split()) == 1 and len(name) <= 3:
        # E.g. the real title "Mai" must not bind "tối mai" to that film.
        return content == name or bool(re.search(r'(?:phim|movie|film)\s+(?:ten\s+)?["“\']?'+pattern+r'(?!\w)', content)
            or re.search(r'["“\']'+pattern+r'["”\']', content))
    return True
