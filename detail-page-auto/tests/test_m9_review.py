"""Regression tests for the M9 review findings (M9_REVIEW.md I-1~I-6)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from core.editor import preview_job
from core.facts import ProductFacts
from core.palette import lowest_contrast
from core.render import render
from core.schema import Document
from core.themes import THEME_IDS
from core.workflow import accept_job, create_job, ingest_job, overflow_regenerate_job, read_json, regenerate_job
from test_m8a import open_page
from test_m9 import rich_document

ANSWER = (ROOT / 'samples/answer-rich.txt').read_text(encoding='utf-8')

# Text inside each gradient area, as drawn; checked against the gradient the manifest records.
AREA_TEXT_JS = r'''areas => {
  const hex = c => { const m = c.match(/\d+(\.\d+)?/g).map(Number); return '#' + m.slice(0, 3).map(v => Math.round(v).toString(16).padStart(2, '0')).join(''); };
  const out = [];
  for (const [area, selector] of Object.entries(areas)) {
    const root = document.querySelector(selector);
    if (!root) continue;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (!node.textContent.trim()) continue;
      const style = getComputedStyle(node.parentElement);
      out.push([area, hex(style.color), node.textContent.trim().slice(0, 16)]);
    }
  }
  return out;
}'''
AREAS = {'key-message': '.solution', 'hero-copy': '.theme-bold .hero .copy, .theme-impact .hero .copy', 'key-specs': '.theme-bold .stats'}


# I-1: every text drawn on a gradient meets the contrast the manifest records

@pytest.mark.parametrize('brand', ['#6e6e6e', '#305b46', '#ffd400'])
@pytest.mark.parametrize('theme', THEME_IDS)
def test_all_text_on_gradients_meets_contrast(tmp_path, theme, brand):
    def change(facts):
        facts['product']['brand_color'] = brand
        facts['product']['category'] = '산업용 가상 구성 부품 안내 및 설치 사양'
    bundle = render(rich_document(change), ROOT / 'samples', tmp_path, theme=theme, design_version=2)
    gradients = read_json(bundle / 'manifest.json')['color_scheme']['gradients']
    pw, browser, page = open_page(bundle)
    try:
        drawn = page.evaluate(AREA_TEXT_JS, AREAS)
    finally:
        browser.close(); pw.stop()
    checked = [(area, color, text, lowest_contrast(color, gradients[area])) for area, color, text in drawn if area in gradients]
    assert checked
    assert all(ratio >= 4.5 for *_, ratio in checked), [c for c in checked if c[3] < 4.5]


# I-2: regenerating copy keeps the chosen colour settings

def test_regeneration_keeps_colour_settings(tmp_path):
    facts = ProductFacts.model_validate(read_json(ROOT / 'samples/facts-rich.json'))
    job = create_job(facts, ROOT / 'samples', tmp_path, theme='modern', design_version=2)
    ingest_job(job, ANSWER)
    preview_job(job, color_mode='solid', secondary_color='#8a2be2')
    child = regenerate_job(job)
    manifest = read_json(child / 'manifest.json')
    assert (manifest['design_version'], manifest['color_mode'], manifest['secondary_color']) == (2, 'solid', '#8a2be2')
    ingest_job(child, ANSWER)
    scheme = read_json(preview_job(child) / 'manifest.json')['color_scheme']
    assert scheme['mode'] == 'solid' and scheme['secondary_source'] == 'manual'


def test_overflow_rewrite_keeps_colour_settings(tmp_path):
    facts = ProductFacts.model_validate(read_json(ROOT / 'samples/facts-rich.json'))
    job = create_job(facts, ROOT / 'samples', tmp_path, theme='modern', design_version=2)
    ingest_job(job, (ROOT / 'samples/answer-rich-long.txt').read_text(encoding='utf-8'), render_output=True)
    preview_job(job, color_mode='tone')
    child = overflow_regenerate_job(job)
    assert read_json(child / 'manifest.json')['color_mode'] == 'tone'


# I-3: v2 classic is aa at every step, with no legacy warning

def test_v2_classic_is_aa_at_every_step(tmp_path):
    data = read_json(ROOT / 'samples/facts-rich.json')
    data['product']['brand_color'] = '#FFFF00'
    job = create_job(ProductFacts.model_validate(data), ROOT / 'samples', tmp_path, theme='classic', design_version=2)
    assert read_json(job / 'manifest.json')['contrast_policy'] == 'aa'
    ingest_job(job, ANSWER, render_output=True)
    assert read_json(job / 'manifest.json')['contrast_policy'] == 'aa'
    preview_job(job)
    accepted = accept_job(job)
    assert read_json(accepted / 'manifest.json')['contrast_policy'] == 'aa'
    assert not any(r.get('code') == 'BRAND_COLOR_LOW_CONTRAST' for r in read_json(accepted / 'review.json'))


def test_v1_classic_still_warns_for_low_contrast(tmp_path):
    data = read_json(ROOT / 'samples/facts-rich.json')
    data['product']['brand_color'] = '#FFFF00'
    job = create_job(ProductFacts.model_validate(data), ROOT / 'samples', tmp_path, theme='classic')
    ingest_job(job, ANSWER)
    accepted = accept_job(job)
    assert read_json(accepted / 'manifest.json')['contrast_policy'] == 'legacy'
    assert any(r.get('code') == 'BRAND_COLOR_LOW_CONTRAST' for r in read_json(accepted / 'review.json'))


# I-4: the parenthetical note of a key spec is measured against its own value

def test_stats_note_lines_are_measured(tmp_path):
    def long_note(facts): facts['highlights'][0]['value'] = '35W (' + '가상 설명 ' * 10 + ')'
    bundle = render(rich_document(long_note), ROOT / 'samples', tmp_path, theme='minimal', design_version=2)
    manifest = read_json(bundle / 'manifest.json')
    note = [m for m in manifest['copy_metrics'] if m['field_path'] == 'items.0.value' and m['role'] == 'note']
    assert note and note[0]['lines'] >= 2 and note[0]['over']
    flagged = [r for r in manifest['copy_reviews'] if r['section_id'] == 'stats-1' and r['field_path'] == 'items.0.value']
    assert flagged and flagged[0]['detail']['source'] == 'seller'


def test_short_stats_note_is_fine(tmp_path):
    def short_note(facts): facts['highlights'][0]['value'] = '35W ~ 120W (풍량 3단 조절 가능)'
    bundle = render(rich_document(short_note), ROOT / 'samples', tmp_path, theme='minimal', design_version=2)
    manifest = read_json(bundle / 'manifest.json')
    assert [m['lines'] for m in manifest['copy_metrics'] if m['role'] == 'note'] == [1]
    assert manifest['copy_reviews'] == []


# I-5: a v2 bundle's input.json renders again

def test_v2_bundle_input_json_renders_again(tmp_path):
    bundle = render(rich_document(), ROOT / 'samples', tmp_path / 'first', theme='industrial', design_version=2)
    data = read_json(bundle / 'input.json')
    assert all('split' not in s for s in data['sections'])
    Document.model_validate(data)
    again = subprocess.run([sys.executable, 'cli.py', '--input', str(bundle / 'input.json'), '--images', str(bundle),
                            '--output', str(tmp_path / 'again'), '--design-version', '2'], capture_output=True, text=True, cwd=ROOT)
    assert again.returncode == 0, again.stderr


# I-6: targets items and groups must say the same thing

def test_targets_items_must_match_groups():
    base = {'schema_version': '1.1', 'product': {'name': 'a', 'category': 'b', 'brand_color': '#305b46'},
            'sections': [{'id': 'hero', 'type': 'hero', 'headline': 'x', 'image': 'product.png'}]}
    bad = dict(base, sections=base['sections'] + [{'id': 't', 'type': 'targets', 'items': ['기존 입력 대상'],
                                                   'groups': [{'name': '업종', 'items': ['새 업종']}]}])
    with pytest.raises(ValidationError, match='추천 대상'):
        Document.model_validate(bad)
    good = dict(base, sections=base['sections'] + [{'id': 't', 'type': 'targets', 'items': ['새 업종', '기존 입력 대상'],
                                                    'groups': [{'name': '업종', 'items': ['새 업종']}, {'name': '대상', 'items': ['기존 입력 대상']}]}])
    Document.model_validate(good)


# R-I-1 (M9_REVIEW_2.md): renders made under older rules are kept but never reused as current

def _as_older_render(bundle: Path):
    """What a render from before the fix looks like: no render revision, older measure/colour revisions."""
    manifest = read_json(bundle / 'manifest.json')
    manifest.pop('render_revision', None)
    manifest['copy_measure_version'] = 'm8a-2'
    manifest['color_scheme']['version'] = 'palette-1'
    (bundle / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')


def test_older_v2_renders_are_not_reused_by_app_download_or_batch(tmp_path):
    from core.batch import _accepted_for, _approval_is_current
    from core.editor import bundle_matches, resume_bundle
    from core.export import current_bundle
    facts = ProductFacts.model_validate(read_json(ROOT / 'samples/facts-rich.json'))
    job = create_job(facts, ROOT / 'samples', tmp_path, theme='impact', design_version=2)
    ingest_job(job, ANSWER)
    preview_job(job)
    accepted = accept_job(job)
    old_approval = accepted / read_json(accepted / 'manifest.json')['rendered_job']
    assert resume_bundle(accepted) == old_approval and _approval_is_current(job, accepted, read_json(accepted / 'manifest.json'))
    _as_older_render(old_approval)
    assert not bundle_matches(accepted, old_approval) and resume_bundle(accepted) is None
    with pytest.raises(ValueError):
        current_bundle(accepted)
    assert not _approval_is_current(job, accepted, read_json(accepted / 'manifest.json')) and _accepted_for(job) is None
    fresh = preview_job(accepted)
    assert resume_bundle(accepted) == fresh and current_bundle(accepted) == fresh
    assert read_json(accepted / 'manifest.json')['review_accepted'] is False
    assert old_approval.is_dir()  # the older result is kept, not deleted


def test_v1_renders_are_unaffected_by_the_v2_revision(tmp_path):
    from core.editor import bundle_matches
    facts = ProductFacts.model_validate(read_json(ROOT / 'samples/facts-rich.json'))
    job = create_job(facts, ROOT / 'samples', tmp_path, theme='classic')
    ingest_job(job, ANSWER)
    bundle = preview_job(job)
    assert 'render_revision' not in read_json(bundle / 'manifest.json') and bundle_matches(job, bundle)


# R3-M-1 (M9_REVIEW_3.md): gallery thumbnails follow the v2 render revision; v1 keys are unchanged

def test_gallery_thumbnail_follows_the_v2_render_revision(tmp_path, monkeypatch):
    import core.render
    from core.editor import gallery_thumbnail
    facts = ProductFacts.model_validate(read_json(ROOT / 'samples/facts-rich.json'))
    v2 = create_job(facts, ROOT / 'samples', tmp_path / 'v2', theme='impact', design_version=2)
    ingest_job(v2, ANSWER)
    first = gallery_thumbnail(v2, 'impact')
    assert gallery_thumbnail(v2, 'impact') == first  # cached
    monkeypatch.setattr(core.render, 'V2_RENDER_REVISION', 'v2-next')
    second = gallery_thumbnail(v2, 'impact')
    assert second != first and first.is_file() and second.is_file()
    v1 = create_job(facts, ROOT / 'samples', tmp_path / 'v1', theme='classic')
    ingest_job(v1, ANSWER)
    before = gallery_thumbnail(v1, 'classic')
    monkeypatch.setattr(core.render, 'V2_RENDER_REVISION', 'v2-other')
    assert gallery_thumbnail(v1, 'classic') == before
