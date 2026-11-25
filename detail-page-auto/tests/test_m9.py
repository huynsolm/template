"""M9: design v2 for all seven themes, design version per job, optional price, use cases, target groups."""
import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from core.assemble import assemble, seller_sections
from core.copy_schema import CopyDraft
from core.editor import build_zip, bundle_matches, preview_job
from core.export import build_export_zip, export_bundle
from core.facts import ProductFacts
from core.ingest import extract_json
from core.pdf import make_pdf
from core.render import render, split_spec_table
from core.schema import Document
from core.themes import THEME_IDS
from core.workflow import accept_job, create_job, ingest_job, read_json
from test_m8a import open_page

ANSWER = (ROOT / 'samples/answer-rich.txt').read_text(encoding='utf-8')


def rich_document(change=None):
    facts = read_json(ROOT / 'samples/facts-rich.json')
    if change: change(facts)
    facts = ProductFacts.model_validate(facts)
    document, _ = assemble(facts, CopyDraft.model_validate(extract_json(ANSWER)))
    return document


# --- data model -----------------------------------------------------------------------------------

def test_new_fields_are_optional_and_old_data_is_unchanged():
    data = read_json(ROOT / 'samples/facts-rich.json')
    facts = ProductFacts.model_validate(data)
    dumped = facts.model_dump(exclude_none=True)
    assert not {'use_cases', 'target_industries', 'target_uses'} & set(dumped)
    sections = seller_sections(facts)
    assert 'cases' not in sections and 'groups' not in sections['targets']
    for value in ([], None):
        again = dict(data, use_cases=value, target_industries=value, target_uses=value)
        assert ProductFacts.model_validate(again).model_dump(exclude_none=True) == dumped


def test_target_groups_and_use_cases_are_assembled():
    def grouped(facts):
        facts['target_industries'] = ['오피스텔', '기숙사']
        facts['target_uses'] = ['바닥 난방', '도로 결빙 방지']
        facts['use_cases'] = [{'name': '일반 바닥 시공', 'desc': '가상 사례 설명 하나'},
                              {'name': '도로 결빙 시공', 'desc': '가상 사례 설명 둘'}]
    document = rich_document(grouped)
    targets = next(s for s in document.sections if s.type == 'targets')
    assert [g.name for g in targets.groups] == ['업종', '용도', '대상']
    assert targets.items == ['오피스텔', '기숙사', '바닥 난방', '도로 결빙 방지'] + read_json(ROOT / 'samples/facts-rich.json')['targets']
    kinds = [s.type for s in document.sections]
    assert kinds.index('cases') == kinds.index('how_to') + 1


def test_price_is_optional_and_a_written_status_is_kept():
    assert Document.model_validate({'schema_version': '1.0', 'product': {'name': 'a', 'category': 'b', 'price': '  ', 'brand_color': '#305b46'},
                                    'sections': [{'id': 'h', 'type': 'hero', 'headline': 'x', 'image': 'product.png'}]}).product.price is None


@pytest.mark.parametrize('version', [1, 2])
def test_empty_price_is_left_off_and_status_is_shown(tmp_path, version):
    def no_price(facts): facts['product']['price'] = ''
    empty = render(rich_document(no_price), ROOT / 'samples', tmp_path / 'empty', theme='modern', design_version=version)
    assert 'class="price"' not in (empty / 'page.html').read_text(encoding='utf-8')
    status = render(rich_document(), ROOT / 'samples', tmp_path / 'status', theme='modern', design_version=version)
    assert '<p class="price">판매하지 않음</p>' in (status / 'page.html').read_text(encoding='utf-8')


# --- v1 stays as it was ---------------------------------------------------------------------------

def test_default_render_and_old_jobs_stay_v1(tmp_path):
    bundle = render(rich_document(), ROOT / 'samples', tmp_path, theme='classic')
    assert read_json(bundle / 'manifest.json')['design_version'] == 1
    html = (bundle / 'page.html').read_text(encoding='utf-8')
    assert 'class="v2' not in html and 'fit-stats.js' in html
    facts = ProductFacts.model_validate(read_json(ROOT / 'samples/facts-rich.json'))
    job = create_job(facts, ROOT / 'samples', tmp_path / 'jobs', theme='modern')
    assert 'design_version' not in read_json(job / 'manifest.json')  # an existing-style job: v1
    ingest_job(job, ANSWER)
    preview = preview_job(job)
    assert read_json(preview / 'manifest.json')['design_version'] == 1
    assert 'design_version' not in read_json(job / 'manifest.json')


# --- v2 in the browser ----------------------------------------------------------------------------

V2_JS = r'''() => {
  const walker = document.createTreeWalker(document.querySelector('main'), NodeFilter.SHOW_TEXT);
  const small = [], families = new Set(), edges = [];
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (!node.textContent.trim()) continue;
    const el = node.parentElement, style = getComputedStyle(el);
    const size = parseFloat(style.fontSize);
    if (size < (el.closest('.section-label') ? 15 : 22)) small.push([el.className, size, node.textContent.trim().slice(0, 16)]);
    families.add(style.fontFamily.split(',')[0].trim().replace(/"/g, ''));
    const range = document.createRange(); range.selectNodeContents(node);
    for (const r of range.getClientRects()) if (r.width > 0) edges.push([r.left, r.right, node.textContent.trim().slice(0, 12)]);
  }
  const h1 = document.querySelector('h1');
  return {small, families: [...families], bad: edges.filter(e => e[0] < 40 || e[1] > 820),
          h1: parseFloat(getComputedStyle(h1).fontSize), sub: parseFloat(getComputedStyle(document.querySelector('.hero .sub')).fontSize),
          overflow: document.documentElement.scrollWidth > 860, v2: document.body.classList.contains('v2'),
          fit: !!document.querySelector('script[src="assets/fit-stats.js"]')};
}'''


@pytest.mark.parametrize('theme', THEME_IDS)
def test_v2_page_type_spacing_fonts_and_measurement(tmp_path, theme):
    bundle = render(rich_document(), ROOT / 'samples', tmp_path, theme=theme, design_version=2, png=True)
    manifest = read_json(bundle / 'manifest.json')
    assert manifest['design_version'] == 2 and manifest['contrast_policy'] == 'aa'
    assert manifest['copy_rules_enforced'] is True and manifest['copy_reviews'] == []
    assert manifest['copy_metrics'] and not manifest['needs_review']
    pw, browser, page = open_page(bundle)
    try:
        r = page.evaluate(V2_JS)
    finally:
        browser.close(); pw.stop()
    assert r['v2'] and not r['fit'] and not r['overflow']
    assert r['small'] == [], r['small']
    assert r['bad'] == [], r['bad']
    assert len(r['families']) <= 2, r['families']
    assert r['h1'] >= 64 and r['sub'] >= 22 and r['sub'] < r['h1'] * 0.5


def test_v2_long_answer_is_measured_and_flagged(tmp_path):
    facts = ProductFacts.model_validate(read_json(ROOT / 'samples/facts-rich.json'))
    document, _ = assemble(facts, CopyDraft.model_validate(extract_json((ROOT / 'samples/answer-rich-long.txt').read_text(encoding='utf-8'))))
    bundle = render(document, ROOT / 'samples', tmp_path, theme='classic', design_version=2)
    codes = {r['code'] for r in read_json(bundle / 'manifest.json')['copy_reviews']}
    assert {'COPY_TOO_LONG', 'LIST_TOO_MANY'} <= codes
    assert all('.DRAFT.' in p['file'] for p in read_json(bundle / 'manifest.json')['pages'])


def test_stats_note_keeps_the_text_and_never_shrinks(tmp_path):
    def long_value(facts): facts['highlights'][0]['value'] = '35W ~ 120W (풍량 3단 조절 가능)'
    bundle = render(rich_document(long_value), ROOT / 'samples', tmp_path, theme='minimal', design_version=2)
    pw, browser, page = open_page(bundle)
    try:
        first = page.evaluate("() => { const d = document.querySelector('.keyspec > div'); return [d.querySelector('dd').textContent, d.querySelector('.note').textContent, parseFloat(getComputedStyle(d.querySelector('dd')).fontSize)]; }")
    finally:
        browser.close(); pw.stop()
    assert first[0] + ' ' + first[1] == '35W ~ 120W (풍량 3단 조절 가능)' and first[2] >= 22


def test_spec_common_columns_are_split_without_losing_cells():
    table = {'columns': ['No.', '규격', '전압', '전력'],
             'rows': [['1', 'A 100', 'AC 220V', '10W'], ['2', 'A 200', 'AC 220V', '20W']]}
    split = split_spec_table(table)
    assert split['common'] == [('전압', 'AC 220V')]
    assert split['columns'] == ['No.', '규격', '전력'] and split['rows'] == [['1', 'A 100', '10W'], ['2', 'A 200', '20W']]
    assert split_spec_table({'columns': ['a', 'b'], 'rows': [['1', '2']]})['common'] == []
    same = split_spec_table({'columns': ['a', 'b'], 'rows': [['1', '2'], ['1', '2']]})
    assert same['common'] == [] and same['columns'] == ['a', 'b']


def test_v2_renders_groups_cases_and_v1_renders_them_plainly(tmp_path):
    def grouped(facts):
        facts['target_industries'] = ['오피스텔']
        facts['target_uses'] = ['바닥 난방']
        facts['use_cases'] = [{'name': '일반 바닥 시공', 'desc': '가상 사례 설명 하나'}]
    document = rich_document(grouped)
    v2 = (render(document, ROOT / 'samples', tmp_path / 'v2', theme='industrial', design_version=2) / 'page.html').read_text(encoding='utf-8')
    assert '<div class="group-name">업종</div>' in v2 and '<div class="group-name">용도</div>' in v2
    assert '<h2>적용 사례</h2>' in v2 and 'class="steps"' in v2
    v1 = (render(document, ROOT / 'samples', tmp_path / 'v1', theme='classic') / 'page.html').read_text(encoding='utf-8')
    assert '<h2>적용 사례</h2>' in v1 and '<li>오피스텔</li>' in v1 and 'group-name' not in v1


# --- versions through the job ---------------------------------------------------------------------

def test_version_follows_the_job_and_a_change_needs_a_new_approval(tmp_path):
    facts = ProductFacts.model_validate(read_json(ROOT / 'samples/facts-rich.json'))
    job = create_job(facts, ROOT / 'samples', tmp_path, theme='natural', design_version=2)
    ingest_job(job, ANSWER, render_output=True)
    assert read_json(next((job / 'rendered').iterdir()) / 'manifest.json')['design_version'] == 2
    v2 = preview_job(job)
    assert read_json(v2 / 'manifest.json')['design_version'] == 2 and bundle_matches(job, v2)
    accepted = accept_job(job)
    manifest = read_json(accepted / 'manifest.json')
    assert manifest['design_version'] == 2 and read_json(accepted / manifest['rendered_job'] / 'manifest.json')['design_version'] == 2
    v1 = preview_job(accepted, design_version=1)
    after = read_json(accepted / 'manifest.json')
    assert after['design_version'] == 1 and after['review_accepted'] is False and 'rendered_job' not in after
    assert not bundle_matches(accepted, v2) and bundle_matches(accepted, v1)


def test_v2_jpg_pdf_and_both_zips(tmp_path):
    facts = ProductFacts.model_validate(read_json(ROOT / 'samples/facts-rich.json'))
    job = create_job(facts, ROOT / 'samples', tmp_path, theme='bold', design_version=2)
    ingest_job(job, ANSWER)
    bundle = preview_job(job)
    pdf = make_pdf(bundle)
    manifest = read_json(bundle / 'manifest.json')
    assert manifest['pdf']['pages'] == len(manifest['pages']) and manifest['pdf']['text_check']['missing'] == 0
    with zipfile.ZipFile(io.BytesIO(build_zip(bundle))) as archive:
        names = archive.namelist()
        assert pdf.name in names and all(p['file'] in names for p in manifest['pages']) and 'assets/layout.js' in names
    result = export_bundle(bundle, 'generic', output_dir=tmp_path / 'exports')
    _, data = build_export_zip(Path(result['folder']))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert pdf.name in archive.namelist() and json.loads(archive.read('manifest.json'))['design_version'] == 2


@pytest.mark.parametrize('theme', THEME_IDS)
def test_v2_pdf_keeps_every_visible_text(tmp_path, theme):
    for facts_name, answer_name in (('facts.json', 'answer.txt'), ('facts-rich.json', 'answer-rich.txt')):
        facts = ProductFacts.model_validate(read_json(ROOT / 'samples' / facts_name))
        job = create_job(facts, ROOT / 'samples', tmp_path / facts_name, theme=theme, design_version=2)
        ingest_job(job, (ROOT / 'samples' / answer_name).read_text(encoding='utf-8'))
        bundle = preview_job(job)
        make_pdf(bundle)
        check = read_json(bundle / 'manifest.json')['pdf']['text_check']
        assert check['missing'] == 0 and check['runs'] > 10


# --- entry points ---------------------------------------------------------------------------------

def test_cli_new_jobs_are_v2_and_m1_stays_v1(tmp_path):
    made = subprocess.run([sys.executable, 'cli.py', 'prompt', '--facts', 'samples/facts-rich.json', '--images', 'samples',
                           '--output', str(tmp_path / 'jobs')], capture_output=True, text=True, cwd=ROOT)
    assert made.returncode == 0, made.stderr
    assert read_json(Path(made.stdout.strip().splitlines()[-1]) / 'manifest.json')['design_version'] == 2
    m1 = subprocess.run([sys.executable, 'cli.py', '--input', 'samples/product.json', '--images', 'samples', '--output', str(tmp_path / 'm1')],
                        capture_output=True, text=True, cwd=ROOT)
    assert read_json(Path(m1.stdout.strip().splitlines()[-1]) / 'manifest.json')['design_version'] == 1


def test_app_new_job_is_v2_and_preview_can_switch_to_v1(monkeypatch, tmp_path):
    from test_app import stage, start
    app = start(monkeypatch, tmp_path)
    app.button(key='create').click().run()
    job = Path(app.session_state['job'])
    assert read_json(job / 'manifest.json')['design_version'] == 2
    stage(app, 2)
    app.text_area(key='answer_text').set_value((ROOT / 'samples/answer.txt').read_text(encoding='utf-8'))
    app.button(key='ingest').click().run()
    stage(app, 4)
    app.radio(key='design_choice').set_value(1).run(timeout=120)
    assert not app.exception
    assert read_json(job / 'manifest.json')['design_version'] == 1
    assert read_json(Path(app.session_state['bundle']) / 'manifest.json')['design_version'] == 1
