"""Conservative checks for explicitly requested facts, independent of similarity scores."""
import re
import unicodedata

NUMBER = r"(?:\d+(?:[.,]\d+)?|\b(?:mot|hai|ba|bon|nam|sau|bay|tam|chin|muoi|one|two|three|four|five|six|seven|eight|nine|ten)\b)"


def canonical(text):
    return ' '.join(unicodedata.normalize('NFC',text).split())


def folded(text):
    return ''.join(c for c in unicodedata.normalize('NFD',text.lower().replace('đ','d')) if unicodedata.category(c)!='Mn')


def explicit_questions(question):
    pair = re.fullmatch(r"([^?？]+[?？])\s+([^?？]+[?？])\s*", question)
    if pair:
        return tuple(part.strip() for part in pair.groups())
    joined = re.fullmatch(r"([^?？]+),\s*(?:và|and)\s+([^?？]+)[?？]\s*", question, re.IGNORECASE)
    if joined and all(re.search(r"\b(?:nao|gi|bao nhieu|what|which|how|where|who)\b", folded(part))
                      for part in joined.groups()):
        return tuple(part.strip() + "?" for part in joined.groups())
    return (question,)


def clarification_needed(question):
    query = folded(canonical(question))
    if re.fullmatch(r"(?:toi |minh |em )?nen (?:chon|dung) (?:goc may|goc quay|co canh) nao cho (?:canh|phan doan) (?:nay|do)[?.! ]*", query):
        return "Bạn muốn cảnh đó tạo cảm giác gì, chẳng hạn nhân vật trông yếu thế hay mạnh mẽ? Mình sẽ gợi ý góc máy theo mục tiêu của cảnh."
    if re.fullmatch(r"(?:chiec )?ghe (?:do|nay|kia) (?:la )?(?:cua (?:toi|minh|em) )?(?:cua (?:toi|minh|em)|chua|roi chua|phai khong)[?.! ]*", query):
        return "Bạn đang nói đến ghế và suất chiếu nào? Bạn đã chọn ghế hay đã thanh toán trên giao diện?"
    return ""


def echoes_question(question, answer):
    question = folded(canonical(question))
    answer = folded(canonical(answer))
    if answer.rstrip().endswith("?"):
        return True
    parts = (part.strip(" .?!") for part in re.split(r"[?\n]", question))
    return any(answer.strip(" .?!") == part for part in parts if part) or any(
        cue in question and cue in answer for cue in ("dieu gi", "bao nhieu", "may phut", "may ngay")
    )


def support_spans(source):
    # The server supplies the literal source spans. The model selects IDs rather
    # than attempting to reproduce quotes (which can introduce subtle typos).
    text=canonical(source['text'])  # PDF layout line breaks are not sentence boundaries.
    parts=re.split(r'(?<=[.!?])\s+|(?<=[.!?][”"])\s+',text)
    result=[]
    for i,part in enumerate(parts):
        if i==0 and source.get('provenance',{}).get('character_start',0)>0:
            continue  # Character chunking can start in the middle of a sentence.
        if len(part)>=8 and re.search(r'[.!?][”"]?\d*$',part):
            # An anaphoric sentence can depend on the preceding definition or film title.
            if (i > 0 and (i > 1 or not source.get("provenance", {}).get("character_start"))
                    and re.match(r"(?:This|That) (?:movie|film|shot|movement|technique)\b", part)):
                part = f"{parts[i - 1]} {part}"
            result.append(dict(id=f"{source['id']}:span:{i}",text=part))
    return result


def covers_specifics(question, evidence):
    query, passage=folded(question),folded(evidence)
    # A page/chunk that merely discusses movies cannot support a claim about a
    # particular year, age, percentage or named numeric identifier absent from it.
    numbers=set(re.findall(r'\d+',query))
    if not numbers.issubset(set(re.findall(r'\d+',passage))):
        return False
    requirements=[(r'(?:bao nhieu|may)\s+phan tram',r'%|phan tram|percent'),
        (r'(?:bao nhieu|may)\s+ngay',r'days?\b|ngay\b'),
        (r'(?:bao nhieu|may)\s+phut',r'minutes?\b|phut\b'),
        (r'(?:bao nhieu|may)\s+ve\b',r've\b|tickets?\b'),
        (r'(?:bao nhieu|may)\s+(?:kg|ki\s*lo|kilograms?)\b',r'kg\b|ki\s*lo\b|kilograms?\b'),
        (r'(?:bao nhieu|may)\s+do\s+(?:moi giay|tren giay)',r'(?:do|degrees?)\s+(?:moi giay|tren giay|per second)|°/s')]
    for question_pattern,unit_pattern in requirements:
        if re.search(question_pattern,query) and not re.search(rf'{NUMBER}\s*(?:{unit_pattern})', passage):
            return False
    if re.search(r'\b(?:toi da|gioi han)\b.*\b(?:bao nhieu|may)\s+ve\b', query) and not re.search(
            r'\b(?:toi da|gioi han|maximum|limit)\b', passage):
        return False
    for pattern in (r"\biso\b", r"\bhoa don\b"):
        if re.search(pattern, query) and not re.search(pattern, passage):
            return False
    word_number=r'(?:một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười)'
    for unit,unit_pattern in [('phần trăm',r'%|phan tram|percent'),('phút',r'\bphut\b|\bminutes?\b'),
                             ('ngày',r'\bngay\b|\bdays?\b'),('tuổi',r'\btuoi\b|\byears?\b')]:
        if re.search(r'\b'+word_number+r'\s+'+unit+r'\b',question.casefold()) and not (re.search(NUMBER,passage) and re.search(unit_pattern,passage)):
            return False
    if ('so dien thoai' in query or 'hotline' in query) and not re.search(r'(?<!\d)(?:\d[ .-]?){8,12}(?!\d)',passage):
        return False
    return True
