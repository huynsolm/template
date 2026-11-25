"""M9 colours: theme default gradients (tone/duo), solid option, automatic or manual secondary colour,
contrast over the whole gradient, limited use, records, v1 unchanged."""
import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from core.editor import bundle_matches, preview_job
from core.facts import ProductFacts
from core.palette import THEME_DEFAULT_MODE, _fit, color_scheme, lowest_contrast, mix
from core.render import render
from core.themes import THEME_IDS, contrast_ratio, theme_styles
from core.workflow import create_job, ingest_job, read_json
from test_m8a import open_page
from test_m9 import rich_document

ANSWER = (ROOT / 'samples/answer-rich.txt').read_text(encoding='utf-8')


def test_theme_defaults():
    assert {t for t, m in THEME_DEFAULT_MODE.items() if m == 'tone'} == {'classic', 'minimal', 'natural', 'industrial'}
    assert {t for t, m in THEME_DEFAULT_MODE.items() if m == 'duo'} == {'bold', 'modern', 'impact'}
    assert set(THEME_DEFAULT_MODE) == set(THEME_IDS)


def test_contrast_includes_the_middle_of_the_gradient():
    stops = ['#ff0000', '#00ff00']
    ends = min(contrast_ratio('#000000', c) for c in stops)
    middle = contrast_ratio('#000000', mix(stops[0], stops[1], 0.5))
    assert middle < ends  # the middle is darker than both ends here
    assert lowest_contrast('#000000', stops) <= middle


def test_failing_text_is_adjusted_and_recorded():
    adjustments, checks = [], []
    text, stops = _fit('key-message', '#ffffff', ['#9fd4c0', '#cfe8de'], adjustments, checks)
    assert lowest_contrast(text, stops) >= 4.5 and checks[0]['lowest_contrast'] >= 4.5
    assert adjustments and adjustments[0]['stops'][0] == ['#9fd4c0', '#cfe8de']


@pytest.mark.parametrize('brand', ['#305b46', '#ffd400', '#9ad1ff', '#111111'])
@pytest.mark.parametrize('theme', THEME_IDS)
def test_every_text_area_meets_contrast_and_brand_is_kept(theme, brand):
    styles = theme_styles(theme, brand, policy='aa')
    for mode in ('solid', 'tone', 'duo'):
        record = color_scheme(theme, brand, styles['resolved_colors'], mode)['record']
        assert record['brand_original'] == brand and record['mode'] == mode
        assert all(c['lowest_contrast'] >= 4.5 for c in record['contrast_checks']), record['contrast_checks']
        for check in record['contrast_checks']:
            assert lowest_contrast(check['text'], check['stops']) >= 4.5


def test_manual_secondary_colour_is_used_and_recorded():
    styles = theme_styles('modern', '#305b46', policy='aa')
    record = color_scheme('modern', '#305b46', styles['resolved_colors'], 'duo', '#8A2BE2')['record']
    assert record['secondary_source'] == 'manual' and record['secondary']['partner'] == '#8a2be2'
    adjusted = [a for a in record['contrast_adjustments'] if a['area'] == 'key-message']
    assert (adjusted[0]['stops'][0][-1] if adjusted else record['gradients']['key-message'][-1]) == '#8a2be2'
    with pytest.raises(ValueError):
        color_scheme('modern', '#305b46', styles['resolved_colors'], 'duo', 'red')


GRADIENTS_JS = r'''() => {
  const bg = sel => { const el = document.querySelector(sel); return el ? getComputedStyle(el).backgroundImage : null; };
  return {solution: bg('.solution'), panel: bg('.hero .photo'), common: bg('.spec .common'), table: bg('.spec-table'),
          notes: bg('.notes'), notice: bg('.notice-box'), pain: bg('.pain'), features: bg('.features'), faq: bg('.faq'),
          filters: [...document.images].map(i => [getComputedStyle(i).filter, getComputedStyle(i).mixBlendMode, getComputedStyle(i).opacity])};
}'''


@pytest.mark.parametrize('theme', THEME_IDS)
def test_gradients_only_on_first_screen_and_key_message(tmp_path, theme):
    bundle = render(rich_document(), ROOT / 'samples', tmp_path, theme=theme, design_version=2)
    manifest = read_json(bundle / 'manifest.json')
    assert manifest['color_scheme']['mode'] == THEME_DEFAULT_MODE[theme]
    pw, browser, page = open_page(bundle)
    try:
        r = page.evaluate(GRADIENTS_JS)
    finally:
        browser.close(); pw.stop()
    assert 'gradient' in r['solution'] and 'gradient' in r['panel']
    for plain in ('common', 'table', 'notes', 'notice', 'pain', 'features', 'faq'):
        assert r[plain] in (None, 'none'), (plain, r[plain])
    assert all(f == ['none', 'normal', '1'] for f in r['filters'])  # photos are never recoloured


def test_solid_mode_has_no_gradient_and_v1_has_no_scheme(tmp_path):
    bundle = render(rich_document(), ROOT / 'samples', tmp_path / 'solid', theme='modern', design_version=2, color_mode='solid')
    scheme = read_json(bundle / 'manifest.json')['color_scheme']
    assert scheme['mode'] == 'solid' and len(scheme['gradients']['key-message']) == 1 and 'hero-photo-panel' not in scheme['gradients']
    pw, browser, page = open_page(bundle)
    try:
        r = page.evaluate(GRADIENTS_JS)
    finally:
        browser.close(); pw.stop()
    assert r['solution'] == 'none' and r['panel'] == 'none'
    v1 = render(rich_document(), ROOT / 'samples', tmp_path / 'v1', theme='modern')
    assert 'color_scheme' not in read_json(v1 / 'manifest.json')
    assert '--key-bg' not in (v1 / 'page.html').read_text(encoding='utf-8')


def test_colour_change_needs_a_new_preview_and_approval(tmp_path):
    facts = ProductFacts.model_validate(read_json(ROOT / 'samples/facts-rich.json'))
    job = create_job(facts, ROOT / 'samples', tmp_path, theme='modern', design_version=2)
    ingest_job(job, ANSWER)
    first = preview_job(job)
    assert bundle_matches(job, first) and 'color_mode' not in read_json(job / 'manifest.json')
    solid = preview_job(job, color_mode='solid')
    assert read_json(job / 'manifest.json')['color_mode'] == 'solid'
    assert not bundle_matches(job, first) and bundle_matches(job, solid)
    manual = preview_job(job, color_mode='duo', secondary_color='#8a2be2')
    assert read_json(manual / 'manifest.json')['color_scheme']['secondary_source'] == 'manual'
    assert not bundle_matches(job, solid) and bundle_matches(job, manual)
    back = preview_job(job, color_mode=None, secondary_color=None)
    assert {'color_mode', 'secondary_color'}.isdisjoint(read_json(job / 'manifest.json')) and bundle_matches(job, back)


def test_preview_screen_colour_choice(monkeypatch, tmp_path):
    from test_app import stage, start
    app = start(monkeypatch, tmp_path)
    app.button(key='create').click().run()
    job = Path(app.session_state['job'])
    stage(app, 2)
    app.text_area(key='answer_text').set_value((ROOT / 'samples/answer.txt').read_text(encoding='utf-8'))
    app.button(key='ingest').click().run()
    stage(app, 4)
    app.radio(key='color_choice').set_value('solid').run(timeout=120)
    assert not app.exception and read_json(job / 'manifest.json')['color_mode'] == 'solid'
    app.checkbox(key='secondary_manual').check().run()
    app.color_picker(key='secondary_pick').set_value('#8a2be2').run(timeout=120)
    app.radio(key='color_choice').set_value('duo').run(timeout=120)
    manifest = read_json(job / 'manifest.json')
    assert manifest['color_mode'] == 'duo' and manifest['secondary_color'] == '#8a2be2'
    assert any('색 방식' in c.value for c in app.caption)
