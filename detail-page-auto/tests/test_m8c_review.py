"""Regression tests for the M8-C review findings (M8_C_REVIEW.md C-1, I-1~I-4, M-1)."""
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest
from PIL import Image, ImageDraw
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from core.colors import suggest_colors
from core.editor import build_zip
from core.export import build_export_zip, export_bundle
from core.pdf import make_pdf
from core.render import render
from core.schema import Document
from core.workflow import read_json


def document(headline='공통 검증 문구', title='공통 검증 문구'):
    return Document.model_validate({
        'schema_version': '1.0',
        'product': {'name': '가상 시험', 'category': '가상', 'price': '표시 없음', 'brand_color': '#305b46'},
        'sections': [
            {'id': 'hero', 'type': 'hero', 'headline': headline, 'image': 'rich-hero.png'},
            {'id': 'pain', 'type': 'pain', 'title': title, 'items': ['누락 확인용 본문']},
        ],
    })


def inject(bundle: Path, script: str):
    """Change only what Chromium prints: the page is untouched until the print starts."""
    html = bundle / 'page.html'
    html.write_text(html.read_text(encoding='utf-8').replace(
        '</body>', f"<script>window.addEventListener('beforeprint', () => {{ {script} }});</script></body>"), encoding='utf-8')


# C-1: a repeated text missing in one place is not covered by its other occurrence

@pytest.mark.parametrize('theme', ['classic', 'modern'])
def test_repeated_text_missing_at_print_time_fails(tmp_path, theme):
    bundle = render(document(), ROOT / 'samples', tmp_path, png=True, theme=theme)
    inject(bundle, "document.querySelector('h1').style.visibility = 'hidden';")
    with pytest.raises(ValueError, match='글자 보존 실패.*hero'):
        make_pdf(bundle)
    assert not list(bundle.glob('*.pdf')) and not list(bundle.glob('*.tmp')) and 'pdf' not in read_json(bundle / 'manifest.json')


def test_text_contained_in_a_longer_text_is_matched_separately(tmp_path):
    bundle = render(document(headline='공통 검증 문구와 더 긴 머리말', title='공통 검증 문구'), ROOT / 'samples', tmp_path, png=True)
    inject(bundle, "document.querySelector('.pain h2').style.visibility = 'hidden';")
    with pytest.raises(ValueError, match='글자 보존 실패.*pain'):
        make_pdf(bundle)


def test_unique_text_missing_at_print_time_fails(tmp_path):
    bundle = render(document(headline='유일한 검증 머리말'), ROOT / 'samples', tmp_path, png=True)
    inject(bundle, "document.querySelector('h1').style.visibility = 'hidden';")
    with pytest.raises(ValueError, match='글자 보존 실패.*hero'):
        make_pdf(bundle)


def test_repeated_text_present_everywhere_passes(tmp_path):
    bundle = render(document(), ROOT / 'samples', tmp_path, png=True)
    make_pdf(bundle)
    assert read_json(bundle / 'manifest.json')['pdf']['text_check']['missing'] == 0


# I-1: text hidden by an ancestor is not required

def test_text_hidden_by_an_ancestor_is_not_required(tmp_path):
    bundle = render(document(headline='유일한 검증 머리말'), ROOT / 'samples', tmp_path, png=True)
    html = bundle / 'page.html'
    text = html.read_text(encoding='utf-8')
    first = text.index('<section')
    head = text.index('>', first) + 1
    html.write_text(text[:head] + '<div style="display:none"><p>숨은검수전용문구</p></div>'
                    '<div style="visibility:hidden;position:absolute"><p>안보임문구</p></div>' + text[head:], encoding='utf-8')
    make_pdf(bundle)
    assert read_json(bundle / 'manifest.json')['pdf']['text_check']['missing'] == 0


# I-2: the hidden RGB of fully transparent pixels never matters

def rgba_photo(path: Path, clear) -> Path:
    image = Image.new('RGBA', (240, 240), clear)
    ImageDraw.Draw(image).rectangle((50, 50, 190, 190), fill=(20, 150, 70, 255))
    image.save(path)
    return path


def test_identical_looking_rgba_photos_give_identical_candidates(tmp_path):
    green = suggest_colors([rgba_photo(tmp_path / 'green.png', (20, 150, 70, 0))])
    black = suggest_colors([rgba_photo(tmp_path / 'black.png', (0, 0, 0, 0))])
    assert green == black and green and green[0]['color'] == '#149646' and green[0]['share'] == 1.0


def test_transparent_palette_png(tmp_path):
    image = Image.new('RGBA', (240, 240), (200, 30, 30, 0))
    ImageDraw.Draw(image).rectangle((50, 50, 190, 190), fill=(20, 150, 70, 255))
    paletted = image.quantize(colors=4)
    transparent = paletted.getpixel((0, 0))
    paletted.save(tmp_path / 'p.png', transparency=transparent)
    reference = suggest_colors([rgba_photo(tmp_path / 'ref.png', (0, 0, 0, 0))])
    assert [c['color'] for c in suggest_colors([tmp_path / 'p.png'])] == [c['color'] for c in reference]


# I-3: the Canva checklist matches the committed sample PDFs

def test_canva_checklist_matches_the_sample_pdfs():
    checklist = (ROOT / 'docs/canva-check.md').read_text(encoding='utf-8')
    assert '모두 7쪽' not in checklist and '7쪽이고' not in checklist
    for theme in ('modern', 'natural', 'classic'):
        reader = PdfReader(ROOT / f'docs/samples/canva-sample-{theme}.pdf')
        sizes = ' / '.join(f'{float(p.mediabox.width):.0f}×{float(p.mediabox.height):.0f}' for p in reader.pages)
        assert f'| {theme} | {len(reader.pages)}쪽 | {sizes} |' in checklist
    for column in ('쪽 수', '쪽 크기', '글자 편집', '글꼴 대체', '정렬', '캡처 경로'):
        assert column in checklist
    assert '확인 예정' in (ROOT / 'README.md').read_text(encoding='utf-8')


# I-4: both ZIP paths carry the PDF the manifest records

def preview_bundle(tmp_path):
    from core.editor import preview_job
    from core.facts import ProductFacts
    from core.workflow import create_job, ingest_job
    facts = ProductFacts.model_validate(read_json(ROOT / 'samples/facts-rich.json'))
    job = create_job(facts, ROOT / 'samples', tmp_path, theme='modern')
    ingest_job(job, (ROOT / 'samples/answer-rich.txt').read_text(encoding='utf-8'))
    return preview_job(job)


def test_both_zips_carry_the_recorded_pdf(tmp_path):
    bundle = preview_bundle(tmp_path)
    pdf = make_pdf(bundle)
    with zipfile.ZipFile(io.BytesIO(build_zip(bundle))) as archive:
        meta = json.loads(archive.read('manifest.json'))
        assert meta['pdf']['file'] == pdf.name and archive.read(pdf.name) == pdf.read_bytes()
    result = export_bundle(bundle, 'generic', output_dir=tmp_path / 'exports')
    _, data = build_export_zip(Path(result['folder']))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        meta = json.loads(archive.read('manifest.json'))
        assert meta['pdf']['file'] == pdf.name and archive.read(pdf.name) == pdf.read_bytes()


def test_zip_refuses_a_recorded_pdf_that_is_gone(tmp_path):
    bundle = preview_bundle(tmp_path)
    make_pdf(bundle).unlink()
    with pytest.raises(ValueError, match='PDF'):
        build_zip(bundle)
    result = export_bundle(bundle, 'generic', output_dir=tmp_path / 'exports')
    with pytest.raises(ValueError, match='PDF'):
        build_export_zip(Path(result['folder']))


def test_profile_zip_without_pdf_has_no_pdf_record(tmp_path):
    bundle = render(document(headline='일반 검증 문구', title='다른 제목'), ROOT / 'samples', tmp_path, png=True, theme='modern')
    result = export_bundle(bundle, 'generic', output_dir=tmp_path / 'exports')
    _, data = build_export_zip(Path(result['folder']))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert 'pdf' not in json.loads(archive.read('manifest.json')) and not [n for n in archive.namelist() if n.endswith('.pdf')]


# M-1: presentation-only variation selectors; real characters still count

def test_variation_selector_alone_does_not_fail_but_is_recorded(tmp_path):
    bundle = render(document(headline='제품 · 확인 ※ 주의 ⭐️ 😀 USB-C AC-220V', title='다른 제목'), ROOT / 'samples', tmp_path, png=True, theme='modern')
    make_pdf(bundle)
    check = read_json(bundle / 'manifest.json')['pdf']['text_check']
    assert check['missing'] == 0 and check['ignored_presentation'] == {'U+FE0F': 1}


def test_a_missing_emoji_still_fails(tmp_path):
    bundle = render(document(headline='별표 ⭐️ 시험', title='다른 제목'), ROOT / 'samples', tmp_path, png=True, theme='modern')
    inject(bundle, "const h = document.querySelector('h1'); h.textContent = h.textContent.replace('⭐', '');")
    with pytest.raises(ValueError, match='글자 보존 실패.*hero'):
        make_pdf(bundle)
