"""M5-B: platform export profiles and export checks. No network, no real platform values."""
import io
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.export import (  # noqa: E402
    Profile, build_export_zip, export_bundle, list_profiles, load_profile, save_user_profile,
)


@pytest.fixture(scope='module')
def bundle(tmp_path_factory):
    """One real Chromium render of the sample, with lossless PNG pages."""
    from core.render import render
    from core.schema import Document
    data = json.loads((ROOT / 'samples/product.json').read_text(encoding='utf-8'))
    # Make one section much taller than the small fake profiles below, so it must be split inside.
    features = next(s for s in data['sections'] if s['type'] == 'features')
    features['items'] = [{'title': f'특징 {i}', 'desc': '여러 줄로 이어지는 설명 문장입니다. ' * 6} for i in range(1, 7)]
    return render(Document.model_validate(data), ROOT / 'samples', tmp_path_factory.mktemp('render'), png=True, max_height=8000)


def fake(**values):
    base = {'name': '테스트', 'status': 'verified', 'source_url': 'https://example.invalid/spec',
            'checked_date': '2026-11-14', 'width': 860, 'max_height_per_image': 1500,
            'max_file_bytes': 20_000_000, 'max_images': 50, 'formats': ['jpg'], 'jpeg_quality': 90}
    base.update(values)
    return Profile.model_validate({k: v for k, v in base.items() if v is not None})


def pages(result):
    return [Image.open(Path(result['folder']) / f['file']) for f in result['files']]


def is_blank_row(image, y):
    low, high = image.crop((0, y, image.width, y + 1)).convert('L').getextrema()
    return high - low <= 12


# --- splitting and resizing ----------------------------------------------------------------

@pytest.mark.parametrize('width,height', [(860, 1500), (640, 900)])
def test_fake_profiles_control_width_and_split_height(tmp_path, bundle, width, height):
    result = export_bundle(bundle, fake(width=width, max_height_per_image=height), tmp_path)
    assert result['status'] in ('pass', 'warning'), result['checks']
    images = pages(result)
    assert len(images) >= 2
    assert all(im.width == width and im.height <= height for im in images)
    render_height = json.loads((bundle / 'manifest.json').read_text())['height']
    assert abs(sum(im.height for im in images) - round(render_height * width / 860)) <= len(images)


def test_section_boundaries_are_preferred_and_text_rows_are_never_cut(tmp_path, bundle):
    result = export_bundle(bundle, fake(max_height_per_image=900), tmp_path)
    manifest = json.loads((bundle / 'manifest.json').read_text())
    boundaries = {s['top'] for s in manifest['sections']}
    cuts = [f['top'] for f in result['files']][1:]
    inside = [c for c in cuts if c not in boundaries]
    assert any(c in boundaries for c in cuts)          # section boundary used where possible
    assert inside                                      # the tall features section had to be split inside
    whole = Image.new('RGB', (860, manifest['height']))
    y = 0
    for page in manifest['pages']:
        with Image.open(bundle / page['png']) as png:
            whole.paste(png.convert('RGB'), (0, y)); y += png.height
    for cut in inside:
        assert is_blank_row(whole, cut), cut                 # only blank rows between text lines


def test_a_section_without_any_blank_row_is_an_error(tmp_path):
    """A section that is all pixels (no blank row) cannot be split without cutting through it."""
    import random
    folder = tmp_path / 'job-noise'
    folder.mkdir()
    rng = random.Random(1)
    noise = Image.frombytes('L', (860, 1000), bytes(rng.randrange(256) for _ in range(860 * 1000))).convert('RGB')
    noise.save(folder / 'page-001.png')
    manifest = {'width': 860, 'height': 1000, 'review_accepted': False, 'job_id': folder.name,
                'pages': [{'file': 'page-001.png', 'png': 'page-001.png', 'top': 0, 'bottom': 1000, 'width': 860, 'height': 1000}],
                'sections': [{'id': 'photo-1', 'top': 0, 'bottom': 1000}]}
    (folder / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    result = export_bundle(folder, fake(max_height_per_image=400), tmp_path / 'out')
    assert result['status'] == 'error'
    assert any(c['code'] == 'SPLIT_IMPOSSIBLE' and 'photo-1' in c['message'] for c in result['checks'])
    assert result['files'] == [] and not Path(result['folder']).exists()


# --- file size, image count, format --------------------------------------------------------

def test_oversized_file_lowers_jpeg_quality_and_succeeds(tmp_path, bundle):
    generous = export_bundle(bundle, fake(), tmp_path / 'a')
    largest = max(f['bytes'] for f in generous['files'])
    result = export_bundle(bundle, fake(max_file_bytes=largest - 1, min_jpeg_quality=60), tmp_path / 'b')
    assert result['status'] == 'pass', result['checks']
    assert all(f['bytes'] <= largest - 1 for f in result['files'])
    assert any(f['quality'] < 90 for f in result['files'])
    assert all(f['quality'] >= 60 for f in result['files'])
    assert any(c['code'] == 'QUALITY_REDUCED' for c in result['checks'])


def test_oversized_file_at_minimum_quality_is_an_error(tmp_path, bundle):
    result = export_bundle(bundle, fake(max_file_bytes=5_000), tmp_path)
    assert result['status'] == 'error'
    error = next(c for c in result['checks'] if c['code'] == 'FILE_TOO_LARGE')
    assert '80' in error['message']  # stopped at the default minimum quality
    assert result['files'] == []


def test_too_many_images_is_an_error(tmp_path, bundle):
    result = export_bundle(bundle, fake(max_height_per_image=900, max_images=1), tmp_path)
    assert result['status'] == 'error'
    assert any(c['code'] == 'TOO_MANY_IMAGES' for c in result['checks'])


def test_format_not_allowed_by_profile_is_an_error(tmp_path, bundle):
    result = export_bundle(bundle, fake(formats=['jpg']), tmp_path, fmt='png')
    assert result['status'] == 'error'
    assert any(c['code'] == 'FORMAT_NOT_ALLOWED' for c in result['checks'])


def test_png_export_when_allowed(tmp_path, bundle):
    result = export_bundle(bundle, fake(formats=['png']), tmp_path)
    assert result['status'] == 'pass'
    assert all(f['file'].endswith('.png') for f in result['files'])


# --- unverified / empty profiles -------------------------------------------------------------

@pytest.mark.parametrize('profile_id', ['generic', 'smartstore', 'coupang'])
def test_shipped_profiles_are_unverified_and_export_with_a_warning(tmp_path, bundle, profile_id):
    profile = load_profile(profile_id)
    assert profile.status == 'unverified'
    result = export_bundle(bundle, profile_id, tmp_path)
    assert result['status'] == 'warning'
    assert result['files']
    assert any(c['code'] == 'PROFILE_UNVERIFIED' and '규격 미확인' in c['message'] for c in result['checks'])
    name, data = build_export_zip(result['folder'])
    assert name.endswith('.UNVERIFIED.zip')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['export']['profile']['id'] == profile_id
        assert manifest['export']['unverified'] is True
        assert set(archive.namelist()) >= {f['file'] for f in result['files']}


def test_platform_templates_have_no_invented_values():
    for profile_id in ('smartstore', 'coupang'):
        profile = load_profile(profile_id)
        assert profile.width is None and profile.max_height_per_image is None
        assert profile.max_file_bytes is None and profile.max_images is None
        assert profile.source_url is None and profile.checked_date is None


def test_generic_profile_matches_previous_defaults():
    profile = load_profile('generic')
    assert (profile.width, profile.max_height_per_image, profile.jpeg_quality) == (860, 4000, 90)
    assert '특정 플랫폼 규격 아님' in profile.notes


def test_missing_values_are_listed_as_warnings(tmp_path, bundle):
    result = export_bundle(bundle, fake(status='unverified', max_file_bytes=None, max_images=None), tmp_path)
    codes = [c['code'] for c in result['checks']]
    assert 'PROFILE_VALUE_MISSING' in codes and 'PROFILE_UNVERIFIED' in codes


def test_nothing_ever_claims_upload_ready(tmp_path, bundle):
    for profile in (fake(), load_profile('generic')):
        result = export_bundle(bundle, profile, tmp_path / profile.name)
        assert '업로드 가능' not in json.dumps(result, ensure_ascii=False)
    assert '업로드 가능' not in (ROOT / 'core/export.py').read_text(encoding='utf-8').replace("'업로드 가능'", '')


def test_export_manifest_records_profile_values_source_and_checks(tmp_path, bundle):
    result = export_bundle(bundle, fake(), tmp_path)
    name, data = build_export_zip(result['folder'])
    # verified profile with every value: no UNVERIFIED marker; the M1 render was never approved, so DRAFT
    assert name == f'{bundle.name}-custom.DRAFT.zip'
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        record = json.loads(archive.read('manifest.json'))['export']
    assert record['profile']['source_url'] == 'https://example.invalid/spec'
    assert record['profile']['checked_date'] == '2026-11-14'
    assert record['profile']['values']['max_height_per_image'] == 1500
    assert record['checks'] == result['checks']
    assert record['source_job_id'] == bundle.name


def test_render_snapshot_is_not_modified(tmp_path, bundle):
    before = {p: p.read_bytes() for p in bundle.rglob('*') if p.is_file()}
    export_bundle(bundle, fake(width=640), tmp_path)
    assert {p: p.read_bytes() for p in bundle.rglob('*') if p.is_file()} == before


# --- profile files ----------------------------------------------------------------------------

@pytest.mark.parametrize('text,match', [
    ('name="x"\nstatus="unverified"\nchecked_date="2026/11/14"\n', 'checked_date'),
    ('name="x"\nstatus="unverified"\nchecked_date="2026-02-30"\n', 'checked_date'),
    ('name="x"\nstatus="unverified"\nwidth=-860\n', 'width'),
    ('name="x"\nstatus="unverified"\nmax_file_bytes=0\n', 'max_file_bytes'),
    ('name="x"\nstatus="unverified"\ncolour="red"\n', 'colour'),
    ('name="x"\nstatus="maybe"\n', 'status'),
    ('name="x"\nstatus="verified"\nwidth=860\n', 'verified'),
    ('name="x"\nstatus="unverified"\nformats=["gif"]\n', 'formats'),
    ('name="x"\nstatus="unverified"\nsource_url="javascript:alert(1)"\n', 'source_url'),
    ('name="x"\nstatus="unverified"\njpeg_quality=70\nmin_jpeg_quality=80\n', 'min_jpeg_quality'),
    ('name="x"\nstatus=\n', 'TOML'),
])
def test_invalid_profile_files_are_rejected(tmp_path, text, match):
    (tmp_path / 'bad.toml').write_text(text, encoding='utf-8')
    with pytest.raises(ValueError, match=match):
        load_profile('bad', profiles_dir=tmp_path)


@pytest.mark.parametrize('profile_id', ['../generic', 'Generic', '', 'a/b', 'user'])
def test_unknown_or_unsafe_profile_ids_are_rejected(profile_id):
    with pytest.raises(ValueError, match='프로필'):
        load_profile(profile_id)


def test_user_profiles_are_saved_listed_and_not_tracked_by_git(tmp_path):
    profiles = tmp_path / 'profiles'
    shutil.copytree(ROOT / 'profiles', profiles, ignore=shutil.ignore_patterns('user'))
    save_user_profile('my-shop', {'name': '내 쇼핑몰', 'status': 'unverified', 'width': 1000}, profiles_dir=profiles)
    assert (profiles / 'user/my-shop.toml').is_file()
    assert load_profile('my-shop', profiles_dir=profiles).width == 1000
    ids = [p['id'] for p in list_profiles(profiles_dir=profiles)]
    assert ids[:3] == ['generic', 'smartstore', 'coupang'] and 'my-shop' in ids
    with pytest.raises(ValueError, match='프로필'):
        save_user_profile('generic', {'name': 'x', 'status': 'unverified'}, profiles_dir=profiles)
    with pytest.raises(ValueError, match='width'):
        save_user_profile('bad', {'name': 'x', 'status': 'unverified', 'width': -1}, profiles_dir=profiles)
    assert not (profiles / 'user/bad.toml').exists()
    ignored = subprocess.run(['git', 'check-ignore', '-q', 'detail-page-auto/profiles/user/my-shop.toml'],
                             cwd=ROOT.parent, check=False)
    assert ignored.returncode == 0


# --- CLI --------------------------------------------------------------------------------------

def test_cli_export(tmp_path):
    from core.facts import ProductFacts
    from core.workflow import accept_job, create_job, ingest_job
    facts = ProductFacts.model_validate_json((ROOT / 'samples/facts.json').read_text(encoding='utf-8'))
    job = create_job(facts, ROOT / 'samples', tmp_path)
    ingest_job(job, (ROOT / 'samples/answer.txt').read_text(encoding='utf-8'))
    accepted = accept_job(job)
    run = lambda *a: subprocess.run([sys.executable, str(ROOT / 'cli.py'), *map(str, a)], capture_output=True, text=True, cwd=ROOT)
    ok = run('export', '--job', accepted, '--profile', 'generic', '--output', tmp_path / 'zips')
    assert ok.returncode == 0, ok.stderr
    path = Path(ok.stdout.strip())
    assert path.is_file() and path.name.endswith('-generic.UNVERIFIED.zip')
    assert '규격 미확인' in ok.stderr
    bad = run('export', '--job', accepted, '--profile', 'nope')
    assert bad.returncode != 0 and '프로필' in bad.stderr
    no_preview = run('export', '--job', job, '--profile', 'generic')
    assert no_preview.returncode != 0 and '미리보기' in no_preview.stderr


def test_default_export_folder_is_outside_rendered_snapshots(tmp_path):
    from core.editor import preview_job
    from core.facts import ProductFacts
    from core.workflow import create_job, ingest_job
    facts = ProductFacts.model_validate_json((ROOT / 'samples/facts.json').read_text(encoding='utf-8'))
    job = create_job(facts, ROOT / 'samples', tmp_path)
    ingest_job(job, (ROOT / 'samples/answer.txt').read_text(encoding='utf-8'))
    bundle = preview_job(job)
    before = sorted(p.name for p in (job / 'rendered').iterdir())
    result = export_bundle(bundle, 'generic')
    assert Path(result['folder']).parent == job / 'exports'
    assert Path(result['folder']).name.startswith('export-')
    assert sorted(p.name for p in (job / 'rendered').iterdir()) == before


def test_user_profile_folder_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv('DETAIL_PAGE_USER_PROFILES', str(tmp_path / 'mine'))
    save_user_profile('env-shop', {'name': '환경변수 폴더', 'status': 'unverified', 'max_images': 3})
    assert (tmp_path / 'mine/env-shop.toml').is_file()
    listed = {p['id']: p for p in list_profiles()}
    assert listed['env-shop']['error'] is None and listed['env-shop']['user']
    assert load_profile('env-shop').max_images == 3
    assert not (ROOT / 'profiles/user/env-shop.toml').exists()
