"""M6 input, offline rendering, and preview regressions."""
import json
import mimetypes
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlparse

from playwright.sync_api import sync_playwright
from pydantic import ValidationError
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.assemble import assemble
from core.copy_schema import CopyDraft
from core.editor import bundle_matches
from core.facts import ProductFacts
from core.ingest import extract_json
from core.render import chromium_path, render
from core.themes import THEME_IDS, contrast_ratio
from core.workflow import accept_job, create_job, ingest_job, read_json


@pytest.fixture
def rich():
    return read_json(ROOT/'samples/facts-rich.json')


def assembled(sample):
    facts = ProductFacts.model_validate_json((ROOT/f'samples/facts{sample}.json').read_text())
    answer = (ROOT/f'samples/answer{sample}.txt').read_text()
    return assemble(facts, CopyDraft.model_validate(extract_json(answer)))[0]


@pytest.mark.parametrize('case', ['ok','http','protocol-relative','parent','absolute','missing','no-license'])
def test_font_registry(tmp_path, monkeypatch, case):
    from core import fonts

    folder = tmp_path/'font'
    folder.mkdir()
    filename = {'http':'https://example.org/a.woff2','protocol-relative':'//host/a.woff2',
                'parent':'../a.woff2','absolute':'/a.woff2','missing':'missing.woff2'}.get(case, './a.woff2')
    (folder/'fonts.css').write_text(f'@font-face {{ font-family: "Example"; src: url("{filename}"); }}')
    (folder/'a.woff2').write_bytes(b'test')
    if case != 'no-license':
        (folder/'LICENSE.txt').write_text('test fixture')
    monkeypatch.setattr(fonts, 'FONT_ROOT', tmp_path)
    if case == 'ok':
        assert fonts.load_font('font').family == 'Example'
    else:
        with pytest.raises(ValueError):
            fonts.load_font('font')


@pytest.mark.parametrize(('field','case','location'), [
    ('highlights','too_many',('highlights',)),
    ('highlights','unknown_fact',('highlights',)),
    ('spec_table','row_width',('spec_table','rows')),
    ('spec_table','too_wide',('spec_table','columns')),
    ('images','too_many',('images',)),
])
def test_rich_input_errors(rich, field, case, location):
    if case == 'row_width':
        rich[field]['rows'][0].pop()
    elif case == 'too_wide':
        rich[field]['columns'] = ['열'] * 9
    elif case == 'unknown_fact':
        rich[field][0]['fact_id'] = 'missing'
    elif field == 'images':
        rich[field] = [{'path':f'photo-{i}.png','role':'feature'} for i in range(11)]
    else:
        rich[field] = rich[field] * 3
    with pytest.raises(ValidationError) as error:
        ProductFacts.model_validate(rich)
    assert location in [entry['loc'] for entry in error.value.errors()]


def test_repeated_image_roles_and_long_alt(rich):
    description = '길게 작성한 이미지 설명 ' * 40
    detail = next(image for image in rich['images'] if image['role'] == 'detail')
    detail['alt'] = description
    rich['images'].extend([detail] * 11)
    facts = ProductFacts.model_validate(rich)
    copy = CopyDraft.model_validate(extract_json((ROOT/'samples/answer-rich.txt').read_text()))
    document, _ = assemble(facts, copy)
    gallery = next(section for section in document.sections if section.type == 'gallery')
    assert [photo.alt for photo in gallery.items] == [description]


NEW_THEMES = THEME_IDS[3:]


@pytest.mark.parametrize('theme', NEW_THEMES)
@pytest.mark.parametrize('brand', ['#ffff00','#10211b','#777777'])
def test_rich_render_and_dom_contrast(tmp_path, theme, brand):
    document = assembled('-rich')
    assert document.schema_version == '1.1'
    assert [s.type for s in document.sections] == [
        'hero','stats','pain','solution','image','features','structure','targets','gallery','how_to','spec','faq','notice']
    bundle = render(document, ROOT/'samples', tmp_path, theme=theme, brand_color=brand)
    manifest = read_json(bundle/'manifest.json')
    expected = {'pretendard'}
    expected.update({'natural': {'gowun-batang'}, 'impact': {'black-han-sans'}}.get(theme, set()))
    assert {font['id'] for font in manifest['fonts']} == expected
    assert {path.name for path in (bundle/'assets/fonts').iterdir()} == expected
    assert all((bundle/'assets/fonts'/font/'LICENSE.txt').is_file() for font in expected)
    assert manifest['font_loaded'] and not manifest['network_requests']
    assert manifest['width'] == 860 and not manifest['horizontal_overflow']
    assert manifest['brand_color'] == brand
    tops = {section['top'] for section in manifest['sections']}
    assert len(manifest['pages']) > 1
    assert all(part['top'] in tops and part['width'] == 860 for part in manifest['pages'])

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=chromium_path(pw.chromium.executable_path))
        try:
            page = browser.new_page(viewport={'width':860,'height':1000}, offline=True)

            def local(route):
                url = urlparse(route.request.url)
                path = (bundle/unquote(url.path).lstrip('/')).resolve()
                assert url.netloc == '127.0.0.1:18600' and path.is_relative_to(bundle) and path.is_file()
                route.fulfill(body=path.read_bytes(), content_type=mimetypes.guess_type(path.name)[0] or 'application/octet-stream')

            page.route('**/*', local)
            page.goto('http://127.0.0.1:18600/page.html')
            families = page.evaluate("async () => {await document.fonts.ready; return [...document.fonts].filter(f=>f.status==='loaded').map(f=>f.family)}")
            assert {font['family'] for font in manifest['fonts']} <= set(families)
            pairs = page.evaluate('''() => {
                const walker = document.createTreeWalker(document.querySelector('main'), NodeFilter.SHOW_TEXT);
                const pairs = [];
                while (walker.nextNode()) {
                    if (!walker.currentNode.textContent.trim()) continue;
                    const element = walker.currentNode.parentElement;
                    const {color, fontSize} = getComputedStyle(element);
                    for (let ancestor = element; ancestor; ancestor = ancestor.parentElement) {
                        const bg = getComputedStyle(ancestor).backgroundColor;
                        if (bg !== 'rgba(0, 0, 0, 0)') {
                            pairs.push([color,bg,/^H[1-3]$/.test(element.tagName) && parseFloat(fontSize) >= 24 ? 3 : 4.5]);
                            break;
                        }
                    }
                }
                return pairs;
            }''')

            def hex_color(css):
                return '#' + ''.join(f'{int(channel):02x}' for channel in re.findall(r'\d+',css)[:3])

            visible = page.evaluate('''() => {
                const image = document.querySelector('.hero img').getBoundingClientRect();
                const copy = document.querySelector('.hero-copy').getBoundingClientRect();
                const overlap = Math.max(0, Math.min(image.right,copy.right)-Math.max(image.left,copy.left))
                    * Math.max(0, Math.min(image.bottom,copy.bottom)-Math.max(image.top,copy.top));
                return 1-overlap/(image.width*image.height);
            }''')
            assert visible >= .7
            assert page.locator('.section-label').all_text_contents() == ['CHECK','SOLUTION','POINT','STRUCTURE','WHERE','SPEC','FAQ']
            for count in (1,2,3,4):
                widths = page.evaluate('''count => {
                    const grid = document.querySelector('.photo-grid');
                    const original = grid.firstElementChild.cloneNode(true);
                    grid.replaceChildren(...Array.from({length:count},()=>original.cloneNode(true)));
                    return [grid.clientWidth, ...[...grid.children].map(e=>e.getBoundingClientRect().width)];
                }''', count)
                expected = widths[0] if count == 1 else (widths[0]-16)/2
                assert all(abs(width-expected)<1 for width in widths[1:])
            assert pairs
            for foreground, background, minimum in pairs:
                assert contrast_ratio(hex_color(foreground), hex_color(background)) >= minimum, (theme,brand,foreground,background)
            assert hex_color(page.locator('.stats').evaluate('(e)=>getComputedStyle(e).backgroundColor')) == brand
            assert hex_color(page.locator('.point').first.evaluate('(e)=>getComputedStyle(e).borderTopColor')) == (brand if theme != 'impact' else manifest['resolved_colors']['text'])
            assert hex_color(page.locator('.target-list li').first.evaluate('(e)=>getComputedStyle(e).borderTopColor')) == brand
        finally:
            browser.close()


@pytest.mark.parametrize('theme', NEW_THEMES)
def test_old_facts_and_schema_render_in_new_themes(tmp_path, theme):
    document = assembled('')
    assert document.schema_version == '1.0'
    assert {'stats','targets','structure','image','gallery'}.isdisjoint(s.type for s in document.sections)
    bundle = render(document, ROOT/'samples', tmp_path, theme=theme)
    assert read_json(bundle/'manifest.json')['font_loaded']


def test_gallery_brand_approval_and_resume(tmp_path, monkeypatch):
    monkeypatch.setenv('DETAIL_PAGE_OUTPUTS', str(tmp_path))
    facts = ProductFacts.model_validate_json((ROOT/'samples/facts-rich.json').read_text())
    job = create_job(facts, ROOT/'samples', tmp_path)
    assert read_json(job/'manifest.json')['theme'] == 'modern'
    ingest_job(job, (ROOT/'samples/answer-rich.txt').read_text())
    accepted = accept_job(job)
    original_facts = (accepted/'facts.json').read_bytes()
    previous_meta = read_json(accepted/'manifest.json')
    previous_bundle = accepted/previous_meta['rendered_job']
    app = AppTest.from_file(str(ROOT/'app/main.py'),default_timeout=180).run()
    app.selectbox(key='resume_job').set_value(str(accepted))
    app.button(key='resume').click().run()
    assert app.session_state['job'] == str(accepted)
    app.sidebar.radio[0].set_value('⑤ 미리보기').run()
    app.toggle(key='show_gallery').set_value(True).run()
    assert not app.exception and not app.error
    assert len(list((accepted/'gallery').glob('*.png'))) == len(THEME_IDS)
    app.button(key='gallery_natural').click().run()
    natural = Path(app.session_state['bundle'])
    assert natural != previous_bundle and previous_bundle.is_dir()
    assert read_json(natural/'manifest.json')['theme'] == 'natural'
    assert read_json(accepted/'manifest.json')['review_accepted'] is False
    assert not bundle_matches(accepted, previous_bundle)
    approved_natural = accept_job(accepted)
    approved_natural_bundle = approved_natural/read_json(approved_natural/'manifest.json')['rendered_job']
    app.toggle(key='show_gallery').set_value(False).run()
    app.selectbox(key='resume_job').set_value(str(approved_natural)).run()
    app.button(key='resume').click().run()
    app.sidebar.radio[0].set_value('⑤ 미리보기').run()
    app.color_picker(key='preview_brand').set_value('#336699').run()
    changed = Path(app.session_state['bundle'])
    assert changed != approved_natural_bundle and approved_natural_bundle.is_dir()
    assert read_json(changed/'manifest.json')['brand_color'] == '#336699'
    assert read_json(approved_natural/'manifest.json')['review_accepted'] is False
    assert not bundle_matches(approved_natural, approved_natural_bundle)
    assert (approved_natural/'facts.json').read_bytes() == original_facts
    restarted = AppTest.from_file(str(ROOT/'app/main.py'),default_timeout=180).run()
    restarted.selectbox(key='resume_job').set_value(str(approved_natural))
    restarted.button(key='resume').click().run()
    restarted.sidebar.radio[0].set_value('⑤ 미리보기').run()
    assert not restarted.exception
    assert restarted.selectbox(key='theme_choice').value == 'natural'
    assert restarted.color_picker(key='preview_brand').value == '#336699'
