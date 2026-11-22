"""Actual local Streamlit + Chromium flow, never automating external AI sites."""
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import zipfile

from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.ingest import extract_json
from core.render import chromium_path


def make_screenshots(tmp_path: Path, images: Path, artifacts: Path):
    tmp_path.mkdir(parents=True,exist_ok=True)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0)); port=listener.getsockname()[1]
    environment=os.environ.copy()
    environment['DETAIL_PAGE_OUTPUTS']=str(tmp_path/'jobs')
    artifacts.mkdir(parents=True,exist_ok=True)
    images.mkdir(parents=True,exist_ok=True)
    with (tmp_path/'server.log').open('w') as log:
        process=subprocess.Popen([sys.executable,'-m','streamlit','run','app/main.py','--server.address','127.0.0.1','--server.port',str(port),'--browser.gatherUsageStats','false'],cwd=ROOT,env=environment,stdout=log,stderr=subprocess.STDOUT,shell=False)
        try:
            deadline=time.monotonic()+30
            while True:
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/_stcore/health',timeout=1) as response:
                        assert response.status==200
                    break
                except OSError:
                    assert process.poll() is None,'Streamlit exited unexpectedly'
                    if time.monotonic()>deadline: raise AssertionError('Streamlit startup timed out')
                    time.sleep(.1)
            with sync_playwright() as pw:
                expect.set_options(timeout=60000)
                browser=pw.chromium.launch(executable_path=chromium_path(pw.chromium.executable_path))
                try:
                    page=browser.new_page(viewport={'width':1440,'height':1100},accept_downloads=True)
                    page.set_default_timeout(60000)
                    page.goto(f'http://127.0.0.1:{port}')
                    expect(page.get_by_role('heading',name='상품 상세페이지 만들기',exact=True)).to_be_visible()
                    page.get_by_role('button',name='샘플 데이터 넣기',exact=True).click()
                    expect(page.get_by_role('textbox',name='상품명',exact=True)).to_have_value('가상 샘플 보틀')
                    page.locator('input[type=file]').nth(1).set_input_files(ROOT/'samples/product-hires.png')
                    expect(page.get_by_text('사진 1 역할',exact=True)).to_be_visible()
                    page.get_by_role('button',name='사진 처리 미리보기',exact=True).click()
                    expect(page.get_by_text('사진 1 처리 후',exact=True)).to_be_visible()
                    page.screenshot(path=str(images/'01-input.png'),full_page=True)
                    page.get_by_role('button',name='저장하고 프롬프트 만들기',exact=True).click()
                    expect(page.get_by_role('heading',name='② 프롬프트 복사',exact=True)).to_be_visible()
                    page.screenshot(path=str(images/'02-prompt.png'),full_page=True)
                    page.get_by_role('button',name='답변 붙여넣기로 이동',exact=True).click()
                    answer=extract_json((ROOT/'samples/answer.txt').read_text())
                    answer['hero']['fact_ids']=['unknown-fact']
                    page.get_by_role('textbox',name='답변 전체',exact=True).fill(json.dumps(answer,ensure_ascii=False))
                    page.get_by_role('button',name='답변 검증·조립',exact=True).click()
                    expect(page.get_by_role('heading',name='④ 검수·문구 수정',exact=True)).to_be_visible()
                    expect(page.get_by_text('검수: 존재하지 않는 fact_ids: unknown-fact · hero',exact=True)).to_be_visible()
                    page.screenshot(path=str(images/'03-review.png'),full_page=True)
                    headline=page.get_by_role('textbox',name='대표 문구 · headline (상한 80자)',exact=True)
                    headline.fill('사람이 검수한 샘플 보틀')
                    evidence=page.get_by_role('combobox',name='대표 문구 · hero 근거 사실',exact=True)
                    evidence.fill('design');evidence.press('Enter');evidence.press('Escape')
                    page.get_by_role('button',name='수정 저장·재검수',exact=True).click()
                    expect(page.get_by_text('수정과 검수 목록을 저장했습니다.',exact=True)).to_be_visible()
                    page.get_by_role('button',name='저장한 문구 미리보기',exact=True).click()
                    page.get_by_role('button',name='저장된 문구로 미리보기 생성',exact=True).click()
                    expect(page.get_by_text('DRAFT · 승인 전 미리보기입니다. 검수 항목과 문구를 확인하세요.',exact=True)).to_be_visible()
                    page.screenshot(path=str(images/'04-preview.png'),full_page=True)
                    page.get_by_role('button',name='승인 단계로 이동',exact=True).click()
                    approve=page.get_by_role('button',name='모두 확인했으며 승인',exact=True)
                    expect(approve).to_be_disabled()
                    for label in page.get_by_role('checkbox').evaluate_all('(nodes) => nodes.map(n => n.getAttribute("aria-label"))'):
                        page.get_by_text(label,exact=True).click()
                        expect(page.get_by_role('checkbox',name=label,exact=True)).to_be_checked()
                    expect(approve).to_be_enabled()
                    approve.click()
                    expect(page.get_by_role('heading',name='⑦ 다운로드',exact=True)).to_be_visible()
                    download=page.get_by_role('button',name='ZIP 다운로드',exact=True)
                    expect(download).to_be_visible()
                    page.screenshot(path=str(images/'05-download.png'),full_page=True)
                    with page.expect_download() as waiting:
                        download.click()
                    result=waiting.value
                    target=artifacts/'approved.zip'; result.save_as(target)
                    with zipfile.ZipFile(target) as archive:
                        manifest=json.loads(archive.read('manifest.json'))
                        assert manifest['review_accepted'] is True
                        assert manifest['needs_review'] is False
                        expect(page.get_by_text('작업 버전 ID: '+manifest['job_id'],exact=True)).to_be_visible()
                        assert all('.DRAFT.' not in part['file'] for part in manifest['pages'])
                        assert '사람이 검수한 샘플 보틀' in archive.read('draft.json').decode()
                    (artifacts/'browser-result.json').write_text(json.dumps({'job_id':manifest['job_id'],'same_version':True,'bound_address':'127.0.0.1','steps':'1-7','zip':'approved.zip'},ensure_ascii=False,indent=2))
                finally:
                    browser.close()
        finally:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=10)

    return json.loads((artifacts/'browser-result.json').read_text())


def make_theme_screenshots(images: Path, artifacts: Path):
    """Explicit-only documentation captures; no test writes tracked images."""
    from PIL import Image
    from core.assemble import assemble
    from core.copy_schema import CopyDraft
    from core.facts import ProductFacts
    from core.ingest import extract_json
    from core.render import render
    from core.workflow import read_json
    from core.themes import THEME_IDS
    images.mkdir(parents=True,exist_ok=True)
    artifacts.mkdir(parents=True,exist_ok=True)
    facts = ProductFacts.model_validate_json((ROOT/'samples/facts-rich.json').read_text())
    copy = CopyDraft.model_validate(extract_json((ROOT/'samples/answer-rich.txt').read_text()))
    document, _ = assemble(facts,copy)
    results={}
    for theme in THEME_IDS:
        bundle = render(document, ROOT/'samples', artifacts, theme=theme, png=True)
        manifest = read_json(bundle/'manifest.json')
        top = Image.new('RGB', (860, min(1800, manifest['height'])))
        for part in manifest['pages']:
            if part['top'] >= top.height:
                break
            with Image.open(bundle/part['png']) as rendered:
                top.paste(rendered, (0, part['top']))
        target = images/f'theme-{theme}.png'
        top.save(target)
        font_bytes = sum(path.stat().st_size for path in (bundle/'assets/fonts').rglob('*') if path.is_file())
        results[theme] = {'image': str(target), 'font_bytes': font_bytes, 'elapsed_seconds': manifest['elapsed_seconds']}
    return results


def make_m7_screenshots(images: Path, output: Path):
    from core.extract import extraction_prompt
    from PIL import Image
    from tools.m7_scenario import run_scenario
    from core.workflow import read_json
    images.mkdir(parents=True,exist_ok=True)
    (images.parent/'extract-prompt.md').write_text(extraction_prompt(),encoding='utf-8')
    scenario = run_scenario(output)
    for name, source in [('m7-before',scenario['source']),('m7-after',scenario['cropped'])]:
        with Image.open(source) as photo:
            photo.save(images/(name+'.png'))
    meta = read_json(scenario['bundle']/'manifest.json')
    top = Image.new('RGB',(860,min(1800,meta['height'])))
    for part in meta['pages']:
        if part['top'] >= top.height:
            break
        with Image.open(scenario['bundle']/part.get('png',part['file'])) as photo:
            top.paste(photo,(0,part['top']))
    top.save(images/'m7-detail.png')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0))
        port = listener.getsockname()[1]
    environment = {**os.environ,'DETAIL_PAGE_OUTPUTS':str(output/'jobs')}
    with (output/'m7-server.log').open('w') as log:
        process = subprocess.Popen([sys.executable,'-m','streamlit','run','app/main.py','--server.address','127.0.0.1',
                                    '--server.port',str(port),'--browser.gatherUsageStats','false'],
                                   cwd=ROOT,env=environment,stdout=log,stderr=subprocess.STDOUT,shell=False)
        try:
            deadline = time.monotonic()+30
            while True:
                try:
                    urllib.request.urlopen(f'http://127.0.0.1:{port}/_stcore/health',timeout=1).close()
                    break
                except OSError:
                    if process.poll() is not None or time.monotonic()>deadline:
                        raise RuntimeError('Streamlit startup failed')
                    time.sleep(.1)
            with sync_playwright() as pw:
                browser = pw.chromium.launch(executable_path=chromium_path(pw.chromium.executable_path))
                try:
                    page = browser.new_page(viewport={'width':1440,'height':1100})
                    page.set_default_timeout(60000)
                    page.goto(f'http://127.0.0.1:{port}')
                    expect(page.get_by_role('heading',name='① 상품 정보',exact=True)).to_be_visible(timeout=60000)
                    page.locator('input[type=file]').nth(1).set_input_files(scenario['source'])
                    page.get_by_text('자료에서 입력 만들기',exact=True).click()
                    page.get_by_role('textbox',name='정리 답변 붙여넣기',exact=True).fill((ROOT/'samples/extract-answer.txt').read_text())
                    page.get_by_role('button',name='가져오기',exact=True).click()
                    page.get_by_role('button',name='미리보기 값을 입력에 적용',exact=True).click()
                    expect(page.get_by_role('textbox',name='상품명',exact=True)).to_have_value('가상 모듈형 환기함',timeout=60000)
                    page.get_by_role('textbox',name='가격 (표시용)',exact=True).fill('가상 판매자 입력 가격')
                    page.get_by_role('textbox',name='가격 (표시용)',exact=True).press('Tab')
                    expect(page.get_by_role('heading',name='입력 점검 결과',exact=True)).to_be_visible(timeout=60000)
                    page.get_by_role('heading',name='① 상품 정보',exact=True).scroll_into_view_if_needed()
                    page.screenshot(path=str(images/'m7-input.png'),full_page=True)
                finally:
                    browser.close()
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
    return {'summary':scenario['summary'],'images':[str(images/name) for name in
            ('m7-before.png','m7-after.png','m7-detail.png','m7-input.png')]}



if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='샘플 화면 캡처를 명시적으로 갱신합니다. pytest에서는 임시 경로만 사용합니다.')
    parser.add_argument('--images',type=Path,default=ROOT/'docs/images')
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/m4-browser')
    parser.add_argument('--themes-only',action='store_true',help='테마 7종의 상세페이지 상단 캡처만 생성')
    parser.add_argument('--m7-only',action='store_true',help='가상 브로슈어 입력 도우미 캡처')
    args=parser.parse_args()
    if args.m7_only:
        print(json.dumps(make_m7_screenshots(args.images,args.output),ensure_ascii=False,indent=2))
        sys.exit(0)
    if args.themes_only:
        print(json.dumps(make_theme_screenshots(args.images,args.output),ensure_ascii=False,indent=2))
        sys.exit(0)
    print(json.dumps(make_screenshots(args.output/'work',args.images,args.output),ensure_ascii=False,indent=2))
