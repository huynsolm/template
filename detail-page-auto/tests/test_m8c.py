"""M8-C: brand colour candidates from photos and PDF export with preserved text."""
import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from core.assemble import assemble
from core.colors import job_color_suggestions, photo_paths, suggest_colors
from core.copy_schema import CopyDraft
from core.editor import build_zip, preview_job
from core.facts import ProductFacts
from core.ingest import extract_json
from core.pdf import PAGE_SLACK_PX, make_pdf
from core.render import render
from core.themes import THEME_IDS
from core.workflow import create_job, ingest_job, read_json

ANSWER = (ROOT / 'samples/answer-rich.txt').read_text(encoding='utf-8')


def product_photo(path: Path, background='#ffffff', body='#c8102e', part='#7f7f7f'):
    image = Image.new('RGB', (900, 700), background)
    draw = ImageDraw.Draw(image)
    draw.rectangle((250, 150, 650, 600), fill=body)      # the coloured product
    draw.rectangle((330, 220, 570, 300), fill=part)      # a grey panel
    image.save(path)
    return path


# --- colours --------------------------------------------------------------------------------------

def test_product_colour_ranks_first_and_background_and_greys_are_left_out(tmp_path):
    photo = product_photo(tmp_path / 'p.png')
    found = suggest_colors([photo])
    assert found and found[0]['color'] == '#c8102e'
    assert not any(c['color'] in ('#ffffff', '#7f7f7f') for c in found)
    assert set(found[0]['themes']) == set(THEME_IDS) and found[0]['contrast_on_white'] > 4.5
    assert suggest_colors([photo]) == found  # deterministic


def test_coloured_background_is_taken_from_the_edges(tmp_path):
    photo = product_photo(tmp_path / 'p.png', background='#1f5fbf', body='#e8a317')
    colours = [c['color'] for c in suggest_colors([photo])]
    assert colours[0] == '#e8a317' and '#1f5fbf' not in colours


def test_photos_are_not_modified_and_generated_pictures_are_not_used(tmp_path):
    import hashlib
    photo = product_photo(tmp_path / 'p.png')
    before = hashlib.sha256(photo.read_bytes()).hexdigest()
    suggest_colors([photo])
    assert hashlib.sha256(photo.read_bytes()).hexdigest() == before
    data = read_json(ROOT / 'samples/facts-rich.json')
    data['images'][1] = {'path': 'scene.png', 'role': 'lifestyle', 'source': 'ai_generated', 'generator': 'Gemini'}
    facts = ProductFacts.model_validate(data)
    paths = photo_paths(facts, tmp_path)
    assert tmp_path / 'scene.png' not in paths and paths[0] == tmp_path / 'rich-hero.png'


def test_job_suggestions_are_recorded_once(tmp_path):
    facts = ProductFacts.model_validate(read_json(ROOT / 'samples/facts-rich.json'))
    job = create_job(facts, ROOT / 'samples', tmp_path, theme='modern')
    record = job_color_suggestions(job)
    manifest = read_json(job / 'manifest.json')
    assert manifest['color_suggestions'] == record and record['version'] and len(record['photos']) == 5
    assert record['candidates'] and manifest['brand_color'] == facts.product.brand_color  # nothing applied


# --- PDF ------------------------------------------------------------------------------------------

def rich_bundle(tmp_path, theme):
    facts = ProductFacts.model_validate(read_json(ROOT / 'samples/facts-rich.json'))
    document, _ = assemble(facts, CopyDraft.model_validate(extract_json(ANSWER)))
    return render(document, ROOT / 'samples', tmp_path, theme=theme, png=True)


@pytest.mark.parametrize('theme', THEME_IDS)
def test_pdf_pages_match_the_jpg_pages_and_keep_all_text(tmp_path, theme):
    bundle = rich_bundle(tmp_path, theme)
    before = {p.name: p.read_bytes() for p in bundle.iterdir() if p.suffix in ('.jpg', '.png', '.html')}
    pdf = make_pdf(bundle)
    manifest = read_json(bundle / 'manifest.json')
    info = manifest['pdf']
    reader = PdfReader(pdf)
    assert pdf.name == info['file'] == 'page.pdf' and len(reader.pages) == len(manifest['pages']) == info['pages']
    for page, part in zip(reader.pages, manifest['pages']):
        assert float(page.mediabox.width) == pytest.approx(645, abs=0.5)
        assert float(page.mediabox.height) == pytest.approx((part['height'] + PAGE_SLACK_PX) * 0.75, abs=1)
    assert info['text_check']['runs'] > 20 and info['text_check']['missing'] == 0
    assert info['fonts'] and info['network_requests'] == []
    text = ''.join(page.extract_text() for page in reader.pages).replace(' ', '').replace('\n', '')
    assert '공간에맞춰정리한모듈형환기함' in text and '자주묻는질문' in text
    assert {p.name: p.read_bytes() for p in bundle.iterdir() if p.suffix in ('.jpg', '.png', '.html')} == before


def test_missing_text_fails_with_its_location_and_writes_nothing(tmp_path, monkeypatch):
    import pypdf
    bundle = rich_bundle(tmp_path, 'modern')
    original = pypdf.PageObject.extract_text
    # As if a heading had been turned into a picture: its words never reach the PDF text.
    monkeypatch.setattr(pypdf.PageObject, 'extract_text', lambda self, *a, **k: original(self, *a, **k).replace('설비 배치 전에', ''))
    with pytest.raises(ValueError, match='글자 보존 실패.*pain-1'):
        make_pdf(bundle)
    assert not list(bundle.glob('*.pdf')) and not list(bundle.glob('*.tmp')) and 'pdf' not in read_json(bundle / 'manifest.json')


def test_draft_pdf_name_and_zip(tmp_path):
    facts = ProductFacts.model_validate(read_json(ROOT / 'samples/facts-rich.json'))
    job = create_job(facts, ROOT / 'samples', tmp_path, theme='natural')
    ingest_job(job, ANSWER)
    bundle = preview_job(job)
    pdf = make_pdf(bundle)
    assert pdf.name == 'page.DRAFT.pdf'
    with zipfile.ZipFile(io.BytesIO(build_zip(bundle))) as archive:
        assert 'page.DRAFT.pdf' in archive.namelist()
        assert json.loads(archive.read('manifest.json'))['pdf']['file'] == 'page.DRAFT.pdf'


def test_pdf_refuses_an_ai_render_without_sources(tmp_path):
    bundle = rich_bundle(tmp_path, 'modern')
    manifest = read_json(bundle / 'manifest.json')
    manifest['ai_images'] = True
    (bundle / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
    with pytest.raises(ValueError, match='이미지 출처'):
        make_pdf(bundle)


def test_cli_pdf_command(tmp_path):
    facts = ProductFacts.model_validate(read_json(ROOT / 'samples/facts-rich.json'))
    job = create_job(facts, ROOT / 'samples', tmp_path, theme='modern')
    ingest_job(job, ANSWER)
    preview_job(job)
    result = subprocess.run([sys.executable, 'cli.py', 'pdf', '--job', str(job)], capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip().splitlines()[-1]).name == 'page.DRAFT.pdf'


# --- screens --------------------------------------------------------------------------------------

def test_input_screen_offers_colours_and_applies_only_on_click(monkeypatch, tmp_path):
    from test_app import start
    app = start(monkeypatch, tmp_path)
    before = app.session_state['product_brand_color']
    app.button(key='find_colors').click().run()
    assert not app.exception
    assert app.session_state['product_brand_color'] == before
    chosen = app.session_state['color_input'][0]['color']
    app.button(key='use_color_0').click().run()
    assert app.session_state['product_brand_color'] == chosen


def test_preview_colours_and_download_pdf(monkeypatch, tmp_path):
    from test_app import stage, start
    app = start(monkeypatch, tmp_path)
    app.button(key='create').click().run()
    job = Path(app.session_state['job'])
    stage(app, 2)
    app.text_area(key='answer_text').set_value((ROOT / 'samples/answer.txt').read_text(encoding='utf-8'))
    app.button(key='ingest').click().run()
    stage(app, 4)
    app.button(key='find_job_colors').click().run()
    record = read_json(job / 'manifest.json')['color_suggestions']
    app.button(key='use_preview_color_0').click().run(timeout=120)
    assert not app.exception
    assert app.session_state['preview_brand'] == record['candidates'][0]['color']
    assert read_json(job / 'manifest.json')['brand_color'] == record['candidates'][0]['color']
    stage(app, 6)
    app.button(key='make_pdf').click().run(timeout=120)
    assert not app.exception
    bundle = Path(app.session_state['bundle'])
    assert (bundle / 'page.DRAFT.pdf').is_file()
    assert any(b.key == 'download_pdf_button' for b in app.get('download_button'))
