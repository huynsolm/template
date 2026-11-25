"""M8-A "one section, one message" rules shared by the prompt, the renderer and the UI.

Limits are counted in rendered lines (the renderer measures them in Chromium).
Character budgets are only approximate guidance for the copy prompt; the measured
line count is authoritative. Nothing here shortens or rewrites copy.
"""
from dataclasses import dataclass

# role -> rendered line limit
LINE_LIMITS = {
    'hero_head': 2,   # 대표 제목만 2줄 허용
    'head': 1,
    'sub': 1,
    'support': 2,
    'item': 1,
    'faq_answer': 3,  # FAQ 답변 예외
}
ROLE_NAMES = {
    'hero_head': '대표 제목', 'head': '헤드 카피', 'sub': '서브 카피', 'support': '보조 설명',
    'item': '목록 항목', 'faq_answer': 'FAQ 답변',
}

# Elements measured inside each section type. (selector, path template, role, data getter)
# Selectors are relative to the section element and work for legacy and M6 templates,
# so no template markup has to change.
MEASURE_SPEC = {
    'hero': [('h1', 'headline', 'hero_head'), ('p:not(.price)', 'subcopy', 'sub')],
    'pain': [('h2', 'title', 'head'), ('li', 'items.{i}', 'item')],
    'solution': [('h2', 'title', 'head'), ('h2 ~ p, .quote p', 'body', 'support')],
    'features': [('h3', 'items.{i}.title', 'head'), ('h3 + p', 'items.{i}.desc', 'support')],
    'how_to': [('li h3', 'steps.{i}.title', 'head'), ('li h3 + p', 'steps.{i}.desc', 'support')],
    'faq': [('h3', 'items.{i}.q', 'head'), ('h3 + p', 'items.{i}.a', 'faq_answer')],
    'stats': [('dt', 'items.{i}.label', 'item'), ('dd', 'items.{i}.value', 'item')],
    'targets': [('li', 'items.{i}', 'item')],
    'structure': [('dt', 'items.{i}.name', 'item'), ('dd', 'items.{i}.desc', 'item')],
    'cases': [('h3', 'items.{i}.name', 'head'), ('h3 + p', 'items.{i}.desc', 'support')],
}
# Information and legal sections are never measured.
UNMEASURED = ('spec', 'notice', 'review', 'gallery', 'image')

# (min, max) item counts; only an excess is reported.
LIST_LIMITS = {'pain': (2, 4), 'features': (3, 5), 'how_to': (2, 4), 'faq': (2, 5)}
LIST_FIELD = {'pain': 'items', 'features': 'items', 'how_to': 'steps', 'faq': 'items'}

DENSE_SECTION_LINES = 10


@dataclass(frozen=True)
class Budget:
    role: str
    lines: int
    chars: int


def chars_per_line(font_px: float, width_px: float = 740.0) -> int:
    # Korean glyphs are roughly 1em wide; keep a small margin for punctuation and spacing.
    return max(1, int(width_px / font_px * 0.92))


def budgets(type_scale: dict | None = None, width_px: float = 740.0) -> dict[str, Budget]:
    """Approximate character budgets per role from a theme's type scale (pixels)."""
    scale = {'hero_head': 66, 'head': 46, 'item_head': 31, 'sub': 26, 'body': 24}
    scale.update(type_scale or {})
    size = {'hero_head': scale['hero_head'], 'head': scale['item_head'], 'sub': scale['sub'],
            'support': scale['body'], 'item': scale['body'], 'faq_answer': scale['body']}
    result = {role: Budget(role, LINE_LIMITS[role], LINE_LIMITS[role] * chars_per_line(size[role], width_px))
              for role in LINE_LIMITS}
    # Section titles (h2) are larger than item titles; give them their own budget.
    result['section_head'] = Budget('section_head', 1, chars_per_line(scale['head'], width_px))
    return result


def prompt_guidance(type_scale: dict | None = None) -> str:
    """The one-message rules as prompt text, with budgets derived from the type scale."""
    b = budgets(type_scale)
    lo = lambda kind: LIST_LIMITS[kind][0]
    hi = lambda kind: LIST_LIMITS[kind][1]
    return '\n'.join([
        '## 1 섹션 1 메시지 (문구 길이 규칙)',
        '각 섹션은 핵심 메시지 하나만 전달하세요. 섹션마다 헤드 카피 1줄, 서브 카피 1줄, 보조 설명 1~2줄을 넘기지 마세요.',
        '아래 글자 수는 상세페이지 폭(860px)에서 한 줄에 들어가는 대략적인 기준입니다. 프로그램이 실제 줄 수를 재서 넘치면 수정을 요청합니다. 넘쳐도 자르지 않습니다.',
        f'- 대표 제목(hero.headline): 2줄 이내, 약 {b["hero_head"].chars}자 이하',
        f'- 대표 보조 문구(hero.subcopy): 1줄, 약 {b["sub"].chars}자 이하',
        f'- 섹션 제목(pain.title, solution.title): 1줄, 약 {b["section_head"].chars}자 이하',
        f'- 항목 제목(features·how_to의 title, faq의 q): 1줄, 약 {b["head"].chars}자 이하',
        f'- 보조 설명(solution.body, features·how_to의 desc): 2줄 이내, 약 {b["support"].chars}자 이하',
        f'- 고객 고민 항목(pain.items): 항목당 1줄, 약 {b["item"].chars}자 이하',
        f'- FAQ 답변(faq의 a): 3줄 이내, 약 {b["faq_answer"].chars}자 이하',
        f'- 개수: 고객 고민 {lo("pain")}~{hi("pain")}개, 특징 {lo("features")}~{hi("features")}개, '
        f'사용 방법 {lo("how_to")}~{hi("how_to")}단계, FAQ {lo("faq")}~{hi("faq")}개',
        '한 문장에 여러 장점을 몰아넣지 말고, 덜 중요한 내용은 빼세요.',
    ])
