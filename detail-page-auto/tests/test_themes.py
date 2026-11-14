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
@pytest.mark.parametrize('theme', ['minimal', 'bold'])
def test_color_pairs_meet_aa(brand, theme):
    from core.themes import theme_styles, contrast_ratio
    styles = theme_styles(theme, brand)
    assert styles['contrast_policy']=='aa'
    assert styles['resolved_colors']['brand-original']==brand
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


@pytest.mark.parametrize('brand', ['#305b46', '#234567', '#c7b195', '#FFFF00'])
def test_classic_pixel_identical_to_original(tmp_path, monkeypatch, brand):
    from core.render import render, capture
    from core.schema import Document
    data=json.loads((ROOT/'samples/product.json').read_text())
    data['product']['brand_color']=brand
    doc=Document.model_validate(data)
    out=render(doc, ROOT/'samples', tmp_path, png=True)
    themed,_=capture(out/'page.html')
    from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
    env=Environment(loader=FileSystemLoader(ROOT/'templates'),autoescape=select_autoescape(['html']),undefined=StrictUndefined)
    original_html=env.from_string((ROOT/'tests/fixtures/classic-original.html').read_text()).render(
        **json.loads((out/'input.json').read_text()))
    assert (out/'page.html').read_text()==original_html
    assert (out/'assets/theme.css').read_bytes()==(ROOT/'tests/fixtures/classic-original.css').read_bytes()
    (out/'page.html').write_text(original_html)
    (out/'assets/theme.css').write_bytes((ROOT/'tests/fixtures/classic-original.css').read_bytes())
    original,_=capture(out/'page.html')
    assert themed.size == original.size
    assert ImageChops.difference(themed, original).getbbox() is None
    manifest=json.loads((out/'manifest.json').read_text())
    assert manifest['contrast_adjustments'] == []
    assert manifest['contrast_policy']=='legacy'
    assert manifest['resolved_colors']['brand-text']==brand
    low=brand in ('#c7b195','#FFFF00')
    assert bool(manifest['contrast_reviews'])==low
    reviews=json.loads((out/'review.json').read_text())
    assert bool(reviews)==low
    if low:
        assert reviews[0]['code']=='BRAND_COLOR_LOW_CONTRAST'
        assert manifest['contrast_reviews']==reviews


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
            assert manifest['contrast_policy']==('legacy' if theme=='classic' else 'aa')
            assert bool(manifest['contrast_adjustments'])==(theme!='classic')
            assert manifest['resolved_colors']['brand-original']=='#FFFF00'
            reviews=json.loads(z.read('review.json'))
            assert any(r.get('code')=='BRAND_COLOR_LOW_CONTRAST' for r in reviews)==(theme=='classic')
    accepted=accept_job(job)
    meta=read_json(accepted/'manifest.json')
    assert meta['theme']=='bold'
    assert read_json(accepted/meta['rendered_job']/'manifest.json')['theme']=='bold'
    assert meta['contrast_adjustments']
    assert meta['contrast_policy']=='aa'
    assert meta['resolved_colors']==read_json(accepted/meta['rendered_job']/'manifest.json')['resolved_colors']
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
    path=tmp_path/'themes/minimal/theme.toml'
    path.write_text(path.read_text().replace('background = "#ffffff"','background = "#000000"'))
    monkeypatch.setattr(themes,'THEMES_ROOT',tmp_path/'themes')
    document=Document.model_validate_json((ROOT/'samples/product.json').read_text())
    bundle=render(document,ROOT/'samples',tmp_path/'rendered',theme='minimal')
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
    path=tmp_path/'themes/minimal/theme.toml'
    path.write_text(path.read_text().replace('background = "#ffffff"','background = "#000000"'))
    monkeypatch.setattr(themes,'THEMES_ROOT',tmp_path/'themes')
    bad=preview_job(job,theme='minimal')
    assert read_json(bad/'manifest.json')['needs_review']
    good=preview_job(job,theme='bold')
    assert read_json(good/'review.json') == []
    assert read_json(good/'manifest.json')['needs_review'] is False


@pytest.mark.parametrize('theme',['classic','minimal','bold'])
@pytest.mark.parametrize('brand',['#FFFF00','#000000','#777777','#c7b195'])
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
                    const heading=/^H[1-6]$/.test(element.tagName);
                    result.push({tag:element.tagName,foreground:style.color,background,
                        minimum:(heading && (size>=24 || (bold && size>=18.667)))?3:4.5});
                }
                return result;
            }''')
            assert pairs
            def hex_color(value):
                channels=[int(n) for n in re.findall(r'\d+',value)[:3]]
                return '#'+''.join(f'{n:02x}' for n in channels)
            if theme!='classic':
                for pair in pairs:
                    ratio=contrast_ratio(hex_color(pair['foreground']),hex_color(pair['background']))
                    assert ratio>=pair['minimum'], (theme,brand,pair,ratio)
            else:
                assert hex_color(page.locator('.eyebrow').evaluate('(e)=>getComputedStyle(e).color')).lower()==brand.lower()
            border=page.locator('blockquote').evaluate('(e)=>getComputedStyle(e).borderLeftColor')
            assert hex_color(border).lower()==brand.lower()
            if theme=='bold':
                for background in page.locator('main > section:nth-child(odd)').evaluate_all('(es)=>es.map(e=>getComputedStyle(e).backgroundColor)'):
                    assert hex_color(background).lower()==brand.lower()
        finally:
            browser.close()


@pytest.mark.parametrize('brand',['#c7b195','#FFFF00','#000000','#305b46'])
def test_classic_legacy_does_not_adjust_any_color(brand):
    from core.themes import theme_styles
    styles=theme_styles('classic',brand)
    assert styles['contrast_policy']=='legacy'
    assert styles['contrast_adjustments']==[]
    assert styles['resolved_colors']['brand-text']==brand
    low=brand in ('#c7b195','#FFFF00')
    assert bool(styles['contrast_reviews'])==low
    if low:
        assert styles['contrast_reviews'][0]['code']=='BRAND_COLOR_LOW_CONTRAST'


@pytest.mark.parametrize('theme',['classic','minimal','bold'])
def test_policy_metadata_in_job_render_zip_and_approval(tmp_path,theme):
    from core.workflow import create_job,ingest_job,accept_job,read_json
    from core.editor import preview_job,build_zip,reassess_draft
    from core.facts import ProductFacts
    data=json.loads((ROOT/'samples/facts.json').read_text())
    data['product']['brand_color']='#c7b195'
    job=create_job(ProductFacts.model_validate(data),ROOT/'samples',tmp_path,theme=theme)
    expected='legacy' if theme=='classic' else 'aa'
    assert read_json(job/'manifest.json')['contrast_policy']==expected
    ingest_job(job,(ROOT/'samples/answer.txt').read_text())
    bundle=preview_job(job)
    original=(bundle/'manifest.json').read_bytes()
    accepted=accept_job(job)
    accepted_manifest=read_json(accepted/'manifest.json')
    manifests=[read_json(job/'manifest.json'),read_json(bundle/'manifest.json'),
               accepted_manifest,read_json(accepted/accepted_manifest['rendered_job']/'manifest.json')]
    with zipfile.ZipFile(io.BytesIO(build_zip(bundle))) as z:
        manifests.append(json.loads(z.read('manifest.json')))
        assert any(r.get('code')=='BRAND_COLOR_LOW_CONTRAST' for r in json.loads(z.read('review.json')))==(theme=='classic')
    assert all(m['contrast_policy']==expected for m in manifests)
    assert all(m['resolved_colors']==manifests[0]['resolved_colors'] for m in manifests)
    assert all(m['resolved_colors']['brand-original']=='#c7b195' for m in manifests)
    assert all(bool(m['contrast_adjustments'])==(theme!='classic') for m in manifests)
    assert all(any(r.get('code')=='BRAND_COLOR_LOW_CONTRAST' for r in m['contrast_reviews'])==(theme=='classic') for m in manifests)
    assert any(r.get('code')=='BRAND_COLOR_LOW_CONTRAST' for r in read_json(job/'review.json'))==(theme=='classic')
    assert any(r.get('code')=='BRAND_COLOR_LOW_CONTRAST' for r in reassess_draft(job))==(theme=='classic')
    assert (bundle/'manifest.json').read_bytes()==original


def test_switching_policy_refreshes_reviews_without_changing_snapshot(tmp_path):
    from core.editor import preview_job
    from core.workflow import read_json
    job=make_job(tmp_path,'#c7b195')
    classic=preview_job(job)
    before=(classic/'review.json').read_bytes()
    aa=preview_job(job,theme='minimal')
    assert not read_json(aa/'review.json')
    assert not read_json(job/'review.json')
    legacy=preview_job(job,theme='classic')
    assert read_json(job/'review.json')[0]['code']=='BRAND_COLOR_LOW_CONTRAST'
    assert read_json(legacy/'manifest.json')['contrast_policy']=='legacy'
    assert (classic/'review.json').read_bytes()==before


@pytest.mark.parametrize('old_policy',[None,'aa'])
def test_obsolete_classic_policy_bundle_is_not_reused(tmp_path,old_policy):
    from core.editor import preview_job,bundle_matches
    from core.workflow import read_json,write_json
    job=make_job(tmp_path)
    bundle=preview_job(job)
    assert bundle_matches(job,bundle)
    meta=read_json(bundle/'manifest.json')
    if old_policy is None: meta.pop('contrast_policy',None)
    else: meta['contrast_policy']=old_policy
    write_json(bundle/'manifest.json',meta)
    assert not bundle_matches(job,bundle)


def test_theme_policy_cannot_override_classic_legacy(tmp_path,monkeypatch):
    import core.themes as themes
    shutil.copytree(ROOT/'themes',tmp_path/'themes')
    path=tmp_path/'themes/classic/theme.toml'
    text=path.read_text()
    if 'contrast_policy' in text: text=text.replace('contrast_policy = "legacy"','contrast_policy = "aa"')
    else: text+='\ncontrast_policy = "aa"\n'
    path.write_text(text)
    monkeypatch.setattr(themes,'THEMES_ROOT',tmp_path/'themes')
    with pytest.raises(ValueError): themes.load_theme('classic')


@pytest.mark.parametrize('initial,selected',[('classic','bold'),('bold','classic')])
def test_failed_ingest_keeps_selected_theme_metadata_consistent(tmp_path,initial,selected):
    from core.workflow import create_job,ingest_job,read_json
    from core.facts import ProductFacts
    from core.themes import theme_styles,contrast_metadata
    data=json.loads((ROOT/'samples/facts.json').read_text())
    data['product']['brand_color']='#FFFF00'
    job=create_job(ProductFacts.model_validate(data),ROOT/'samples',tmp_path,theme=initial)
    with pytest.raises(ValueError): ingest_job(job,'not JSON',theme=selected)
    meta=read_json(job/'manifest.json')
    assert meta['theme']==selected and meta['status']=='needs_correction'
    assert contrast_metadata(meta)==contrast_metadata(theme_styles(selected,'#FFFF00'))
    assert not (job/'review.json').exists()


def test_replacing_old_approved_policy_invalidates_approval_pointer(tmp_path):
    from core.workflow import accept_job,read_json,write_json
    from core.editor import preview_job
    accepted=accept_job(make_job(tmp_path,'#c7b195'))
    metadata=read_json(accepted/'manifest.json')
    old_bundle=accepted/metadata['rendered_job']
    # Model an approved snapshot from the superseded classic-AA implementation.
    metadata['contrast_policy']='aa'
    write_json(accepted/'manifest.json',metadata)
    old_metadata=read_json(old_bundle/'manifest.json');old_metadata['contrast_policy']='aa'
    write_json(old_bundle/'manifest.json',old_metadata)
    previous={str(p.relative_to(old_bundle)):p.read_bytes() for p in old_bundle.rglob('*') if p.is_file()}
    new_bundle=preview_job(accepted)
    assert new_bundle!=old_bundle
    current=read_json(accepted/'manifest.json')
    assert current['contrast_policy']=='legacy'
    assert current['review_accepted'] is False
    assert 'rendered_job' not in current
    assert all((old_bundle/name).read_bytes()==value for name,value in previous.items())
