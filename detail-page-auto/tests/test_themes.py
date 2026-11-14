"""M5-A: shared structures, accessible colors and immutable themed versions."""
import io
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from PIL import ImageChops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.mark.parametrize('brand', ['#FFFF00', '#000000', '#777777', '#305b46', '#FFFFFF'])
@pytest.mark.parametrize('theme', ['classic', 'minimal', 'bold'])
def test_color_pairs_meet_aa(brand, theme):
    from core.themes import theme_styles, contrast_ratio
    styles = theme_styles(theme, brand)
    for pair in styles['contrast_pairs']:
        assert contrast_ratio(pair['foreground'], pair['background']) >= pair['minimum']
    assert styles['contrast_reviews'] == []
    for item in styles['contrast_adjustments']:
        assert item['original'] != item['adjusted']
        assert item['contrast_ratio'] >= item['minimum']
        assert item['original_contrast_ratio'] < item['minimum']


def test_classic_sample_has_no_adjustments():
    from core.themes import theme_styles
    assert theme_styles('classic', '#305b46')['contrast_adjustments'] == []


@pytest.mark.parametrize('theme', ['../classic', 'unknown', '', '/classic'])
def test_unknown_theme_rejected(theme):
    from core.themes import load_theme
    with pytest.raises(ValueError): load_theme(theme)


@pytest.mark.parametrize('css', [
    '@IMPORT "evil.css";', 'a{background:url(https://example.com/a)}',
    'a{background:url(//example.com/a)}', 'a{background:url(data:text/plain,evil)}',
    'a{background:u\\72l(https://example.com/a)}', 'a{background:u/**/rl(https://example.com/a)}',
    'a{background:url(../outside.png)}',
])
def test_forbidden_css_rejected(css):
    from core.themes import validate_css
    with pytest.raises(ValueError): validate_css(css)


def test_missing_token_rejected(tmp_path, monkeypatch):
    import core.themes as themes
    shutil.copytree(ROOT/'themes', tmp_path/'themes')
    path=tmp_path/'themes/minimal/theme.toml'
    path.write_text(path.read_text().replace('radius = 0', 'unused = 0'))
    monkeypatch.setattr(themes, 'THEMES_ROOT', tmp_path/'themes')
    with pytest.raises(ValueError): themes.load_theme('minimal')


@pytest.mark.parametrize('theme', ['classic', 'minimal', 'bold'])
def test_themes_render_offline(tmp_path, theme):
    from core.render import render
    from core.schema import Document
    doc=Document.model_validate_json((ROOT/'samples/product.json').read_text())
    out=render(doc, ROOT/'samples', tmp_path, png=True, theme=theme)
    manifest=json.loads((out/'manifest.json').read_text())
    assert manifest['theme'] == theme
    assert manifest['width'] == 860
    assert manifest['font_loaded'] and not manifest['horizontal_overflow']
    assert manifest['network_requests'] == []
    assert manifest['contrast_reviews'] == []


@pytest.mark.parametrize('brand', ['#305b46', '#234567'])
def test_classic_pixel_identical_to_original(tmp_path, monkeypatch, brand):
    from core.render import render, capture
    from core.schema import Document
    data=json.loads((ROOT/'samples/product.json').read_text())
    data['product']['brand_color']=brand
    doc=Document.model_validate(data)
    out=render(doc, ROOT/'samples', tmp_path, png=True)
    themed,_=capture(out/'page.html')
    # Keep the legacy stylesheet as an independent committed test fixture.
    (out/'assets/theme.css').write_bytes((ROOT/'tests/fixtures/classic-original.css').read_bytes())
    (out/'page.html').write_text((out/'page.html').read_text().replace('style="', 'style="--brand: '+brand+'; ', 1))
    original,_=capture(out/'page.html')
    assert themed.size == original.size
    assert ImageChops.difference(themed, original).getbbox() is None
    assert json.loads((out/'manifest.json').read_text())['contrast_adjustments'] == []


def make_job(tmp_path, brand='#FFFF00'):
    from core.facts import ProductFacts
    from core.workflow import create_job, ingest_job
    data=json.loads((ROOT/'samples/facts.json').read_text())
    data['product']['brand_color']=brand
    job=create_job(ProductFacts.model_validate(data), ROOT/'samples', tmp_path)
    ingest_job(job, (ROOT/'samples/answer.txt').read_text())
    return job


def test_theme_snapshots_zip_and_accept_preserve_history(tmp_path):
    from core.editor import preview_job, build_zip
    from core.workflow import accept_job, read_json, regenerate_job
    job=make_job(tmp_path)
    first=preview_job(job)
    before={str(p.relative_to(first)):p.read_bytes() for p in first.rglob('*') if p.is_file()}
    second=preview_job(job, theme='bold')
    assert second != first
    assert all((first/name).read_bytes()==content for name,content in before.items())
    assert read_json(job/'manifest.json')['theme']=='bold'
    for bundle,theme in [(first,'classic'),(second,'bold')]:
        with zipfile.ZipFile(io.BytesIO(build_zip(bundle))) as z:
            manifest=json.loads(z.read('manifest.json'))
            assert manifest['theme']==theme
            assert manifest['contrast_adjustments']
            assert all('대비' not in r['reason'] for r in json.loads(z.read('review.json')))
    accepted=accept_job(job)
    meta=read_json(accepted/'manifest.json')
    assert meta['theme']=='bold'
    assert read_json(accepted/meta['rendered_job']/'manifest.json')['theme']=='bold'
    assert meta['contrast_adjustments']
    assert read_json(regenerate_job(job)/'manifest.json')['theme']=='bold'


@pytest.mark.parametrize('command', ['ingest', 'accept', 'generate'])
def test_cli_theme_option(command):
    result=subprocess.run([sys.executable, str(ROOT/'cli.py'), command, '--help'],capture_output=True,text=True)
    assert result.returncode==0
    assert '--theme {classic,minimal,bold}' in result.stdout


def test_m1_cli_theme(tmp_path):
    result=subprocess.run([sys.executable,str(ROOT/'cli.py'),'--input',str(ROOT/'samples/product.json'),
                           '--images',str(ROOT/'samples'),'--output',str(tmp_path),'--theme','minimal'],capture_output=True,text=True)
    assert result.returncode==0, result.stderr
    assert json.loads((Path(result.stdout.strip())/'manifest.json').read_text())['theme']=='minimal'


def test_workflow_theme_inheritance_and_old_jobs(tmp_path):
    from core.facts import ProductFacts
    from core.workflow import create_job, ingest_job, generate_job, read_json, write_json
    facts=ProductFacts.model_validate_json((ROOT/'samples/facts.json').read_text())
    answer=(ROOT/'samples/answer.txt').read_text()
    class FakeProvider:
        name='fake'
        def generate(self,prompt): return answer
    job=generate_job(facts,ROOT/'samples',tmp_path,FakeProvider(),theme='minimal')
    assert read_json(job/'manifest.json')['theme']=='minimal'
    job=create_job(facts,ROOT/'samples',tmp_path,theme='bold')
    ingest_job(job,answer)
    assert read_json(job/'manifest.json')['theme']=='bold'
    old=create_job(facts,ROOT/'samples',tmp_path)
    manifest=read_json(old/'manifest.json');manifest.pop('theme');write_json(old/'manifest.json',manifest)
    ingest_job(old,answer)
    from core.editor import preview_job
    assert read_json(preview_job(old)/'manifest.json')['theme']=='classic'


def test_invalid_theme_does_not_consume_attempt(tmp_path):
    from core.workflow import ingest_job, create_job, read_json
    from core.facts import ProductFacts
    facts=ProductFacts.model_validate_json((ROOT/'samples/facts.json').read_text())
    job=create_job(facts,ROOT/'samples',tmp_path)
    with pytest.raises(ValueError,match='theme'):
        ingest_job(job,(ROOT/'samples/answer.txt').read_text(),theme='../bad')
    assert read_json(job/'manifest.json')['attempts']==0


def test_impossible_token_pair_is_reviewed(tmp_path,monkeypatch):
    import core.themes as themes
    from core.render import render
    from core.schema import Document
    shutil.copytree(ROOT/'themes',tmp_path/'themes')
    path=tmp_path/'themes/classic/theme.toml'
    path.write_text(path.read_text().replace('alternate = "#f1f6f1"','alternate = "#000000"'))
    monkeypatch.setattr(themes,'THEMES_ROOT',tmp_path/'themes')
    document=Document.model_validate_json((ROOT/'samples/product.json').read_text())
    bundle=render(document,ROOT/'samples',tmp_path/'rendered')
    manifest=json.loads((bundle/'manifest.json').read_text())
    assert manifest['contrast_reviews']
    assert manifest['needs_review'] is True
    assert all('.DRAFT.' in p['file'] for p in manifest['pages'])


def test_switch_from_impossible_theme_clears_render_review_flag(tmp_path,monkeypatch):
    import core.themes as themes
    from core.workflow import read_json
    from core.editor import preview_job
    job=make_job(tmp_path,'#305b46')
    shutil.copytree(ROOT/'themes',tmp_path/'themes')
    path=tmp_path/'themes/classic/theme.toml'
    path.write_text(path.read_text().replace('alternate = "#f1f6f1"','alternate = "#000000"'))
    monkeypatch.setattr(themes,'THEMES_ROOT',tmp_path/'themes')
    bad=preview_job(job)
    assert read_json(bad/'manifest.json')['needs_review']
    good=preview_job(job,theme='minimal')
    assert read_json(good/'review.json') == []
    assert read_json(good/'manifest.json')['needs_review'] is False


@pytest.mark.parametrize('theme',['classic','minimal','bold'])
@pytest.mark.parametrize('brand',['#FFFF00','#000000','#777777'])
def test_browser_text_contrast(tmp_path,theme,brand):
    """Check computed CSS, not the palette function's own list of color pairs."""
    import re
    from urllib.parse import urlparse,unquote
    from playwright.sync_api import sync_playwright
    from core.render import render,chromium_path
    from core.schema import Document
    from core.themes import contrast_ratio
    data=json.loads((ROOT/'samples/product.json').read_text())
    data['product']['brand_color']=brand
    bundle=render(Document.model_validate(data),ROOT/'samples',tmp_path,theme=theme)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=chromium_path(pw.chromium.executable_path))
        try:
            page=browser.new_page(viewport={'width':860,'height':1000},offline=True)
            def local(route):
                parsed=urlparse(route.request.url)
                path=(bundle/unquote(parsed.path).lstrip('/')).resolve()
                assert parsed.netloc=='127.0.0.1:18600' and path.is_relative_to(bundle) and path.is_file()
                import mimetypes
                route.fulfill(body=path.read_bytes(),content_type=mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
            page.route('**/*',local)
            page.goto('http://127.0.0.1:18600/page.html')
            page.evaluate('document.fonts.ready')
            pairs=page.evaluate('''() => {
                const nodes=document.createTreeWalker(document.querySelector('main'),NodeFilter.SHOW_TEXT);
                const result=[];
                while(nodes.nextNode()) {
                    const node=nodes.currentNode;
                    if(!node.textContent.trim()) continue;
                    const element=node.parentElement, style=getComputedStyle(element);
                    let ancestor=element, background='rgb(255, 255, 255)';
                    while(ancestor) {
                        const value=getComputedStyle(ancestor).backgroundColor;
                        if(value!=='rgba(0, 0, 0, 0)' && value!=='transparent') {background=value;break;}
                        ancestor=ancestor.parentElement;
                    }
                    const size=parseFloat(style.fontSize), bold=parseInt(style.fontWeight)>=700;
                    result.push({tag:element.tagName,foreground:style.color,background,
                        minimum:(size>=24 || (bold && size>=18.667))?3:4.5});
                }
                return result;
            }''')
            assert pairs
            def hex_color(value):
                channels=[int(n) for n in re.findall(r'\d+',value)[:3]]
                return '#'+''.join(f'{n:02x}' for n in channels)
            for pair in pairs:
                ratio=contrast_ratio(hex_color(pair['foreground']),hex_color(pair['background']))
                assert ratio>=pair['minimum'], (theme,brand,pair,ratio)
        finally:
            browser.close()
