"""Pure, offline checks for pasted reference material and generated copy."""
import re
from collections import defaultdict


EMAIL = re.compile(r'(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])', re.IGNORECASE)
PHONE = re.compile(r'(?<!\d)0\d{1,2}[-.\s]?\d{3,4}[-.\s]?\d{4}(?!\d)')
ORDER = re.compile(r'(?:�ֹ�\s*(?:��ȣ|ID)|order\s*(?:no\.?|number|id)?)[\s:#-]*[A-Z0-9-]{6,}', re.IGNORECASE)


def _value(item, name, default=''):
    return getattr(item, name, item.get(name, default) if isinstance(item, dict) else default)


def _normalized(text):
    chars, positions = [], []
    for index, char in enumerate(text):
        if char.isalnum():
            chars.append(char.casefold())
            positions.append(index)
    return ''.join(chars), positions


def similarity_matches(generated, reference, *, n=8, min_length=15):
    """Return maximal copied spans with original generated/reference offsets."""
    left, left_positions = _normalized(generated)
    right, right_positions = _normalized(reference)
    if n < 1 or min_length < n or len(left) < min_length or len(right) < min_length:
        return []
    grams = defaultdict(list)
    for index in range(len(right) - n + 1):
        grams[right[index:index + n]].append(index)
    raw = set()
    for left_start in range(len(left) - n + 1):
        for right_start in grams.get(left[left_start:left_start + n], ()):
            a, b = left_start, right_start
            while a and b and left[a - 1] == right[b - 1]:
                a -= 1
                b -= 1
            a_end, b_end = left_start + n, right_start + n
            while a_end < len(left) and b_end < len(right) and left[a_end] == right[b_end]:
                a_end += 1
                b_end += 1
            if a_end - a >= min_length:
                raw.add((a, a_end, b, b_end))
    maximal = []
    for candidate in sorted(raw, key=lambda item: (item[0], -(item[1] - item[0]), item[2])):
        if any(old[0] <= candidate[0] and candidate[1] <= old[1]
               and old[2] <= candidate[2] and candidate[3] <= old[3] for old in maximal):
            continue
        maximal.append(candidate)
    return [{
        'start': left_positions[a],
        'end': left_positions[a_end - 1] + 1,
        'text': generated[left_positions[a]:left_positions[a_end - 1] + 1],
        'reference_start': right_positions[b],
        'reference_end': right_positions[b_end - 1] + 1,
        'reference_text': reference[right_positions[b]:right_positions[b_end - 1] + 1],
        'normalized_length': a_end - a,
    } for a, a_end, b, b_end in maximal]


def _copy_units(document):
    for section in document.sections:
        kind = section.type
        if kind == 'hero':
            yield section.id, 'hero', ' '.join(filter(None, (section.headline, section.subcopy)))
        elif kind == 'solution':
            yield section.id, 'solution', section.title + ' ' + section.body
        elif kind == 'pain':
            yield section.id, 'pain.title', section.title
            for index, item in enumerate(section.items):
                yield section.id, f'pain.items.{index}.text', item
        elif kind in ('features', 'how_to', 'faq'):
            items = section.steps if kind == 'how_to' else section.items
            for index, item in enumerate(items):
                text = ' '.join(value for key, value in item.model_dump().items()
                                if isinstance(value, str) and key != 'image')
                yield section.id, f'{kind}.{index}', text


def reference_reviews(facts, document, *, n=8, min_length=15):
    """Review generated copy against pasted references without changing it."""
    if not facts.references:
        return []
    reviews = []
    names = []
    for name in [*facts.reference_names, *(reference.label for reference in facts.references)]:
        if name not in names:
            names.append(name)
    for section_id, field_path, text in _copy_units(document):
        for reference in facts.references:
            for match in similarity_matches(text, reference.text, n=n, min_length=min_length):
                reviews.append({
                    'section_id': section_id,
                    'field_path': field_path,
                    'reason': '���� �ڷ�� ǥ�� ����',
                    'detail': {**match, 'reference_id': reference.id, 'reference_label': reference.label},
                    'fact_ids': [],
                })
        lowered = text.casefold()
        for name in names:
            start = lowered.find(name.casefold())
            if start >= 0:
                reviews.append({
                    'section_id': section_id,
                    'field_path': field_path,
                    'reason': '���� �ڷ��� ����硤�귣�� �̸� ����',
                    'detail': {'name': name, 'start': start, 'end': start + len(name),
                               'text': text[start:start + len(name)]},
                    'fact_ids': [],
                })
    return reviews


def personal_data_warnings(references):
    """Find identifiers before save; findings are advisory and text is never altered."""
    findings = []
    for reference in references:
        text = _value(reference, 'text')
        for kind, pattern in (('email', EMAIL), ('phone', PHONE), ('order_number', ORDER)):
            for match in pattern.finditer(text):
                findings.append({
                    'reference_id': _value(reference, 'id'),
                    'reference_label': _value(reference, 'label'),
                    'kind': kind,
                    'start': match.start(),
                    'end': match.end(),
                    'text': match.group(0),
                })
    return findings

