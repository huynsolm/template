"""Regression tests for the M8-A review findings (M8_A_REVIEW.md #1-#7 and #9)."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from core.editor import bundle_matches, latest_copy_metrics, preview_job, save_draft
from core.facts import ProductFacts
from core.ingest import extract_json
from core.measure import MEASURE_VERSION
from core.render import render
from core.schema import Document
from core.workflow import create_job, ingest_job, overflow_regenerate_job, read_json, write_json
from test_m8a import COPY_CODES, bundle_of, copy_items, open_page


def facts_job(tmp_path, theme='modern', change_facts=None, change_answer=None):
    facts = read_json(ROOT / 'samples/facts-rich.json')
    if change_facts: change_facts(facts)
    job = create_job(ProductFacts.model_validate(facts), ROOT / 'samples', tmp_path, theme=theme)
    answer = extract_json((ROOT / 'samples/answer-rich.txt').read_text(encoding='utf-8'))
    if change_answer: change_answer(answer)
    ingest_job(job, '```json\n' + json.dumps(answer, ensure_ascii=False) + '\n```', render_output=True, theme=theme)
    return job


def metric(job, section_type, field_path):
    metrics = read_json(bundle_of(job) / 'manifest.json')['copy_metrics']
    return next(m for m in metrics if m['section_type'] == section_type and m['field_path'] == field_path)


# 1. a snapshot measured by an older (or no) measurement version is not reused for a new theme

def test_preview_from_an_older_measurement_version_is_not_reused(tmp_path):
    job = facts_job(tmp_path)
    first = preview_job(job)
    assert read_json(first / 'manifest.json')['copy_measure_version'] == MEASURE_VERSION
    assert bundle_matches(job, first)
    manifest = read_json(first / 'manifest.json')
    del manifest['copy_measure_version']; del manifest['copy_metrics']  # as written before M8-A
    write_json(first / 'manifest.json', manifest)
    assert not bundle_matches(job, first)
    assert latest_copy_metrics(job)[1] is False
    second = preview_job(job)
    assert second != first and first.is_dir()  # the old snapshot is kept
    assert bundle_matches(job, second)


# 2. seller sections count toward the section density and point to ①

def test_seller_section_density_is_checked_and_points_to_product_info(tmp_path):
    def many_targets(facts): facts['targets'] = [f'적용 장소 {i}' for i in range(12)]
    job = facts_job(tmp_path, change_facts=many_targets)
    dense = [i for i in copy_items(job) if i['code'] == 'SECTION_TOO_DENSE']
    assert [i['field_path'] for i in dense] == ['targets']
    assert dense[0]['detail']['source'] == 'seller' and '①' in dense[0]['reason']


# 3. seller-only overflow is never sent to the AI

def test_seller_only_overflow_does_not_create_a_rewrite_job(tmp_path):
    def long_desc(facts): facts['structure'][0]['desc'] = '가' * 50
    job = facts_job(tmp_path, change_facts=long_desc)
    items = copy_items(job)
    assert [(i['section_id'], i['field_path']) for i in items] == [('structure-1', 'items.0.desc')]
    assert items[0]['detail']['source'] == 'seller' and '①' in items[0]['reason']
    jobs_before = sorted(p.name for p in tmp_path.iterdir())
    with pytest.raises(ValueError, match='AI가 다시 쓸 문구가 없습니다'):
        overflow_regenerate_job(job)
    assert sorted(p.name for p in tmp_path.iterdir()) == jobs_before


# 4. aggregate warnings carry the section's current copy

def test_density_rewrite_request_carries_the_current_copy(tmp_path):
    def dense_features(answer):
        answer['features'] = [
            {'title': f'특징 {i}', 'desc': '밀도재현설명 ' + '가' * 35, 'fact_ids': ['design']} for i in range(5)]
    job = facts_job(tmp_path, change_answer=dense_features)
    assert 'SECTION_TOO_DENSE' in {i['code'] for i in copy_items(job)}
    child = overflow_regenerate_job(job)
    prompt = (child / 'prompt.md').read_text(encoding='utf-8')
    block = prompt[prompt.index('<copy_overflow>'):prompt.index('</copy_overflow>')]
    request = json.loads(block.split('\n', 1)[1])
    dense = next(entry for entry in request if entry['code'] == 'SECTION_TOO_DENSE')
    assert [item['desc'] for item in dense['current']['items']] == ['밀도재현설명 ' + '가' * 35] * 5
    assert dense['lines'] > dense['limit']
    assert {f['field_path'] for f in dense['fields']} >= {'items.0.title', 'items.0.desc'}
    assert all(f['text'] for f in dense['fields'])


# 5. the last measurement survives a save and is reported as stale

def test_saved_edit_keeps_the_last_measurement_as_stale(tmp_path):
    job = facts_job(tmp_path)
    preview_job(job)
    metrics, fresh = latest_copy_metrics(job)
    assert metrics and fresh
    draft = read_json(job / 'draft.json')
    next(s for s in draft['sections'] if s['type'] == 'solution')['body'] = '긴 가상 설명입니다. ' * 30
    save_draft(job, draft, [])
    metrics, fresh = latest_copy_metrics(job)
    assert metrics and fresh is False


def test_review_screen_marks_badges_stale_before_and_after_save(monkeypatch, tmp_path):
    from test_app import start, stage
    app = start(monkeypatch, tmp_path)
    app.button(key='create').click().run()
    job = Path(app.session_state['job'])
    stage(app, 2)
    app.text_area(key='answer_text').set_value((ROOT / 'samples/answer.txt').read_text(encoding='utf-8'))
    app.button(key='ingest').click().run()
    stage(app, 4)
    app.button(key='preview').click().run(timeout=120)
    stage(app, 3)
    key = f'edit_{job.name}_solution-1_body'
    assert any('허용 2줄' in c.value for c in app.caption)
    app.text_area(key=key).set_value('긴 가상 설명입니다. ' * 30).run()
    assert any('지난 미리보기' in c.value and '다시 미리보기' in c.value for c in app.caption)
    app.button(key='save_edits').click().run()
    assert not app.exception
    assert any('다시 미리보기' in i.value for i in app.info)
    assert any('지난 미리보기' in c.value for c in app.caption)


# 6. empty visual lines in pre-wrap text are counted (measurement and alignment)

def test_prewrap_empty_lines_are_counted(tmp_path):
    data = read_json(ROOT / 'samples/product.json')
    next(s for s in data['sections'] if s['type'] == 'solution')['body'] = '첫째\n\n셋째'
    bundle = render(Document.model_validate(data), ROOT / 'samples', tmp_path, theme='classic')
    m = next(m for m in read_json(bundle / 'manifest.json')['copy_metrics'] if m['section_type'] == 'solution' and m['field_path'] == 'body')
    assert m['lines'] == 3 and m['over'] is True


def test_prewrap_empty_lines_drive_alignment(tmp_path):
    """layout.js counts lines the same way: a pre-wrap paragraph with an empty line is 3 lines -> left."""
    from playwright.sync_api import sync_playwright
    from core.render import chromium_path
    script = (ROOT / 'templates/layout.js').read_text(encoding='utf-8')
    html = ('<html><body style="width:860px;font:24px sans-serif;line-height:1.6"><main>'
            '<section class="solution" data-align="auto"><p style="white-space:pre-wrap">첫째\n\n셋째</p></section>'
            '<section class="solution" data-align="auto"><p style="white-space:pre-wrap">첫째\n둘째</p></section>'
            '</main></body></html>')
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=chromium_path(pw.chromium.executable_path))
        try:
            page = browser.new_page(offline=True)
            page.set_content(html)
            page.add_script_tag(content=script)
            page.wait_for_function("() => document.documentElement.hasAttribute('data-layout-done')")
            result = page.evaluate("() => [...document.querySelectorAll('section')].map(s => s.className)")
        finally:
            browser.close()
    assert result == ['solution copy-align-left', 'solution copy-align-center']


# 7. stats values never shrink below 22px in the new themes; a value that does not fit is reported

@pytest.mark.parametrize('theme', ('modern', 'natural'))
def test_stats_value_keeps_the_22px_minimum_and_is_reported(tmp_path, theme):
    def long_value(facts): facts['highlights'][0]['value'] = '가' * 80
    job = facts_job(tmp_path, theme, change_facts=long_value)
    m = metric(job, 'stats', 'items.0.value')
    assert m['font_size'] >= 22 and m['lines'] > 1
    pw, browser, page = open_page(bundle_of(job))
    try:
        sizes = page.evaluate("() => [...document.querySelectorAll('.stat-list dd')].map(e => parseFloat(getComputedStyle(e).fontSize))")
        overflow = page.evaluate('() => document.documentElement.scrollWidth > 860')
    finally:
        browser.close(); pw.stop()
    assert min(sizes) >= 22 and not overflow
    item = next(i for i in copy_items(job) if i['field_path'] == 'items.0.value')
    assert item['code'] == 'COPY_TOO_LONG' and item['detail']['source'] == 'seller' and '①' in item['reason']


# 9. stats labels are measured against one line

def test_stats_label_is_measured(tmp_path):
    def long_label(facts): facts['highlights'][0]['label'] = '가' * 80
    job = facts_job(tmp_path, change_facts=long_label)
    m = metric(job, 'stats', 'items.0.label')
    assert m['limit'] == 1 and m['over'] is True
    assert ('stats-1', 'items.0.label') in {(i['section_id'], i['field_path']) for i in copy_items(job)}


# heading weight rule: 800, or the heaviest bundled weight of the heading face

def test_heading_weight_must_reach_800_or_the_faces_heaviest_weight():
    from core.themes import required_heading_weight
    assert required_heading_weight('pretendard') == 800
    assert required_heading_weight('gowun-batang') == 700
    assert required_heading_weight('black-han-sans') == 400


# R2-1: an approval rendered by older rules gives way to the current preview

def test_stale_old_approval_falls_back_to_the_current_preview(tmp_path):
    import shutil
    from core.editor import resume_bundle
    job = facts_job(tmp_path)
    first = preview_job(job)
    old = first.with_name('job-oldaccept')
    shutil.copytree(first, old)
    manifest = read_json(old / 'manifest.json'); del manifest['copy_measure_version']
    write_json(old / 'manifest.json', manifest)  # approved before the measurement version existed
    manifest = read_json(job / 'manifest.json')
    manifest.update(review_accepted=True, rendered_job=str(old.relative_to(job)))
    write_json(job / 'manifest.json', manifest)
    assert resume_bundle(job) == first  # reopening the job shows the valid preview, not nothing
    second = preview_job(job)
    manifest = read_json(job / 'manifest.json')
    assert manifest['review_accepted'] is False and 'rendered_job' not in manifest
    assert resume_bundle(job) == second and old.is_dir()
