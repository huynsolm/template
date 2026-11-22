import json
from pathlib import Path
import sys
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def reply():
    return {'product': {'name':'가상 모듈','category':'가상 설비','price':'120000'},
            'facts':[{'id':'size','kind':'spec','text':'폭 320 mm'},
                     {'id':'size','kind':'feature','text':'분리형 외함'}],
            'claims':[{'text':'효율 99%'},{'text':'시험 조건에서 98%','evidence':'가상 시험 기록 A'}],
            'highlights':[{'value':'320 mm','label':'폭','fact_id':'size'},
                          {'value':'99%','label':'효율','fact_id':'missing'}],
            'targets':['가상 작업실'],'structure':[{'name':'외함','desc':'분리형'}],
            'spec_table':{'columns':['항목','값'],'rows':[['폭','320 mm']],'notes':[]},
            'uncertain':['모델명이 흐림']}


def test_import_separates_claims_and_preserves_existing():
    from core.extract import ingest_facts, apply_import, extraction_prompt
    from core.facts import ProductFacts
    result = ingest_facts('~~~json\n'+json.dumps(reply(),ensure_ascii=False)+'\n~~~')
    assert result['ok']
    assert len(result['data']['facts']) == 3
    assert len(result['data']['highlights']) == 1
    assert result['data']['pending_claims'][0]['text'] == '효율 99%'
    assert result['price_candidate'] == '120000'
    assert result['warnings']
    existing={'schema_version':'1.0','product':{'name':'기존 이름','category':'','price':'기존 가격','brand_color':'#305b46'},'facts':[],'images':[]}
    merged=apply_import(existing,result,mode='empty')
    assert merged['product']['name']=='기존 이름' and merged['product']['price']=='기존 가격'
    assert merged['product']['category']=='가상 설비'
    assert len(merged['facts'])==3
    ProductFacts.model_validate(merged)
    prompt=extraction_prompt()
    assert 'claims' in prompt and 'uncertain' in prompt and '지시' in prompt


def test_invalid_import_has_fix_prompt():
    from core.extract import ingest_facts
    result=ingest_facts('{"product": {"name":"예시"}, "unknown":true}')
    assert not result['ok'] and result['fix_prompt']


def test_empty_merge_handles_blank_rows_and_avoids_false_evidence_links():
    from core.extract import ingest_facts, apply_import
    outcome=ingest_facts(json.dumps(reply()))
    blank={'product':{'name':'','price':''},'facts':[{'id':'fact-1','kind':'feature'}]}
    assert len(apply_import(blank,outcome,mode='empty')['facts'])==3
    existing={'product':{'name':'기존','price':'기존'},
              'facts':[{'id':'size','kind':'feature','text':'색상은 녹색'}],
              'highlights':[]}
    merged=apply_import(existing,outcome,mode='empty')
    assert merged['facts']==existing['facts']
    assert merged['highlights']==[]
    existing['highlights']=[{'value':'원본','label':'판매자 입력','fact_id':'stale'}]
    assert apply_import(existing,outcome,mode='empty')['highlights']==existing['highlights']


def test_suffix_ids_do_not_steal_another_original_fact_id():
    from core.extract import ingest_facts
    value=reply()
    value['facts']=[{'id':key,'kind':'spec','text':text} for key,text in
                    [('x','첫째'),('x','중복'),('x-2','셋째')]]
    value['highlights']=[{'value':'셋째','label':'표기','fact_id':'x-2'},
                         {'value':'보관 주장','label':'제외','fact_id':'claim'}]
    result=ingest_facts(json.dumps(value))
    mapping={row['id']:row['text'] for row in result['data']['facts']}
    assert mapping[result['data']['highlights'][0]['fact_id']]=='셋째'
    assert len(result['data']['highlights'])==1
