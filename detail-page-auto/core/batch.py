"""M5-C: create many product jobs from one sheet (XLSX or CSV) and track them as a batch.

Each product becomes an ordinary job (``create_job``) under ``outputs/batch-<id>/products/<product_id>/``.
Broken products are excluded with errors located as sheet��row��column��reason (Excel row numbers);
the rest continue. Prompts never mix products. There is no bulk approval: every product goes
through the normal �� checklist; only approved products are exported.
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
    'products': ['product_id', '��ǰ��', 'ī�װ���', '����', '�귣�� ��', '�׸�', '������', '���� ����', '�ȳ� ����'],
    'facts': ['product_id', 'fact_id', '����', '����', '�ٰ�'],
    'images': ['product_id', '���ϸ�', '����', '��� ���� ����'],
    'reviews': ['product_id', '�ı�', '����', '��ó', '�㰡 Ȯ��'],
    'references': ['product_id', 'reference_id', '��', '����', '����', '��ó �޸�'],
}
REQUIRED_SHEETS = ('products', 'facts', 'images')
DESCRIPTIONS = {
    'product_id': '��ǰ�� �����ϴ� �̸�. ���������ڡ�-��_ 1~40��. ���� �̸��� ���Դϴ�.',
    '��ǰ��': '��ǰ �̸� (�ʼ�)', 'ī�װ���': '�з� (�ʼ�)', '����': '�Ǹ� ���� ���� (�ʼ�). AI�� ������ ������ �ʽ��ϴ�.',
    '�귣�� ��': '#RRGGBB ���� (��: #305b46)', '�׸�': 'classic(�⺻) / minimal / bold', '������': '�������� ������: generic(�⺻) / smartstore / coupang / ����� ������ �̸�',
    '���� ����': '���� ��Ʈ ���� �Ʒ��� ��ǰ�� ���� �̸�. ��Ʈ �� ��δ� �� �� �����ϴ�.', '�ȳ� ����': '���� �ȳ�(����)',
    'fact_id': '��� id (��ǰ �ȿ��� �ߺ� �Ұ�). AI �亯�� �ٰŷ� ���Դϴ�.', '����': '�Ǹ��ڰ� Ȯ���� ��� ���� (�ִ� 500��)',
    '����': '���� / Ư¡ / ���� / ���� / ��Ÿ. ������ �ٰŰ� �ʿ��մϴ�.', '�ٰ�': '������ �ٰ� (������ �� �ʼ�)',
    '���ϸ�': '���� ���� ���� PNG/JPEG ���� �̸�', '����': '��ǥ / Ư¡ / �ذ� / ��Ÿ (ù ������ ��ǥ ����)',
    '��� ���� ����': '�� / �ƴϿ� (�⺻ �ƴϿ�)', '�ı�': '���� ���� �ı� ����. AI�� �ı⸦ ������ �ʽ��ϴ�.',
    '����': '1~5 ����', '��ó': '�ı⸦ ���� ��', '�㰡 Ȯ��': '�� = ��� �㰡�� Ȯ���� (�ʼ�)',
    'reference_id': '���� �ڷ� id. ��ǰ ��� fact_id�� ��ĥ �� �����ϴ�.', '��': '�ڷḦ �˾ƺ� �̸� (��: ����� A ��������)',
    '����': '���� ������ �ٿ����� ���� �ڷ� (�ִ� 5,000��)', '��ó �޸�': '��ó ���. URL�� ��� ���α׷��� �������� �ʽ��ϴ�.',
}
KINDS = {'����': 'spec', 'Ư¡': 'feature', '����': 'usage', '����': 'claim', '��Ÿ': 'other'}
ROLES = {'��ǥ': 'hero', 'Ư¡': 'feature', '�ذ�': 'solution', '��Ÿ': 'other'}
REFERENCE_KINDS = {'�����': 'competitor', '���� ��Ҹ�': 'customer_voice', '��Ÿ': 'other'}
YES = {'��', 'y', 'yes', 'true', '1', 'o'}
NO = {'', '�ƴϿ�', '�ƴϿ�', 'n', 'no', 'false', '0', 'x'}
PRODUCT_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$')
MAX_PRODUCTS = 50
MAX_BYTES = 5 * 1024 * 1024
MAX_XLSX_ENTRIES = 1000
MAX_XLSX_MEMBER_BYTES = 20 * 1024 * 1024
MAX_XLSX_EXPANDED_BYTES = 50 * 1024 * 1024
MAX_XLSX_COMPRESSION_RATIO = 200
ANSWER_FILE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,39}\.txt$')
STATUS_LABELS = {'input_error': '�Է� ����', 'awaiting_answer': '������Ʈ ���', 'answer_error': '�亯 ����',
                 'needs_review': '�˼� �ʿ�', 'approved': '���ε�'}
PRODUCT_FIELDS = {'name': '��ǰ��', 'category': 'ī�װ���', 'price': '����', 'brand_color': '�귣�� ��'}
FACT_FIELDS = {'id': 'fact_id', 'text': '����', 'kind': '����', 'evidence': '�ٰ�'}
IMAGE_FIELDS = {'path': '���ϸ�', 'role': '����', 'processing': '��� ���� ����', 'alt': '���ϸ�'}
REVIEW_FIELDS = {'text': '�ı�', 'rating': '����', 'source': '��ó', 'permission_confirmed': '�㰡 Ȯ��'}
REFERENCE_FIELDS = {'id': 'reference_id', 'label': '��', 'kind': '����', 'text': '����', 'source_note': '��ó �޸�'}


def now():
    return datetime.now(timezone.utc).isoformat()


# Common validation messages in the words a seller would use (the same wording as the single-product screen).
REASONS = (('Field required', '�ʼ� �Է��Դϴ�'), ('String should have at least 1 character', '�� ���� �̻� �Է��� �ּ���'),
           ('String should match pattern', '������ ���� �ʽ��ϴ�'), ('permission_confirmed must be true', '�㰡 Ȯ���� "��"���� �մϴ�'),
           ('claim requires evidence', '������ �ٰŸ� �Է��ؾ� �մϴ�'), ('Input should be', '������ �ʴ� ���Դϴ�. �Է� ����:'))


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
        return '��' if value else '�ƴϿ�'
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def _rows(sheet: str, header: list, rows) -> list[tuple[int, dict]]:
    """``rows`` are raw value lists after the header; returns (Excel row number, {header: text})."""
    missing = [h for h in HEADERS[sheet] if h not in header]
    if missing:
        raise ValueError(f'{sheet} ��Ʈ(����)�� ���� �����ϴ�: {", ".join(missing)} (ù ���� �� �̸��̾�� �մϴ�)')
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
                raise ValueError(f'XLSX ���� �׸��� �ʹ� �����ϴ� (�ִ� {MAX_XLSX_ENTRIES}��)')
            expanded = sum(info.file_size for info in infos)
            if expanded > MAX_XLSX_EXPANDED_BYTES:
                raise ValueError(f'XLSX ���� ���� ũ�Ⱑ ����({MAX_XLSX_EXPANDED_BYTES:,}����Ʈ)�� �ѽ��ϴ�')
            for info in infos:
                if info.file_size > MAX_XLSX_MEMBER_BYTES:
                    raise ValueError(f'XLSX ���� ���� �׸��� �ʹ� Ů�ϴ�: {info.filename}')
                if (info.file_size >= 1024 * 1024 and info.compress_size > 0
                        and info.file_size / info.compress_size > MAX_XLSX_COMPRESSION_RATIO):
                    raise ValueError(f'XLSX ������� ������������ �����ϴ�: {info.filename}')
            names = [info.filename for info in infos]
            types = archive.read('[Content_Types].xml').decode('utf-8', 'replace') if '[Content_Types].xml' in names else ''
            return names, types
    except zipfile.BadZipFile as exc:
        raise ValueError(f'XLSX ������ �� �� �����ϴ�: {path.name}') from exc


def _is_macro(path: Path) -> bool:
    names, types = _xlsx_metadata(path)
    return any(n.lower().endswith('vbaproject.bin') for n in names) or 'macroEnabled' in types


def read_sheets(source: Path, max_bytes: int = MAX_BYTES) -> dict[str, list[tuple[int, dict]]]:
    """XLSX workbook (stored values only, no formula evaluation) or a folder of UTF-8 CSV files."""
    source = Path(source)
    if source.is_dir():
        files = {sheet: source / f'{sheet}.csv' for sheet in HEADERS}
        missing = [f'{s}.csv' for s in REQUIRED_SHEETS if not files[s].is_file()]
        if missing:
            raise ValueError(f'CSV ������ �����ϴ�: {", ".join(missing)}')
        present = {s: p for s, p in files.items() if p.is_file()}
        if sum(p.stat().st_size for p in present.values()) > max_bytes:
            raise ValueError(f'���� ũ�Ⱑ ����({max_bytes:,}����Ʈ)�� �ѽ��ϴ�')
        sheets = {}
        for sheet, path in present.items():
            try:
                text = path.read_bytes().decode('utf-8-sig')
            except UnicodeDecodeError as exc:
                raise ValueError(f'{path.name}: UTF-8(BOM ���) ���ڵ��� �����մϴ�. �������� "CSV UTF-8"�� �ٽ� �����ϼ���.') from exc
            table = list(csv.reader(io.StringIO(text)))
            if not table:
                raise ValueError(f'{path.name}: �� �̸� ���� �����ϴ�')
            sheets[sheet] = _rows(sheet, [h.strip() for h in table[0]], enumerate(table[1:], 2))
        sheets.setdefault('reviews', [])
        sheets.setdefault('references', [])
        return sheets
    if not source.is_file():
        raise ValueError(f'�Է� ������ �����ϴ�: {source}')
    if source.suffix.lower() in ('.xlsm', '.xltm', '.xlam'):
        raise ValueError('��ũ�ΰ� ���Ե� ���� ����(.xlsm ��)�� ���� �ʽ��ϴ�. ��ũ�� ���� .xlsx�� �����ϼ���.')
    if source.suffix.lower() != '.xlsx':
        raise ValueError('XLSX ���� �Ǵ� CSV ������ �� ������ �����մϴ�')
    if source.stat().st_size > max_bytes:
        raise ValueError(f'���� ũ�Ⱑ ����({max_bytes:,}����Ʈ)�� �ѽ��ϴ�')
    if _is_macro(source):
        raise ValueError('��ũ�ΰ� ���Ե� ���� ����(.xlsm ��)�� ���� �ʽ��ϴ�. ��ũ�� ���� .xlsx�� �����ϼ���.')
    from openpyxl import load_workbook
    try:
        book = load_workbook(source, read_only=True, data_only=True)  # stored values; formulas are not evaluated
    except Exception as exc:  # openpyxl raises several types for corrupt files
        raise ValueError(f'XLSX ������ ���� �� �����ϴ�: {exc}') from exc
    try:
        missing = [s for s in REQUIRED_SHEETS if s not in book.sheetnames]
        if missing:
            raise ValueError(f'��Ʈ�� �����ϴ�: {", ".join(missing)}')
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
    """Map a pydantic error location in ProductFacts to sheet��row��column."""
    head = loc[0] if loc else None
    if head == 'product' or head == 'notice' or head is None:
        column = PRODUCT_FIELDS.get(loc[1], '') if head == 'product' and len(loc) > 1 else ('�ȳ� ����' if head == 'notice' else '')
        return 'products', rows['product'], column
    sheet, fields = {'facts': ('facts', FACT_FIELDS), 'images': ('images', IMAGE_FIELDS),
                     'reviews': ('reviews', REVIEW_FIELDS), 'references': ('references', REFERENCE_FIELDS)}[head]
    index = loc[1] if len(loc) > 1 and isinstance(loc[1], int) else 0
    row = rows[sheet][index] if rows[sheet] else rows['product']
    column = fields.get(loc[2], '') if len(loc) > 2 else ''
    return (sheet if rows[sheet] else 'products'), row, column


def _validate_product(number, record, children, photo_root: Path):
    """Return (ProductFacts, photo folder, theme, profile, []) or (None, ..., errors)."""
    from .themes import load_theme
    from .export import load_profile
    errors = []
    theme = record['�׸�'] or 'classic'
    profile = record['������'] or 'generic'
    try:
        load_theme(theme)
    except ValueError:
        errors.append(_error('products', number, '�׸�', f'�� �� ���� �׸�: {theme} (classic, minimal, bold)'))
    try:
        load_profile(profile)
    except ValueError as exc:
        errors.append(_error('products', number, '������', str(exc)))
    folder = None
    if not _safe_relative(record['���� ����']):
        errors.append(_error('products', number, '���� ����', '���� ��Ʈ �Ʒ��� ��� ���� �̸��̾�� �մϴ� (���� ��Ρ�..���������� �Ұ�)'))
    else:
        folder = (photo_root / record['���� ����']).resolve()
        if not folder.is_relative_to(photo_root) or not folder.is_dir():
            errors.append(_error('products', number, '���� ����', '���� ��Ʈ �Ʒ��� �� ������ �����ϴ�'))
            folder = None

    rows = {'product': number, 'facts': [], 'images': [], 'reviews': [], 'references': []}
    facts, images, reviews, references = [], [], [], []
    seen = set()
    for row, item in children['facts']:
        if item['fact_id'] in seen:
            errors.append(_error('facts', row, 'fact_id', f'���� ��ǰ �ȿ��� fact_id�� �ߺ��˴ϴ�: {item["fact_id"]}'))
            continue
        seen.add(item['fact_id'])
        fact = {'id': item['fact_id'], 'text': item['����'], 'kind': KINDS.get(item['����'], item['����'])}
        if item['�ٰ�']:
            fact['evidence'] = item['�ٰ�']
        facts.append(fact); rows['facts'].append(row)
    for row, item in children['images']:
        if not _safe_relative(item['���ϸ�']) or '/' in item['���ϸ�']:
            errors.append(_error('images', row, '���ϸ�', '���� ���� ���� ���� �̸��� �� �� �ֽ��ϴ� (��Ρ�..���������á����� ���� �Ұ�)'))
            continue
        remove = _bool(item['��� ���� ����'])
        images.append({'path': item['���ϸ�'], 'role': ROLES.get(item['����'], item['����'] or 'other'),
                       'processing': {'remove_background': remove}})
        rows['images'].append(row)
    for row, item in children['reviews']:
        rating = item['����']
        reviews.append({'text': item['�ı�'], 'rating': int(rating) if rating.isdigit() else rating,
                        'source': item['��ó'], 'permission_confirmed': _bool(item['�㰡 Ȯ��'])})
        rows['reviews'].append(row)
    for row, item in children['references']:
        references.append({'id': item['reference_id'], 'label': item['��'],
                           'kind': REFERENCE_KINDS.get(item['����'], item['����']),
                           'text': item['����'], 'source_note': item['��ó �޸�']})
        rows['references'].append(row)
    if not children['images']:
        errors.append(_error('products', number, '���� ����', 'images ��Ʈ�� �� ��ǰ�� ������ �����ϴ�'))
    if len(reviews) > 10:
        errors.append(_error('reviews', rows['reviews'][10], '�ı�', '�ı�� ��ǰ���� �ִ� 10������ �Է��� �� �ֽ��ϴ�'))
    distinct_images = set()
    for index, image in enumerate(images):
        distinct_images.add(image['path'])
        if len(distinct_images) > 5:
            errors.append(_error('images', rows['images'][index], '���ϸ�', '������ ��ǰ���� ���� �ٸ� ���� �ִ� 5������ �Է��� �� �ֽ��ϴ�'))
            break
    if errors:
        return None, folder, theme, profile, errors

    data = {'schema_version': '1.0',
            'product': {'name': record['��ǰ��'], 'category': record['ī�װ���'], 'price': record['����'], 'brand_color': record['�귣�� ��']},
            'facts': facts, 'images': images, 'reviews': reviews, 'references': references}
    if record['�ȳ� ����']:
        data['notice'] = record['�ȳ� ����']
    try:
        product = ProductFacts.model_validate(data)
    except ValidationError as exc:
        for item in exc.errors(include_url=False):
            sheet, row, column = _locate(item['loc'], rows)
            if not column and sheet == 'facts' and 'evidence' in item['msg']:
                column = '�ٰ�'
            if not column and sheet == 'reviews' and 'permission' in item['msg']:
                column = '�㰡 Ȯ��'
            errors.append(_error(sheet, row, column, item['msg'].removeprefix('Value error, ')))
        return None, folder, theme, profile, errors
    try:
        product.validate_images(folder)
    except ValueError as exc:
        match = re.match(r'images\.(.+?): (.*)', str(exc))
        name = match.group(1) if match else ''
        row = next((r for r, (_, i) in zip(rows['images'], children['images']) if i['���ϸ�'] == name), number)
        errors.append(_error('images' if match else 'products', row, '���ϸ�' if match else '���� ����',
                             match.group(2) if match else str(exc)))
        return None, folder, theme, profile, errors
    return product, folder, theme, profile, []


def import_batch(source: Path, photo_root: Path, output: Path, *, max_products: int = MAX_PRODUCTS, max_bytes: int = MAX_BYTES) -> Path:
    """Create ``output/batch-<id>/`` with one job per valid product and ``batch.json``."""
    photo_root = Path(photo_root).resolve(strict=True)
    sheets = read_sheets(source, max_bytes)
    if len(sheets['products']) > max_products:
        raise ValueError(f'��ǰ�� �� ���� �ִ� {max_products}������ ������ �� �ֽ��ϴ� (���� {len(sheets["products"])}��)')
    errors, products, order = [], {}, []
    for number, record in sheets['products']:
        pid = record['product_id']
        if not PRODUCT_ID.fullmatch(pid):
            errors.append(_error('products', number, 'product_id', 'product_id�� ���������ڡ�-��_ 1~40�ڿ��� �մϴ�'))
        elif pid in products:
            errors.append(_error('products', number, 'product_id', f'product_id�� �ߺ��˴ϴ�: {pid} (���� ���� �ุ ���)'))
        else:
            products[pid] = (number, record, {'facts': [], 'images': [], 'reviews': [], 'references': []})
            order.append(pid)
    for sheet in ('facts', 'images', 'reviews', 'references'):
        for number, record in sheets[sheet]:
            if record['product_id'] not in products:
                errors.append(_error(sheet, number, 'product_id', f'products ��Ʈ�� ���� product_id: {record["product_id"]}'))
            else:
                products[record['product_id']][2][sheet].append((number, record))

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    batch = Path(tempfile.mkdtemp(prefix='batch-', dir=output))
    entries = []
    for pid in order:
        number, record, children = products[pid]
        product, folder, theme, profile, problems = _validate_product(number, record, children, photo_root)
        entry = {'product_id': pid, 'name': record['��ǰ��'], 'row': number, 'theme': theme, 'profile': profile,
                 'photo_folder': record['���� ����'], 'job': None, 'accepted_job': None, 'errors': problems,
                 'status': 'input_error', 'message': ''}
        if product is not None:
            try:
                job = create_job(product, folder, batch / 'products' / pid, theme=theme)
                entry.update(job=str(job.relative_to(batch)), status='awaiting_answer')
            except ValueError as exc:
                entry['errors'] = [_error('products', number, '���� ����', f'�۾��� ���� �� �����ϴ�: {exc}')]
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
        raise ValueError('batch.json ������ �ùٸ��� �ʽ��ϴ�')
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
    'products': [{'product_id': 'example-1', '��ǰ��': '���� ��Ʋ', 'ī�װ���': '��Ȱ��ǰ', '����': '12,000��', '�귣�� ��': '#305b46',
                  '�׸�': 'classic', '������': 'generic', '���� ����': 'example-1', '�ȳ� ����': '���� ��ǰ�Դϴ�. ���� ��ǰ ������ �ٲټ���.'}],
    'facts': [{'product_id': 'example-1', 'fact_id': 'design', '����': '������ ������ ��Ʋ', '����': 'Ư¡', '�ٰ�': ''},
              {'product_id': 'example-1', 'fact_id': 'spec-demo', '����': '�뷮 500ml', '����': '����', '�ٰ�': ''},
              {'product_id': 'example-1', 'fact_id': 'usage', '����': '��� �� �������� Ȯ���Ѵ�', '����': '����', '�ٰ�': ''}],
    'images': [{'product_id': 'example-1', '���ϸ�': 'main.png', '����': '��ǥ', '��� ���� ����': '�ƴϿ�'}],
    'reviews': [],
    'references': [],
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
    lists = {('products','�׸�'): ('classic,minimal,bold', True),
             ('products','������'): ('generic,smartstore,coupang', False),
             ('facts','����'): (','.join(KINDS), True),
             ('references','����'): (','.join(REFERENCE_KINDS), True),
             ('images','����'): (','.join(ROLES), True),
             ('images','��� ���� ����'): ('��,�ƴϿ�', True),
             ('reviews','�㰡 Ȯ��'): ('��,�ƴϿ�', True)}
    for sheet, headers in HEADERS.items():
        ws = book.create_sheet(sheet)
        ws.append(headers)
        for column, header in enumerate(headers, 1):
            cell = ws.cell(1, column)
            description = ('����� / ���� ��Ҹ� / ��Ÿ' if sheet == 'references' and header == '����'
                           else DESCRIPTIONS[header])
            cell.comment = Comment(description, 'detail-page-auto')
            cell.font = Font(bold=True)
            cell.fill = PatternFill('solid', fgColor='E5EEE7')
            ws.column_dimensions[get_column_letter(column)].width = max(14, len(header) * 3)
            if (sheet,header) in lists:
                options, strict = lists[(sheet,header)]
                rule = DataValidation(type='list', formula1=f'"{options}"', allow_blank=True, showErrorMessage=strict)
                rule.add(f'{get_column_letter(column)}2:{get_column_letter(column)}{rows}')
                ws.add_data_validation(rule)
        for record in EXAMPLE[sheet]:
            ws.append([record.get(h, '') for h in headers])
        ws.freeze_panes = 'A2'
    guide = book.create_sheet('�ȳ�', 0)
    lines = ['��ǰ ��� ���ø� ����',
             '1. products ��Ʈ: ��ǰ 1�� = 1��. product_id�� �ٸ� ��Ʈ�� �����մϴ�.',
             '2. facts ��Ʈ: �Ǹ��ڰ� Ȯ���� ���. ������ �ٰŰ� �ʿ��մϴ�.',
             '3. images ��Ʈ: ���� ���� ���� ���� �̸�. ���� ������ ������ �� ������ ���� ��Ʈ ���� �Ʒ��� �־�� �մϴ�.',
             '4. reviews ��Ʈ(����): ���� ���� �ı⸸, �㰡 Ȯ�� ���� "��". AI�� �ı⡤������������ ������ �ʽ��ϴ�.',
             '   ��: product_id=example-1, �ı�=���� ���� �ı� ����, ����=5, ��ó=����� ����, �㰡 Ȯ��=��',
             '5. references ��Ʈ(����): ���� �ٿ����� ���� �ڷ��̸� URL�� ��ϸ� �ϰ� �������� �ʽ��ϴ�.',
             '6. �� �� �̸��� ���콺�� �ø��� ������ ���Դϴ�. example-1 ���� ���� ����ų� ���� ��ǰ���� �ٲټ���.',
             '7. ������ ������� �ʰ� ����� ���� �н��ϴ�. ��ũ�� ����(.xlsm)�� ���� �ʽ��ϴ�.',
             f'8. �� ���� �ִ� {MAX_PRODUCTS}�� ��ǰ, ���� ũ�� {MAX_BYTES // (1024 * 1024)}MB���� �����ɴϴ�.']
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
        raise ValueError('batch.json�� �۾� ��ΰ� �ϰ� �۾� ���� ���� ����ŵ�ϴ�')
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
        raise ValueError(f'�亯 ������ �����ϴ�: {answers}')
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
            report[pid] = {'result': 'missing', 'message': f'{pid}.txt �亯 ������ �����ϴ�'}
            continue
        try:
            text = path.read_bytes().decode('utf-8-sig')
            ingest_job(_job(batch, entry), text, source_label='batch:' + path.name)
            report[pid] = {'result': 'ok', 'message': ''}
        except UnicodeDecodeError:
            report[pid] = {'result': 'error', 'message': f'{pid}.txt: UTF-8 �ؽ�Ʈ�� �ƴմϴ�'}
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
                raise ValueError(f'�亯 ���� �̸��� <product_id>.txt���� �մϴ�: {name}')
            if name in seen:
                raise ValueError(f'�亯 ���� �̸��� �ߺ��˴ϴ�: {name}')
            seen.add(name)
            if not isinstance(payload, bytes):
                raise ValueError(f'�亯 ������ ���� �� �����ϴ�: {name}')
            (staging / name).write_bytes(payload)
        return ingest_answers(batch, staging)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def generate_batch(batch: Path, provider, max_attempts: int = 3) -> dict:
    """Run a subscription CLI for each waiting product, one after another.

    A provider error (usage limit, login, timeout) stops the run at once without retrying, so no further
    quota is spent; remaining products stay "������Ʈ ���".
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
                report[pid] = {'result': 'skipped', 'message': f"���ε��� ���� ({STATUS_LABELS[entry['status']]}) ? �쿡�� ��ǰ���� �����ϼ���"}
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
            raise ValueError('���ε� ��ǰ�� ���� ������ ���� �����ϴ�. ��ǰ���� �쿡�� �����ϼ���.')
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


