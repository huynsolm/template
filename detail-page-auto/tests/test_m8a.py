"""M8-A: one section one message, type hierarchy, automatic alignment and rendered line measurement."""
import hashlib
import json
import mimetypes
import shutil
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest
from playwright.sync_api import sync_playwright
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from core.copy_rules import LINE_LIMITS, budgets, prompt_guidance
from core.facts import ProductFacts
from core.ingest import extract_json
from core.measure import subject, target_chars
from core.prompting import make_prompt
from core.render import chromium_path
from core.workflow import create_job, ingest_job, overflow_regenerate_job, read_json

NEW_THEMES = ('modern', 'natural', 'impact', 'industrial')
LEGACY = ('classic', 'minimal', 'bold')
COPY_CODES = {'COPY_TOO_LONG', 'LIST_TOO_MANY', 'SECTION_TOO_DENSE'}


def rich_job(tmp_path, theme, answer='answer-rich.txt'):
    facts = ProductFacts.model_validate(read_json(ROOT / 'samples/facts-rich.json'))
    job = create_job(facts, ROOT / 'samples', tmp_path, theme=theme)
    ingest_job(job, (ROOT / 'samples' / answer).read_text(encoding='utf-8'), render_output=True, theme=theme)
    return job


def bundle_of(job):
    return next((job / 'rendered').iterdir())


def copy_items(job):
    return [item for item in read_json(job / 'review.json') if item.get('code') in COPY_CODES]


def open_page(bundle):
    """Open a bundle in Chromium through the same offline virtual origin as the renderer."""
    pw = sync_playwright().start()
    browser = pw.chromium.launch(executable_path=chromium_path(pw.chromium.executable_path))
    page = browser.new_page(viewport={'width': 860, 'height': 1000}, offline=True)

    def local(route):
        url = urlparse(route.request.url)
        path = (bundle / unquote(url.path).lstrip('/')).resolve()
        assert url.netloc == '127.0.0.1:18600' and path.is_relative_to(bundle) and path.is_file()
        route.fulfill(body=path.read_bytes(), content_type=mimetypes.guess_type(path.name)[0] or 'application/octet-stream')

    page.route('**/*', local)
    page.goto('http://127.0.0.1:18600/page.html')
    page.evaluate("async () => { await document.fonts.ready; }")
    page.wait_for_function("() => !document.querySelector('script[src=\"assets/layout.js\"]') || document.documentElement.hasAttribute('data-layout-done')")
    return pw, browser, page


# --- rules and prompt -------------------------------------------------------------------------

def test_rule_helpers():
    assert target_chars(90, 3, 2) == 60
    assert target_chars(10, 0, 1) == 10
    assert [subject(w) for w in ('보조 설명', '서브 카피', 'FAQ 답변', '헤드 카피')] == ['보조 설명이', '서브 카피가', 'FAQ 답변이', '헤드 카피가']
    assert LINE_LIMITS == {'hero_head': 2, 'head': 1, 'sub': 1, 'support': 2, 'item': 1, 'faq_answer': 3}
    b = budgets()
    assert b['section_head'].chars < b['support'].chars and b['support'].lines == 2


def test_prompt_v5_and_v6_carry_the_one_message_rules():
    facts = ProductFacts.model_validate(read_json(ROOT / 'samples/facts-rich.json'))
    prompt = make_prompt(facts)
    assert prompt.startswith((ROOT / 'prompts/copy_v5.md').read_text(encoding='utf-8'))
    assert prompt_guidance() in prompt
    assert '1 섹션 1 메시지' in prompt and '고객 고민 2~4개' in prompt and '자르지 않습니다' in prompt
    data = read_json(ROOT / 'samples/facts-rich.json')
    data['references'] = [{'id': 'ref-1', 'label': '참고', 'kind': 'other', 'text': '참고 자료 본문입니다.'}]
    with_refs = make_prompt(ProductFacts.model_validate(data))
    assert with_refs.startswith((ROOT / 'prompts/copy_v6.md').read_text(encoding='utf-8'))
    assert prompt_guidance() in with_refs
    # Older prompt versions stay unchanged on disk.
    assert '1 섹션 1 메시지' not in (ROOT / 'prompts/copy_v3.md').read_text(encoding='utf-8')


# --- measurement --------------------------------------------------------------------------------

@pytest.mark.parametrize('theme', NEW_THEMES)
def test_normal_answer_has_no_copy_overflow(tmp_path, theme):
    job = rich_job(tmp_path, theme)
    assert copy_items(job) == []
    manifest = read_json(bundle_of(job) / 'manifest.json')
    assert manifest['copy_rules_enforced'] is True
    assert manifest['copy_metrics'] and all(not m['over'] for m in manifest['copy_metrics'])
    measured = {(m['section_id'], m['field_path']) for m in manifest['copy_metrics']}
    assert {('hero-1', 'headline'), ('solution-1', 'body'), ('features-1', 'items.0.desc'), ('faq-1', 'items.0.a')} <= measured
    assert not any(m['section_type'] in ('spec', 'notice', 'review') for m in manifest['copy_metrics'])


@pytest.mark.parametrize('theme', ('modern', 'industrial'))
def test_long_answer_is_flagged_where_it_overflows_and_never_cut(tmp_path, theme):
    job = rich_job(tmp_path, theme, 'answer-rich-long.txt')
    items = copy_items(job)
    found = {(i['code'], i['section_id'], i['field_path']) for i in items}
    assert {('COPY_TOO_LONG', 'hero-1', 'subcopy'), ('COPY_TOO_LONG', 'solution-1', 'body'),
            ('COPY_TOO_LONG', 'features-1', 'items.0.desc'), ('LIST_TOO_MANY', 'pain-1', 'items'),
            ('SECTION_TOO_DENSE', 'features-1', 'features')} <= found
    for item in items:
        if item['code'] == 'COPY_TOO_LONG':
            d = item['detail']
            assert d['lines'] > d['limit'] and d['target_chars'] == target_chars(d['chars'], d['lines'], d['limit'])
            assert f"{d['lines']}줄" in item['reason'] and f"{d['target_chars']}자" in item['reason']
    long = extract_json((ROOT / 'samples/answer-rich-long.txt').read_text(encoding='utf-8'))
    draft = read_json(job / 'draft.json')
    solution = next(s for s in draft['sections'] if s['type'] == 'solution')
    pain = next(s for s in draft['sections'] if s['type'] == 'pain')
    assert solution['body'] == long['solution']['body']
    assert pain['items'] == [i['text'] for i in long['pain']['items']]
    bundle = bundle_of(job)
    assert long['solution']['body'] in (bundle / 'page.html').read_text(encoding='utf-8')
    assert all('.DRAFT.' in p['file'] for p in read_json(bundle / 'manifest.json')['pages'])
    assert read_json(job / 'manifest.json')['needs_review'] is True


@pytest.mark.parametrize('theme', LEGACY)
def test_legacy_themes_only_report_measurements(tmp_path, theme):
    job = rich_job(tmp_path, theme, 'answer-rich-long.txt')
    bundle = bundle_of(job)
    manifest = read_json(bundle / 'manifest.json')
    assert manifest['copy_rules_enforced'] is False and manifest['copy_reviews'] == []
    assert manifest['copy_metrics'] and manifest['copy_reviews_informational']
    assert copy_items(job) == []
    html = (bundle / 'page.html').read_text(encoding='utf-8')
    assert 'data-align' not in html and 'layout.js' not in html
    assert not (bundle / 'assets/layout.js').exists()


# --- typography, spacing, fonts and alignment in the browser ------------------------------------

EXCEPTIONS_JS = r'''() => {
  const minimum = el => {
    if (el.closest('.eyebrow, .section-label')) return 15;
    if (el.closest('.stat-list dt')) return 16;
    if (el.closest('.spec-panel th, .spec-panel td')) return 16;
    if (el.closest('.spec-notes')) return 18;
    return 22;
  };
  const walker = document.createTreeWalker(document.querySelector('main'), NodeFilter.SHOW_TEXT);
  const small = []; const families = new Set(); const edges = [];
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (!node.textContent.trim()) continue;
    const el = node.parentElement;
    const style = getComputedStyle(el);
    const size = parseFloat(style.fontSize);
    if (size < minimum(el)) small.push([el.tagName, el.className, size, node.textContent.trim().slice(0, 20)]);
    families.add(style.fontFamily.split(',')[0].trim().replace(/"/g, ''));
    const range = document.createRange(); range.selectNodeContents(node);
    for (const r of range.getClientRects()) if (r.width > 0) edges.push([r.left, r.right]);
  }
  const size = sel => parseFloat(getComputedStyle(document.querySelector(sel)).fontSize);
  const weight = sel => parseInt(getComputedStyle(document.querySelector(sel)).fontWeight);
  return {small, families: [...families], minLeft: Math.min(...edges.map(e => e[0])),
          maxRight: Math.max(...edges.map(e => e[1])), h1: size('h1'), h2: size('h2'),
          sub: size('.hero-copy p:not(.price)'), body: size('.solution p'),
          h1Weight: weight('h1'), h2Weight: weight('h2'), h1Family: getComputedStyle(document.querySelector('h1')).fontFamily,
          overflow: document.documentElement.scrollWidth > 860};
}'''


@pytest.mark.parametrize('theme', NEW_THEMES)
def test_dom_type_scale_spacing_and_fonts(tmp_path, theme):
    job = rich_job(tmp_path, theme)
    pw, browser, page = open_page(bundle_of(job))
    try:
        r = page.evaluate(EXCEPTIONS_JS)
    finally:
        browser.close(); pw.stop()
    assert r['small'] == [], r['small']
    assert 64 <= r['h1'] <= 82 and 40 <= r['h2'] <= 52
    assert r['h2'] * 0.5 <= r['sub'] <= r['h2'] * 0.6 and r['sub'] >= 22
    assert r['body'] >= 22
    # Headings are 800 or heavier, except faces whose heaviest bundled weight is lower
    # (user decision 2026-11-24): Black Han Sans 400 (impact), Gowun Batang 700 (natural).
    if theme == 'impact':
        assert 'Black Han Sans' in r['h1Family'] and r['h1Weight'] == 400
    elif theme == 'natural':
        assert 'Gowun Batang' in r['h1Family'] and r['h1Weight'] == r['h2Weight'] == 700
    else:
        assert r['h1Weight'] >= 800 and r['h2Weight'] >= 800
    assert len(r['families']) <= 2, r['families']
    assert r['minLeft'] >= 40 and r['maxRight'] <= 820, (r['minLeft'], r['maxRight'])
    assert not r['overflow']


ALIGN_JS = "() => Object.fromEntries([...document.querySelectorAll('main > section[data-align]')].map(s => [s.dataset.section, [s.dataset.align, s.classList.contains('copy-align-center') ? 'center' : s.classList.contains('copy-align-left') ? 'left' : null, getComputedStyle(s).textAlign]]))"


@pytest.mark.parametrize('theme', ('modern', 'impact'))
def test_auto_alignment_from_measured_copy(tmp_path, theme):
    short = rich_job(tmp_path / 'short', theme)
    long = rich_job(tmp_path / 'long', theme, 'answer-rich-long.txt')
    results = {}
    for name, job in (('short', short), ('long', long)):
        moved = tmp_path / f'moved-{name}'
        shutil.copytree(bundle_of(job), moved)
        pw, browser, page = open_page(moved)
        try:
            results[name] = page.evaluate(ALIGN_JS)
        finally:
            browser.close(); pw.stop()
        metrics = read_json(bundle_of(job) / 'manifest.json')['copy_metrics']
        recorded = {m['section_id']: m['align'] for m in metrics if m['align']}
        assert all(results[name][sid][1] == align for sid, align in recorded.items())
    assert results['short']['solution-1'][1:] == ['center', 'center']
    assert results['long']['solution-1'][1:] == ['left', 'left']
    for name in results:
        assert results[name]['pain-1'][1:] == ['left', 'left']
        assert results[name]['faq-1'][1] in ('center', 'left')
        assert results[name]['features-1'][1] == 'left'


def test_natural_keeps_its_fixed_centre_sections(tmp_path):
    job = rich_job(tmp_path, 'natural')
    pw, browser, page = open_page(bundle_of(job))
    try:
        result = page.evaluate(ALIGN_JS)
    finally:
        browser.close(); pw.stop()
    assert result['pain-1'][:2] == ['center', 'center'] and result['features-1'][:2] == ['center', 'center']
    assert result['solution-1'][0] == 'auto'


# --- rewrite request for overflowing copy -------------------------------------------------------

def test_overflow_regenerate_job_requests_only_overflowing_sections(tmp_path):
    job = rich_job(tmp_path, 'modern', 'answer-rich-long.txt')
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in job.iterdir() if p.is_file()}
    child = overflow_regenerate_job(job)
    after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in job.iterdir() if p.is_file()}
    assert before == after  # the previous job is not modified
    overflow_sections = {i['section_id'] for i in copy_items(job)}
    locked = read_json(child / 'locked.json')
    assert set(locked).isdisjoint(overflow_sections)
    assert {'how_to-1', 'faq-1'} <= set(locked)
    prompt = (child / 'prompt.md').read_text(encoding='utf-8')
    assert '## 줄 수 초과 수정 요청' in prompt and '<copy_overflow>' in prompt
    block = prompt[prompt.index('<copy_overflow>'):prompt.index('</copy_overflow>')]
    assert {i['section_id'] for i in json.loads(block.split('\n', 1)[1])} == overflow_sections
    assert read_json(child / 'manifest.json')['regenerated_for'] == 'copy_overflow'


def test_overflow_regenerate_job_requires_overflow(tmp_path):
    job = rich_job(tmp_path, 'modern')
    with pytest.raises(ValueError, match='줄 수를 넘은 문구가 없습니다'):
        overflow_regenerate_job(job)


def test_review_screen_badges_summary_and_rewrite_button(monkeypatch, tmp_path):
    from test_app import start, stage
    app = start(monkeypatch, tmp_path)
    app.button(key='create').click().run()
    job = Path(app.session_state['job'])
    answer = extract_json((ROOT / 'samples/answer.txt').read_text(encoding='utf-8'))
    long_body = ('긴 본문입니다. ' * 30).strip()
    answer['solution']['body'] = long_body
    stage(app, 2)
    app.text_area(key='answer_text').set_value('```json\n' + json.dumps(answer, ensure_ascii=False) + '\n```')
    app.button(key='ingest').click().run()
    stage(app, 3)
    assert not any('줄 수 초과' in w.value for w in app.warning)
    assert app.button(key='overflow_rewrite').disabled
    stage(app, 4)
    app.button(key='preview').click().run(timeout=120)
    assert not app.exception
    assert any(i.get('code') == 'COPY_TOO_LONG' for i in read_json(job / 'review.json'))
    stage(app, 3)
    assert any('줄 수 초과' in w.value for w in app.warning)
    assert any('허용 2줄' in w.value and '줄이기 권장' in w.value for w in app.warning)
    assert any('허용 1줄' in c.value for c in app.caption)
    edit_key = f'edit_{job.name}_solution-1_body'
    assert app.text_area(key=edit_key).value == long_body  # not shortened
    assert not app.button(key='overflow_rewrite').disabled
    app.button(key='overflow_rewrite').click().run()
    assert not app.exception
    child = Path(app.session_state['job'])
    assert child != job and '<copy_overflow>' in (child / 'prompt.md').read_text(encoding='utf-8')
