"""M8-C: PDF export of a render snapshot with real, selectable text.

The bundle's own page.html is printed by the same offline Chromium the renderer uses, split at
the same places as the JPG pages, and every text run on the page is checked in the PDF's
extracted text. Missing text fails the export and says where; text is never turned into images.
"""
import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, Error as BrowserError

from .render import open_offline

PX_TO_PT = 0.75
PAGE_SLACK_PX = 2  # rounding room so a page's content never spills onto an extra page

SPLIT_JS = r'''pages => {
  const css = [];
  pages.forEach((p, i) => {
    css.push(`@page p${i} { size: 860px ${p.bottom - p.top + %d}px; margin: 0; }`);
    for (const s of document.querySelectorAll('main > section')) {
      const top = Math.ceil(s.getBoundingClientRect().top);
      if (top >= p.top && top < p.bottom) s.style.page = 'p' + i;
    }
  });
  const style = document.createElement('style');
  style.textContent = css.join('\n');
  document.head.appendChild(style);
}''' % PAGE_SLACK_PX

TEXT_JS = r'''() => {
  // Every visible text run, with the document position used to place it on a PDF page.
  // Visibility includes ancestors (display:none, visibility:hidden, content-visibility).
  const out = [];
  for (const section of document.querySelectorAll('main > section')) {
    const walker = document.createTreeWalker(section, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      const text = node.textContent.trim();
      if (!text) continue;
      const element = node.parentElement;
      if (!element.checkVisibility({checkVisibilityCSS: true})) continue;
      const range = document.createRange();
      range.selectNodeContents(node);
      const rects = [...range.getClientRects()].filter(r => r.width > 0 && r.height > 0);
      if (!rects.length) continue;
      out.push({section_id: section.dataset.section, text,
                top: Math.min(...rects.map(r => r.top)) + window.scrollY,
                bottom: Math.max(...rects.map(r => r.bottom)) + window.scrollY});
    }
  }
  return out;
}'''

# Variation selectors only choose how a character is drawn (e.g. U+FE0F emoji style); PDF text
# extraction may drop them. They are ignored and counted; every other character must be present.
PRESENTATION = re.compile('[︀-️\U000e0100-\U000e01ef]')


def _squash(text: str) -> str:
    return PRESENTATION.sub('', re.sub(r'[\s­]+', '', text)).casefold()


POSITION_TOLERANCE_PT = 4


def page_characters(page) -> tuple[str, list[float]]:
    """A page's text as one squashed string, with the baseline height (pt from the bottom) of each character."""
    chars, heights = [], []
    def visit(text, cm, tm, font, size):
        y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
        for char in _squash(text):
            chars.append(char); heights.append(y)
    page.extract_text(visitor_text=visit)
    return ''.join(chars), heights


def match_runs(runs: list[dict], pdf_pages: list, pages: list[dict]) -> list[dict]:
    """Runs not found in the PDF where they are drawn.

    Each run is looked for on its own page, only among characters whose baselines lie within the
    run's own box (so a repeated text elsewhere does not count), longest text first. A matched
    span is used up, so two occurrences need two occurrences in the PDF and a short text inside a
    longer one cannot borrow its letters."""
    texts, heights = [], []
    for page in pdf_pages:
        text, height = page_characters(page)
        texts.append(text); heights.append(height)
    missing = []
    def page_of(run):
        for index, page in enumerate(pages):
            if page['top'] <= run['top'] < page['bottom']:
                return index
        return len(pages) - 1
    for run in sorted(runs, key=lambda r: (-len(_squash(r['text'])), r['top'])):
        needle = _squash(run['text'])
        if not needle:
            continue
        index = page_of(run)
        page_height = float(pdf_pages[index].mediabox.height)
        high = page_height - (run['top'] - pages[index]['top']) * PX_TO_PT + POSITION_TOLERANCE_PT
        low = page_height - (run['bottom'] - pages[index]['top']) * PX_TO_PT - POSITION_TOLERANCE_PT
        text, height = texts[index], heights[index]
        found, start = -1, text.find(needle)
        while start >= 0:
            if all(low <= height[i] <= high for i in range(start, start + len(needle))):
                found = start
                break
            start = text.find(needle, start + 1)
        if found < 0:
            missing.append(run)
            continue
        texts[index] = text[:found] + '\x00' * len(needle) + text[found + len(needle):]
    return sorted(missing, key=lambda r: r['top'])


def ignored_presentation(runs: list[dict], page_texts: list[str]) -> dict:
    wanted, got = {}, {}
    for text, counter in [(r['text'], wanted) for r in runs] + [(t, got) for t in page_texts]:
        for char in PRESENTATION.findall(text):
            key = f'U+{ord(char):04X}'
            counter[key] = counter.get(key, 0) + 1
    return {key: count - got.get(key, 0) for key, count in sorted(wanted.items()) if count > got.get(key, 0)}


def _fonts(obj, seen=None) -> set[str]:
    seen = set() if seen is None else seen
    names = set()
    resources = obj.get('/Resources')
    if resources is None:
        return names
    resources = resources.get_object()
    for value in resources.get('/Font', {}).values():
        font = value.get_object()
        base = font.get('/BaseFont')
        names.add(str(base).lstrip('/').split('+', 1)[-1] if base else f"{str(font.get('/Subtype', '')).lstrip('/')} (이름 없음)")
    for value in resources.get('/XObject', {}).values():
        child = value.get_object()
        if id(child) not in seen:
            seen.add(id(child))
            names |= _fonts(child, seen)
    return names


def pdf_name(manifest: dict) -> str:
    draft = any('.DRAFT.' in page['file'] for page in manifest['pages'])
    return 'page.DRAFT.pdf' if draft else 'page.pdf'


def make_pdf(bundle: Path) -> Path:
    """Write the bundle's PDF next to its JPGs and record ``pdf`` in its manifest."""
    from pypdf import PdfReader
    from .image_checks import export_block
    bundle = Path(bundle).resolve(strict=True)
    manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
    blocked = export_block(bundle, manifest)
    if blocked:
        raise ValueError(blocked)
    families = [font['family'] for font in manifest.get('fonts', [])] or ['DetailKorean']
    started = time.perf_counter()
    try:
        with sync_playwright() as pw:
            browser, page, network, failures = open_offline(pw, bundle / 'page.html', families)
            try:
                page.emulate_media(media='screen')
                runs = page.evaluate(TEXT_JS)
                page.evaluate(SPLIT_JS, manifest['pages'])
                data = page.pdf(print_background=True, prefer_css_page_size=True)
                if failures or network:
                    raise ValueError(f'asset loading failed or forbidden request: {failures + network}')
            finally:
                browser.close()
    except BrowserError as exc:
        raise ValueError(f'Chromium PDF output failed: {exc}') from exc
    target = bundle / pdf_name(manifest)
    temporary = target.with_suffix('.pdf.tmp')
    temporary.write_bytes(data)
    try:
        reader = PdfReader(temporary)
        if len(reader.pages) != len(manifest['pages']):
            raise ValueError(f"PDF 쪽 수({len(reader.pages)})가 이미지 장 수({len(manifest['pages'])})와 다릅니다.")
        page_texts = [page.extract_text() or '' for page in reader.pages]
        missing = match_runs(runs, reader.pages, manifest['pages'])
        if missing:
            where = ', '.join(f"{run['section_id']}: {run['text'][:30]}" for run in missing[:5])
            raise ValueError(f'PDF에서 글자 {len(missing)}곳이 빠졌습니다(글자 보존 실패). 위치: {where}')
        fonts = sorted(set().union(*(_fonts(page) for page in reader.pages)))
        sizes = [[round(float(page.mediabox.width), 2), round(float(page.mediabox.height), 2)] for page in reader.pages]
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    temporary.replace(target)
    manifest['pdf'] = {'file': target.name, 'pages': len(sizes), 'page_sizes_pt': sizes, 'fonts': fonts,
                       'text_check': {'runs': len(runs), 'missing': 0, 'matching': 'position-occurrence',
                                      'ignored_presentation': ignored_presentation(runs, page_texts)},
                       'network_requests': network,
                       'elapsed_seconds': round(time.perf_counter() - started, 3)}
    (bundle / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return target
