"""Conservative checks for explicitly requested facts, independent of similarity scores."""
import re
import unicodedata


def canonical(text):
    return ' '.join(unicodedata.normalize('NFC',text).split())


def folded(text):
    return ''.join(c for c in unicodedata.normalize('NFD',text.lower().replace('đ','d')) if unicodedata.category(c)!='Mn')


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
            result.append(dict(id=f"{source['id']}:span:{i}",text=part))
    return result


def covers_specifics(question, evidence):
    query, passage=folded(question),folded(evidence)
    # A page/chunk that merely discusses movies cannot support a claim about a
    # particular year, age, percentage or named numeric identifier absent from it.
    numbers=set(re.findall(r'\d+',query))
    if not numbers.issubset(set(re.findall(r'\d+',passage))):
        return False
    numeric=r'\d+|\b(?:mot|hai|ba|bon|nam|sau|bay|tam|chin|muoi|one|two|three|four|five|six|seven|eight|nine|ten)\b'
    requirements=[(r'(?:bao nhieu|may)\s+(?:phan tram)',r'%|phan tram|percent'),
        (r'(?:bao nhieu|may)\s+(?:ngay)',r'\bngay\b|\bdays?\b'),
        (r'(?:bao nhieu|may)\s+(?:phut)',r'\bphut\b|\bminutes?\b')]
    for question_pattern,unit_pattern in requirements:
        if re.search(question_pattern,query) and not (re.search(numeric,passage) and re.search(unit_pattern,passage)):
            return False
    word_number=r'(?:một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười)'
    for unit,unit_pattern in [('phần trăm',r'%|phan tram|percent'),('phút',r'\bphut\b|\bminutes?\b'),
                             ('ngày',r'\bngay\b|\bdays?\b'),('tuổi',r'\btuoi\b|\byears?\b')]:
        if re.search(r'\b'+word_number+r'\s+'+unit+r'\b',question.casefold()) and not (re.search(numeric,passage) and re.search(unit_pattern,passage)):
            return False
    if ('so dien thoai' in query or 'hotline' in query) and not re.search(r'(?<!\d)(?:\d[ .-]?){8,12}(?!\d)',passage):
        return False
    return True
