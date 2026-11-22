import json
from pathlib import Path
import sys
from streamlit.testing.v1 import AppTest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from test_m7_extract import reply


def test_extract_ui_updates_inputs_and_readiness(tmp_path,monkeypatch):
    monkeypatch.setenv('DETAIL_PAGE_OUTPUTS',str(tmp_path))
    app=AppTest.from_file(str(ROOT/'app/main.py'),default_timeout=60).run()
    assert app.button(key='create').disabled
    app.button(key='sample').click().run()
    app.text_area(key='extract_answer').set_value(json.dumps(reply(),ensure_ascii=False))
    app.button(key='extract_parse').click().run()
    assert not app.exception
    assert app.text_input(key='product_name').value=='가상 샘플 보틀'
    app.button(key='extract_apply').click().run()
    assert not app.exception
    assert app.text_input(key='product_name').value=='가상 모듈'
    assert app.text_input(key='product_price').value=='판매하지 않음'
    assert app.session_state['input_metadata']['pending_claims']
    assert any('근거가 필요한 주장' in row.value for row in app.warning)
    assert not app.button(key='create').disabled
    assert app.checkbox(key='spec_verified_'+app.session_state['rich_revision']).value is False


def test_approval_requires_numeric_expression_confirmation(tmp_path,monkeypatch):
    from core.facts import ProductFacts
    from core.workflow import create_job,ingest_job,read_json
    from core.editor import save_draft
    monkeypatch.setenv('DETAIL_PAGE_OUTPUTS',str(tmp_path))
    facts=ProductFacts.model_validate_json((ROOT/'samples/facts.json').read_text())
    job=create_job(facts,ROOT/'samples',tmp_path)
    ingest_job(job,(ROOT/'samples/answer.txt').read_text())
    document=read_json(job/'draft.json')
    document['sections'][0]['headline']='가상 효율 99%'
    save_draft(job,document,[])
    app=AppTest.from_file(str(ROOT/'app/main.py'),default_timeout=120).run()
    app.button(key='resume').click().run()
    app.sidebar.radio[0].set_value('⑥ 승인').run()
    assert not app.exception
    for checkbox in app.checkbox:
        if not checkbox.key.startswith('check_claim_'):
            checkbox.check()
    app.run()
    assert app.button(key='accept').disabled
    for checkbox in app.checkbox:
        checkbox.check()
    app.run()
    assert not app.button(key='accept').disabled
    app.button(key='accept').click().run()
    assert not app.exception
    accepted=Path(app.session_state['job'])
    assert read_json(accepted/'manifest.json')['claim_checks'][0]['confirmed']
