"""M5-C: sheet-based batch creation. No AI services, no network."""
import io
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.batch import (  # noqa: E402
    HEADERS, STATUS_LABELS, batch_status, export_prompts, import_batch, ingest_answers, write_template,
)

ANSWER = (ROOT / 'samples/answer.txt').read_text(encoding='utf-8')


@pytest.fixture
def photos(tmp_path):
    root = tmp_path / 'photos'
    for folder in ('p1', 'p2', 'p3', 'p4', 'p5'):
        (root / folder).mkdir(parents=True)
        shutil.copyfile(ROOT / 'samples/product-hires.png', root / folder / 'main.png')
    (tmp_path / 'outside.png').write_bytes((ROOT / 'samples/product-hires.png').read_bytes())
    return root


def product(pid, **extra):
    row = {'product_id': pid, '상품명': f'상품 {pid}', '카테고리': '생활용품', '가격': '10,000원',
           '브랜드 색': '#305b46', '테마': 'classic', '프로필': 'generic', '사진 폴더': pid, '안내 문구': ''}
    row.update(extra)
    return row


def facts_for(pid):
    return [{'product_id': pid, 'fact_id': 'design', '문구': '간결한 형태', '종류': '특징', '근거': ''},
            {'product_id': pid, 'fact_id': 'spec-demo', '문구': '가상 예시 상품', '종류': '스펙', '근거': ''},
            {'product_id': pid, 'fact_id': 'usage', '문구': '설명서를 확인한다', '종류': '사용법', '근거': ''}]


def image_for(pid, name='main.png'):
    return {'product_id': pid, '파일명': name, '역할': '대표', '배경 제거 여부': '아니오'}


def make_book(path, products, facts, images, reviews=(), start_from_template=True):
    """Fill the generated template (its example rows are replaced) or a blank workbook."""
    if start_from_template:
        write_template(path)
        book = load_workbook(path)
    else:
        book = Workbook(); book.remove(book.active)
        for sheet in ('products', 'facts', 'images', 'reviews'):
            book.create_sheet(sheet).append(HEADERS[sheet])
    for sheet, rows in (('products', products), ('facts', facts), ('images', images), ('reviews', reviews)):
        ws = book[sheet]
        ws.delete_rows(2, ws.max_row)
        for row in rows:
            ws.append([row.get(h, '') for h in HEADERS[sheet]])
    book.save(path)
    return path


def three(tmp_path):
    return make_book(tmp_path / '상품목록.xlsx', [product('p1'), product('p2', 테마='minimal'), product('p3', 테마='bold', 프로필='smartstore')],
                     [f for p in ('p1', 'p2', 'p3') for f in facts_for(p)], [image_for(p) for p in ('p1', 'p2', 'p3')])


def entries(batch):
    return {p['product_id']: p for p in json.loads((batch / 'batch.json').read_text(encoding='utf-8'))['products']}


# --- template ----------------------------------------------------------------------------------

def test_template_has_sheets_headers_example_descriptions_and_dropdowns(tmp_path):
    path = write_template(tmp_path / 't.xlsx')
    book = load_workbook(path)
    for sheet, headers in HEADERS.items():
        ws = book[sheet]
        assert [c.value for c in ws[1]] == headers
        # one example row; reviews has none so that no invented review can reach a page by accident
        if sheet == 'reviews':
            assert ws.max_row == 1
        else:
            assert ws.max_row >= 2
        assert all(c.comment and c.comment.text for c in ws[1])  # column descriptions
    assert '안내' in book.sheetnames
    lists = ' '.join(str(dv.formula1) for ws in book.worksheets for dv in ws.data_validations.dataValidation)
    for option in ('classic', 'minimal', 'bold', 'generic', '특징', '주장', '대표', '예'):
        assert option in lists


def test_template_example_rows_import_as_one_product(tmp_path):
    root = tmp_path / 'photos' / 'example-1'
    root.mkdir(parents=True)
    shutil.copyfile(ROOT / 'samples/product-hires.png', root / 'main.png')
    batch = import_batch(write_template(tmp_path / 't.xlsx'), tmp_path / 'photos', tmp_path / 'out')
    assert entries(batch)['example-1']['status'] == 'awaiting_answer'


# --- import ------------------------------------------------------------------------------------

def test_three_products_become_three_jobs(tmp_path, photos):
    batch = import_batch(three(tmp_path), photos, tmp_path / 'out')
    assert batch.parent == tmp_path / 'out' and batch.name.startswith('batch-')
    items = entries(batch)
    assert list(items) == ['p1', 'p2', 'p3']
    for pid, theme, profile in (('p1', 'classic', 'generic'), ('p2', 'minimal', 'generic'), ('p3', 'bold', 'smartstore')):
        job = batch / items[pid]['job']
        assert items[pid]['status'] == 'awaiting_answer' and items[pid]['errors'] == []
        assert (items[pid]['theme'], items[pid]['profile']) == (theme, profile)
        assert json.loads((job / 'manifest.json').read_text())['theme'] == theme
        facts = json.loads((job / 'facts.json').read_text())
        assert facts['product']['name'] == f'상품 {pid}' and [f['id'] for f in facts['facts']] == ['design', 'spec-demo', 'usage']
        assert (job / 'prompt.md').is_file()


def location(batch, pid):
    return [(e['sheet'], e['row'], e['column']) for e in entries(batch)[pid]['errors']]


def test_only_the_broken_products_are_excluded_with_sheet_row_column(tmp_path, photos):
    facts = [f for p in ('p1', 'p2', 'p3', 'p4', 'p5') for f in facts_for(p)]
    facts[6]['종류'] = '주장'  # p3 'design' row → a claim without evidence (facts sheet row 8)
    reviews = [{'product_id': 'p4', '후기': '좋아요', '별점': 5, '출처': '스토어 리뷰', '허가 확인': '아니오'}]
    book = make_book(tmp_path / 'b.xlsx',
                     [product('p1'), product('p2', 상품명=''), product('p3'), product('p4'), product('p5')],
                     facts, [image_for('p1'), image_for('p2'), image_for('p3'), image_for('p4'), image_for('p5', 'missing.png')],
                     reviews)
    batch = import_batch(book, photos, tmp_path / 'out')
    items = entries(batch)
    assert items['p1']['status'] == 'awaiting_answer'
    for pid in ('p2', 'p3', 'p4', 'p5'):
        assert items[pid]['status'] == 'input_error' and items[pid]['job'] is None
    assert location(batch, 'p2') == [('products', 3, '상품명')]
    assert location(batch, 'p3') == [('facts', 8, '근거')]
    assert location(batch, 'p4') == [('reviews', 2, '허가 확인')]
    assert location(batch, 'p5') == [('images', 6, '파일명')]
    assert all(e['reason'] for p in ('p2', 'p3', 'p4', 'p5') for e in items[p]['errors'])


@pytest.mark.parametrize('folder,name', [('../', 'outside.png'), ('p1', '../../outside.png'), ('p1', '/etc/passwd'),
                                        ('/tmp', 'main.png'), ('p1', 'sub/main.png'), ('p1', 'C:\\\\x.png')])
def test_photos_outside_the_photo_root_or_malicious_names_are_rejected(tmp_path, photos, folder, name):
    book = make_book(tmp_path / 'b.xlsx', [product('p1', **{'사진 폴더': folder}), product('p2')],
                     facts_for('p1') + facts_for('p2'), [image_for('p1', name), image_for('p2')])
    items = entries(import_batch(book, photos, tmp_path / 'out'))
    assert items['p1']['status'] == 'input_error'
    assert items['p1']['errors'][0]['sheet'] in ('products', 'images')
    assert items['p2']['status'] == 'awaiting_answer'


def test_control_characters_in_file_names_are_rejected(tmp_path, photos):
    folder = write_csvs(tmp_path / 'csv')
    text = (folder / 'images.csv').read_text(encoding='utf-8-sig').replace('p1,main.png', 'p1,ma\x01in.png')
    (folder / 'images.csv').write_text(text, encoding='utf-8')
    items = entries(import_batch(folder, photos, tmp_path / 'out'))
    assert [(e['sheet'], e['row'], e['column']) for e in items['p1']['errors']] == [('images', 2, '파일명')]
    assert items['p2']['status'] == 'awaiting_answer'


def test_rows_for_unknown_or_duplicate_products_are_reported(tmp_path, photos):
    book = make_book(tmp_path / 'b.xlsx', [product('p1'), product('p1'), product('p2')],
                     facts_for('p1') + facts_for('p2') + [{'product_id': 'ghost', 'fact_id': 'x', '문구': 'x', '종류': '특징'}],
                     [image_for('p1'), image_for('p2')])
    batch = import_batch(book, photos, tmp_path / 'out')
    data = json.loads((batch / 'batch.json').read_text())
    assert [(e['sheet'], e['row'], e['column']) for e in data['errors']] == [('products', 3, 'product_id'), ('facts', 8, 'product_id')]
    assert entries(batch)['p2']['status'] == 'awaiting_answer'


@pytest.mark.parametrize('value', ['', 'p 1', '../p1', 'a' * 41])
def test_invalid_product_ids_are_reported(tmp_path, photos, value):
    book = make_book(tmp_path / 'b.xlsx', [product(value), product('p2')], facts_for('p2'), [image_for('p2')])
    batch = import_batch(book, photos, tmp_path / 'out')
    data = json.loads((batch / 'batch.json').read_text())
    assert ('products', 2, 'product_id') in [(e['sheet'], e['row'], e['column']) for e in data['errors']]
    assert entries(batch)['p2']['status'] == 'awaiting_answer'


def test_unknown_theme_and_profile_are_column_errors(tmp_path, photos):
    book = make_book(tmp_path / 'b.xlsx', [product('p1', 테마='neon'), product('p2', 프로필='nope'), product('p3')],
                     [f for p in ('p1', 'p2', 'p3') for f in facts_for(p)], [image_for(p) for p in ('p1', 'p2', 'p3')])
    batch = import_batch(book, photos, tmp_path / 'out')
    assert location(batch, 'p1') == [('products', 2, '테마')]
    assert location(batch, 'p2') == [('products', 3, '프로필')]
    assert entries(batch)['p3']['status'] == 'awaiting_answer'


# --- formats and limits ---------------------------------------------------------------------------

def write_csvs(folder, encoding='utf-8-sig'):
    import csv
    folder.mkdir()
    data = {'products': [product('p1'), product('p2'), product('p3')],
            'facts': [f for p in ('p1', 'p2', 'p3') for f in facts_for(p)],
            'images': [image_for(p) for p in ('p1', 'p2', 'p3')]}
    for sheet, rows in data.items():
        with open(folder / f'{sheet}.csv', 'w', encoding=encoding, newline='') as handle:
            writer = csv.DictWriter(handle, HEADERS[sheet])
            writer.writeheader(); writer.writerows(rows)
    return folder


def test_csv_with_bom_gives_the_same_result(tmp_path, photos):
    batch = import_batch(write_csvs(tmp_path / 'csv'), photos, tmp_path / 'out')
    assert [(pid, e['status']) for pid, e in entries(batch).items()] == [('p1', 'awaiting_answer'), ('p2', 'awaiting_answer'), ('p3', 'awaiting_answer')]


def test_csv_in_another_encoding_is_a_clear_error(tmp_path, photos):
    with pytest.raises(ValueError, match='UTF-8'):
        import_batch(write_csvs(tmp_path / 'csv', encoding='cp949'), photos, tmp_path / 'out')
    assert not (tmp_path / 'out').exists() or not list((tmp_path / 'out').iterdir())


def test_formula_cells_use_the_stored_value(tmp_path, photos):
    path = make_book(tmp_path / 'f.xlsx', [product('p1', 상품명='=CONCAT("수식","상품")')], facts_for('p1'), [image_for('p1')])
    # Excel stores the last calculated value next to the formula; emulate that saved value.
    with zipfile.ZipFile(path) as source:
        files = {name: source.read(name) for name in source.namelist()}
    sheet = next(n for n in files if n.startswith('xl/worksheets/') and b'CONCAT' in files[n])
    cached = lambda m: b'<c r="B2" t="str"><f>' + m.group(1) + b'</f><v>' + '계산된 상품명'.encode() + b'</v>'
    files[sheet], count = re.subn(rb'<c r="B2"[^>]*><f>(.*?)</f>(?:<v\s*/>|<v></v>)?', cached, files[sheet])
    assert count == 1
    with zipfile.ZipFile(path, 'w') as target:
        for name, data in files.items(): target.writestr(name, data)
    batch = import_batch(path, photos, tmp_path / 'out')
    job = batch / entries(batch)['p1']['job']
    assert json.loads((job / 'facts.json').read_text())['product']['name'] == '계산된 상품명'


def test_macro_workbooks_are_rejected(tmp_path, photos):
    path = three(tmp_path)
    macro = tmp_path / 'macro.xlsm'
    shutil.copyfile(path, macro)
    with pytest.raises(ValueError, match='매크로'):
        import_batch(macro, photos, tmp_path / 'out')
    # A macro workbook renamed to .xlsx is still rejected by its content.
    with zipfile.ZipFile(path, 'a') as archive:
        archive.writestr('xl/vbaProject.bin', b'\x00')
    with pytest.raises(ValueError, match='매크로'):
        import_batch(path, photos, tmp_path / 'out')


def test_row_and_file_size_limits(tmp_path, photos):
    path = make_book(tmp_path / 'many.xlsx', [product(f'p{i}') for i in range(1, 52)], [], [])
    with pytest.raises(ValueError, match='50'):
        import_batch(path, photos, tmp_path / 'out')
    assert import_batch(three(tmp_path), photos, tmp_path / 'out2', max_products=3)
    with pytest.raises(ValueError, match='크기'):
        import_batch(three(tmp_path), photos, tmp_path / 'out3', max_bytes=1000)


def test_missing_sheet_or_header_is_a_clear_error(tmp_path, photos):
    path = three(tmp_path)
    book = load_workbook(path); book['facts']['C1'] = '설명'; book.save(path)
    with pytest.raises(ValueError, match='facts.*문구'):
        import_batch(path, photos, tmp_path / 'out')
    book = load_workbook(path); del book['images']; book.save(path)
    with pytest.raises(ValueError, match='images'):
        import_batch(path, photos, tmp_path / 'out')


# --- prompts, answers, CLI, status, export ------------------------------------------------------

@pytest.fixture
def batch(tmp_path, photos):
    return import_batch(three(tmp_path), photos, tmp_path / 'out')


def statuses(batch):
    return {e['product_id']: e['status'] for e in batch_status(batch)}


def test_prompts_are_one_file_per_product_and_a_zip(batch):
    folder, name, data = export_prompts(batch)
    assert sorted(p.name for p in folder.iterdir()) == ['p1.md', 'p2.md', 'p3.md']
    for pid in ('p1', 'p2', 'p3'):
        job = batch / entries(batch)[pid]['job']
        assert (folder / f'{pid}.md').read_text(encoding='utf-8') == (job / 'prompt.md').read_text(encoding='utf-8')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert sorted(archive.namelist()) == ['prompts/p1.md', 'prompts/p2.md', 'prompts/p3.md']
    assert name.endswith('-prompts.zip')


def test_answer_folder_with_ok_bad_and_missing_files(batch, tmp_path):
    answers = tmp_path / 'answers'
    answers.mkdir()
    (answers / 'p1.txt').write_text(ANSWER, encoding='utf-8')
    (answers / 'p2.txt').write_text('{"not": "a copy answer"}', encoding='utf-8')
    (answers / 'unknown.txt').write_text(ANSWER, encoding='utf-8')
    report = ingest_answers(batch, answers)
    assert statuses(batch) == {'p1': 'needs_review', 'p2': 'answer_error', 'p3': 'awaiting_answer'}
    assert report['p1']['result'] == 'ok'
    assert report['p2']['result'] == 'error' and report['p2']['message']
    assert report['p3']['result'] == 'missing'
    assert report['unknown_files'] == ['unknown.txt']
    # the failed product gets a fix prompt in the next prompt export, the others are not repeated
    folder, _, _ = export_prompts(batch)
    job = batch / entries(batch)['p2']['job']
    assert sorted(p.name for p in folder.iterdir()) == ['p2.md', 'p3.md']
    assert (folder / 'p2.md').read_text(encoding='utf-8') == (job / 'fix-prompt.md').read_text(encoding='utf-8')
    # a second pass with a corrected answer completes p2
    (answers / 'p2.txt').write_text(ANSWER, encoding='utf-8')
    (answers / 'p3.txt').write_text(ANSWER, encoding='utf-8')
    ingest_answers(batch, answers)
    assert statuses(batch) == {'p1': 'needs_review', 'p2': 'needs_review', 'p3': 'needs_review'}


class FakeProvider:
    name = 'fake'

    def __init__(self, limit_at):
        self.calls = 0
        self.limit_at = limit_at

    def generate(self, prompt):
        from core.providers import ProviderError
        self.calls += 1
        if self.calls == self.limit_at:
            raise ProviderError('CLI usage limit reached; switch to paste mode.', 5)
        return ANSWER


def test_cli_generation_is_sequential_and_stops_at_the_usage_limit(batch):
    from core.batch import generate_batch
    provider = FakeProvider(limit_at=2)
    result = generate_batch(batch, provider)
    assert provider.calls == 2                      # no retry after the usage limit
    assert result['stopped'] and 'usage limit' in result['reason']
    assert statuses(batch) == {'p1': 'needs_review', 'p2': 'awaiting_answer', 'p3': 'awaiting_answer'}
    # attempts were not spent on the product that hit the limit
    job = batch / entries(batch)['p2']['job']
    assert json.loads((job / 'manifest.json').read_text())['attempts'] == 0


def test_no_bulk_approval_and_only_approved_products_are_exported(batch, tmp_path):
    import core.batch as module
    from core.batch import export_batch
    from core.workflow import accept_job
    assert not any('approve' in name or 'accept' in name for name in dir(module) if callable(getattr(module, name)) and not name.startswith('_'))
    answers = tmp_path / 'answers'; answers.mkdir()
    for pid in ('p1', 'p2', 'p3'):
        (answers / f'{pid}.txt').write_text(ANSWER, encoding='utf-8')
    ingest_answers(batch, answers)
    with pytest.raises(ValueError, match='승인'):
        export_batch(batch)                       # nothing approved yet
    for pid in ('p1', 'p3'):                      # each product through the normal ⑥ approval
        accept_job(batch / entries(batch)[pid]['job'])
    assert statuses(batch) == {'p1': 'approved', 'p2': 'needs_review', 'p3': 'approved'}
    name, data, report = export_batch(batch)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        assert {n.split('/')[0] for n in names} == {'p1', 'p3', 'batch-export.json'}
        p1 = json.loads(archive.read('p1/manifest.json'))
        p3 = json.loads(archive.read('p3/manifest.json'))
    assert (p1['export']['profile']['id'], p1['theme']) == ('generic', 'classic')
    assert (p3['export']['profile']['id'], p3['theme']) == ('smartstore', 'bold')
    assert p3['width'] == 848
    assert report['p2']['result'] == 'skipped' and '승인' in report['p2']['message']
    assert name.startswith(batch.name)


def test_status_survives_reopening(batch, tmp_path):
    answers = tmp_path / 'answers'; answers.mkdir()
    (answers / 'p1.txt').write_text(ANSWER, encoding='utf-8')
    ingest_answers(batch, answers)
    copy = tmp_path / 'moved' / batch.name
    shutil.copytree(batch, copy)
    assert statuses(copy) == {'p1': 'needs_review', 'p2': 'awaiting_answer', 'p3': 'awaiting_answer'}
    assert set(STATUS_LABELS.values()) == {'입력 오류', '프롬프트 대기', '답변 오류', '검수 필요', '승인됨'}


# --- CLI ---------------------------------------------------------------------------------------

def cli(*args, env=None):
    import os
    import subprocess
    return subprocess.run([sys.executable, str(ROOT / 'cli.py'), *map(str, args)], capture_output=True, text=True,
                          cwd=ROOT, env={**os.environ, **(env or {})})


def test_cli_batch_flow(tmp_path, photos):
    template = tmp_path / '상품목록.xlsx'
    assert cli('batch', 'template', '--output', template).returncode == 0 and template.is_file()
    book = make_book(tmp_path / 'b.xlsx', [product('p1'), product('p2', 상품명='')], facts_for('p1') + facts_for('p2'),
                     [image_for('p1'), image_for('p2')])
    imported = cli('batch', 'import', '--input', book, '--photos', photos, '--output', tmp_path / 'out')
    assert imported.returncode == 0, imported.stderr
    batch = Path(imported.stdout.strip())
    assert 'products 3행 상품명' in imported.stderr          # error location is printed
    prompts = cli('batch', 'prompts', '--batch', batch, '--output', tmp_path / 'prompts.zip')
    assert prompts.returncode == 0 and zipfile.ZipFile(tmp_path / 'prompts.zip').namelist() == ['prompts/p1.md']
    answers = tmp_path / 'answers'; answers.mkdir()
    (answers / 'p1.txt').write_text(ANSWER, encoding='utf-8')
    assert cli('batch', 'ingest', '--batch', batch, '--answers', answers).returncode == 0
    status = cli('batch', 'status', '--batch', batch)
    assert status.returncode == 0
    assert 'p1\t검수 필요' in status.stdout and 'p2\t입력 오류' in status.stdout
    nothing = cli('batch', 'export', '--batch', batch, '--output', tmp_path / 'approved.zip')
    assert nothing.returncode != 0 and '승인' in nothing.stderr
    from core.workflow import accept_job
    accept_job(batch / entries(batch)['p1']['job'])
    done = cli('batch', 'export', '--batch', batch, '--output', tmp_path / 'approved.zip')
    assert done.returncode == 0, done.stderr
    assert 'p1/manifest.json' in zipfile.ZipFile(tmp_path / 'approved.zip').namelist()


def test_cli_batch_generate_stops_at_usage_limit(tmp_path, batch):
    counter = tmp_path / 'calls'
    script = tmp_path / 'fake_cli.py'
    script.write_text(f'''import sys, pathlib
sys.stdin.read()
p = pathlib.Path({str(counter)!r}); n = int(p.read_text()) + 1 if p.exists() else 1; p.write_text(str(n))
if n == 2:
    print("Error: usage limit reached", file=sys.stderr); sys.exit(1)
print(open({str(ROOT / 'samples/answer.txt')!r}, encoding='utf-8').read())
''', encoding='utf-8')
    config = tmp_path / 'providers.toml'
    config.write_text(f'[providers.codex]\ncommand = {json.dumps([sys.executable, str(script)])}\n', encoding='utf-8')
    result = cli('batch', 'generate', '--batch', batch, '--provider', 'codex', '--providers-config', config)
    assert result.returncode != 0 and '사용량' in result.stderr
    assert counter.read_text() == '2'
    assert statuses(batch) == {'p1': 'needs_review', 'p2': 'awaiting_answer', 'p3': 'awaiting_answer'}


def test_cli_batch_import_rejects_macro_files(tmp_path, photos):
    macro = tmp_path / 'm.xlsm'
    shutil.copyfile(three(tmp_path), macro)
    result = cli('batch', 'import', '--input', macro, '--photos', photos, '--output', tmp_path / 'out')
    assert result.returncode != 0 and '매크로' in result.stderr


def test_error_reasons_are_in_korean(tmp_path, photos):
    facts = facts_for('p3')
    facts[0]['종류'] = '주장'
    reviews = [{'product_id': 'p4', '후기': '좋아요', '별점': 5, '출처': '스토어', '허가 확인': '아니오'}]
    book = make_book(tmp_path / 'b.xlsx', [product('p2', 상품명=''), product('p3'), product('p4')],
                     facts_for('p2') + facts + facts_for('p4'), [image_for(p) for p in ('p2', 'p3', 'p4')], reviews)
    items = entries(import_batch(book, photos, tmp_path / 'out'))
    assert items['p2']['errors'][0]['reason'] == '한 글자 이상 입력해 주세요'
    assert items['p3']['errors'][0]['reason'] == '주장은 근거를 입력해야 합니다'
    assert items['p4']['errors'][0]['reason'] == '허가 확인이 "예"여야 합니다'


# --- M5-C Codex Important regressions -------------------------------------------------------------

def test_approved_status_survives_batch_move(batch, tmp_path):
    from core.workflow import accept_job
    answers = tmp_path / 'move-answers'; answers.mkdir()
    (answers / 'p1.txt').write_text(ANSWER, encoding='utf-8')
    ingest_answers(batch, answers)
    accept_job(batch / entries(batch)['p1']['job'])
    assert statuses(batch)['p1'] == 'approved'

    destination = tmp_path / 'moved'; destination.mkdir()
    moved = Path(shutil.move(str(batch), destination))
    assert statuses(moved)['p1'] == 'approved'


@pytest.mark.parametrize('change', ['copy', 'theme'])
def test_source_change_invalidates_approval_and_export(batch, tmp_path, change):
    from core.batch import export_batch
    from core.workflow import accept_job
    answers = tmp_path / ('freshness-' + change); answers.mkdir()
    (answers / 'p1.txt').write_text(ANSWER, encoding='utf-8')
    ingest_answers(batch, answers)
    source = batch / entries(batch)['p1']['job']
    accept_job(source)
    assert statuses(batch)['p1'] == 'approved'

    if change == 'copy':
        draft = json.loads((source / 'draft.json').read_text(encoding='utf-8'))
        draft['sections'][0]['headline'] = '승인 뒤 바뀐 문구'
        (source / 'draft.json').write_text(json.dumps(draft, ensure_ascii=False) + '\n', encoding='utf-8')
    else:
        manifest = json.loads((source / 'manifest.json').read_text(encoding='utf-8'))
        manifest['theme'] = 'bold'
        (source / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False) + '\n', encoding='utf-8')

    assert statuses(batch)['p1'] == 'needs_review'
    with pytest.raises(ValueError, match='승인'):
        export_batch(batch)


def test_uploaded_answers_process_only_current_files(batch):
    from core.batch import ingest_uploaded_answers
    persistent = batch / 'answers'; persistent.mkdir()
    (persistent / 'p1.txt').write_text('{"stale": "invalid"}', encoding='utf-8')

    report = ingest_uploaded_answers(batch, [('p2.txt', ANSWER.encode('utf-8'))])

    assert report['p1']['result'] == 'missing'
    assert report['p2']['result'] == 'ok'
    assert statuses(batch) == {'p1': 'awaiting_answer', 'p2': 'needs_review', 'p3': 'awaiting_answer'}
    assert not list(batch.glob('.answer-upload-*'))


def test_xlsx_expansion_is_bounded_before_xml_is_read(tmp_path, photos):
    path = tmp_path / 'compressed-bomb.xlsx'
    expanded = b'A' * (21 * 1024 * 1024)
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', expanded)
    assert path.stat().st_size < 5 * 1024 * 1024

    with pytest.raises(ValueError, match='압축 해제'):
        import_batch(path, photos, tmp_path / 'out')


@pytest.mark.parametrize(
    ('kind', 'expected'),
    [('reviews', ('reviews', 12, '후기')), ('images', ('images', 7, '파일명'))],
)
def test_aggregate_limits_report_first_excess_source_cell(tmp_path, photos, kind, expected):
    reviews = []
    images = [image_for('p1')]
    if kind == 'reviews':
        reviews = [
            {'product_id': 'p1', '후기': f'실제 후기 {i}', '별점': 5, '출처': '스토어', '허가 확인': '예'}
            for i in range(1, 12)
        ]
    else:
        for i in range(1, 6):
            name = f'extra-{i}.png'
            shutil.copyfile(photos / 'p1' / 'main.png', photos / 'p1' / name)
            images.append(image_for('p1', name))

    book = make_book(tmp_path / f'{kind}.xlsx', [product('p1')], facts_for('p1'), images, reviews)
    batch = import_batch(book, photos, tmp_path / 'out')
    assert location(batch, 'p1') == [expected]
