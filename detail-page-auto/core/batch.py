"""M5-C: create many product jobs from one sheet (XLSX or CSV) and track them as a batch.

Each product becomes an ordinary job (``create_job``) under ``outputs/batch-<id>/products/<product_id>/``.
Broken products are excluded with errors located as sheet·row·column·reason (Excel row numbers);
the rest continue. Prompts never mix products. There is no bulk approval: every product goes
through the normal ⑥ checklist; only approved products are exported.
"""
import csv
import io
import json
import re
import shutil
import tempfile
import zipfile
from pathlib import PurePosixPath, PureWindowsPath
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from .facts import ProductFacts
from .workflow import create_job, read_json, write_json

HEADERS = {
    'products': ['product_id', '상품명', '카테고리', '가격', '브랜드 색', '테마', '프로필', '사진 폴더', '안내 문구'],
    'facts': ['product_id', 'fact_id', '문구', '종류', '근거'],
    'images': ['product_id', '파일명', '역할', '배경 제거 여부'],
    'reviews': ['product_id', '후기', '별점', '출처', '허가 확인'],
}
REQUIRED_SHEETS = ('products', 'facts', 'images')
DESCRIPTIONS = {
    'product_id': '상품을 구분하는 이름. 영문·숫자·-·_ 1~40자. 파일 이름에 쓰입니다.',
    '상품명': '상품 이름 (필수)', '카테고리': '분류 (필수)', '가격': '판매 가격 문구 (필수). AI는 가격을 만들지 않습니다.',
    '브랜드 색': '#RRGGBB 형식 (예: #305b46)', '테마': 'classic(기본) / minimal / bold', '프로필': '내보내기 프로필: generic(기본) / smartstore / coupang / 사용자 프로필 이름',
    '사진 폴더': '사진 루트 폴더 아래의 상품별 폴더 이름. 루트 밖 경로는 쓸 수 없습니다.', '안내 문구': '구매 안내(선택)',
    'fact_id': '사실 id (상품 안에서 중복 불가). AI 답변의 근거로 쓰입니다.', '문구': '판매자가 확인한 사실 문장 (최대 500자)',
    '종류': '스펙 / 특징 / 사용법 / 주장 / 기타. 주장은 근거가 필요합니다.', '근거': '주장의 근거 (주장일 때 필수)',
    '파일명': '사진 폴더 안의 PNG/JPEG 파일 이름', '역할': '대표 / 특징 / 해결 / 기타 (첫 사진은 대표 권장)',
    '배경 제거 여부': '예 / 아니오 (기본 아니오)', '후기': '실제 고객 후기 원문. AI는 후기를 만들지 않습니다.',
    '별점': '1~5 정수', '출처': '후기를 받은 곳', '허가 확인': '예 = 사용 허가를 확인함 (필수)',
}
KINDS = {'스펙': 'spec', '특징': 'feature', '사용법': 'usage', '주장': 'claim', '기타': 'other'}
ROLES = {'대표': 'hero', '특징': 'feature', '해결': 'solution', '기타': 'other'}
YES = {'예', 'y', 'yes', 'true', '1', 'o'}
NO = {'', '아니오', '아니요', 'n', 'no', 'false', '0', 'x'}
PRODUCT_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$')
MAX_PRODUCTS = 50
MAX_BYTES = 5 * 1024 * 1024
MAX_XLSX_ENTRIES = 1000
MAX_XLSX_MEMBER_BYTES = 20 * 1024 * 1024
MAX_XLSX_EXPANDED_BYTES = 50 * 1024 * 1024
MAX_XLSX_COMPRESSION_RATIO = 200
ANSWER_FILE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,39}\.txt$')
STATUS_LABELS = {'input_error': '입력 오류', 'awaiting_answer': '프롬프트 대기', 'answer_error': '답변 오류',
                 'needs_review': '검수 필요', 'approved': '승인됨'}
PRODUCT_FIELDS = {'name': '상품명', 'category': '카테고리', 'price': '가격', 'brand_color': '브랜드 색'}
FACT_FIELDS = {'id': 'fact_id', 'text': '문구', 'kind': '종류', 'evidence': '근거'}
IMAGE_FIELDS = {'path': '파일명', 'role': '역할', 'processing': '배경 제거 여부', 'alt': '파일명'}
REVIEW_FIELDS = {'text': '후기', 'rating': '별점', 'source': '출처', 'permission_confirmed': '허가 확인'}


def now():
    return datetime.now(timezone.utc).isoformat()


# Common validation messages in the words a seller would use (the same wording as the single-product screen).
REASONS = (('Field required', '필수 입력입니다'), ('String should have at least 1 character', '한 글자 이상 입력해 주세요'),
           ('String should match pattern', '형식이 맞지 않습니다'), ('permission_confirmed must be true', '허가 확인이 "예"여야 합니다'),
           ('claim requires evidence', '주장은 근거를 입력해야 합니다'), ('Input should be', '허용되지 않는 값입니다. 입력 가능:'))


def _reason(text: str) -> str:
    for english, korean in REASONS:
        if text.startswith(english):
            return korean + text[len(english):] if english == 'Input should be' else korean
    return text


def _error(sheet, row, column, reason):
    return {'sheet': sheet, 'row': row, 'column': column, 'reason': _reason(reason)}


# --- reading ---------------------------------------------------------------------------------------

def _cell(value) -> str:
    if value is None:
        return ''
    if isinstance(value, bool):
        return '예' if value else '아니오'
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def _rows(sheet: str, header: list, rows) -> list[tuple[int, dict]]:
    """``rows`` are raw value lists after the header; returns (Excel row number, {header: text})."""
    missing = [h for h in HEADERS[sheet] if h not in header]
    if missing:
        raise ValueError(f'{sheet} 시트(파일)에 열이 없습니다: {", ".join(missing)} (첫 줄은 열 이름이어야 합니다)')
    index = {h: header.index(h) for h in HEADERS[sheet]}
    out = []
    for number, values in rows:
        values = list(values)
        record = {h: _cell(values[i]) if i < len(values) else '' for h, i in index.items()}
        if any(record.values()):
            out.append((number, record))
    return out


def _xlsx_metadata(path: Path) -> tuple[list[str], str]:
    """Inspect archive metadata before expanding XML so compressed input stays bounded."""
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_XLSX_ENTRIES:
                raise ValueError(f'XLSX 압축 항목이 너무 많습니다 (최대 {MAX_XLSX_ENTRIES}개)')
            expanded = sum(info.file_size for info in infos)
            if expanded > MAX_XLSX_EXPANDED_BYTES:
                raise ValueError(f'XLSX 압축 해제 크기가 상한({MAX_XLSX_EXPANDED_BYTES:,}바이트)을 넘습니다')
            for info in infos:
                if info.file_size > MAX_XLSX_MEMBER_BYTES:
                    raise ValueError(f'XLSX 압축 해제 항목이 너무 큽니다: {info.filename}')
                if (info.file_size >= 1024 * 1024 and info.compress_size > 0
                        and info.file_size / info.compress_size > MAX_XLSX_COMPRESSION_RATIO):
                    raise ValueError(f'XLSX 압축률이 비정상적으로 높습니다: {info.filename}')
            names = [info.filename for info in infos]
            types = archive.read('[Content_Types].xml').decode('utf-8', 'replace') if '[Content_Types].xml' in names else ''
            return names, types
    except zipfile.BadZipFile as exc:
        raise ValueError(f'XLSX 파일을 열 수 없습니다: {path.name}') from exc


def _is_macro(path: Path) -> bool:
    names, types = _xlsx_metadata(path)
    return any(n.lower().endswith('vbaproject.bin') for n in names) or 'macroEnabled' in types


def read_sheets
def read_sheets(source: Path, max_bytes: int = MAX_BYTES) -> dict[str, list[tuple[int, dict]]]:
    """XLSX workbook (stored values only, no formula evaluation) or a folder of UTF-8 CSV files."""
    source = Path(source)
    if source.is_dir():
        files = {sheet: source / f'{sheet}.csv' for sheet in HEADERS}
        missing = [f'{s}.csv' for s in REQUIRED_SHEETS if not files[s].is_file()]
        if missing:
            raise ValueError(f'CSV 파일이 없습니다: {", ".join(missing)}')
        present = {s: p for s, p in files.items() if p.is_file()}
        if sum(p.stat().st_size for p in present.values()) > max_bytes:
            raise ValueError(f'파일 크기가 상한({max_bytes:,}바이트)을 넘습니다')
        sheets = {}
        for sheet, path in present.items():
            try:
                text = path.read_bytes().decode('utf-8-sig')
            except UnicodeDecodeError as exc:
                raise ValueError(f'{path.name}: UTF-8(BOM 허용) 인코딩만 지원합니다. 엑셀에서 "CSV UTF-8"로 다시 저장하세요.') from exc
            table = list(csv.reader(io.StringIO(text)))
            if not table:
                raise ValueError(f'{path.name}: 열 이름 줄이 없습니다')
            sheets[sheet] = _rows(sheet, [h.strip() for h in table[0]], enumerate(table[1:], 2))
        sheets.setdefault('reviews', [])
        return sheets
    if not source.is_file():
        raise ValueError(f'입력 파일이 없습니다: {source}')
    if source.suffix.lower() in ('.xlsm', '.xltm', '.xlam'):
        raise ValueError('매크로가 포함된 통합 문서(.xlsm 등)는 열지 않습니다. 매크로 없는 .xlsx로 저장하세요.')
    if source.suffix.lower() != '.xlsx':
        raise ValueError('XLSX 파일 또는 CSV 파일이 든 폴더만 지원합니다')
    if source.stat().st_size > max_bytes:
        raise ValueError(f'파일 크기가 상한({max_bytes:,}바이트)을 넘습니다')
    if _is_macro(source):
        raise ValueError('매크로가 포함된 통합 문서(.xlsm 등)는 열지 않습니다. 매크로 없는 .xlsx로 저장하세요.')
    from openpyxl import load_workbook
    try:
        book = load_workbook(source, read_only=True, data_only=True)  # stored values; formulas are not evaluated
    except Exception as exc:  # openpyxl raises several types for corrupt files
        raise ValueError(f'XLSX 파일을 읽을 수 없습니다: {exc}') from exc
    try:
        missing = [s for s in REQUIRED_SHEETS if s not in book.sheetnames]
        if missing:
            raise ValueError(f'시트가 없습니다: {", ".join(missing)}')
        sheets = {}
        for sheet in HEADERS:
            if sheet not in book.sheetnames:
                sheets[sheet] = []
                continue
            rows = book[sheet].iter_rows(values_only=True)
            header = [_cell(v) for v in next(rows, ())]
            sheets[sheet] = _rows(sheet, header, enumerate(rows, 2))
        return sheets
    finally:
        book.close()


# --- validation ------------------------------------------------------------------------------------

def _safe_relative(value: str) -> bool:
    if not value or '\\' in value or ':' in value or any(ord(c) < 32 for c in value):
        return False
    path = Path(value)
    return not path.is_absolute() and '..' not in path.parts


def _bool(value: str):
    lowered = value.strip().lower()
    if lowered in YES:
        return True
    if lowered in NO:
        return False
    return value  # left as text so validation reports the column


def _locate(loc, rows) -> tuple[str, int, str]:
    """Map a pydantic error location in ProductFacts to sheet·row·column."""
    head = loc[0] if loc else None
    if head == 'product' or head == 'notice' or head is None:
        column = PRODUCT_FIELDS.get(loc[1], '') if head == 'product' and len(loc) > 1 else ('안내 문구' if head == 'notice' else '')
        return 'products', rows['product'], column
    sheet, fields = {'facts': ('facts', FACT_FIELDS), 'images': ('images', IMAGE_FIELDS), 'reviews': ('reviews', REVIEW_FIELDS)}[head]
    index = loc[1] if len(loc) > 1 and isinstance(loc[1], int) else 0
    row = rows[sheet][index] if rows[sheet] else rows['product']
    column = fields.get(loc[2], '') if len(loc) > 2 else ''
    return (sheet if rows[sheet] else 'products'), row, column


def _validate_product(number, record, children, photo_root: Path):
    """Return (ProductFacts, photo folder, theme, profile, []) or (None, ..., errors)."""
    from .themes import load_theme
    from .export import load_profile
    errors = []
    theme = record['테마'] or 'classic'
    profile = record['프로필'] or 'generic'
    try:
        load_theme(theme)
    except ValueError:
        errors.append(_error('products', number, '테마', f'알 수 없는 테마: {theme} (classic, minimal, bold)'))
    try:
        load_profile(profile)
    except ValueError as exc:
        errors.append(_error('products', number, '프로필', str(exc)))
    folder = None
    if not _safe_relative(record['사진 폴더']):
        errors.append(_error('products', number, '사진 폴더', '사진 루트 아래의 상대 폴더 이름이어야 합니다 (절대 경로·..·역슬래시 불가)'))
    else:
        folder = (photo_root / record['사진 폴더']).resolve()
        if not folder.is_relative_to(photo_root) or not folder.is_dir():
            errors.append(_error('products', number, '사진 폴더', '사진 루트 아래에 이 폴더가 없습니다'))
            folder = None

    rows = {'product': number, 'facts': [], 'images': [], 'reviews': []}
    facts, images, reviews = [], [], []
    seen = set()
    for row, item in children['facts']:
        if item['fact_id'] in seen:
            errors.append(_error('facts', row, 'fact_id', f'같은 상품 안에서 fact_id가 중복됩니다: {item["fact_id"]}'))
            continue
        seen.add(item['fact_id'])
        fact = {'id': item['fact_id'], 'text': item['문구'], 'kind': KINDS.get(item['종류'], item['종류'])}
        if item['근거']:
            fact['evidence'] = item['근거']
        facts.append(fact); rows['facts'].append(row)
    for row, item in children['images']:
        if not _safe_relative(item['파일명']) or '/' in item['파일명']:
            errors.append(_error('images', row, '파일명', '사진 폴더 안의 파일 이름만 쓸 수 있습니다 (경로·..·역슬래시·제어 문자 불가)'))
            continue
        remove = _bool(item['배경 제거 여부'])
        images.append({'path': item['파일명'], 'role': ROLES.get(item['역할'], item['역할'] or 'other'),
                       'processing': {'remove_background': remove}})
        rows['images'].append(row)
    for row, item in children['reviews']:
        rating = item['별점']
        reviews.append({'text': item['후기'], 'rating': int(rating) if rating.isdigit() else rating,
                        'source': item['출처'], 'permission_confirmed': _bool(item['허가 확인'])})
        rows['reviews'].append(row)
    if not children['images']:
        errors.append(_error('products', number, '사진 폴더', 'images 시트에 이 상품의 사진이 없습니다'))
    if len(reviews) > 10:
        errors.append(_error('reviews', rows['reviews'][10], '후기', '후기는 상품마다 최대 10개까지 입력할 수 있습니다'))
    distinct_images = set()
    for index, image in enumerate(images):
        distinct_images.add(image['path'])
        if len(distinct_images) > 5:
            errors.append(_error('images', rows['images'][index], '파일명', '사진은 상품마다 서로 다른 파일 최대 5개까지 입력할 수 있습니다'))
            break
    if errors:
        return None, folder, theme, profile, errors

    data = {'schema_version': '1.0',
            'product': {'name': record['상품명'], 'category': record['카테고리'], 'price': record['가격'], 'brand_color': record['브랜드 색']},
            'facts': facts, 'images': images, 'reviews': reviews}
    if record['안내 문구']:
        data['notice'] = record['안내 문구']
    try:
        product = ProductFacts.model_validate(data)
    except ValidationError as exc:
        for item in exc.errors(include_url=False):
            sheet, row, column = _locate(item['loc'], rows)
            if not column and sheet == 'facts' and 'evidence' in item['msg']:
                column = '근거'
            if not column and sheet == 'reviews' and 'permission' in item['msg']:
                column = '허가 확인'
            errors.append(_error(sheet, row, column, item['msg'].removeprefix('Value error, ')))
        return None, folder, theme, profile, errors
    try:
        product.validate_images(folder)
    except ValueError as exc:
        match = re.match(r'images\.(.+?): (.*)', str(exc))
        name = match.group(1) if match else ''
        row = next((r for r, (_, i) in zip(rows['images'], children['images']) if i['파일명'] == name), number)
        errors.append(_error('images' if match else 'products', row, '파일명' if match else '사진 폴더',
                             match.group(2) if match else str(exc)))
        return None, folder, theme, profile, errors
    return product, folder, theme, profile, []


def import_batch(source: Path, photo_root: Path, output: Path, *, max_products: int = MAX_PRODUCTS, max_bytes: int = MAX_BYTES) -> Path:
    """Create ``output/batch-<id>/`` with one job per valid product and ``batch.json``."""
    photo_root = Path(photo_root).resolve(strict=True)
    sheets = read_sheets(source, max_bytes)
    if len(sheets['products']) > max_products:
        raise ValueError(f'상품은 한 번에 최대 {max_products}개까지 가져올 수 있습니다 (현재 {len(sheets["products"])}개)')
    errors, products, order = [], {}, []
    for number, record in sheets['products']:
        pid = record['product_id']
        if not PRODUCT_ID.fullmatch(pid):
            errors.append(_error('products', number, 'product_id', 'product_id는 영문·숫자·-·_ 1~40자여야 합니다'))
        elif pid in products:
            errors.append(_error('products', number, 'product_id', f'product_id가 중복됩니다: {pid} (먼저 나온 행만 사용)'))
        else:
            products[pid] = (number, record, {'facts': [], 'images': [], 'reviews': []})
            order.append(pid)
    for sheet in ('facts', 'images', 'reviews'):
        for number, record in sheets[sheet]:
            if record['product_id'] not in products:
                errors.append(_error(sheet, number, 'product_id', f'products 시트에 없는 product_id: {record["product_id"]}'))
            else:
                products[record['product_id']][2][sheet].append((number, record))

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    batch = Path(tempfile.mkdtemp(prefix='batch-', dir=output))
    entries = []
    for pid in order:
        number, record, children = products[pid]
        product, folder, theme, profile, problems = _validate_product(number, record, children, photo_root)
        entry = {'product_id': pid, 'name': record['상품명'], 'row': number, 'theme': theme, 'profile': profile,
                 'photo_folder': record['사진 폴더'], 'job': None, 'accepted_job': None, 'errors': problems,
                 'status': 'input_error', 'message': ''}
        if product is not None:
            try:
                job = create_job(product, folder, batch / 'products' / pid, theme=theme)
                entry.update(job=str(job.relative_to(batch)), status='awaiting_answer')
            except ValueError as exc:
                entry['errors'] = [_error('products', number, '사진 폴더', f'작업을 만들 수 없습니다: {exc}')]
        entries.append(entry)
    write_json(batch / 'batch.json', {'version': 1, 'id': batch.name, 'created_at': now(), 'source': Path(source).name,
                                      'photo_root': str(photo_root), 'products': entries, 'errors': errors})
    return batch


# --- status ----------------------------------------------------------------------------------------

def _source_name(value: str) -> str:
    """Read a stored source basename on either Windows or POSIX after a batch is moved."""
    return PureWindowsPath(value).name if '\\' in value else PurePosixPath(value).name


def _approval_is_current(job: Path, accepted: Path, manifest: dict) -> bool:
    """An approval is portable, but valid only for the exact source draft, facts and theme policy."""
    if not manifest.get('source_job') or _source_name(str(manifest['source_job'])) != job.name:
        return False
    try:
        if (job / 'draft.json').read_bytes() != (accepted / 'draft.json').read_bytes():
            return False
        if (job / 'facts.json').read_bytes() != (accepted / 'facts.json').read_bytes():
            return False
        source = read_json(job / 'manifest.json')
        from .themes import load_theme
        return (manifest.get('theme', 'classic') == source.get('theme', 'classic')
                and manifest.get('contrast_policy') == load_theme(source.get('theme', 'classic')).contrast_policy)
    except (OSError, ValueError, KeyError):
        return False


def _accepted_for(job: Path) -> Path | None:
    """Latest current approval for ``job``; portable when the whole batch folder moves."""
    found = []
    for candidate in job.parent.glob('job-*'):
        manifest = candidate / 'manifest.json'
        if candidate == job or candidate.is_symlink() or not manifest.is_file():
            continue
        data = read_json(manifest)
        if data.get('review_accepted') and _approval_is_current(job, candidate, data):
            found.append((data.get('accepted_at', ''), candidate))
    return max(found)[1] if found else None


def _status
def _status(batch: Path, entry: dict) -> str:
    if not entry.get('job'):
        return 'input_error'
    job = batch / entry['job']
    accepted = _accepted_for(job)
    entry['accepted_job'] = str(accepted.relative_to(batch)) if accepted else None
    if accepted:
        return 'approved'
    if (job / 'draft.json').is_file():
        return 'needs_review'
    if read_json(job / 'manifest.json').get('status') == 'needs_correction':
        return 'answer_error'
    return 'awaiting_answer'


def load_batch(batch: Path) -> dict:
    batch = Path(batch)
    data = read_json(batch / 'batch.json')
    if not isinstance(data, dict) or data.get('version') != 1:
        raise ValueError('batch.json 형식이 올바르지 않습니다')
    return data


def batch_status(batch: Path) -> list[dict]:
    """Recompute every product's status from its job folders and save it (safe to call any time)."""
    batch = Path(batch)
    data = load_batch(batch)
    for entry in data['products']:
        entry['status'] = _status(batch, entry)
    write_json(batch / 'batch.json', data)
    return data['products']


def list_batches(output: Path) -> list[dict]:
    out = []
    for folder in sorted(Path(output).glob('batch-*'), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = load_batch(folder)
        except (OSError, ValueError):
            continue
        out.append({'path': str(folder), 'created_at': data['created_at'], 'source': data['source'], 'count': len(data['products'])})
    return out


# --- template --------------------------------------------------------------------------------------

EXAMPLE = {
    'products': [{'product_id': 'example-1', '상품명': '예시 보틀', '카테고리': '생활용품', '가격': '12,000원', '브랜드 색': '#305b46',
                  '테마': 'classic', '프로필': 'generic', '사진 폴더': 'example-1', '안내 문구': '예시 상품입니다. 실제 상품 정보로 바꾸세요.'}],
    'facts': [{'product_id': 'example-1', 'fact_id': 'design', '문구': '간결한 형태의 보틀', '종류': '특징', '근거': ''},
              {'product_id': 'example-1', 'fact_id': 'spec-demo', '문구': '용량 500ml', '종류': '스펙', '근거': ''},
              {'product_id': 'example-1', 'fact_id': 'usage', '문구': '사용 전 설명서를 확인한다', '종류': '사용법', '근거': ''}],
    'images': [{'product_id': 'example-1', '파일명': 'main.png', '역할': '대표', '배경 제거 여부': '아니오'}],
    'reviews': [],
}


def write_template(path: Path, rows: int = MAX_PRODUCTS * 20) -> Path:
    """Empty workbook with column descriptions (header comments), one example row and dropdown lists."""
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    book = Workbook()
    book.remove(book.active)
    lists = {'테마': ('classic,minimal,bold', True), '프로필': ('generic,smartstore,coupang', False),
             '종류': (','.join(KINDS), True), '역할': (','.join(ROLES), True),
             '배경 제거 여부': ('예,아니오', True), '허가 확인': ('예,아니오', True)}
    for sheet, headers in HEADERS.items():
        ws = book.create_sheet(sheet)
        ws.append(headers)
        for column, header in enumerate(headers, 1):
            cell = ws.cell(1, column)
            cell.comment = Comment(DESCRIPTIONS[header], 'detail-page-auto')
            cell.font = Font(bold=True)
            cell.fill = PatternFill('solid', fgColor='E5EEE7')
            ws.column_dimensions[get_column_letter(column)].width = max(14, len(header) * 3)
            if header in lists:
                options, strict = lists[header]
                rule = DataValidation(type='list', formula1=f'"{options}"', allow_blank=True, showErrorMessage=strict)
                rule.add(f'{get_column_letter(column)}2:{get_column_letter(column)}{rows}')
                ws.add_data_validation(rule)
        for record in EXAMPLE[sheet]:
            ws.append([record.get(h, '') for h in headers])
        ws.freeze_panes = 'A2'
    guide = book.create_sheet('안내', 0)
    lines = ['상품 목록 템플릿 사용법',
             '1. products 시트: 상품 1개 = 1행. product_id로 다른 시트와 연결합니다.',
             '2. facts 시트: 판매자가 확인한 사실. 주장은 근거가 필요합니다.',
             '3. images 시트: 사진 폴더 안의 파일 이름. 사진 폴더는 가져올 때 지정한 사진 루트 폴더 아래에 있어야 합니다.',
             '4. reviews 시트(선택): 실제 고객 후기만, 허가 확인 열에 "예". AI는 후기·별점·가격을 만들지 않습니다.',
             '   예: product_id=example-1, 후기=실제 받은 후기 원문, 별점=5, 출처=스토어 리뷰, 허가 확인=예',
             '5. 각 열 이름에 마우스를 올리면 설명이 보입니다. example-1 예시 행은 지우거나 실제 상품으로 바꾸세요.',
             '6. 수식은 계산하지 않고 저장된 값만 읽습니다. 매크로 파일(.xlsm)은 열지 않습니다.',
             f'7. 한 번에 최대 {MAX_PRODUCTS}개 상품, 파일 크기 {MAX_BYTES // (1024 * 1024)}MB까지 가져옵니다.']
    for line in lines:
        guide.append([line])
    guide.column_dimensions['A'].width = 110
    path = Path(path)
    book.save(path)
    return path


# --- prompts, answers, CLI generation, export -----------------------------------------------------

PENDING = ('awaiting_answer', 'answer_error')


def _job(batch: Path, entry: dict) -> Path:
    job = (batch / entry['job']).resolve()
    if not job.is_relative_to(batch.resolve()):
        raise ValueError('batch.json의 작업 경로가 일괄 작업 폴더 밖을 가리킵니다')
    return job


def export_prompts(batch: Path):
    """``prompts/<product_id>.md`` for every product still waiting for an answer (fix prompt after a failed
    answer), plus one ZIP of them. One prompt never contains more than one product."""
    batch = Path(batch)
    entries = batch_status(batch)
    folder = batch / 'prompts'
    folder.mkdir(exist_ok=True)
    for old in folder.glob('*.md'):
        old.unlink()
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for entry in entries:
            if entry['status'] not in PENDING:
                continue
            job = _job(batch, entry)
            source = job / ('fix-prompt.md' if entry['status'] == 'answer_error' and (job / 'fix-prompt.md').is_file() else 'prompt.md')
            text = source.read_text(encoding='utf-8')
            (folder / f"{entry['product_id']}.md").write_text(text, encoding='utf-8')
            archive.writestr(f"prompts/{entry['product_id']}.md", text)
    return folder, f'{batch.name}-prompts.zip', output.getvalue()


def ingest_answers(batch: Path, answers: Path) -> dict:
    """Read ``answers/<product_id>.txt`` for each waiting product and validate it with ``ingest_job``.

    Only exact ``<product_id>.txt`` files directly in the folder are read (no links). Products without a
    file stay waiting; unknown files are reported, never guessed.
    """
    from .workflow import ingest_job
    batch, answers = Path(batch), Path(answers)
    if not answers.is_dir():
        raise ValueError(f'답변 폴더가 없습니다: {answers}')
    entries = batch_status(batch)
    ids = {e['product_id'] for e in entries}
    report = {'unknown_files': sorted(p.name for p in answers.glob('*.txt') if p.stem not in ids)}
    for entry in entries:
        pid = entry['product_id']
        if entry['status'] not in PENDING:
            report[pid] = {'result': 'skipped', 'message': STATUS_LABELS[entry['status']]}
            continue
        path = answers / f'{pid}.txt'
        if path.is_symlink() or not path.is_file():
            report[pid] = {'result': 'missing', 'message': f'{pid}.txt 답변 파일이 없습니다'}
            continue
        try:
            text = path.read_bytes().decode('utf-8-sig')
            ingest_job(_job(batch, entry), text, source_label='batch:' + path.name)
            report[pid] = {'result': 'ok', 'message': ''}
        except UnicodeDecodeError:
            report[pid] = {'result': 'error', 'message': f'{pid}.txt: UTF-8 텍스트가 아닙니다'}
        except ValueError as exc:
            report[pid] = {'result': 'error', 'message': str(exc)}
    _remember(batch, report)
    return report


def ingest_uploaded_answers(batch: Path, uploads) -> dict:
    """Ingest only files selected for this action; never replay persistent stale answers."""
    batch = Path(batch).resolve(strict=True)
    staging = Path(tempfile.mkdtemp(prefix='.answer-upload-', dir=batch))
    try:
        seen = set()
        for name, payload in uploads:
            if not isinstance(name, str) or '\\' in name or '/' in name or not ANSWER_FILE.fullmatch(name):
                raise ValueError(f'답변 파일 이름은 <product_id>.txt여야 합니다: {name}')
            if name in seen:
                raise ValueError(f'답변 파일 이름이 중복됩니다: {name}')
            seen.add(name)
            if not isinstance(payload, bytes):
                raise ValueError(f'답변 파일을 읽을 수 없습니다: {name}')
            (staging / name).write_bytes(payload)
        return ingest_answers(batch, staging)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def generate_batch(batch: Path, provider, max_attempts: int = 3) -> dict:
    """Run a subscription CLI for each waiting product, one after another.

    A provider error (usage limit, login, timeout) stops the run at once without retrying, so no further
    quota is spent; remaining products stay "프롬프트 대기".
    """
    from .providers import ProviderError
    from .workflow import generate_job
    batch = Path(batch)
    result = {'stopped': False, 'reason': '', 'products': {}}
    for entry in batch_status(batch):
        if entry['status'] not in PENDING:
            continue
        pid = entry['product_id']
        try:
            generate_job(None, None, None, provider, max_attempts=max_attempts, source_label='batch:cli:' + provider.name,
                         existing_job=_job(batch, entry))
            result['products'][pid] = {'result': 'ok', 'message': ''}
        except ProviderError as exc:
            result.update(stopped=True, reason=str(exc))
            result['products'][pid] = {'result': 'stopped', 'message': str(exc)}
            break
        except ValueError as exc:
            result['products'][pid] = {'result': 'error', 'message': str(exc)}
    _remember(batch, result['products'])
    return result


def export_batch(batch: Path):
    """ZIP of approved products only, one folder per product, each exported with its own profile."""
    from .export import build_export_zip, current_bundle, export_bundle
    batch = Path(batch)
    entries = batch_status(batch)
    report = {}
    output = io.BytesIO()
    exported = 0
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for entry in entries:
            pid = entry['product_id']
            if entry['status'] != 'approved':
                report[pid] = {'result': 'skipped', 'message': f"승인되지 않음 ({STATUS_LABELS[entry['status']]}) — ⑥에서 상품별로 승인하세요"}
                continue
            try:
                accepted = (batch / entry['accepted_job']).resolve()
                outcome = export_bundle(current_bundle(accepted), entry['profile'])
            except ValueError as exc:
                report[pid] = {'result': 'error', 'message': str(exc)}
                continue
            if outcome['status'] == 'error':
                report[pid] = {'result': 'error', 'message': '; '.join(c['message'] for c in outcome['checks'] if c['level'] == 'error')}
                continue
            name, data = build_export_zip(outcome['folder'])
            with zipfile.ZipFile(io.BytesIO(data)) as single:
                for item in single.namelist():
                    archive.writestr(f'{pid}/{item}', single.read(item))
            report[pid] = {'result': 'ok', 'message': name, 'status': outcome['status'],
                           'warnings': [c['message'] for c in outcome['checks'] if c['level'] == 'warning']}
            exported += 1
        if not exported:
            raise ValueError('승인된 상품이 없어 내보낼 것이 없습니다. 상품마다 ⑥에서 승인하세요.')
        archive.writestr('batch-export.json', json.dumps({'batch': batch.name, 'created_at': now(), 'products': report},
                                                         ensure_ascii=False, indent=2) + '\n')
    return f'{batch.name}-approved.zip', output.getvalue(), report


def _remember(batch: Path, results: dict) -> None:
    """Keep the last per-product message in batch.json so the screen can show it after reopening."""
    data = load_batch(batch)
    for entry in data['products']:
        outcome = results.get(entry['product_id'])
        if isinstance(outcome, dict) and outcome.get('result') != 'skipped':
            entry['message'] = outcome.get('message', '')
        entry['status'] = _status(batch, entry)
    write_json(batch / 'batch.json', data)
