"""M8-A rendered copy measurement and review items.

The renderer calls :data:`MEASURE_JS` in the same Chromium page it captures, after
fonts load and the layout script has run. Lines are counted from the text's line
boxes, so the measurement reflects the real fonts, sizes and widths. Copy is never
shortened; excess becomes a review item that says where and by how much.
"""
from .copy_rules import (DENSE_SECTION_LINES, LINE_LIMITS, LIST_FIELD, LIST_LIMITS, MEASURE_SPEC,
                         ROLE_NAMES)

# Sections filled from the seller's product information (①), not from the AI answer.
SELLER_SECTIONS = ('stats', 'targets', 'structure')
# Bump when the measurement or the alignment/fitting it depends on changes, so older
# previews of the M8-A themes are rendered again instead of reused.
MEASURE_VERSION = 'm8a-2'


def subject(word: str) -> str:
    """Korean subject particle: 이 after a final consonant, 가 otherwise."""
    last = word[-1]
    has_final = '가' <= last <= '힣' and (ord(last) - ord('가')) % 28 != 0
    return word + ('이' if has_final else '가')

MEASURE_JS = r'''spec => {
  const lineCount = element => {
    const range = document.createRange();
    range.selectNodeContents(element);
    const tops = [];
    for (const r of range.getClientRects()) {
      // Zero-width boxes are kept: an empty line in pre-wrap text is still a line.
      if (r.height <= 0) continue;
      if (!tops.some(t => Math.abs(t - r.top) < r.height / 2)) tops.push(r.top);
    }
    return tops.length;
  };
  const out = [];
  for (const section of document.querySelectorAll('main > section')) {
    const kind = section.classList[0];
    const rules = spec[kind];
    if (!rules) continue;
    for (const [selector, template, role] of rules) {
      [...section.querySelectorAll(selector)].forEach((element, i) => {
        const text = element.textContent.trim();
        if (!text) return;
        const style = getComputedStyle(element);
        out.push({section_id: section.dataset.section, section_type: kind,
                  field_path: template.replace('{i}', String(i)), role,
                  lines: lineCount(element), chars: [...text].length,
                  font_size: parseFloat(style.fontSize), text,
                  align: section.classList.contains('copy-align-center') ? 'center'
                       : section.classList.contains('copy-align-left') ? 'left' : null});
      });
    }
  }
  return out;
}'''


def measure_spec() -> dict:
    return {kind: [list(rule) for rule in rules] for kind, rules in MEASURE_SPEC.items()}


def annotate(metrics: list[dict]) -> list[dict]:
    """Attach the line limit and overflow flag to each raw measurement."""
    result = []
    for item in metrics:
        limit = LINE_LIMITS[item['role']]
        result.append({**item, 'limit': limit, 'over': item['lines'] > limit})
    return result


def target_chars(chars: int, lines: int, limit: int) -> int:
    return max(1, chars * limit // max(lines, 1))


def source_of(section_type: str) -> str:
    return 'seller' if section_type in SELLER_SECTIONS else 'ai'


SELLER_HINT = ' 판매자 입력이므로 ① 상품 정보에서 고치고 새 작업을 시작하세요.'


def copy_reviews(metrics: list[dict], document=None, dense_limit: int = DENSE_SECTION_LINES) -> list[dict]:
    """COPY_TOO_LONG / SECTION_TOO_DENSE from measurements, LIST_TOO_MANY from the document.

    ``detail.source`` says who can fix it: ``ai`` (the copy answer, ④ or a rewrite request) or
    ``seller`` (product information entered in ①)."""
    reviews = []
    for m in metrics:
        if not m['over']:
            continue
        source = source_of(m['section_type'])
        target = target_chars(m['chars'], m['lines'], m['limit'])
        reviews.append({
            'section_id': m['section_id'], 'field_path': m['field_path'], 'code': 'COPY_TOO_LONG',
            'severity': 'warning', 'fact_ids': [],
            'reason': f"{subject(ROLE_NAMES[m['role']])} {m['lines']}줄입니다(허용 {m['limit']}줄). "
                      f"약 {target}자 이하로 줄이기를 권장합니다." + (SELLER_HINT if source == 'seller' else ''),
            'detail': {'role': m['role'], 'lines': m['lines'], 'limit': m['limit'], 'chars': m['chars'],
                       'target_chars': target, 'text': m['text'], 'source': source},
        })
    totals = {}
    for m in metrics:
        totals.setdefault(m['section_id'], [m['section_type'], 0])[1] += m['lines']
    for section_id, (kind, lines) in totals.items():
        if lines > dense_limit:
            source = source_of(kind)
            reviews.append({
                'section_id': section_id, 'field_path': kind, 'code': 'SECTION_TOO_DENSE',
                'severity': 'warning', 'fact_ids': [],
                'reason': f'섹션 문구가 모두 {lines}줄입니다(권장 {dense_limit}줄 이하). 한 섹션에는 핵심 메시지 하나만 남기세요.'
                          + (SELLER_HINT if source == 'seller' else ''),
                'detail': {'lines': lines, 'limit': dense_limit, 'source': source},
            })
    if document is not None:
        for section in document.sections:
            if section.type not in LIST_LIMITS:
                continue
            count = len(getattr(section, LIST_FIELD[section.type]))
            maximum = LIST_LIMITS[section.type][1]
            if count > maximum:
                reviews.append({
                    'section_id': section.id, 'field_path': LIST_FIELD[section.type], 'code': 'LIST_TOO_MANY',
                    'severity': 'warning', 'fact_ids': [],
                    'reason': f'항목이 {count}개입니다(권장 {maximum}개 이하). 덜 중요한 항목을 빼세요.',
                    'detail': {'count': count, 'limit': maximum, 'source': 'ai'},
                })
    return reviews
