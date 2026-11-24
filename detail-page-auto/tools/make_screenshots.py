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


def make_m8a_screenshots(images: Path, artifacts: Path):
    """M8-A captures: the four M6 themes with the deliberately long sample answer (normal answer: --themes-only)."""
    from PIL import Image
    from core.assemble import assemble
    from core.copy_schema import CopyDraft
    from core.facts import ProductFacts
    from core.ingest import extract_json
    from core.render import render
    from core.workflow import read_json
    images.mkdir(parents=True,exist_ok=True)
    artifacts.mkdir(parents=True,exist_ok=True)
    facts = ProductFacts.model_validate_json((ROOT/'samples/facts-rich.json').read_text())
    results={}
    for name in ('answer-rich-long',):
        copy = CopyDraft.model_validate(extract_json((ROOT/f'samples/{name}.txt').read_text()))
        document, _ = assemble(facts,copy)
        for theme in ('modern','natural','impact','industrial'):
            bundle = render(document, ROOT/'samples', artifacts, theme=theme, png=True)
            manifest = read_json(bundle/'manifest.json')
            top = Image.new('RGB', (860, min(1800, manifest['height'])))
            for part in manifest['pages']:
                if part['top'] >= top.height:
                    break
                with Image.open(bundle/part['png']) as rendered:
                    top.paste(rendered, (0, part['top']))
            target = images/f'm8a-long-{theme}.png'
            top.save(target)
            results[target.name] = [(r['code'], r['section_id'], r['field_path']) for r in manifest['copy_reviews']]
    return results


def make_m8b_screenshots(images: Path, output: Path):
    """M8-B captures: ⑥ side-by-side check of an AI background change, and a labelled AI mood picture.

    Every image is drawn here with Pillow; no AI service is called."""
    import shutil
    from PIL import Image, ImageDraw
    from core.editor import preview_job
    from core.facts import ProductFacts
    from core.workflow import create_job, ingest_job, read_json
    images.mkdir(parents=True,exist_ok=True)
    photos = output/'m8b-photos'; photos.mkdir(parents=True,exist_ok=True)
    for path in ROOT.glob('samples/rich-*.png'):
        shutil.copyfile(path,photos/path.name)
    with Image.open(ROOT/'samples/rich-hero.png') as hero:
        edited = hero.convert('RGB')
        ImageDraw.Draw(edited).rectangle((0,0,edited.width,60),fill='#f4efe6')
        edited.save(photos/'ai-background.png')
    scene = Image.new('RGB',(1720,1290),'#dfe9e4')
    ImageDraw.Draw(scene).rectangle((200,700,1500,1100),fill='#b9c9bf')
    scene.save(photos/'ai-scene.png')
    data = read_json(ROOT/'samples/facts-rich.json')
    data['images'][1] = {'path':'ai-scene.png','role':'lifestyle','source':'ai_generated','generator':'가상 AI 도구'}
    data['images'].append({'path':'ai-background.png','role':'detail','source':'ai_edited','based_on':'rich-hero.png',
                           'generator':'가상 AI 도구','edit_request':'배경만 밝은 베이지로'})
    jobs = output/'m8b-jobs'
    if jobs.exists(): shutil.rmtree(jobs)
    job = create_job(ProductFacts.model_validate(data),photos,jobs,theme='modern')
    ingest_job(job,(ROOT/'samples/answer-rich.txt').read_text(encoding='utf-8'),theme='modern')
    bundle = preview_job(job)
    manifest = read_json(bundle/'manifest.json')
    section = next(s for s in manifest['sections'] if s['id']=='image-1')
    full = Image.new('RGB',(860,manifest['height']))
    for part in manifest['pages']:
        with Image.open(bundle/part['png']) as rendered:
            full.paste(rendered,(0,part['top']))
    full.crop((0,section['top'],860,section['bottom'])).save(images/'m8b-staged.png')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0))
        port = listener.getsockname()[1]
    environment = {**os.environ,'DETAIL_PAGE_OUTPUTS':str(jobs)}
    with (output/'m8b-server.log').open('w') as log:
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
                    page.get_by_role('button',name='기존 작업 이어하기',exact=True).click()
                    page.get_by_text('⑥ 승인',exact=True).click()
                    heading = page.get_by_role('heading',name='AI로 만든 이미지 확인',exact=True)
                    expect(heading).to_be_visible(timeout=60000)
                    page.wait_for_timeout(1500)
                    item = page.get_by_text('AI 배경 변경 · 가상 AI 도구',exact=False).first
                    item.scroll_into_view_if_needed()
                    page.evaluate("() => { const main = document.querySelector('section.stMain, [data-testid=stMain]'); if (main) main.scrollBy(0, -40); }")
                    page.wait_for_timeout(500)
                    page.screenshot(path=str(images/'m8b-approval.png'))
                finally:
                    browser.close()
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
    return {'job':str(job),'images':[str(images/name) for name in ('m8b-approval.png','m8b-staged.png')]}


def make_m8c_screenshots(images: Path, output: Path, samples: Path):
    """M8-C: colour candidates on ①, the first PDF page next to the first JPG, and virtual sample PDFs for the Canva check."""
    import shutil
    from PIL import Image
    from core.assemble import assemble
    from core.copy_schema import CopyDraft
    from core.facts import ProductFacts
    from core.ingest import extract_json
    from core.pdf import make_pdf
    from core.render import render
    images.mkdir(parents=True,exist_ok=True); samples.mkdir(parents=True,exist_ok=True); output.mkdir(parents=True,exist_ok=True)
    facts = ProductFacts.model_validate_json((ROOT/'samples/facts-rich.json').read_text())
    document, _ = assemble(facts, CopyDraft.model_validate(extract_json((ROOT/'samples/answer-rich.txt').read_text())))
    made = []
    for theme in ('modern','natural','classic'):
        bundle = render(document, ROOT/'samples', output, theme=theme, png=True)
        pdf = make_pdf(bundle)
        target = samples/f'canva-sample-{theme}.pdf'
        shutil.copyfile(pdf, target); made.append(str(target))
        if theme == 'modern' and shutil.which('pdftoppm'):
            subprocess.run(['pdftoppm','-png','-r','96','-f','1','-l','1','-singlefile',str(pdf),str(output/'pdf-page1')],check=True,shell=False)
            with Image.open(output/'pdf-page1.png') as pdf_page, Image.open(bundle/json.loads((bundle/'manifest.json').read_text())['pages'][0]['png']) as jpg_page:
                height = max(pdf_page.height, jpg_page.height)
                pair = Image.new('RGB', (pdf_page.width + jpg_page.width + 24, height), 'white')
                pair.paste(jpg_page, (0, 0)); pair.paste(pdf_page.convert('RGB'), (jpg_page.width + 24, 0))
                pair.save(images/'m8c-pdf-vs-jpg.png')
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0))
        port = listener.getsockname()[1]
    environment = {**os.environ,'DETAIL_PAGE_OUTPUTS':str(output/'jobs')}
    with (output/'m8c-server.log').open('w') as log:
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
                    page = browser.new_page(viewport={'width':1440,'height':1000})
                    page.set_default_timeout(60000)
                    page.goto(f'http://127.0.0.1:{port}')
                    page.get_by_role('button',name='샘플 데이터 넣기',exact=True).click()
                    page.get_by_text('사진에서 브랜드 색 후보 찾기',exact=True).click()
                    page.get_by_role('button',name='색 후보 찾기',exact=True).click()
                    expect(page.get_by_role('button',name='이 색 사용').first).to_be_visible(timeout=60000)
                    page.wait_for_timeout(800)
                    page.get_by_role('button',name='이 색 사용').first.scroll_into_view_if_needed()
                    page.evaluate("() => { const main = document.querySelector('[data-testid=stMain], section.stMain'); if (main) main.scrollBy(0, 250); }")
                    page.wait_for_timeout(500)
                    page.screenshot(path=str(images/'m8c-colors.png'))
                finally:
                    browser.close()
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
    return {'samples': made, 'images': [str(images/n) for n in ('m8c-colors.png','m8c-pdf-vs-jpg.png')]}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='샘플 화면 캡처를 명시적으로 갱신합니다. pytest에서는 임시 경로만 사용합니다.')
    parser.add_argument('--images',type=Path,default=ROOT/'docs/images')
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/m4-browser')
    parser.add_argument('--themes-only',action='store_true',help='테마 7종의 상세페이지 상단 캡처만 생성')
    parser.add_argument('--m7-only',action='store_true',help='가상 브로슈어 입력 도우미 캡처')
    parser.add_argument('--m8a-only',action='store_true',help='새 테마 4종 × 긴 샘플 답변 상단 캡처(줄 수 측정 결과 포함)')
    parser.add_argument('--m8b-only',action='store_true',help='AI 이미지 출처 확인(⑥)과 연출 이미지 표시 캡처')
    parser.add_argument('--m8c-only',action='store_true',help='색 후보 화면, PDF 첫 쪽, 캔바 확인용 가상 샘플 PDF')
    parser.add_argument('--samples',type=Path,default=ROOT/'docs/samples')
    args=parser.parse_args()
    if args.m8c_only:
        print(json.dumps(make_m8c_screenshots(args.images,args.output,args.samples),ensure_ascii=False,indent=2))
        sys.exit(0)
    if args.m8b_only:
        print(json.dumps(make_m8b_screenshots(args.images,args.output),ensure_ascii=False,indent=2))
        sys.exit(0)
    if args.m8a_only:
        print(json.dumps(make_m8a_screenshots(args.images,args.output),ensure_ascii=False,indent=2))
        sys.exit(0)
    if args.m7_only:
        print(json.dumps(make_m7_screenshots(args.images,args.output),ensure_ascii=False,indent=2))
        sys.exit(0)
    if args.themes_only:
        print(json.dumps(make_theme_screenshots(args.images,args.output),ensure_ascii=False,indent=2))
        sys.exit(0)
    print(json.dumps(make_screenshots(args.output/'work',args.images,args.output),ensure_ascii=False,indent=2))
