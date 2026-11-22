import json
from pathlib import Path
import sys
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def test_claim_checklists_bind_evidence_and_require_confirmation(tmp_path):
    from core.facts import ProductFacts
    from core.workflow import create_job, ingest_job, read_json
    from core.editor import save_draft
    from core.claims import claim_items, confirmed_claims
    facts=ProductFacts.model_validate_json((ROOT/'samples/facts.json').read_text())
    job=create_job(facts,ROOT/'samples',tmp_path)
    ingest_job(job,(ROOT/'samples/answer.txt').read_text())
    document=read_json(job/'draft.json')
    document['sections'][0]['headline']='가상 시험에서 효율 99%'
    save_draft(job,document,[])
    items=claim_items(job)
    assert len(items)==1 and items[0]['expressions']==['99%']
    assert items[0]['facts'] and not items[0]['has_evidence']
    with pytest.raises(ValueError):
        confirmed_claims(items,[])
    result=confirmed_claims(items,[items[0]['id']])
    assert result[0]['confirmed'] is True


def test_each_expression_and_spec_evidence_are_separate(tmp_path):
    from core.facts import ProductFacts
    from core.workflow import create_job,ingest_job,read_json
    from core.claims import claim_items
    data=read_json(ROOT/'samples/facts.json')
    data['facts'].append({'id':'efficiency','kind':'claim','text':'가상 시험 효율 99%','evidence':'가상 시험 기록'})
    data['facts'].append({'id':'spec-percent','kind':'spec','text':'시험 조건 98%','evidence':'가상 시험 표'})
    job=create_job(ProductFacts.model_validate(data),ROOT/'samples',tmp_path)
    from core.ingest import extract_json
    answer=extract_json((ROOT/'samples/answer.txt').read_text())
    answer['hero'].update(headline='업계 최초로 가상 모델 대비 효율 99%',fact_ids=['efficiency'])
    ingest_job(job,json.dumps(answer,ensure_ascii=False))
    items=claim_items(job)
    hero=[item for item in items if item['section_id']=='hero-1']
    assert {item['expressions'][0] for item in hero}=={'최초','대비','99%'}
    assert all(item['has_evidence'] for item in hero)
    spec=next(item for item in items if item['section_id']=='spec-1')
    assert spec['facts'][0]['id']=='spec-percent' and spec['has_evidence']


def test_explicit_ingest_approval_records_claims(tmp_path):
    from core.facts import ProductFacts
    from core.workflow import create_job,ingest_job,read_json
    from core.ingest import extract_json
    job=create_job(ProductFacts.model_validate_json((ROOT/'samples/facts.json').read_text()),ROOT/'samples',tmp_path)
    answer=extract_json((ROOT/'samples/answer.txt').read_text())
    answer['hero']['headline']='가상 시험 효율 99%'
    ingest_job(job,json.dumps(answer,ensure_ascii=False),render_output=True,accept_review=True)
    meta=read_json(job/'manifest.json')
    assert meta['claim_checks'][0]['confirmed']
    bundle=next((job/'rendered').iterdir())
    assert read_json(bundle/'manifest.json')['claim_checks']==meta['claim_checks']
