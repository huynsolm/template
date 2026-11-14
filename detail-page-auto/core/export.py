"""M5-B platform export profiles: resize, split, size checks and per-profile ZIPs.

Profiles never invent platform values. A profile is ``verified`` only when every value has an
official source URL and check date. Anything else exports with a "규격 미확인" warning and a
``.UNVERIFIED`` ZIP name. Results are described as "검사 통과/경고/오류" — never as upload-ready.
The render snapshot is read-only; each export is written to a new folder under ``<job>/exports/``.
"""
import hashlib
import io
import json
import re
import tempfile
import tomllib
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from PIL import Image, ImageCms
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = ROOT / 'profiles'
BUILTIN_IDS = ('generic', 'smartstore', 'coupang')
PROFILE_ID = re.compile(r'^[a-z0-9][a-z0-9_-]{0,39}$')
RESERVED_IDS = {'user', 'custom'}
VALUE_FIELDS = ('width', 'max_height_per_image', 'max_file_bytes', 'max_images', 'formats', 'jpeg_quality')
# Used only to produce a result when a profile leaves a value empty (= the previous fixed output).
FALLBACK = {'width': 860, 'max_height_per_image': 4000, 'formats': ['jpg'], 'jpeg_quality': 90}
QUALITY_STEP = 5
BLANK_TOLERANCE = 12  # grey levels; a row this uniform contains no text


class Profile(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: str = Field(default='custom', exclude=True)
    name: str = Field(min_length=1, max_length=80)
    status: Literal['verified', 'unverified']
    source_url: str | None = None
    checked_date: str | None = None
    width: int | None = Field(default=None, ge=100, le=4000)
    max_height_per_image: int | None = Field(default=None, ge=100, le=30000)
    max_file_bytes: int | None = Field(default=None, ge=1)
    max_images: int | None = Field(default=None, ge=1, le=1000)
    formats: list[Literal['jpg', 'png']] | None = Field(default=None, min_length=1)
    jpeg_quality: int | None = Field(default=None, ge=1, le=100)
    min_jpeg_quality: int = Field(default=80, ge=1, le=100)
    notes: str = Field(default='', max_length=2000)

    @field_validator('source_url')
    @classmethod
    def _https_only(cls, value):
        if value is not None and not re.fullmatch(r'https://[^\s]+', value):
            raise ValueError('source_url must be an https:// URL (it is recorded, never fetched)')
        return value

    @field_validator('checked_date')
    @classmethod
    def _iso_date(cls, value):
        if value is None:
            return value
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError('checked_date must be YYYY-MM-DD')
        date.fromisoformat(value)  # rejects impossible dates such as 2026-02-30
        return value

    @model_validator(mode='after')
    def _consistent(self):
        quality = self.jpeg_quality if self.jpeg_quality is not None else FALLBACK['jpeg_quality']
        if self.min_jpeg_quality > quality:
            raise ValueError('min_jpeg_quality must not exceed jpeg_quality')
        if self.status == 'verified':
            missing = [f for f in ('source_url', 'checked_date', *VALUE_FIELDS) if getattr(self, f) is None]
            if missing:
                raise ValueError('a verified profile needs an official source_url, checked_date and every value; missing: ' + ', '.join(missing))
        return self

    def missing_values(self) -> list[str]:
        return [f for f in VALUE_FIELDS if getattr(self, f) is None]

    def effective(self) -> dict:
        values = {f: getattr(self, f) if getattr(self, f) is not None else FALLBACK.get(f) for f in VALUE_FIELDS}
        values['min_jpeg_quality'] = self.min_jpeg_quality
        return values

    def record(self) -> dict:
        return {'id': self.id, 'name': self.name, 'status': self.status, 'source_url': self.source_url,
                'checked_date': self.checked_date, 'notes': self.notes,
                'values': {f: getattr(self, f) for f in (*VALUE_FIELDS, 'min_jpeg_quality')}}


def _check_id(profile_id) -> str:
    if not isinstance(profile_id, str) or not PROFILE_ID.fullmatch(profile_id) or profile_id in RESERVED_IDS:
        raise ValueError(f'알 수 없는 프로필입니다: {profile_id!r}')
    return profile_id


def _parse(text: str, profile_id: str) -> Profile:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f'프로필 {profile_id}: TOML 형식 오류: {exc}') from exc
    if 'id' in data:
        raise ValueError(f'프로필 {profile_id}: id는 파일 이름으로 정합니다 (id 항목을 지우세요)')
    if isinstance(data.get('checked_date'), date):
        data['checked_date'] = data['checked_date'].isoformat()
    try:
        return Profile.model_validate({**data, 'id': profile_id})
    except ValidationError as exc:
        details = '; '.join(f"{'.'.join(map(str, e['loc'])) or 'profile'}: {e['msg']}" for e in exc.errors(include_url=False))
        raise ValueError(f'프로필 {profile_id} 오류: {details}') from exc


def user_profiles_dir(profiles_dir: Path | None = None) -> Path:
    """User profiles: <profiles>/user, or DETAIL_PAGE_USER_PROFILES for the app's own profiles."""
    import os
    if profiles_dir is None and os.environ.get('DETAIL_PAGE_USER_PROFILES'):
        return Path(os.environ['DETAIL_PAGE_USER_PROFILES'])
    return (Path(profiles_dir) if profiles_dir else PROFILES_DIR) / 'user'


def _path(profile_id: str, profiles_dir: Path, user_dir: Path) -> Path | None:
    for folder in (profiles_dir, user_dir):
        path = folder / f'{profile_id}.toml'
        if path.is_file():
            return path
    return None


def load_profile(profile_id: str, profiles_dir: Path | None = None) -> Profile:
    user_dir = user_profiles_dir(profiles_dir)
    profiles_dir = Path(profiles_dir) if profiles_dir else PROFILES_DIR
    path = _path(_check_id(profile_id), profiles_dir, user_dir)
    if path is None:
        raise ValueError(f'알 수 없는 프로필입니다: {profile_id!r}')
    return _parse(path.read_text(encoding='utf-8'), profile_id)


def list_profiles(profiles_dir: Path | None = None) -> list[dict]:
    """Built-in profiles first (fixed order), then user profiles. Broken user files are listed with their error."""
    requested = profiles_dir
    user_dir = user_profiles_dir(profiles_dir)
    profiles_dir = Path(profiles_dir) if profiles_dir else PROFILES_DIR
    ids = [i for i in BUILTIN_IDS if (profiles_dir / f'{i}.toml').is_file()]
    ids += sorted(p.stem for p in user_dir.glob('*.toml')
                  if PROFILE_ID.fullmatch(p.stem) and p.stem not in BUILTIN_IDS and p.stem not in RESERVED_IDS)
    out = []
    for profile_id in ids:
        try:
            profile = load_profile(profile_id, requested)
            out.append({'id': profile_id, 'name': profile.name, 'status': profile.status,
                        'user': profile_id not in BUILTIN_IDS, 'error': None})
        except ValueError as exc:
            out.append({'id': profile_id, 'name': profile_id, 'status': 'unverified', 'user': True, 'error': str(exc)})
    return out


def _toml_value(value) -> str:
    if isinstance(value, bool) or value is None:
        raise ValueError('unsupported profile value')
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)  # JSON string syntax is valid TOML basic string syntax
    if isinstance(value, list):
        return '[' + ', '.join(_toml_value(v) for v in value) + ']'
    raise ValueError('unsupported profile value')


def save_user_profile(profile_id: str, data: dict, profiles_dir: Path | None = None) -> Path:
    """Validate and write ``profiles/user/<id>.toml`` (ignored by Git). Built-in ids cannot be replaced."""
    folder = user_profiles_dir(profiles_dir)
    _check_id(profile_id)
    if profile_id in BUILTIN_IDS:
        raise ValueError(f'기본 프로필 이름은 쓸 수 없습니다: {profile_id}')
    data = {k: v for k, v in data.items() if v is not None and v != '' and v != []}
    text = ''.join(f'{key} = {_toml_value(value)}\n' for key, value in data.items())
    _parse(text, profile_id)  # same validation as loading; nothing is written on error
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{profile_id}.toml'
    temporary = path.with_suffix('.toml.tmp')
    temporary.write_text(text, encoding='utf-8')
    temporary.replace(path)
    return path


def current_bundle(job: Path) -> Path:
    """The snapshot an export should use: the approved render, else the preview matching the saved text and theme."""
    from .editor import bundle_matches
    job = Path(job)
    manifest = json.loads((job / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('review_accepted') and manifest.get('rendered_job'):
        bundle = job / manifest['rendered_job']
        if bundle.is_dir():
            return bundle
    preview = job / 'preview.json'
    if preview.is_file():
        bundle = job / json.loads(preview.read_text(encoding='utf-8'))['bundle']
        if bundle.is_dir() and bundle_matches(job, bundle):
            return bundle
    raise ValueError('내보낼 렌더링이 없습니다. 먼저 미리보기를 만들거나 승인하세요 (현재 문구·테마와 같은 미리보기 필요).')


# --- exporting -----------------------------------------------------------------------------------

def _check(level, code, message, **detail):
    return {'level': level, 'code': code, 'message': message, **detail}


def _full_image(bundle: Path, manifest: dict) -> Image.Image:
    """Re-join the snapshot's pages (lossless PNG when available)."""
    full = Image.new('RGB', (manifest['width'], manifest['height']), 'white')
    for page in manifest['pages']:
        with Image.open(bundle / (page.get('png') or page['file'])) as part:
            full.paste(part.convert('RGB'), (0, page['top']))
    return full


def _blank(image: Image.Image, y: int) -> bool:
    low, high = image.crop((0, y, image.width, y + 1)).convert('L').getextrema()
    return high - low <= BLANK_TOLERANCE


def _cuts(image: Image.Image, sections: list[dict], limit: int):
    """Cut at section boundaries first; inside a taller section only at a blank pixel row."""
    cuts = [0]
    for section in sections:
        while section['bottom'] - cuts[-1] > limit:
            if section['top'] > cuts[-1]:
                cuts.append(section['top'])
                continue
            start = cuts[-1]
            cut = next((y for y in range(start + limit, start + max(1, limit // 4), -1) if _blank(image, y)), None)
            if cut is None:
                return None, section['id']
            cuts.append(cut)
    cuts.append(image.height)
    return cuts, None


def _encode(image: Image.Image, fmt: str, quality: int, icc: bytes) -> bytes:
    buffer = io.BytesIO()
    if fmt == 'jpg':
        image.save(buffer, 'JPEG', quality=quality, icc_profile=icc)
    else:
        image.save(buffer, 'PNG', icc_profile=icc)
    return buffer.getvalue()


def export_bundle(bundle: Path, profile: str | Profile, output_dir: Path | None = None, fmt: str | None = None,
                  profiles_dir: Path | None = None) -> dict:
    """Check and export one render snapshot for one profile.

    Returns ``{'status': 'pass'|'warning'|'error', 'checks': [...], 'files': [...], 'folder': str}``.
    On ``error`` nothing is written and ``files`` is empty.
    """
    bundle = Path(bundle).resolve(strict=True)
    if isinstance(profile, str):
        profile = load_profile(profile, profiles_dir)
    manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
    values = profile.effective()
    checks = []
    if profile.status != 'verified':
        checks.append(_check('warning', 'PROFILE_UNVERIFIED',
                             f'규격 미확인: "{profile.name}" 프로필은 공식 문서로 확인되지 않았습니다. 올릴 곳의 규격을 직접 확인하세요.'))
    for field in profile.missing_values():
        fallback = FALLBACK.get(field)
        checks.append(_check('warning', 'PROFILE_VALUE_MISSING',
                             f'규격 미확인: {field} 값이 없습니다. ' + (f'기본값 {fallback}을 썼습니다.' if fallback is not None else '이 항목은 검사하지 않았습니다.'),
                             field=field))
    fmt = fmt or values['formats'][0]
    if fmt not in values['formats']:
        checks.append(_check('error', 'FORMAT_NOT_ALLOWED', f'형식 불일치: 프로필이 허용하는 형식은 {", ".join(values["formats"])}입니다 (요청: {fmt}).'))

    width = values['width']
    full = _full_image(bundle, manifest)
    scale = width / full.width
    if width != full.width:
        full = full.resize((width, round(full.height * scale)), Image.Resampling.LANCZOS)
        checks.append(_check('info', 'RESIZED', f'폭을 {manifest["width"]}px에서 {width}px로 비율을 유지해 바꿨습니다.'))
    sections = [{'id': s['id'], 'top': round(s['top'] * scale), 'bottom': round(s['bottom'] * scale)} for s in manifest['sections']]
    cuts, stuck = _cuts(full, sections, values['max_height_per_image'])
    if cuts is None:
        checks.append(_check('error', 'SPLIT_IMPOSSIBLE',
                             f'분할 불가: {stuck} 섹션을 높이 {values["max_height_per_image"]}px 이하로 나눌 빈 줄이 없습니다 (글자를 자르지 않습니다).'))
        cuts = []
    pieces = list(zip(cuts, cuts[1:]))
    if values['max_images'] is not None and len(pieces) > values['max_images']:
        checks.append(_check('error', 'TOO_MANY_IMAGES', f'장수 초과: {len(pieces)}장이 필요하지만 프로필 최대는 {values["max_images"]}장입니다.'))

    icc = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    draft = '' if manifest.get('review_accepted') else '.DRAFT'
    encoded = []
    reduced = False
    for index, (top, bottom) in enumerate(pieces, 1):
        crop = full.crop((0, top, width, bottom))
        quality = values['jpeg_quality']
        data = _encode(crop, fmt, quality, icc)
        limit = values['max_file_bytes']
        while limit is not None and len(data) > limit and fmt == 'jpg' and quality > values['min_jpeg_quality']:
            quality = max(values['min_jpeg_quality'], quality - QUALITY_STEP)
            data = _encode(crop, fmt, quality, icc)
            reduced = True
        if limit is not None and len(data) > limit:
            floor = f' (JPEG 품질 최솟값 {values["min_jpeg_quality"]}까지 낮춤)' if fmt == 'jpg' else ''
            checks.append(_check('error', 'FILE_TOO_LARGE',
                                 f'용량 초과: {index}번째 이미지가 {len(data):,}바이트로 최대 {limit:,}바이트를 넘습니다{floor}.', image=index))
        encoded.append({'file': f'page-{index:03}{draft}.{fmt}', 'width': width, 'height': bottom - top, 'top': top,
                        'bottom': bottom, 'bytes': len(data), 'quality': quality if fmt == 'jpg' else None, 'data': data})
    if reduced:
        checks.append(_check('info', 'QUALITY_REDUCED', f'용량 기준을 맞추려고 JPEG 품질을 낮췄습니다 (최솟값 {values["min_jpeg_quality"]}).'))

    status = 'error' if any(c['level'] == 'error' for c in checks) else 'warning' if any(c['level'] == 'warning' for c in checks) else 'pass'
    # Default: <job>/exports/, outside rendered/ so render snapshots and their listings stay untouched.
    output_dir = Path(output_dir) if output_dir else (bundle.parent.parent if bundle.parent.name == 'rendered' else bundle.parent) / 'exports'
    folder = output_dir / f'export-{bundle.name}-{profile.id}-{hashlib.sha256(json.dumps(profile.record(), sort_keys=True).encode()).hexdigest()[:8]}-{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")}'
    files = [{k: v for k, v in item.items() if k != 'data'} for item in encoded]
    result = {'status': status, 'checks': checks, 'files': files if status != 'error' else [], 'folder': str(folder)}
    if status == 'error':
        return result

    output_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.pending-export-', dir=output_dir))
    try:
        for item in encoded:
            (staging / item['file']).write_bytes(item['data'])
        record = {'profile': profile.record(), 'effective_values': values, 'format': fmt, 'status': status,
                  'unverified': profile.status != 'verified' or bool(profile.missing_values()),
                  'checks': checks, 'files': files, 'source_job_id': manifest.get('job_id', bundle.name),
                  'source_bundle': str(bundle), 'review_accepted': bool(manifest.get('review_accepted')),
                  'created_at': datetime.now(timezone.utc).isoformat()}
        (staging / 'export.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        staging.rename(folder)
    except BaseException:
        import shutil
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return result


def build_export_zip(folder: Path) -> tuple[str, bytes]:
    """ZIP of one export: its images, the snapshot's HTML/assets/draft/review, and a manifest with ``export``."""
    folder = Path(folder).resolve(strict=True)
    record = json.loads((folder / 'export.json').read_text(encoding='utf-8'))
    bundle = Path(record['source_bundle']).resolve(strict=True)
    manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
    manifest['export'] = record
    entries = {f['file']: folder / f['file'] for f in record['files']}
    for name in ('page.html', 'draft.json', 'review.json'):
        if (bundle / name).is_file():
            entries[name] = bundle / name
    for path in (bundle / 'assets').rglob('*'):
        if path.is_file():
            entries[str(path.relative_to(bundle))] = path
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(entries):
            path = entries[name]
            base = folder if path.is_relative_to(folder) else bundle
            if path.is_symlink() or not path.resolve().is_relative_to(base):
                raise ValueError('unsafe export file: ' + name)
            archive.writestr(name, path.read_bytes())
        archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    suffix = ('' if record['review_accepted'] else '.DRAFT') + ('.UNVERIFIED' if record['unverified'] else '')
    return f"{record['source_job_id']}-{record['profile']['id']}{suffix}.zip", output.getvalue()
