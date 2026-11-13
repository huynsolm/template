"""Local editor and immutable export regression coverage; no AI services."""
import copy
import io
import json
from pathlib import Path
import shutil
import sys
import zipfile

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.workflow import create_job, ingest_job, read_json
from core.facts import ProductFacts

@pytest.fixture
def job(tmp_path):
    facts=ProductFacts.model_validate_json((ROOT/'samples/facts.json').read_text())
    path=create_job(facts,ROOT/'samples',tmp_path)
    ingest_job(path,(ROOT/'samples/answer.txt').read_text())
    return path


def test_save_current_copy_and_persistent_history(job):
    from core.editor import save_draft, reassess_draft
    original=(job/'copy.json').read_bytes()
    data=read_json(job/'draft.json')
    data['sections'][0]['headline']='100% 인증 효과'
    save_draft(job,data,['hero-1'])
    assert (job/'copy.json').read_bytes()==original
    assert read_json(job/'draft.json')==data
    assert read_json(job/'edits.json')['locked_sections']==['hero-1']
    assert read_json(job/'history.json')[-1]['draft']==data
    assert any(i['section_id']=='hero-1' for i in reassess_draft(job))
    assert read_json(job/'review.json')==reassess_draft(job)


@pytest.mark.parametrize('kind',['product','spec','notice','review','lock','schema'])
def test_save_rejects_invalid_or_seller_changes_atomically(job,kind):
    from core.editor import save_draft
    before={p.name:p.read_bytes() for p in job.iterdir() if p.is_file()}
    data=read_json(job/'draft.json')
    locks=[]
    if kind=='product': data['product']['name']='임의 변경'
    if kind=='spec': next(s for s in data['sections'] if s['type']=='spec')['rows'][0][1]='임의 변경'
    if kind=='notice': data['sections'].append({'id':'new-notice','type':'notice','body':'임의 안내'})
    if kind=='review': data['sections'].append({'id':'new-review','type':'review','items':[{'text':'후기','rating':5,'source':'조작','permission_confirmed':True}]})
    if kind=='lock': locks=['unknown']
    if kind=='schema': data['sections'][0]['headline']='가'*81
    with pytest.raises(ValueError): save_draft(job,data,locks)
    assert {p.name:p.read_bytes() for p in job.iterdir() if p.is_file()}==before


def test_new_copy_units_and_unknown_refs_are_reassessed(job):
    from core.editor import reassess_draft
    data=read_json(job/'draft.json')
    section=next(s for s in data['sections'] if s['type']=='features')
    section['items'].append({'title':'100% 효능','desc':'새 문구'})
    (job/'draft.json').write_text(json.dumps(data,ensure_ascii=False))
    review=reassess_draft(job)
    assert any(i['section_id']==section['id'] and not i['fact_ids'] for i in review)
    original=read_json(job/'copy.json'); original['hero']['fact_ids']=['unknown']
    (job/'copy.json').write_text(json.dumps(original))
    assert any('unknown' in i['fact_ids'] for i in reassess_draft(job))


def test_preview_zip_snapshot_and_accepted_provenance(job):
    from core.editor import preview_job, build_zip, save_draft, reassess_draft, job_listing
    from core.workflow import accept_job
    bundle=preview_job(job)
    manifest=read_json(bundle/'manifest.json')
    assert manifest['job_id']==bundle.name
    assert manifest['draft_sha256']
    assert all('.DRAFT.' in p['file'] for p in manifest['pages'])
    old=(bundle/'draft.json').read_bytes()
    data=read_json(job/'draft.json'); data['sections'][0]['headline']='100% 인증 효과'
    save_draft(job,data,[])
    (bundle/'secret.txt').write_text('excluded')
    with zipfile.ZipFile(io.BytesIO(build_zip(bundle))) as archive:
        assert archive.read('draft.json')==old
        assert json.loads(archive.read('manifest.json'))['job_id']==manifest['job_id']
        assert 'secret.txt' not in archive.namelist()
        assert 'input.json' not in archive.namelist()
    # Acceptance must recheck current copy even if a stale review file is empty.
    (job/'review.json').write_text('[]')
    before={str(p.relative_to(job)):p.read_bytes() for p in job.rglob('*') if p.is_file()}
    accepted=accept_job(job)
    assert {str(p.relative_to(job)):p.read_bytes() for p in job.rglob('*') if p.is_file()}==before
    accepted_manifest=read_json(accepted/'manifest.json')
    approved=accepted/accepted_manifest['rendered_job']
    assert not any('.DRAFT.' in p['file'] for p in read_json(approved/'manifest.json')['pages'])
    assert read_json(approved/'draft.json')==data
    assert read_json(approved/'review.json')
    shutil.rmtree(job)
    assert reassess_draft(accepted)
    from core.workflow import regenerate_job
    assert regenerate_job(accepted).is_dir()
    save_draft(accepted,data,[])
    assert any(i['path']==str(accepted) and i['product_name']==data['product']['name'] for i in job_listing(accepted.parent))


def test_regenerated_locked_text_keeps_original_fact_ids(job):
    from core.editor import save_draft, reassess_draft
    from core.workflow import regenerate_job
    from core.ingest import extract_json
    data=read_json(job/'draft.json')
    save_draft(job,data,['hero-1'])
    child=regenerate_job(job)
    answer=extract_json((ROOT/'samples/answer.txt').read_text())
    answer['hero']['fact_ids']=['missing']
    ingest_job(child,json.dumps(answer,ensure_ascii=False))
    assert not any(i['section_id']=='hero-1' for i in reassess_draft(child))


def test_accepted_seller_snapshot_keeps_unused_images(job):
    from core.workflow import accept_job
    facts=read_json(job/'facts.json')
    shutil.copyfile(job/facts['images'][0]['path'],job/'images/unused.png')
    facts['images'].append({'path':'images/unused.png','role':'other'})
    (job/'facts.json').write_text(json.dumps(facts))
    accepted=accept_job(job)
    ProductFacts.model_validate(read_json(accepted/'facts.json')).validate_images(accepted)


def test_generate_existing_job_keeps_locked_copy_and_original_evidence(job):
    from core.editor import save_draft, reassess_draft
    from core.workflow import regenerate_job, generate_job
    from core.ingest import extract_json
    data=read_json(job/'draft.json')
    data['sections'][0]['headline']='사람이 잠근 제목'
    save_draft(job,data,['hero-1'])
    pending=regenerate_job(job)
    with pytest.raises(ValueError): ingest_job(pending,'broken')
    expected_prompt=(pending/'fix-prompt.md').read_text()
    original_files={name:(pending/name).read_bytes() for name in ('locked.json','locked-evidence.json','facts.json')}
    answer=extract_json((ROOT/'samples/answer.txt').read_text())
    answer['hero']['headline']='버려야 할 새 제목'
    answer['hero']['fact_ids']=['missing']
    class FakeProvider:
        name='fake'
        def generate(self,prompt):
            assert prompt==expected_prompt
            return json.dumps(answer,ensure_ascii=False)
    result=generate_job(None,None,None,FakeProvider(),existing_job=pending,source_label='가짜 생성기')
    assert result==pending
    assert read_json(result/'draft.json')['sections'][0]['headline']=='사람이 잠근 제목'
    assert not any(i['section_id']=='hero-1' for i in reassess_draft(result))
    assert all((pending/name).read_bytes()==content for name,content in original_files.items())
    manifest=read_json(result/'manifest.json')
    assert manifest['attempts']==2 and manifest['max_attempts']==3
    assert manifest['method']=='cli:fake' and manifest['source_label']=='가짜 생성기'
    with pytest.raises(ValueError,match='succeeded'):
        generate_job(None,None,None,FakeProvider(),existing_job=pending)


def test_generate_existing_job_counts_prior_attempts_against_cap(job):
    from core.workflow import regenerate_job, generate_job
    pending=regenerate_job(job)
    for _ in range(2):
        with pytest.raises(ValueError): ingest_job(pending,'broken')
    class FakeProvider:
        name='fake'
        calls=0
        def generate(self,prompt):
            self.calls+=1
            return 'broken'
    provider=FakeProvider()
    with pytest.raises(ValueError):
        generate_job(None,None,None,provider,existing_job=pending)
    assert provider.calls==1
    assert read_json(pending/'manifest.json')['attempts']==3
    with pytest.raises(ValueError,match='attempt'):
        generate_job(None,None,None,provider,existing_job=pending)
    assert provider.calls==1


def test_custom_review_terms_survive_edit_regenerate_and_accept(job):
    from core.workflow import regenerate_job, accept_job
    from core.editor import reassess_draft, save_draft
    pending=regenerate_job(job)
    ingest_job(pending,(ROOT/'samples/answer.txt').read_text(),terms=('매일',))
    assert any(i['section_id']=='hero-1' for i in read_json(pending/'review.json'))
    assert reassess_draft(pending)==read_json(pending/'review.json')
    save_draft(pending,read_json(pending/'draft.json'),[])
    child=regenerate_job(pending)
    ingest_job(child,(ROOT/'samples/answer.txt').read_text())
    assert any(i['section_id']=='hero-1' for i in reassess_draft(child))
    accepted=accept_job(child)
    assert any(i['section_id']=='hero-1' for i in reassess_draft(accepted))
    assert read_json(accepted/'manifest.json')['review_terms']==['매일']


def test_evidence_edits_resolve_warnings_and_keep_original_and_history(job):
    from core.editor import save_draft, evidence_units, reassess_draft, change_copy_items
    original=(job/'copy.json').read_bytes()
    data=read_json(job/'draft.json')
    data['sections'][0]['headline']='100% 인증 효과'
    changed=change_copy_items(data,'features-1','add')
    data=changed['data']
    save_draft(job,data,[])
    assert read_json(job/'manifest.json')['needs_review'] is True
    assert any(u['path']=='features.1' and u['fact_ids']==[] for u in evidence_units(job))
    changed=change_copy_items(data,'features-1','remove',1)
    save_draft(job,changed['data'],[],evidence={'hero':['spec-demo']})
    assert reassess_draft(job)==[]
    assert read_json(job/'manifest.json')['needs_review'] is False
    assert (job/'copy.json').read_bytes()==original
    assert read_json(job/'edited-evidence.json')['hero-1']['hero']==['spec-demo']
    history=read_json(job/'history.json')[-1]
    assert history['evidence']['hero-1']['hero']==['spec-demo']
    assert history['previous_evidence'].get('hero-1',{}).get('hero') is None


@pytest.mark.parametrize('evidence',[{'hero':['missing']},{'hero':'design'},{'hero':['design','design']},{'missing':['design']}])
def test_invalid_evidence_is_rejected_atomically(job,evidence):
    from core.editor import save_draft
    before={p.name:p.read_bytes() for p in job.iterdir() if p.is_file()}
    with pytest.raises(ValueError):
        save_draft(job,read_json(job/'draft.json'),[],evidence=evidence)
    assert {p.name:p.read_bytes() for p in job.iterdir() if p.is_file()}==before


@pytest.mark.parametrize('kind',['pain','features','how_to','faq'])
def test_core_list_mutation_limits_and_remapping(job,kind):
    from core.editor import change_copy_items
    data=read_json(job/'draft.json'); before=copy.deepcopy(data)
    sid=kind+'-1'; prefix='pain.items.' if kind=='pain' else kind+'.'
    path=lambda n: prefix+str(n)+('.text' if kind=='pain' else '')
    with pytest.raises(ValueError): change_copy_items(data,sid,'remove',0)
    added=change_copy_items(data,sid,'add')
    assert data==before
    assert added['path_map'][path(0)]==path(0)
    assert added['path_map'][path(1)] is None
    removed=change_copy_items(added['data'],sid,'remove',0)
    assert removed['path_map'][path(0)]==path(1)
    current=data
    for _ in range(9): current=change_copy_items(current,sid,'add')['data']
    with pytest.raises(ValueError): change_copy_items(current,sid,'add')
    with pytest.raises(ValueError): change_copy_items(data,sid,'remove',-1)
    with pytest.raises(ValueError): change_copy_items(data,'hero-1','add')


def test_deleting_item_does_not_inherit_evidence_of_old_position(job):
    from core.editor import save_draft,evidence_units,change_copy_items
    data=read_json(job/'draft.json')
    data=change_copy_items(data,'features-1','add')['data']
    next(s for s in data['sections'] if s['id']=='features-1')['items'][1]['title']='추가 문구'
    save_draft(job,data,[],evidence={'features.0':['design'],'features.1':['usage']})
    data=change_copy_items(data,'features-1','remove',0)['data']
    save_draft(job,data,[])
    refs=next(u for u in evidence_units(job) if u['path']=='features.0')
    assert refs['fact_ids']==[]


def test_list_mutation_remaps_evidence_in_core(job):
    from core.editor import save_draft,evidence_units,change_copy_items
    data=read_json(job/'draft.json')
    refs={u['key']:u['fact_ids'] for u in evidence_units(job)}
    added=change_copy_items(data,'features-1','add',evidence=refs)
    assert added['evidence']['features-1:features.1']==[]
    added['evidence']['features-1:features.1']=['usage']
    removed=change_copy_items(added['data'],'features-1','remove',0,evidence=added['evidence'])
    assert refs['features-1:features.0']==['design']
    assert removed['evidence']['features-1:features.0']==['usage']
    assert 'features-1:features.1' not in removed['evidence']
    save_draft(job,removed['data'],[],evidence=removed['evidence'])
    assert next(u for u in evidence_units(job) if u['key']=='features-1:features.0')['fact_ids']==['usage']
