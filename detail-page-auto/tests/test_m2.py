import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_facts_models_exist():
    from core.facts import ProductFacts
    assert ProductFacts is not None

@pytest.fixture
def facts():
    from core.facts import ProductFacts
    return ProductFacts.model_validate_json((ROOT/'samples/facts.json').read_text())

@pytest.fixture
def answer():
    return (ROOT/'samples/answer.txt').read_text()

@pytest.mark.parametrize('case',['duplicate','claim','extra'])
def test_invalid_facts(facts,case):
    from core.facts import ProductFacts
    data=facts.model_dump()
    if case=='duplicate': data['facts'].append(data['facts'][0])
    if case=='claim': data['facts'][0]['kind']='claim'; data['facts'][0]['evidence']=None
    if case=='extra': data['extra']=1
    with pytest.raises(ValueError): ProductFacts.model_validate(data)

@pytest.mark.parametrize('wrapper',['fence','prose','plain'])
def test_extract(answer,wrapper):
    from core.ingest import extract_json
    obj=json.loads(answer.split('```json')[1].split('```')[0])
    raw=json.dumps(obj,ensure_ascii=False)
    text={'fence':answer,'prose':'여기 답변입니다. '+raw+' 끝입니다.','plain':raw}[wrapper]
    assert extract_json(text)==obj

@pytest.mark.parametrize('text',['{} {}','```json\n{}\n```\n```json\n{}\n```','{broken','{"a":1,"a":2}'])
def test_extract_invalid(text):
    from core.ingest import extract_json
    with pytest.raises(ValueError): extract_json(text)


def test_workflow_and_render(tmp_path,facts,answer):
    from core.workflow import create_job,ingest_job
    from core.schema import Document
    job=create_job(facts,ROOT/'samples',tmp_path)
    assert '<facts>' in (job/'prompt.md').read_text()
    ingest_job(job,answer,source_label='테스트 답변',render_output=True)
    doc=Document.model_validate_json((job/'draft.json').read_text())
    assert not any(s.type=='review' for s in doc.sections)
    assert doc.product==facts.product
    assert (job/'rendered').is_dir()
    assert len(list((job/'rendered').glob('job-*/page-001.jpg')))==1
    manifest=json.loads((job/'manifest.json').read_text())
    assert manifest['attempts']==1 and manifest['method']=='paste'
    assert manifest['source_label']=='테스트 답변'

@pytest.mark.parametrize('case',['long','missing','extra','review','price'])
def test_repair_then_success(tmp_path,facts,answer,case):
    from core.workflow import create_job,ingest_job
    from core.ingest import extract_json
    job=create_job(facts,ROOT/'samples',tmp_path)
    data=extract_json(answer)
    if case=='long': data['hero']['headline']='가'*81
    if case=='missing': del data['hero']['headline']
    if case in ['extra','review','price']: data[case]='금지'
    with pytest.raises(ValueError): ingest_job(job,json.dumps(data,ensure_ascii=False))
    assert (job/'fix-prompt.md').exists()
    assert 'headline' in (job/'fix-prompt.md').read_text() if case in ['long','missing'] else True
    assert not (job/'draft.json').exists()
    ingest_job(job,answer)
    assert json.loads((job/'manifest.json').read_text())['attempts']==2
    assert (job/'attempts/answer-1.txt').exists()
    assert (job/'attempts/errors-2.json').read_text().strip()=='[]'


def test_reviews_claims_and_unknown(facts,answer):
    from core.ingest import extract_json
    from core.copy_schema import CopyDraft
    from core.assemble import assemble
    from core.schema import ReviewItem
    facts.reviews=[ReviewItem(text='판매자 제공 테스트 원문',rating=4,source='테스트',permission_confirmed=True)]
    data=extract_json(answer)
    data['hero']['headline']='100% 인증 효과'
    data['hero']['fact_ids']=['missing']
    doc,review=assemble(facts,CopyDraft.model_validate(data))
    assert next(s for s in doc.sections if s.type=='review').items==facts.reviews
    assert any('missing' in x['fact_ids'] for x in review)
    assert len(review)>=2
    assert doc.sections[0].headline=='100% 인증 효과'


def test_locked_regeneration(tmp_path,facts,answer):
    from core.workflow import create_job,ingest_job,regenerate_job
    from core.ingest import extract_json
    job=create_job(facts,ROOT/'samples',tmp_path)
    ingest_job(job,answer)
    previous=json.loads((job/'draft.json').read_text())
    previous['sections'][0]['headline']='사람이 고친 제목'
    (job/'draft.json').write_text(json.dumps(previous,ensure_ascii=False))
    (job/'edits.json').write_text('{"locked_sections":["hero-1"]}')
    before={p.name:p.read_bytes() for p in job.iterdir() if p.is_file()}
    child=regenerate_job(job)
    data=extract_json(answer); data['hero']['headline']='새 AI 제목'
    ingest_job(child,json.dumps(data,ensure_ascii=False))
    result=json.loads((child/'draft.json').read_text())
    assert result['sections'][0]==previous['sections'][0]
    assert all((job/name).read_bytes()==content for name,content in before.items())
    assert '사람이 고친 제목' in (child/'prompt.md').read_text()


def test_attempt_limit(tmp_path,facts):
    from core.workflow import create_job,ingest_job
    job=create_job(facts,ROOT/'samples',tmp_path,max_attempts=1)
    with pytest.raises(ValueError): ingest_job(job,'broken')
    with pytest.raises(ValueError,match='attempt'): ingest_job(job,'broken')
    assert not (job/'attempts/answer-2.txt').exists()


def test_cli_provider_retry_and_limits(tmp_path,facts,answer):
    from core.providers import CliProvider
    from core.workflow import generate_job
    counter=tmp_path/'counter'
    fixture=tmp_path/'answer.txt'; fixture.write_text(answer)
    script=tmp_path/'fake.py'
    script.write_text('import sys\nfrom pathlib import Path\nc=Path(sys.argv[1]); n=int(c.read_text()) if c.exists() else 0; c.write_text(str(n+1))\nprompt=sys.stdin.read()\nprint("broken" if n==0 else Path(sys.argv[2]).read_text())\n')
    config=tmp_path/'providers.toml'
    config.write_text('[providers.codex]\ncommand = '+json.dumps([sys.executable,str(script),str(counter),str(fixture)]))
    provider=CliProvider('codex',config_path=config)
    job=generate_job(facts,ROOT/'samples',tmp_path/'jobs',provider)
    manifest=json.loads((job/'manifest.json').read_text())
    assert manifest['attempts']==2 and manifest['method']=='cli:codex'
    assert counter.read_text()=='2'
    counter.unlink()
    with pytest.raises(ValueError): generate_job(facts,ROOT/'samples',tmp_path/'jobs',provider,max_attempts=1)
    assert counter.read_text()=='1'


def test_cli_paste_commands_and_validation_code(tmp_path):
    prompt=subprocess.run([sys.executable,str(ROOT/'cli.py'),'prompt','--facts',str(ROOT/'samples/facts.json'),'--images',str(ROOT/'samples'),'--output',str(tmp_path)],capture_output=True,text=True)
    assert prompt.returncode==0,prompt.stderr
    job=Path(prompt.stdout.strip())
    bad=tmp_path/'bad.txt'; bad.write_text('{"hero":{}}')
    result=subprocess.run([sys.executable,str(ROOT/'cli.py'),'ingest','--job',str(job),'--answer',str(bad)],capture_output=True,text=True)
    assert result.returncode==2
    result=subprocess.run([sys.executable,str(ROOT/'cli.py'),'ingest','--job',str(job),'--answer',str(ROOT/'samples/answer.txt'),'--source-label','고정 테스트 답변'],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_assembly_failure_has_no_success_outputs(tmp_path,facts,answer):
    from core.facts import Fact
    from core.workflow import create_job,ingest_job
    facts.facts.extend(Fact(id=f'spec-{i}',kind='spec',text='항목') for i in range(10))
    job=create_job(facts,ROOT/'samples',tmp_path)
    with pytest.raises(ValueError): ingest_job(job,answer)
    assert (job/'fix-prompt.md').exists()
    assert not any((job/f).exists() for f in ['draft.json','copy.json','review.json'])


def test_facts_images_use_m1_rules(tmp_path,facts):
    from core.workflow import create_job
    facts.images[0].path='../product.png'
    with pytest.raises(ValueError): create_job(facts,ROOT/'samples',tmp_path)
    assert not list(tmp_path.iterdir())


def test_json_with_quoted_braces_and_fenced_ambiguity():
    from core.ingest import extract_json
    assert extract_json('앞 {"text":"괄호 } { 및 \\\"인용\\\""} 뒤')['text']=='괄호 } { 및 "인용"'
    with pytest.raises(ValueError): extract_json('```json\n{}\n```\n{}')


def test_configurable_evidence_terms(facts,answer):
    from core.ingest import extract_json
    from core.copy_schema import CopyDraft
    from core.assemble import assemble
    data=extract_json(answer); data['hero']['headline']='특수표현'
    _,normal=assemble(facts,CopyDraft.model_validate(data),terms=())
    _,flagged=assemble(facts,CopyDraft.model_validate(data),terms=('특수표현',))
    assert not normal
    assert any(i['section_id']=='hero-1' for i in flagged)


def test_locks_survive_multiple_generations(tmp_path,facts,answer):
    from core.workflow import create_job,ingest_job,regenerate_job
    job=create_job(facts,ROOT/'samples',tmp_path)
    ingest_job(job,answer)
    original=json.loads((job/'draft.json').read_text())
    original['sections'][0]['headline']='유지할 수동 문구'
    (job/'draft.json').write_text(json.dumps(original,ensure_ascii=False))
    (job/'edits.json').write_text('{"locked_sections":["hero-1"]}')
    child=regenerate_job(job); ingest_job(child,answer)
    grandchild=regenerate_job(child); ingest_job(grandchild,answer)
    result=json.loads((grandchild/'draft.json').read_text())
    assert result['sections'][0]==original['sections'][0]


def test_locked_custom_image_is_preserved(tmp_path,facts,answer):
    from core.workflow import create_job,ingest_job,regenerate_job
    from PIL import Image
    job=create_job(facts,ROOT/'samples',tmp_path)
    ingest_job(job,answer)
    Image.new('RGB',(100,100),'red').save(job/'manual.png')
    doc=json.loads((job/'draft.json').read_text()); doc['sections'][0]['image']='manual.png'
    (job/'draft.json').write_text(json.dumps(doc,ensure_ascii=False))
    (job/'edits.json').write_text('{"locked_sections":["hero-1"]}')
    child=regenerate_job(job)
    ingest_job(child,answer)
    assert (child/'manual.png').read_bytes()==(job/'manual.png').read_bytes()
    assert json.loads((child/'draft.json').read_text())['sections'][0]==doc['sections'][0]
