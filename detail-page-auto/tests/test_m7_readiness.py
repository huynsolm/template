from pathlib import Path
import sys
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def test_document_readiness_and_overrides(tmp_path):
    from core.readiness import check_readiness
    Image.new('RGB',(793,1122),'white').save(tmp_path/'page.png')
    data={'product':{'name':'예시','price':'130000','brand_color':'#777777'},
          'facts':[], 'images':[{'path':'page.png','role':'hero'}]}
    codes={r['code'] for r in check_readiness(data,tmp_path,{})}
    assert {'DOCUMENT_PHOTO','FEW_FACTS','NO_HIGHLIGHTS','NO_SPEC','NO_TARGETS','NUMERIC_PRICE','GREY_BRAND','LOW_RESOLUTION'} <= codes
    data['images'][0]['processing']={'crop':{'top':.1}}
    assert 'DOCUMENT_PHOTO' not in {r['code'] for r in check_readiness(data,tmp_path,{})}
    data['images'][0].pop('processing')
    data['images'][0]['document_confirmed']=True
    assert 'DOCUMENT_PHOTO' not in {r['code'] for r in check_readiness(data,tmp_path,{})}
    data['images'][0]['role']='diagram'
    codes={r['code'] for r in check_readiness(data,tmp_path,{})}
    assert 'DOCUMENT_PHOTO' not in codes and 'NO_HERO' in codes


def test_required_readiness_for_raw_empty_form(tmp_path):
    from core.readiness import check_readiness
    result=check_readiness({'product':{},'facts':[],'images':[]},tmp_path,{})
    assert {'NO_HERO','EMPTY_NAME'} <= {r['code'] for r in result if r['level']=='필수'}
    # M9 (user decision 2026-11-25): price is optional; an empty price is left off the page.
    assert 'EMPTY_PRICE' in {r['code'] for r in result if r['level']=='권장'}


def test_readiness_recommendations_and_sample_values(tmp_path):
    from core.readiness import check_readiness
    Image.new('RGB',(1000,1400),'white').save(tmp_path/'page.png')
    data={'product':{'name':'가상 샘플 보틀','price':'판매하지 않음','brand_color':'#305b46'},
          'facts':[],'images':[{'path':'page.png','role':'diagram'}],
          'pending_claims':[{'text':'최고 성능'}]}
    findings=check_readiness(data,tmp_path,{})
    codes={item['code'] for item in findings}
    assert {'NO_STRUCTURE','PENDING_CLAIMS','SAMPLE_TEXT','NO_HERO'} <= codes
    data['images'][0].update(role='hero',processing={'crop':{'left':.45,'right':.45}})
    assert any(item['code']=='INVALID_PHOTO' and item['level']=='필수' for item in check_readiness(data,tmp_path,{}))


def test_malformed_leaf_values_are_controlled_errors(tmp_path):
    from core.readiness import check_readiness
    for data in ({'product':{'name':['x']}},{'images':[{'path':None,'role':'hero'}]}):
        result=check_readiness(data,tmp_path,{})
        assert any(item['level']=='필수' for item in result)
