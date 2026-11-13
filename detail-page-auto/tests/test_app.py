import sys
from pathlib import Path
from streamlit.testing.v1 import AppTest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def test_app_starts(tmp_path,monkeypatch):
    monkeypatch.setenv('DETAIL_PAGE_OUTPUTS',str(tmp_path))
    app=AppTest.from_file(str(ROOT/'app/main.py')).run()
    assert not app.exception
    assert any('상세페이지' in t.value for t in app.title)

import io
import json
import zipfile
import pytest


def start(monkeypatch,tmp_path):
    monkeypatch.setenv('DETAIL_PAGE_OUTPUTS',str(tmp_path))
    app=AppTest.from_file(str(ROOT/'app/main.py'),default_timeout=60).run()
    app.button(key='sample').click().run()
    assert not app.exception
    return app


def stage(app,index):
    app.sidebar.radio[0].set_value(['① 상품 정보','② 프롬프트','③ 답변 붙여넣기','④ 검수·수정','⑤ 미리보기','⑥ 승인','⑦ 다운로드'][index]).run()
    assert not app.exception
    return app


@pytest.mark.parametrize('case',['empty_name','claim','review'])
def test_input_errors(monkeypatch,tmp_path,case):
    app=start(monkeypatch,tmp_path)
    if case=='empty_name': app.text_input(key='product_name').set_value('')
    if case=='claim': app.selectbox(key='fact_kind_label_'+app.session_state['fact_rows'][0]['_uid']).set_value('주장')
    if case=='review':
        next(b for b in app.button if b.label=='후기 추가').click().run()
        uid=app.session_state['review_rows'][0]['_uid']
        app.text_area(key=f'review_text_{uid}').set_value('실제 허가 확인 전 후기')
        app.text_input(key=f'review_source_{uid}').set_value('원본')
    app.button(key='create').click().run()
    assert app.error
    assert not app.session_state['job']
    assert not app.exception


def test_prompt_invalid_answer_then_success(monkeypatch,tmp_path):
    app=start(monkeypatch,tmp_path)
    app.button(key='create').click().run()
    assert app.session_state['stage']=='② 프롬프트'
    assert app.code
    job=Path(app.session_state['job'])
    stage(app,2)
    bad=json.loads((ROOT/'samples/copy-example.json').read_text())
    bad['pain']['title']='가'*81
    app.text_area(key='answer_text').set_value(json.dumps(bad,ensure_ascii=False))
    app.button(key='ingest').click().run()
    assert app.error
    assert any('수정 요청' in w.value for w in app.warning)
    assert (job/'fix-prompt.md').exists()
    assert any('고객 고민' in error.value for error in app.error)
    app.text_area(key='answer_text').set_value((ROOT/'samples/answer.txt').read_text())
    app.button(key='ingest').click().run()
    assert app.session_state['stage']=='④ 검수·수정'
    assert not app.exception


def test_edit_restart_recheck_approve_and_zip(monkeypatch,tmp_path):
    app=start(monkeypatch,tmp_path)
    app.button(key='create').click().run()
    job=Path(app.session_state['job'])
    stage(app,2)
    app.text_area(key='answer_text').set_value((ROOT/'samples/answer.txt').read_text())
    app.button(key='ingest').click().run()
    edit_key=f'edit_{job.name}_hero-1_headline'
    app.text_area(key=edit_key).set_value('100% 인증 효과')
    app.button(key='save_edits').click().run()
    assert any('검수' in w.value for w in app.warning)
    assert json.loads((job/'review.json').read_text())
    assert (job/'history.json').exists()
    restarted=AppTest.from_file(str(ROOT/'app/main.py'),default_timeout=60).run()
    restarted.selectbox(key='resume_job').set_value(str(job))
    restarted.button(key='resume').click().run()
    assert restarted.text_area(key=edit_key).value=='100% 인증 효과'
    stage(restarted,4)
    restarted.button(key='preview').click().run(timeout=60)
    assert not restarted.exception
    assert restarted.session_state['bundle']
    existing=set((job/'rendered').iterdir())
    restarted.button(key='preview').click().run(timeout=60)
    assert set((job/'rendered').iterdir())==existing
    stage(restarted,6)
    draft_data=restarted.session_state['download_zip']
    bundle=Path(restarted.session_state['bundle'])
    with zipfile.ZipFile(io.BytesIO(draft_data)) as z:
        manifest=json.loads(z.read('manifest.json'))
        assert manifest['job_id']==json.loads((bundle/'manifest.json').read_text())['job_id']
        assert all('.DRAFT.' in p['file'] for p in manifest['pages'])
    stage(restarted,5)
    assert restarted.button(key='accept').disabled
    for i in range(5): restarted.checkbox(key=f'check_{job.name}_{i}').check()
    restarted.run()
    assert not restarted.button(key='accept').disabled
    restarted.button(key='accept').click().run(timeout=60)
    assert restarted.session_state['stage']=='⑦ 다운로드'
    assert not restarted.exception
    assert Path(restarted.session_state['job'])!=job
    with zipfile.ZipFile(io.BytesIO(restarted.session_state['download_zip'])) as z:
        manifest=json.loads(z.read('manifest.json'))
        assert manifest['review_accepted'] is True
        assert all('.DRAFT.' not in p['file'] for p in manifest['pages'])
        assert manifest['job_id'] in '\n'.join(c.value for c in restarted.caption)
        assert 'draft.json' in z.namelist() and 'review.json' in z.namelist()


def test_return_to_input_keeps_fields(monkeypatch,tmp_path):
    app=start(monkeypatch,tmp_path)
    original=app.text_input(key='product_name').value
    app.button(key='create').click().run()
    stage(app,0)
    assert app.text_input(key='product_name').value==original
    assert app.text_input(key='product_price').value=='판매하지 않음'


def test_unexpected_error_is_safe_and_recoverable(monkeypatch,tmp_path):
    import core.workflow
    app=start(monkeypatch,tmp_path)
    def fail(*args,**kwargs): raise RuntimeError('SECRET-MUST-NOT-LEAK')
    monkeypatch.setattr(core.workflow,'create_job',fail)
    app.button(key='create').click().run()
    assert not app.exception
    assert any('예상치 못한 오류' in e.value for e in app.error)
    assert all('SECRET-MUST-NOT-LEAK' not in e.value for e in app.error)
    files=list(tmp_path.rglob('ui-error-*.log'))
    assert files and all('SECRET-MUST-NOT-LEAK' not in f.read_text() for f in files)
    assert app.button(key='create')


def test_optional_subcopy_can_be_saved(monkeypatch,tmp_path):
    from core.facts import ProductFacts
    from core.workflow import create_job,ingest_job
    monkeypatch.setenv('DETAIL_PAGE_OUTPUTS',str(tmp_path))
    facts=ProductFacts.model_validate_json((ROOT/'samples/facts.json').read_text())
    job=create_job(facts,ROOT/'samples',tmp_path)
    ingest_job(job,(ROOT/'samples/answer.txt').read_text())
    document=json.loads((job/'draft.json').read_text()); document['sections'][0]['subcopy']=None
    (job/'draft.json').write_text(json.dumps(document,ensure_ascii=False))
    app=AppTest.from_file(str(ROOT/'app/main.py'),default_timeout=60).run()
    app.selectbox(key='resume_job').set_value(str(job)); app.button(key='resume').click().run()
    app.button(key='save_edits').click().run()
    assert not app.exception
    assert not app.error
    assert 'subcopy' not in json.loads((job/'draft.json').read_text())['sections'][0]


def test_fact_rows_reorder_and_delete(monkeypatch,tmp_path):
    app=start(monkeypatch,tmp_path)
    uid=app.session_state['fact_rows'][0]['_uid']
    app.text_area(key='fact_text_'+uid).set_value('직접 수정한 사실')
    app.button(key='down_'+uid).click().run()
    assert app.session_state['fact_rows'][1]['text']=='직접 수정한 사실'
    app.button(key='delete_'+uid).click().run()
    assert len(app.session_state['fact_rows'])==2
    assert not app.exception


def test_local_settings_and_launcher():
    import tomllib
    import subprocess
    config=tomllib.loads((ROOT/'.streamlit/config.toml').read_text())
    assert config['server']['address']=='127.0.0.1'
    assert config['server']['maxUploadSize']==10
    assert config['browser']['gatherUsageStats'] is False
    assert '--server.address 127.0.0.1' in (ROOT/'run_app.sh').read_text()
    assert '--server.address 127.0.0.1' in (ROOT/'run_app.bat').read_text()


def test_claim_evidence_is_saved_from_existing_row(monkeypatch,tmp_path):
    app=start(monkeypatch,tmp_path)
    uid=app.session_state['fact_rows'][0]['_uid']
    app.selectbox(key='fact_kind_label_'+uid).set_value('주장')
    app.text_input(key='fact_evidence_'+uid).set_value('판매자가 제공한 테스트 근거 문서')
    app.button(key='create').click().run()
    assert not app.error
    job=Path(app.session_state['job'])
    fact=json.loads((job/'facts.json').read_text())['facts'][0]
    assert fact['kind']=='claim'
    assert fact['evidence']=='판매자가 제공한 테스트 근거 문서'


def test_evidence_and_item_delete_clear_review(monkeypatch,tmp_path):
    from core.workflow import create_job,ingest_job
    from core.facts import ProductFacts
    from core.ingest import extract_json
    monkeypatch.setenv('DETAIL_PAGE_OUTPUTS',str(tmp_path))
    facts=ProductFacts.model_validate_json((ROOT/'samples/facts.json').read_text())
    job=create_job(facts,ROOT/'samples',tmp_path)
    data=extract_json((ROOT/'samples/answer.txt').read_text())
    data['hero']['fact_ids']=['missing']
    data['features'].append({'title':'100% 효과','desc':'삭제할 문구','fact_ids':[]})
    ingest_job(job,json.dumps(data,ensure_ascii=False))
    app=AppTest.from_file(str(ROOT/'app/main.py'),default_timeout=60).run()
    app.selectbox(key='resume_job').set_value(str(job));app.button(key='resume').click().run()
    assert app.warning
    selected=next(m for m in app.multiselect if 'hero 근거 사실' in m.label)
    assert all('missing' not in o for o in selected.options)
    selected.set_value(['design'])
    app.button(key='remove_features-1_1').click().run()
    assert not app.exception
    assert not json.loads((job/'review.json').read_text())
    assert json.loads((job/'manifest.json').read_text())['needs_review'] is False
    assert len(next(s for s in json.loads((job/'draft.json').read_text())['sections'] if s['type']=='features')['items'])==1


def test_background_preview_and_five_checks(monkeypatch,tmp_path):
    import core.background
    import core.images
    from PIL import Image,ImageDraw
    class Fake:
        cache_key='apptest-fake'
        def remove(self,image):
            result=image.convert('RGBA');alpha=Image.new('L',image.size,0)
            ImageDraw.Draw(alpha).rectangle((image.width//4,image.height//4,image.width*3//4,image.height*3//4),fill=255)
            result.putalpha(alpha);return result
    monkeypatch.setattr(core.background,'available',lambda:True)
    monkeypatch.setattr(core.images,'get_remover',lambda:Fake())
    app=start(monkeypatch,tmp_path)
    next(c for c in app.checkbox if '배경 제거' in c.label).check().run()
    app.button(key='photo_preview').click().run(timeout=60)
    assert not app.exception and not app.error
    preview=Path(app.session_state['photo_preview_job'])
    meta=json.loads((preview/'manifest.json').read_text())
    assert meta['image_processing'][0]['background_removed']
    captions=[img.caption for node in app.get('image') for img in node.proto.imgs]
    assert any('처리 전' in caption for caption in captions)
    assert any('처리 후' in caption for caption in captions)
    assert any('체크무늬' in caption for caption in captions)
    app.button(key='create').click().run()
    stage(app,2);app.text_area(key='answer_text').set_value((ROOT/'samples/answer.txt').read_text());app.button(key='ingest').click().run()
    stage(app,5)
    assert len([c for c in app.checkbox if c.key.startswith('check_')])==5
    assert app.button(key='accept').disabled


def test_missing_background_option_disabled(monkeypatch,tmp_path):
    import core.background
    monkeypatch.setattr(core.background,'available',lambda:False)
    app=start(monkeypatch,tmp_path)
    assert next(c for c in app.checkbox if '배경 제거' in c.label).disabled
    app.button(key='create').click().run()
    assert app.session_state['stage']=='② 프롬프트'
