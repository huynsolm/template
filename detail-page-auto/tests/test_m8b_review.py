"""Regression tests for the M8-B review findings (M8_B_REVIEW.md C-1, C-2, I-1~I-4, M-1)."""
import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from pydantic import ValidationError
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from core.editor import preview_job, resume_bundle
from core.export import build_export_zip, export_bundle
from core.workflow import accept_job, create_job, ingest_job, read_json
from test_m8b import AI_EDITED, AI_SCENE, ANSWER, BASE, facts_with, virtual_images

CONFIRM = {'image-5': ['no_product'], 'image-6': ['shape', 'color', 'composition']}


def rendered_ai_job(tmp_path):
    photos = virtual_images(tmp_path / 'photos')
    job = create_job(facts_with(BASE + [AI_SCENE, AI_EDITED]), photos, tmp_path / 'jobs', theme='modern')
    ingest_job(job, ANSWER, render_output=True)
    return job, photos


# C-1: every render of a job carries the image sources, and so does its export ZIP

def test_ingest_render_and_export_carry_image_sources(tmp_path):
    job, _ = rendered_ai_job(tmp_path)
    bundle = next((job / 'rendered').iterdir())
    sources = read_json(bundle / 'manifest.json')['image_sources']
    assert [s['source'] for s in sources][-2:] == ['ai_generated', 'ai_edited']
    assert all('.DRAFT.' in p['file'] for p in read_json(bundle / 'manifest.json')['pages'])
    exported = export_bundle(bundle, 'generic', output_dir=tmp_path / 'exports')
    _, data = build_export_zip(Path(exported['folder']))
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert json.loads(archive.read('manifest.json'))['image_sources'] == sources


def test_export_refuses_a_render_without_image_sources(tmp_path):
    job, _ = rendered_ai_job(tmp_path)
    bundle = next((job / 'rendered').iterdir())
    manifest = read_json(bundle / 'manifest.json'); del manifest['image_sources']
    (bundle / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
    with pytest.raises(ValueError, match='이미지 출처'):
        export_bundle(bundle, 'generic', output_dir=tmp_path / 'exports')


# C-2: the M1 command never writes normal file names for a job draft with unconfirmed AI images

def test_m1_render_of_an_ai_job_draft_stays_draft(tmp_path):
    job, _ = rendered_ai_job(tmp_path)
    result = subprocess.run([sys.executable, 'cli.py', '--input', str(job / 'draft.json'), '--images', str(job),
                             '--output', str(tmp_path / 'm1'), '--png', '--theme', 'modern'],
                            capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    manifest = read_json(Path(result.stdout.strip().splitlines()[-1]) / 'manifest.json')
    assert manifest['needs_review'] is True and all('.DRAFT.' in p['file'] for p in manifest['pages'])
    assert [s['source'] for s in manifest['image_sources']][-2:] == ['ai_generated', 'ai_edited']


def test_m1_render_of_a_staged_document_without_job_files_stays_draft(tmp_path):
    job, _ = rendered_ai_job(tmp_path)
    loose = tmp_path / 'loose'; loose.mkdir()
    draft = read_json(job / 'draft.json')
    for name in {s['image'] for s in draft['sections'] if 'image' in s} | {i['image'] for s in draft['sections'] for i in s.get('items', []) if isinstance(i, dict) and 'image' in i}:
        (loose / name).parent.mkdir(parents=True, exist_ok=True)
        (loose / name).write_bytes((job / name).read_bytes())
    result = subprocess.run([sys.executable, 'cli.py', '--input', str(job / 'draft.json'), '--images', str(loose),
                             '--output', str(tmp_path / 'm1'), '--theme', 'modern'], capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    manifest = read_json(Path(result.stdout.strip().splitlines()[-1]) / 'manifest.json')
    assert manifest['needs_review'] is True and all('.DRAFT.' in p['file'] for p in manifest['pages'])


def test_photo_only_m1_render_is_unchanged(tmp_path):
    result = subprocess.run([sys.executable, 'cli.py', '--input', 'samples/product.json', '--images', 'samples',
                             '--output', str(tmp_path / 'm1')], capture_output=True, text=True, cwd=ROOT)
    manifest = read_json(Path(result.stdout.strip().splitlines()[-1]) / 'manifest.json')
    assert manifest['needs_review'] is False and 'image_sources' not in manifest


# I-1: a generated picture never becomes the representative (hero) photo

def test_generated_picture_is_never_the_hero(tmp_path):
    with pytest.raises(ValidationError, match='대표 사진'):
        facts_with([AI_SCENE])
    photos = virtual_images(tmp_path / 'photos')
    job = create_job(facts_with([AI_SCENE, {'path': 'rich-detail.png', 'role': 'detail'}]), photos, tmp_path / 'jobs')
    ingest_job(job, ANSWER)
    draft = read_json(job / 'draft.json')
    facts = read_json(job / 'facts.json')
    hero = next(s for s in draft['sections'] if s['type'] == 'hero')
    assert hero['image'] == facts['images'][1]['derived_path']  # the real photo, not the scene


# I-2: the same physical file cannot be both the real photo and an AI image

@pytest.mark.parametrize('alias', ['./rich-hero.png', 'sub/../rich-hero.png'])
def test_path_aliases_of_one_file_are_rejected(tmp_path, alias):
    photos = virtual_images(tmp_path / 'photos')
    (photos / 'sub').mkdir(exist_ok=True)
    with pytest.raises((ValueError, ValidationError), match='같은 파일|같은 작업의 실제 사진'):
        create_job(facts_with(BASE + [dict(AI_EDITED, path=alias, based_on='rich-hero.png')]), photos, tmp_path / 'jobs')
    with pytest.raises((ValueError, ValidationError), match='같은 파일|같은 작업의 실제 사진'):
        create_job(facts_with(BASE + [dict(AI_EDITED, based_on=alias)] + [dict(AI_SCENE, path=alias.replace('hero', 'lifestyle'))]), photos, tmp_path / 'jobs')
    assert not any((tmp_path / 'jobs').glob('job-*')) if (tmp_path / 'jobs').exists() else True


def test_symlink_or_copy_names_resolving_to_one_file_are_rejected(tmp_path):
    photos = virtual_images(tmp_path / 'photos')
    (photos / 'same.png').hardlink_to(photos / 'rich-hero.png')
    # A hard link is a different name for the same file; the job still copies it, so it is caught by content identity.
    with pytest.raises(ValueError, match='같은 파일'):
        create_job(facts_with(BASE + [dict(AI_EDITED, path='same.png')]), photos, tmp_path / 'jobs')


# I-3: the tool field holds a name only

@pytest.mark.parametrize('name', ['tools.example.com', 'example.co.kr', 'AIza' + 'A' * 35, 'sk-' + 'a1' * 12,
                                  'ghp_' + 'B' * 36, 'tool<script>', 'ChatGPT\nhttps'])
def test_generator_rejects_addresses_and_tokens(name):
    with pytest.raises(ValidationError, match='이름만'):
        facts_with(BASE + [dict(AI_EDITED, generator=name)])


@pytest.mark.parametrize('name', ['ChatGPT', 'Gemini 2.5', 'Midjourney v7', '가상 AI 도구', 'GPT-4o', 'Image (beta)'])
def test_generator_accepts_tool_names(name):
    assert facts_with(BASE + [dict(AI_EDITED, generator=name)]).images[-1].generator == name


# I-4: ⑤ preview shows the AI images and that they still need confirmation

def test_preview_screen_shows_ai_sources_and_pending_confirmation(monkeypatch, tmp_path):
    job, _ = rendered_ai_job(tmp_path)
    preview_job(job)
    monkeypatch.setenv('DETAIL_PAGE_OUTPUTS', str(job.parent))
    app = AppTest.from_file(str(ROOT / 'app/main.py'), default_timeout=60).run()
    app.selectbox(key='resume_job').set_value(str(job))
    app.button(key='resume').click().run()
    from test_app import stage
    stage(app, 4)
    texts = [w.value for w in app.warning]
    assert any('AI 생성' in t and 'AI 배경 변경' in t and '⑥' in t for t in texts), texts


# M-1: confirmations stay with an accepted job while its images are unchanged

def test_confirmations_persist_on_an_unchanged_accepted_job(tmp_path):
    job, _ = rendered_ai_job(tmp_path)
    accepted = accept_job(job, image_confirmations=CONFIRM)
    old = resume_bundle(accepted)
    new = preview_job(accepted)
    assert not any(r.get('code') == 'AI_IMAGE_UNCONFIRMED' for r in read_json(accepted / 'review.json'))
    assert read_json(accepted / 'manifest.json')['review_accepted'] is True and resume_bundle(accepted) == old
    assert all('.DRAFT.' in p['file'] for p in read_json(new / 'manifest.json')['pages'])  # a preview is always a draft


# --- re-review (M8_B_REVIEW_2.md) -------------------------------------------------------------------

def test_staged_draft_without_job_files_cannot_be_exported_without_sources(tmp_path):
    """R2-C-1: a render known to hold AI pictures but with no source record is not exported."""
    import shutil
    job, _ = rendered_ai_job(tmp_path)
    loose = tmp_path / 'loose'
    shutil.copytree(job / 'images', loose / 'images')
    result = subprocess.run([sys.executable, 'cli.py', '--input', str(job / 'draft.json'), '--images', str(loose),
                             '--output', str(tmp_path / 'm1'), '--png', '--theme', 'modern'], capture_output=True, text=True, cwd=ROOT)
    assert result.returncode == 0, result.stderr
    bundle = Path(result.stdout.strip().splitlines()[-1])
    manifest = read_json(bundle / 'manifest.json')
    assert manifest['ai_images'] is True and manifest['image_sources_known'] is False
    with pytest.raises(ValueError, match='이미지 출처'):
        export_bundle(bundle, 'generic', output_dir=tmp_path / 'exports')
    assert not (tmp_path / 'exports').exists() or not any((tmp_path / 'exports').iterdir())


def test_legacy_staged_render_without_flags_is_not_exported(tmp_path):
    job, _ = rendered_ai_job(tmp_path)
    bundle = next((job / 'rendered').iterdir())
    manifest = read_json(bundle / 'manifest.json')
    for key in ('image_sources', 'ai_images', 'image_sources_known'): manifest.pop(key, None)
    (bundle / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
    (bundle.parent.parent / 'facts.json').rename(bundle.parent.parent / 'facts.moved.json')  # no job facts either
    with pytest.raises(ValueError, match='이미지 출처'):
        export_bundle(bundle, 'generic', output_dir=tmp_path / 'exports')


def test_kept_confirmations_reach_new_previews_and_the_screen(monkeypatch, tmp_path):
    """R2-I-1: a new preview of an accepted job carries its image checks; ⑤ shows them as confirmed."""
    job, _ = rendered_ai_job(tmp_path)
    accepted = accept_job(job, image_confirmations=CONFIRM)
    monkeypatch.setenv('DETAIL_PAGE_OUTPUTS', str(job.parent))
    app = AppTest.from_file(str(ROOT / 'app/main.py'), default_timeout=120).run()
    app.selectbox(key='resume_job').set_value(str(accepted))
    app.button(key='resume').click().run()
    from test_app import stage
    stage(app, 4)
    app.selectbox(key='theme_choice').set_value('minimal').run()
    preview = Path(app.session_state['bundle'])
    checks = read_json(preview / 'manifest.json')['image_checks']
    assert {c['id'] for c in checks} == set(CONFIRM)
    assert all('.DRAFT.' in p['file'] for p in read_json(preview / 'manifest.json')['pages'])
    assert not any('확인 전' in w.value for w in app.warning)
    assert any('확인 완료' in i.value for i in app.info)


def test_partial_confirmation_is_shown_per_image(monkeypatch, tmp_path):
    job, _ = rendered_ai_job(tmp_path)
    manifest = read_json(job / 'manifest.json')
    manifest['image_checks'] = [{'id': 'image-6', 'index': 6, 'source': 'ai_edited', 'path': read_json(job / 'facts.json')['images'][6]['path'],
                                 'checks': ['shape', 'color', 'composition']}]
    (job / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
    bundle = preview_job(job)
    assert [c['id'] for c in read_json(bundle / 'manifest.json')['image_checks']] == ['image-6']
    monkeypatch.setenv('DETAIL_PAGE_OUTPUTS', str(job.parent))
    app = AppTest.from_file(str(ROOT / 'app/main.py'), default_timeout=120).run()
    app.selectbox(key='resume_job').set_value(str(job))
    app.button(key='resume').click().run()
    from test_app import stage
    stage(app, 4)
    pending = [w.value for w in app.warning if '확인 전' in w.value]
    assert len(pending) == 1 and '사진 6' in pending[0] and '사진 7' not in pending[0]
    assert any('사진 7' in i.value and '확인 완료' in i.value for i in app.info)


def test_checks_for_a_different_image_are_not_carried(tmp_path):
    job, _ = rendered_ai_job(tmp_path)
    manifest = read_json(job / 'manifest.json')
    manifest['image_checks'] = [{'id': 'image-6', 'index': 6, 'source': 'ai_edited', 'path': 'images/other.png', 'checks': ['shape']}]
    (job / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False), encoding='utf-8')
    assert 'image_checks' not in read_json(preview_job(job) / 'manifest.json')


@pytest.mark.parametrize('name', ['DALL·E 3', 'Adobe Firefly', 'Stable Diffusion XL'])
def test_generator_accepts_names_with_a_middle_dot(name):
    """R2-M-1"""
    assert facts_with(BASE + [dict(AI_EDITED, generator=name)]).images[-1].generator == name
