"""Single-user local UI. Business rules and exports live in core/."""
import copy
import json
import os
import sys
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

import streamlit as st
from pydantic import ValidationError

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.facts import ProductFacts
from core.workflow import create_job,ingest_job,regenerate_job,generate_job,accept_job,read_json
from core.uploads import stage_uploads
from core.themes import THEME_IDS
from core.editor import bundle_matches

STEPS=['�� ��ǰ ����','�� ������Ʈ','�� �亯 �ٿ��ֱ�','�� �˼�������','�� �̸�����','�� ����','�� �ٿ�ε�']
KINDS={'����':'spec','Ư¡':'feature','����':'usage','����':'claim','��Ÿ':'other'}
ROLES={'��ǥ':'hero','Ư¡':'feature','�ذ�':'solution','��Ÿ':'other'}
REFERENCE_KINDS={'�����':'competitor','���� ��Ҹ�':'customer_voice','��Ÿ':'other'}
NAMES={'hero':'��ǥ ����','pain':'���� ����','solution':'�ذ�','features':'Ư¡','how_to':'����','review':'�ı�','spec':'����','faq':'���� ���� ����','notice':'��ۡ���ȯ����ǰ �ȳ�'}
LABELS={'product':'��ǰ ����','name':'��ǰ��','category':'ī�װ���','price':'����','facts':'��ǰ ���','text':'����','evidence':'�ٰ�','reviews':'�ı�','permission_confirmed':'��� �㰡 Ȯ��','hero':'��ǥ ����','headline':'����','subcopy':'���� ����','images':'����','claim':'����','body':'����','features':'Ư¡','how_to':'����','faq':'�������亯','sections':'����'}
S=st.session_state


def display_time(value):
    try: return datetime.fromisoformat(value).astimezone(ZoneInfo('Asia/Seoul')).strftime('%Y-%m-%d %H:%M KST')
    except (ValueError,TypeError): return value


def outputs():
    return Path(os.environ.get('DETAIL_PAGE_OUTPUTS',str(ROOT/'outputs'))).resolve()


def go(index):
    S['next_stage']=STEPS[index]
    st.rerun()


def schedule_open(path,index):
    S['pending_job']=str(path)
    go(index)


def form_load(data=None,image_root=None):
    data=data or {'product':{'name':'','category':'','price':'','brand_color':'#305b46'},'facts':[{'id':'fact-1','text':'','kind':'feature'}],'images':[],'reviews':[]}
    for key in list(S):
        if key.startswith(('fact_','review_','reference_','edit_','lock_','check_','evidence_')): del S[key]
    for key,value in data['product'].items(): S['product_'+key]=value
    revision=uuid.uuid4().hex[:8]
    S['form_buffer']=copy.deepcopy(data)
    S['fact_rows']=[dict(row,_uid=revision+'-'+str(i)) for i,row in enumerate(data['facts'])]
    S['review_rows']=[dict(row,_uid=revision+'-'+str(i)) for i,row in enumerate(data.get('reviews',[]))]
    S['reference_rows']=[dict(row,_uid=revision+'-'+str(i)) for i,row in enumerate(data.get('references',[]))]
    S['reference_names_text']=', '.join(data.get('reference_names',[]))
    S['notice']=data.get('notice','')
    S['image_refs']=copy.deepcopy(data.get('images',[]))
    S['image_root']=str(image_root) if image_root else ''
    S['photo_preview_job']=''
    S['field_errors']={}; S['upload_error']=''


def open_job(path):
    job=Path(path)
    data=read_json(job/'facts.json')
    form_load(data,job)
    S['job']=str(job); S['bundle']=''; S['last_error']=''
    manifest=read_json(job/'manifest.json')
    S['theme_choice']=manifest.get('theme','classic')
    if manifest.get('review_accepted') and manifest.get('rendered_job'):
        S['bundle']=str(job/manifest['rendered_job'])
    elif (job/'preview.json').exists():
        info=read_json(job/'preview.json')
        bundle=job/info['bundle']
        if bundle.is_dir(): S['bundle']=str(bundle)
    if S['bundle'] and (job/'draft.json').exists():
        if not bundle_matches(job,Path(S['bundle'])): S['bundle']=''


def error_text(exc):
    text=str(exc)
    labels={**NAMES,**LABELS}
    for source in sorted(labels,key=len,reverse=True): text=text.replace(source,labels[source])
    if 'claim requires evidence' in str(exc): text+='\n������ �ٰŸ� �Է��ؾ� ������ �� �ֽ��ϴ�.'
    text=text.replace('Field required','�ʼ� �Է��Դϴ�.').replace('String should have at least 1 character','�� ���� �̻� �Է��� �ּ���.')
    text=text.replace('CLI time limit exceeded.','CLI ���� �ð��� �ʰ��߽��ϴ�. �ٿ��ֱ� ������� �����ϼ���.').replace('CLI usage limit reached; switch to paste mode.','���� ��뷮 �ѵ��� �����߽��ϴ�. �ٿ��ֱ� ������� ��ȯ�ϼ���.')
    if 'permission_confirmed' in str(exc): text+='\n�ı��� ��� �㰡 Ȯ���� üũ�� �ּ���.'
    return text


def perform(name,fn):
    if S.get('busy'): return False,None
    S['busy']=True
    S['last_error']=''; S['field_errors']={}
    try:
        with st.spinner(name+' ���Դϴ١�'):
            return True,fn()
    except ValidationError as exc:
        S['field_errors']={'.'.join(map(str,e['loc'])):error_text(e['msg']) for e in exc.errors()}
        S['last_error']='�Է� ������ Ȯ���� �ּ���. '+error_text(exc)
    except (ValueError,OSError) as exc:
        S['last_error']=error_text(exc)
    except Exception as exc:
        job=Path(S['job']) if S.get('job') else outputs()/'app-errors'
        job.mkdir(parents=True,exist_ok=True)
        path=job/('ui-error-'+uuid.uuid4().hex+'.log')
        # No input values, environment, CLI output or credential/config dumps.
        path.write_text('operation='+name+'\nexception_type='+type(exc).__name__+'\n',encoding='utf-8')
        S['last_error']='����ġ ���� ������ �߻��߽��ϴ�. �ٽ� �õ��� �ּ���. ���� ���: '+str(path)
    finally:
        S['busy']=False
    return False,None


def field_error(path):
    for key,message in S.get('field_errors',{}).items():
        if key==path or key.startswith(path+'.'): st.error(message)


def sync_rows(kind):
    for row in S[kind+'_rows']:
        uid=row['_uid']
        fields=(['id','text','evidence'] if kind=='fact' else
                ['text','rating','source','permission_confirmed'] if kind=='review' else
                ['id','label','text','source_note'])
        for key in fields:
            widget=f'{kind}_{key}_{uid}'
            if widget in S: row[key]=S[widget]
        if kind=='fact' and f'fact_kind_label_{uid}' in S:
            row['kind']=KINDS[S[f'fact_kind_label_{uid}']]
        if kind=='reference' and f'reference_kind_label_{uid}' in S:
            row['kind']=REFERENCE_KINDS[S[f'reference_kind_label_{uid}']]


def move_row(kind,index,delta):
    sync_rows(kind)
    rows=S[kind+'_rows']; other=index+delta
    if 0<=other<len(rows): rows[index],rows[other]=rows[other],rows[index]


def remove_row(kind,index):
    sync_rows(kind); S[kind+'_rows'].pop(index)


def add_row(kind):
    sync_rows(kind)
    uid=uuid.uuid4().hex[:8]
    row=({'_uid':uid,'id':'fact-'+uid,'text':'','kind':'feature','evidence':''} if kind=='fact' else
         {'_uid':uid,'text':'','rating':5,'source':'','permission_confirmed':False} if kind=='review' else
         {'_uid':uid,'id':'reference-'+uid,'label':'','kind':'other','text':'','source_note':''})
    S[kind+'_rows'].append(row)


def uploaded():
    files=S.get('photos',[])
    if not files:
        S['image_refs']=[]; S['image_root']=''; return
    try:
        root,refs=stage_uploads([(f.name,f.getvalue()) for f in files],outputs())
        S['image_root']=str(root); S['image_refs']=refs; S['upload_error']=''
    except (ValueError,OSError) as exc:
        S['image_refs']=[]; S['upload_error']=error_text(exc)


def facts_data():
    sync_rows('fact'); sync_rows('review'); sync_rows('reference')
    facts=[]
    for row in S['fact_rows']:
        data={k:v for k,v in row.items() if k!='_uid' and v!=''}
        facts.append(data)
    reviews=[{k:v for k,v in row.items() if k!='_uid'} for row in S['review_rows']]
    data={'schema_version':'1.0','product':{key:S['product_'+key] for key in ['name','category','price','brand_color']},'facts':facts,'images':S['image_refs'],'reviews':reviews}
    references=[{k:v for k,v in row.items() if k!='_uid'} for row in S['reference_rows']]
    if references: data['references']=references
    names=[name.strip() for name in S.get('reference_names_text','').split(',') if name.strip()]
    if names: data['reference_names']=names
    if S.get('notice','').strip(): data['notice']=S['notice']
    S['form_buffer']=copy.deepcopy(data)
    return data


def photo_previews():
    source=S.get('photo_preview_job') or (S.get('job') if S.get('image_root')==S.get('job') else '')
    if not source or not (Path(source)/'manifest.json').exists(): return
    manifest=read_json(Path(source)/'manifest.json')
    for i,record in enumerate(manifest.get('image_processing',[])):
        cols=st.columns(2)
        cols[0].image(str(Path(source)/record['source_path']),caption=f'���� {i+1} ó�� ��',width=220)
        settings=S['image_refs'][i].get('processing',{}) if i<len(S['image_refs']) else {}
        path=record['selected_path'] if settings.get('remove_background') else record['normalized_path']
        cols[1].image(str(Path(source)/path),caption=f'���� {i+1} ó�� ��',width=220)
        if settings.get('remove_background') and record.get('mask_preview_path'):
            st.image(str(Path(source)/record['mask_preview_path']),caption='��� ���� ����ũ (üũ����)',width=220)
    for item in manifest.get('image_reviews',[]): st.warning(item['reason'])


def input_page():
    for key,value in S.get('form_buffer',{}).get('product',{}).items():
        if 'product_'+key not in S: S['product_'+key]=value
    if 'notice' not in S: S['notice']=S.get('form_buffer',{}).get('notice','')
    st.header('�� ��ǰ ����')
    if st.button('���� ������ �ֱ�',key='sample'):
        form_load(read_json(ROOT/'samples/facts.json'),ROOT/'samples'); st.rerun()
    imported=st.file_uploader('���� facts.json �ҷ�����',type=['json'],key='facts_upload')
    if imported and st.button('�Է� ������� �ҷ�����'):
        ok,data=perform('��� �ҷ�����',lambda:ProductFacts.model_validate_json(imported.getvalue()).model_dump(exclude_none=True))
        if ok: form_load(data); S['last_error']='������ ������ ���ε��� �ּ���.'
        st.rerun()
    st.text_input('��ǰ��',key='product_name'); field_error('product.name')
    st.text_input('ī�װ���',key='product_category'); field_error('product.category')
    st.text_input('���� (ǥ�ÿ�)',key='product_price'); field_error('product.price')
    st.color_picker('�귣�� ����',key='product_brand_color')
    st.subheader('��ǰ ���')
    for index,row in enumerate(S['fact_rows']):
        uid=row['_uid']
        with st.container(border=True):
            st.text_input(f'��� ID {index+1}',value=row.get('id',''),key=f'fact_id_{uid}')
            st.text_area(f'��� ���� {index+1}',value=row.get('text',''),key=f'fact_text_{uid}')
            labels=list(KINDS)
            chosen=next(k for k,v in KINDS.items() if v==row.get('kind','feature'))
            label=st.selectbox(f'���� {index+1}',labels,index=labels.index(chosen),key=f'fact_kind_label_{uid}')
            row['kind']=KINDS[label]
            st.text_input(f'�ٰ� {index+1}',value=row.get('evidence',''),key=f'fact_evidence_{uid}')
            field_error(f'facts.{index}')
            cols=st.columns(3)
            cols[0].button('����',key=f'up_{uid}',on_click=move_row,args=('fact',index,-1),disabled=index==0)
            cols[1].button('�Ʒ���',key=f'down_{uid}',on_click=move_row,args=('fact',index,1),disabled=index==len(S['fact_rows'])-1)
            cols[2].button('����',key=f'delete_{uid}',on_click=remove_row,args=('fact',index))
    st.button('��� �� �߰�',on_click=add_row,args=('fact',))
    st.subheader('���� �ڷ� (����)')
    st.info('���۱��� �ִ� ���� ������ ������ �ϰ� �״�� ���� �ʽ��ϴ�. �ּҴ� ��ó �޸�θ� �����ϸ� �������� �ʽ��ϴ�.')
    st.text_input('����硤�귣�� �̸� (��ǥ�� ����)',key='reference_names_text')
    sync_rows('reference')
    for index,row in enumerate(S['reference_rows']):
        uid=row['_uid']
        with st.container(border=True):
            st.text_input(f'���� �ڷ� ID {index+1}',value=row.get('id',''),key=f'reference_id_{uid}')
            st.text_input(f'���� �ڷ� �̸� {index+1}',value=row.get('label',''),key=f'reference_label_{uid}')
            labels=list(REFERENCE_KINDS)
            chosen=next(k for k,v in REFERENCE_KINDS.items() if v==row.get('kind','other'))
            label=st.selectbox(f'���� �ڷ� ���� {index+1}',labels,index=labels.index(chosen),key=f'reference_kind_label_{uid}')
            row['kind']=REFERENCE_KINDS[label]
            st.text_area(f'���� �ڷ� ���� {index+1} (�ִ� 5,000��)',value=row.get('text',''),key=f'reference_text_{uid}')
            st.text_input(f'��ó �޸� {index+1} (URL�� ��ϸ� ��)',value=row.get('source_note',''),key=f'reference_source_note_{uid}')
            field_error(f'references.{index}')
            st.button('���� �ڷ� ����',key=f'delete_reference_{uid}',on_click=remove_row,args=('reference',index))
    st.button('���� �ڷ� �߰�',on_click=add_row,args=('reference',))
    sync_rows('reference')
    from core.similarity import personal_data_warnings
    warning_names={'email':'�̸���','phone':'��ȭ��ȣ','order_number':'�ֹ���ȣ'}
    for finding in personal_data_warnings(S['reference_rows']):
        st.warning(f"{warning_names[finding['kind']]} ���°� �ֽ��ϴ�: {finding['reference_label'] or finding['reference_id']} �� ���� ���� Ȯ���ϰ� ���� �ּ���.")
    st.subheader('����')
    st.file_uploader('��ǰ ���� (PNG/JPEG, �ִ� 5��, ��� 10MB)',type=['png','jpg','jpeg'],accept_multiple_files=True,key='photos',on_change=uploaded)
    if S.get('upload_error'): st.error(S['upload_error'])
    field_error('images')
    from core.background import available
    bg_ready=available()
    if not bg_ready: st.caption('��� ���Ŵ� ���� ��ġ�Դϴ�. requirements-bg.lock�� ��ġ�ϸ� Ȱ��ȭ�˴ϴ�.')
    for i,ref in enumerate(S['image_refs']):
        path=Path(S['image_root'])/ref['path']
        if S['image_root'] and path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(Path(S['image_root']).resolve()): st.image(str(path),width=160)
        labels=list(ROLES); current=next(k for k,v in ROLES.items() if v==ref['role'])
        chosen=st.selectbox(f'���� {i+1} ����',labels,index=labels.index(current),key=f'image_role_{S["image_root"]}_{i}')
        ref['role']=ROLES[chosen]
        from core.images import Processing
        settings=Processing.model_validate(ref.get('processing',{})).model_dump()
        settings['remove_background']=st.checkbox(f'���� {i+1} ��� ���� (����)',value=bool(settings['remove_background'] and bg_ready),disabled=not bg_ready,key=f'bg_{S["image_root"]}_{i}') and bg_ready
        ref['processing']=settings
    if S['image_refs'] and st.button('���� ó�� �̸�����',key='photo_preview',disabled=S.get('busy',False)):
        def preview_photos():
            facts=ProductFacts.model_validate(facts_data())
            if not S['image_root']: raise ValueError('��ǰ ������ ���ε��� �ּ���.')
            return create_job(facts,Path(S['image_root']),outputs(),method='image-preview')
        ok,preview=perform('���� ó��',preview_photos)
        if ok: S['photo_preview_job']=str(preview)
        st.rerun()
    photo_previews()
    st.subheader('���� �ı� (����)')
    st.info('AI�� �ı⸦ ������ ������ ���� �㰡���� �ı⸸ �Է��ϼ���.')
    for index,row in enumerate(S['review_rows']):
        uid=row['_uid']
        with st.container(border=True):
            st.text_area(f'�ı� ���� {index+1}',value=row.get('text',''),key=f'review_text_{uid}')
            st.number_input(f'�ı� ���� {index+1}',min_value=1,max_value=5,value=row.get('rating',5),step=1,key=f'review_rating_{uid}')
            st.text_input(f'�ı� ��ó {index+1}',value=row.get('source',''),key=f'review_source_{uid}')
            st.checkbox('��� �㰡 Ȯ��',value=row.get('permission_confirmed',False),key=f'review_permission_confirmed_{uid}')
            field_error(f'reviews.{index}')
            st.button('�ı� ����',key=f'delete_review_{uid}',on_click=remove_row,args=('review',index))
    st.button('�ı� �߰�',on_click=add_row,args=('review',))
    st.text_area('��ۡ���ȯ����ǰ �ȳ� (����)',key='notice'); field_error('notice')
    data=facts_data()
    st.download_button('facts.json ��������',data=json.dumps(data,ensure_ascii=False,indent=2),file_name='facts.json',mime='application/json')
    if st.button('�����ϰ� ������Ʈ �����',key='create',type='primary',disabled=S.get('busy',False)):
        def create():
            facts=ProductFacts.model_validate(data)
            if not S['image_root']: raise ValueError('��ǰ ������ ���ε��� �ּ���.')
            return create_job(facts,Path(S['image_root'] or '.'),outputs())
        ok,job=perform('��ǰ ��� ����',create)
        if ok: schedule_open(job,1)
        else: st.rerun()


def prompt_page(job):
    st.header('�� ������Ʈ ����')
    st.info('Claude��ChatGPT��Gemini �� �ϳ��� ä��â�� �ٿ��ְ�, �亯 ��ü�� ������ ���� �ܰ迡 �ٿ���������.')
    text=(job/'prompt.md').read_text(encoding='utf-8')
    st.code(text,language='markdown')
    st.download_button('������Ʈ ���� �ٿ�ε�',text,file_name='prompt.md')
    if st.button('�亯 �ٿ��ֱ�� �̵�'): go(2)
    import tomllib
    from core.providers import CliProvider
    configuration=tomllib.loads((ROOT/'providers.toml').read_text())
    enabled=[name for name,value in configuration.get('providers',{}).items() if value.get('command') and value.get('configured',True)]
    if enabled:
        with st.expander('����: �α��ε� ���� CLI ���'):
            name=st.selectbox('���� CLI',enabled)
            if st.button('CLI�� �ڵ� ����',disabled=S.get('busy',False)):
                def generate():
                    facts=ProductFacts.model_validate(read_json(job/'facts.json'))
                    return generate_job(facts,job,outputs(),CliProvider(name),source_label=name,existing_job=job)
                ok,new=perform('CLI ���� ���� (���� �� �ٿ��ֱ� ����� ����ϼ���)',generate)
                if ok: schedule_open(new,3)
                else:
                    S['last_error']='CLI ������ �Ϸ����� ���߽��ϴ�. �α��Ρ����������� �ð������� ��뷮�� Ȯ���ϰ� �ٿ��ֱ� ������� �����ϼ���. '+S['last_error']; st.rerun()


def answer_page(job):
    st.header('�� �亯 �ٿ��ֱ�')
    manifest=read_json(job/'manifest.json')
    st.caption(f'�õ� {manifest.get("attempts",0)} / {manifest.get("max_attempts",5)}')
    text=st.text_area('�亯 ��ü',height=350,key='answer_text')
    source=st.selectbox('�亯 ��ó',['Claude ä��','ChatGPT','Gemini','��Ÿ'])
    if source=='��Ÿ': source=st.text_input('��ó ���� �Է�')
    if st.button('�亯 ����������',key='ingest',type='primary',disabled=S.get('busy',False)):
        ok,_=perform('�亯 ����',lambda:ingest_job(job,text,source_label=source))
        if ok: go(3)
        else: st.rerun()
    if (job/'fix-prompt.md').exists():
        st.warning('�� ���� ��û�� ���� ä�ÿ� �ٿ���������. ��ģ �亯 ��ü�� �ٽ� �Է��� �ּ���.')
        count=manifest.get('attempts',0)
        errors=job/'attempts'/f'errors-{count}.json'
        if errors.exists():
            for error in read_json(errors): st.error(error_text(error.get('field_path','')+': '+error.get('reason','')))
        st.code((job/'fix-prompt.md').read_text(encoding='utf-8'),language='markdown')


def editable_fields(section):
    kind=section['type']
    if kind=='hero': return [('headline',80),('subcopy',300)]
    if kind=='pain': return [('title',80)]+[(f'items.{i}',300) for i in range(len(section['items']))]
    if kind=='solution': return [('title',80),('body',2000)]
    if kind in ('features','how_to'):
        array='items' if kind=='features' else 'steps'
        return [(f'{array}.{i}.{field}',limit) for i in range(len(section[array])) for field,limit in [('title',80),('desc',300)]]
    if kind=='faq': return [(f'items.{i}.{field}',limit) for i in range(len(section['items'])) for field,limit in [('q',200),('a',1000)]]
    return []


def nested(data,path,value=None,set_value=False):
    parts=path.split('.'); node=data
    for part in parts[:-1]: node=node[int(part)] if isinstance(node,list) else node[part]
    last=int(parts[-1]) if isinstance(node,list) else parts[-1]
    if set_value: node[last]=value
    else: return node.get(last,'') if isinstance(node,dict) else node[last]


def edit_key(job,sid,path):
    suffix=S.get('editor_revision','')
    return f'edit_{job.name}_{sid}_{path}'+('_'+suffix if suffix else '')


def evidence_key(job,unit):
    return f'evidence_{job.name}_{unit["key"]}_{S.get("editor_revision","")}'


def editor_snapshot(job,document,units,choices):
    result=copy.deepcopy(document)
    for section in result['sections']:
        for path,_ in editable_fields(section):
            value=S.get(edit_key(job,section['id'],path),nested(section,path) or '')
            if section['type']=='hero' and path=='subcopy' and not value: section.pop('subcopy',None)
            else: nested(section,path,value,True)
    refs={u['key']:S.get(evidence_key(job,u),[fid for fid in u['fact_ids'] if fid in choices]) for u in units}
    return result,refs


def edit_page(job):
    from core.editor import save_draft,evidence_units,change_copy_items
    st.header('�� �˼������� ����')
    document=read_json(job/'draft.json')
    reviews=read_json(job/'review.json')
    for item in reviews:
        if item['section_id']=='images': st.warning('���� �˼�: '+item['reason'])
    facts={f['id']:f['text'] for f in read_json(job/'facts.json')['facts']}
    units=evidence_units(job,document)
    edited,references=editor_snapshot(job,document,units,facts)
    locks=read_json(job/'edits.json').get('locked_sections',[]) if (job/'edits.json').exists() else []
    selected=[]
    st.info('���ݡ���ǰ�����ı⡤���塤�ȳ� ������ �� ��ǰ �������� �����ϰ� �� �۾��� �����ϼ���.')
    for index,section in enumerate(edited['sections']):
        sid=section['id']; kind=section['type']
        with st.container(border=True):
            st.subheader(NAMES[kind])
            for item in reviews:
                if item['section_id']==sid:
                    st.warning('�˼�: '+error_text(item['reason'])+' �� '+item.get('field_path',''))
                    if item.get('reason')=='���� �ڷ�� ǥ�� ����' and item.get('detail'):
                        st.code(item['detail'].get('text',''),language=None)
            fields=editable_fields(section)
            if not fields: st.json(section,expanded=False)
            for path,limit in fields:
                initial=nested(section,path) or ''
                value=st.text_area(f'{NAMES[kind]} �� {path} (���� {limit}��)',value=initial,key=edit_key(job,sid,path))
                st.caption(f'{len(value)} / {limit}��')
                if kind=='hero' and path=='subcopy' and not value:
                    section.pop('subcopy',None)
                else:
                    nested(section,path,value,True)
            for unit in units:
                if unit['section_id']==sid:
                    references[unit['key']]=st.multiselect(f'{NAMES[kind]} �� {unit["path"]} �ٰ� ���',options=list(facts),default=[fid for fid in unit['fact_ids'] if fid in facts],format_func=lambda fid:fid+': '+facts[fid],key=evidence_key(job,unit))
            if kind in ('pain','features','how_to','faq'):
                array='steps' if kind=='how_to' else 'items'
                def mutate(action,item_index=None):
                    snapshot,refs=editor_snapshot(job,document,units,facts)
                    changed=change_copy_items(snapshot,sid,action,item_index,evidence=refs)
                    locked=[part['id'] for part in document['sections'] if S.get(f'lock_{job.name}_{part["id"]}',part['id'] in locks)]
                    save_draft(job,changed['data'],locked,evidence=changed['evidence'])
                for number in range(len(section[array])):
                    if st.button(f'{NAMES[kind]} �׸� {number+1} ����',key=f'remove_{sid}_{number}'):
                        ok,_=perform('��� �׸� ���� �� ��˼�',lambda n=number:mutate('remove',n))
                        if ok: S['editor_revision']=uuid.uuid4().hex[:8];S['bundle']=''
                        st.rerun()
                if st.button(f'{NAMES[kind]} �׸� �߰�',key=f'add_{sid}'):
                    ok,_=perform('��� �׸� �߰�',lambda:mutate('add'))
                    if ok: S['editor_revision']=uuid.uuid4().hex[:8];S['bundle']=''
                    st.rerun()
            if st.checkbox('��� (����� �� ����)',value=sid in locks,key=f'lock_{job.name}_{sid}'): selected.append(sid)
    if st.button('���� ���塤��˼�',key='save_edits',type='primary',disabled=S.get('busy',False)):
        ok,_=perform('���� ���� �� �ٰ� ��˼�',lambda:save_draft(job,edited,selected,evidence=references))
        if ok:
            S['bundle']=''; S['last_error']=''; S['saved_message']='������ �˼� ����� �����߽��ϴ�.'
        st.rerun()
    if S.get('saved_message'): st.success(S['saved_message'])
    if st.button('����� ���� ���� �ٽ� ����',disabled=S.get('busy',False)):
        ok,new=perform('����� ������Ʈ �����',lambda:regenerate_job(job))
        if ok: schedule_open(new,1)
        else: st.rerun()
    if st.button('������ ���� �̸�����',key='to_preview'): go(4)


def display_bundle(bundle):
    manifest=read_json(bundle/'manifest.json')
    st.caption('�۾� ���� ID: '+manifest['job_id'])
    if manifest.get('contrast_adjustments'):
        st.info('�귣�� �� ��� ������')
    if not manifest.get('review_accepted'):
        st.warning('DRAFT �� ���� �� �̸������Դϴ�. �˼� �׸�� ������ Ȯ���ϼ���.')
    if manifest.get('needs_review'):
        if manifest.get('review_accepted'): st.info('���� �Ϸ� �� �˼� ����� review.json�� �����˴ϴ�.')
        else: st.error('�˼� �ʿ�: �ٰš���ġ������ ǥ���� Ȯ���� �ּ���.')
    for page in manifest['pages']: st.image(str(bundle/page['file']),width='stretch')
    return manifest


def preview_page(job):
    from core.editor import preview_job
    st.header('�� �̸�����')
    current_theme=read_json(job/'manifest.json').get('theme','classic')
    if 'theme_choice' not in S: S['theme_choice']=current_theme
    selected=st.selectbox('������ �׸�',THEME_IDS,key='theme_choice')
    if selected!=current_theme:
        ok,bundle=perform('�׸� �̸����� ������',lambda:preview_job(job,theme=selected))
        if ok:
            S['bundle']=str(bundle)
            for key in list(S):
                if key.startswith('check_'): del S[key]
        else:
            return
    if st.button('����� ������ �̸����� ����',key='preview',disabled=S.get('busy',False)):
        bundle=Path(S['bundle']) if S.get('bundle') else None
        if bundle is None or not bundle_matches(job,bundle):
            ok,bundle=perform('�̸����� ������',lambda:preview_job(job,theme=selected))
            if not ok: st.rerun()
            S['bundle']=str(bundle)
        st.rerun()
    if S.get('bundle'): display_bundle(Path(S['bundle']))
    if st.button('���� �ܰ�� �̵�'): go(5)
    if S.get('bundle') and st.button('DRAFT �ٿ�ε� �ܰ�� �̵�'): go(6)


def approval_page(job):
    st.header('�� ����')
    theme=read_json(job/'manifest.json').get('theme','classic')
    context=(str(job),theme)
    if S.get('approval_context')!=context:
        for key in list(S):
            if key.startswith('check_'): del S[key]
        S['approval_context']=context
    st.caption('������ �׸�: '+theme)
    labels=['��� ��ġ Ȯ��','�ı� ��ó���㰡 Ȯ��','ȿ�ɡ���ġ������ ǥ�� Ȯ��','��� �÷��� ���ε� �԰��� ���� Ȯ�� �ʿ����� ����','��ǰ ������ ���¡������� ������ �ٸ��� �ٲ��� �ʾҴ��� Ȯ��']
    checks=[st.checkbox(label,key=f'check_{job.name}_{i}') for i,label in enumerate(labels)]
    if st.button('��� Ȯ�������� ����',key='accept',type='primary',disabled=not all(checks) or S.get('busy',False)):
        ok,accepted=perform('���� ��� ������',lambda:accept_job(job))
        if ok:
            schedule_open(accepted,6)
        else: st.rerun()


def download_page(job):
    from core.editor import build_zip
    st.header('�� �ٿ�ε�')
    if not S.get('bundle'):
        st.info('�뿡�� �̸����⸦ ����ų� �쿡�� ������ �ּ���.'); return
    bundle=Path(S['bundle'])
    if not bundle_matches(job,bundle):
        st.warning('����� ���� �Ǵ� �׸��� ����Ǿ����ϴ�. �뿡�� �� �̸����⸦ ����� �ּ���.'); return
    manifest=read_json(bundle/'manifest.json')
    ok,data=perform('ZIP �غ�',lambda:build_zip(bundle))
    if ok:
        S['download_zip']=data
        filename=manifest['job_id']+('' if manifest.get('review_accepted') else '.DRAFT')+'.zip'
        st.download_button('ZIP �ٿ�ε�',data=data,file_name=filename,mime='application/zip',key='download_zip_button')
    export_section(bundle)
    display_bundle(bundle)


def export_section(bundle):
    """Platform profile check and per-profile ZIP. All rules live in core/export.py."""
    from core.export import build_export_zip, export_bundle, list_profiles, load_profile
    st.subheader('�ø� �� �԰� �˻硤��������')
    st.caption('�������� �������� ���̡��뷮��������������� �˻��� ���� ZIP�� ����ϴ�. ���� ������ Ȯ�ε��� ���� �������� "�԰� ��Ȯ��"���� ǥ���ϸ�, ���� ��� �԰��� �ø� ������ �ٽ� Ȯ���ؾ� �մϴ�.')
    profiles=list_profiles()
    # A newly saved profile is selected on the next run (a widget's value cannot change after it is drawn).
    if 'export_profile_next' in S: S['export_profile']=S.pop('export_profile_next')
    names={p['id']:p['name']+(' �� �԰� ��Ȯ��' if p['status']!='verified' else ' �� ���� ���� Ȯ�ε�')+(' �� ����� ������' if p['user'] else '') for p in profiles}
    profile_id=st.selectbox('�������� ������',[p['id'] for p in profiles],format_func=lambda value:names[value],key='export_profile')
    broken=next(p['error'] for p in profiles if p['id']==profile_id)
    profile=None
    if broken:
        st.error('������ ���� ����: '+broken)
    else:
        profile=load_profile(profile_id)
        if profile.status=='verified':
            st.caption(f'��ó: {profile.source_url} �� Ȯ�� ��¥: {profile.checked_date}')
        if profile.notes: st.caption(profile.notes)
    export_key=(str(bundle),profile_id,json.dumps(profile.record(),sort_keys=True) if profile else None)
    if S.get('export_for')!=export_key:
        S['export_result']=None
        S['export_zip']=None
    if st.button('�԰� �˻� �� ��������',key='export_run',disabled=bool(broken) or S.get('busy',False)):
        ok,result=perform('�԰� �˻硤��������',lambda:export_bundle(bundle,profile_id))
        S['export_result']=result if ok else None
        S['export_for']=export_key
        S['export_zip']=None
        if ok and result['status']!='error':
            S['export_zip']=build_export_zip(result['folder'])
    result=S.get('export_result') if S.get('export_for')==export_key else None
    if result:
        for check in result['checks']:
            {'error':st.error,'warning':st.warning}.get(check['level'],st.caption)(check['message'])
        if result['status']=='error':
            st.error('�������� ����: �� �׸��� ��ģ �� �ٽ� �õ��ϼ���. ZIP�� ������ �ʾҽ��ϴ�.')
        elif S.get('export_zip'):
            if result['status']=='pass':
                st.success('�� �������� ���� �˻縦 ����߽��ϴ�. ���� ��� �԰��� �ø� ������ �ٽ� Ȯ���ϼ���.')
            name,data=S['export_zip']
            st.download_button(name+' �ٿ�ε�',data=data,file_name=name,mime='application/zip',key='export_zip_button')
    with st.expander('�� ������ �����'):
        st.caption('���� �Ǹ��� ���򸻿��� ���� Ȯ���� ���� �Է��ϼ���. ��� �� ���� �˻����� �ʰ� "�԰� ��Ȯ��"���� ǥ���մϴ�. ����� �������� �� ��ǻ�Ϳ��� ����˴ϴ�.')
        new_id=st.text_input('������ �̸�(���� �ҹ��ڡ����ڡ�-��_)',key='new_profile_id')
        new_name=st.text_input('ǥ�� �̸�',key='new_profile_name')
        status=st.selectbox('Ȯ�� ����',['unverified','verified'],format_func=lambda v:{'unverified':'�԰� ��Ȯ��','verified':'���� ������ Ȯ���� (��� ������ó����¥ �ʿ�)'}[v],key='new_profile_status')
        source=st.text_input('���� ���� �ּ� (https://, �������� �ʰ� ��ϸ� ��)',key='new_profile_source')
        checked=st.text_input('Ȯ�� ��¥ (YYYY-MM-DD)',key='new_profile_date')
        width=st.number_input('�̹��� ��(px)',min_value=100,max_value=4000,value=None,step=10,key='new_profile_width')
        height=st.number_input('�̹��� 1�� �ִ� ����(px)',min_value=100,max_value=30000,value=None,step=100,key='new_profile_max_height')
        size=st.number_input('�̹��� 1�� �ִ� �뷮(����Ʈ)',min_value=1,value=None,step=100000,key='new_profile_max_bytes')
        count=st.number_input('�ִ� ���',min_value=1,max_value=1000,value=None,step=1,key='new_profile_max_images')
        formats=st.multiselect('��� ����',['jpg','png'],key='new_profile_formats')
        quality=st.number_input('JPEG ǰ��',min_value=1,max_value=100,value=None,step=1,key='new_profile_quality')
        notes=st.text_area('�޸�',key='new_profile_notes')
        if st.button('������ ����',key='new_profile_save',disabled=S.get('busy',False)):
            from core.export import save_user_profile
            data={'name':new_name,'status':status,'source_url':source.strip() or None,'checked_date':checked.strip() or None,
                  'width':width,'max_height_per_image':height,'max_file_bytes':size,'max_images':count,
                  'formats':formats or None,'jpeg_quality':quality,'notes':notes}
            ok,_=perform('������ ����',lambda:save_user_profile(new_id.strip(),{k:(int(v) if isinstance(v,float) else v) for k,v in data.items()}))
            if ok:
                S['export_profile_next']=new_id.strip()
                st.rerun()


STATUS_TEXT={'input_error':'�Է� ����','awaiting_answer':'������Ʈ ���','answer_error':'�亯 ����','needs_review':'�˼� �ʿ�','approved':'���ε�'}
BADGES={'input_error':'?? �Է� ����','awaiting_answer':'?? ������Ʈ ���','answer_error':'?? �亯 ����','needs_review':'?? �˼� �ʿ�','approved':'?? ���ε�'}

def stage_batch_upload(files):
    """Save the uploaded sheet(s) inside outputs only, with fixed safe names."""
    from core.batch import HEADERS
    folder=outputs()/'.batch-uploads'/uuid.uuid4().hex
    folder.mkdir(parents=True)
    if len(files)==1 and files[0].name.lower().endswith('.xlsx'):
        path=folder/'products.xlsx'; path.write_bytes(files[0].getvalue()); return path
    if any(not f.name.lower().endswith('.csv') for f in files):
        raise ValueError('XLSX ���� 1�� �Ǵ� CSV ����(products.csv, facts.csv, images.csv, reviews.csv, references.csv)�� �÷� �ּ���. ��ũ�� ����(.xlsm)�� ���� �ʽ��ϴ�.')
    for f in files:
        name=Path(f.name).name.lower()
        if name.removesuffix('.csv') not in HEADERS: raise ValueError(f'�� �� ���� CSV ���� �̸�: {f.name} (products/facts/images/reviews/references.csv)')
        (folder/name).write_bytes(f.getvalue())
    return folder


def open_batch_product(entry,batch):
    """Open one product's job in the normal ��~�� screens (approval stays per product)."""
    target=batch/(entry['accepted_job'] or entry['job'])
    index={'approved':6,'needs_review':3,'answer_error':2}.get(entry['status'],1)
    S['mode_next']='��ǰ �ϳ���'
    schedule_open(target,index)


def batch_page():
    from core import batch as B
    st.header('�ϰ� �۾�')
    st.caption('ǥ(XLSX �Ǵ� CSV)�� ���� ��ǰ�� �۾��� �� ���� �����, ��ǰ���� �ٿ��ֱ⡤�˼��������մϴ�. �ϰ� ������ �����ϴ�. ���ε� ��ǰ�� ���� �������ϴ�.')
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        template=B.write_template(Path(folder)/'��ǰ���.xlsx').read_bytes()
    st.download_button('�� ��ǰ ��� ���ø�(XLSX) �ޱ�',data=template,file_name='��ǰ���.xlsx',key='batch_template')
    with st.expander('�� �ϰ� �۾� ��������',expanded=not S.get('batch')):
        files=st.file_uploader('��ǰ ���: XLSX 1�� �Ǵ� CSV 4��(UTF-8)',type=['xlsx','csv'],accept_multiple_files=True,key='batch_upload')
        root=st.text_input('���� ��Ʈ ���� (�� ��ǻ���� ���� ���, ���� ���� ���� �� �Ʒ��� ���)',key='batch_photo_root')
        if st.button('��������',key='batch_import',disabled=S.get('busy',False)):
            def run():
                if not files: raise ValueError('��ǰ ��� ������ �÷� �ּ���.')
                if not root.strip(): raise ValueError('���� ��Ʈ ������ �Է��� �ּ���.')
                return B.import_batch(stage_batch_upload(files),Path(root.strip()).expanduser(),outputs())
            ok,folder=perform('�ϰ� ��������',run)
            if ok: S['batch']=str(folder); st.rerun()
    batches=B.list_batches(outputs())
    if batches:
        labels={b['path']:f"{Path(b['path']).name} �� {b['source']} �� {b['count']}�� �� {display_time(b['created_at'])}" for b in batches}
        chosen=st.selectbox('���� �ϰ� �۾�',list(labels),format_func=lambda v:labels[v],key='batch_resume')
        if st.button('�ϰ� �۾� ����',key='batch_open'):
            S['batch']=chosen; st.rerun()
    if not S.get('batch'): return
    batch=Path(S['batch'])
    try:
        entries=B.batch_status(batch); data=B.load_batch(batch)
    except (OSError,ValueError) as exc:
        st.error('�ϰ� �۾��� �� �� �����ϴ�: '+str(exc)); return
    st.subheader('��ǰ ��� �� '+batch.name)
    for error in data['errors']:
        st.error(f"{error['sheet']} ��Ʈ {error['row']}�� �� {error['column']} ��: {error['reason']}")
    st.dataframe([{'��ǰ':e['product_id'],'��ǰ��':e['name'],'����':BADGES[e['status']],'�׸�':e['theme'],'������':e['profile'],'�޽���':e.get('message','')} for e in entries],hide_index=True,width='stretch')
    for entry in entries:
        pid=entry['product_id']
        for error in entry['errors']:
            st.error(f"{pid}: {error['sheet']} ��Ʈ {error['row']}�� �� {error['column']} ��: {error['reason']}")
        if entry['job'] and st.button(f'{pid} ���� ({STATUS_TEXT[entry["status"]]})',key=f'batch_product_{pid}'):
            open_batch_product(entry,batch)
    st.subheader('�ٿ��ֱ� ���')
    if st.button('��� ���� ��ǰ�� ������Ʈ ZIP �����',key='batch_prompts'):
        ok,result=perform('������Ʈ ����',lambda:B.export_prompts(batch))
        if ok: S['batch_prompts_zip']=(result[1],result[2])
    if S.get('batch_prompts_zip'):
        name,payload=S['batch_prompts_zip']
        st.download_button('������Ʈ ZIP �ٿ�ε� (��ǰ���� ���� ä�ÿ� �ٿ��ֱ�)',data=payload,file_name=name,key='batch_prompts_download')
    answers=st.file_uploader('�亯 ����: <product_id>.txt (��ǰ���� �ϳ�)',type=['txt'],accept_multiple_files=True,key='batch_answers')
    if st.button('�亯 ����������',key='batch_ingest',disabled=S.get('busy',False)):
        def run():
            uploads=[(Path(f.name).name,f.getvalue()) for f in answers or []]
            return B.ingest_uploaded_answers(batch,uploads)
        ok,report=perform('�亯 ����',run)
        if ok: S['batch_ingest_report']=report; st.rerun()
    report=S.get('batch_ingest_report') or {}
    for name in report.get('unknown_files',[]): st.warning('��ǰ�� ���� �亯 ����: '+name)
    import tomllib
    configuration=tomllib.loads((ROOT/'providers.toml').read_text())
    enabled=[name for name,value in configuration.get('providers',{}).items() if value.get('command') and value.get('configured',True)]
    if enabled:
        with st.expander('����: �α��ε� ���� CLI�� ���� ����'):
            st.caption('��� ���� ��ǰ�� �ϳ��� ó���մϴ�. ��뷮 �ѵ��� �ɸ��� ��� ���߰� ���� ��ǰ�� ���� �Ӵϴ�.')
            name=st.selectbox('���� CLI',enabled,key='batch_provider')
            if st.button('���� ����',key='batch_generate',disabled=S.get('busy',False)):
                from core.providers import CliProvider
                ok,result=perform('���� CLI ���� ����',lambda:B.generate_batch(batch,CliProvider(name)))
                if ok and result['stopped']:
                    S['last_error']='���� CLI�� �ߴܵǾ� ���� ��ǰ�� ������Ʈ ���� �ξ����ϴ�. �ٿ��ֱ� ������� �̾����.'
                st.rerun()
    st.subheader('���ε� ��ǰ ��������')
    st.caption('��ǰ���� ��� �� Ȯ�� �׸��� üũ�� ������ ��ǰ�� �����ϴ�. �� ��ǰ�� �����ʷ� �˻��ϸ� "�԰� ��Ȯ��" ����� ��ǰ ������ manifest�� �����ϴ�.')
    if st.button('���ε� ��ǰ ZIP �����',key='batch_export',disabled=S.get('busy',False)):
        ok,result=perform('���ε� ��ǰ ��������',lambda:B.export_batch(batch))
        S['batch_export_result']=result if ok else None
    if S.get('batch_export_result'):
        name,payload,outcome=S['batch_export_result']
        for pid,item in outcome.items():
            if item['result']!='ok': st.warning(f'{pid}: {item["message"]}')
            for warning in item.get('warnings',[]): st.warning(f'{pid}: {warning}')
        st.download_button('���ε� ��ǰ ZIP �ٿ�ε�',data=payload,file_name=name,key='batch_export_download')


def main():
    st.set_page_config(page_title='�������� �����',page_icon='??',layout='wide')
    if 'pending_job' in S: open_job(S.pop('pending_job'))
    if 'fact_rows' not in S: form_load()
    for key,value in [('job',''),('bundle',''),('busy',False),('last_error',''),('stage',STEPS[0])]:
        if key not in S: S[key]=value
    if 'next_stage' in S: S['stage']=S.pop('next_stage')
    if 'mode_next' in S: S['mode']=S.pop('mode_next')
    st.title('��ǰ �������� �����')
    st.caption('��ǰ ����� �ְ� �� ä�ÿ� �ٿ��ְ� �� �˼��� �� �̹����� �����ϼ���. ���� ���� �� AI API ��� ����')
    from core.editor import job_listing
    with st.sidebar:
        mode=st.selectbox('�۾� ���',['��ǰ �ϳ���','�ϰ� �۾�'],key='mode')
    if mode=='�ϰ� �۾�':
        if S.get('last_error'): st.error(S['last_error'])
        batch_page(); return
    with st.sidebar:
        st.header('�۾� �̾��ϱ�')
        if st.button('�� �۾� ����'):
            form_load(); S['job']=''; S['bundle']=''; S['last_error']=''; go(0)
        jobs=job_listing(outputs())
        options=[item['path'] for item in jobs]
        labels={item['path']:f'{item["product_name"]} �� {display_time(item["created_at"])} �� {item["status"]}' for item in jobs}
        if options:
            selected=st.selectbox('�ֱ� �۾�',options,format_func=lambda value:labels[value],key='resume_job')
            if st.button('���� �۾� �̾��ϱ�',key='resume'):
                ok,_=perform('�۾� �ҷ�����',lambda:open_job(selected))
                if ok: go(6 if S['bundle'] else (3 if (Path(S['job'])/'draft.json').exists() else 1))
                else: st.rerun()
        st.radio('���� �ܰ�',STEPS,key='stage')
    if S.get('last_error'): st.error(S['last_error'])
    if S['stage']==STEPS[0]: input_page(); return
    if not S.get('job'): st.info('�翡�� ��ǰ ������ �����ϰų� ���� �۾��� �����ϼ���.'); return
    job=Path(S['job']); st.caption('�۾� ����: '+job.name)
    if S['stage'] in STEPS[3:] and not (job/'draft.json').exists(): st.info('�鿡�� �亯�� ���� ������ �ּ���.'); return
    pages={STEPS[1]:prompt_page,STEPS[2]:answer_page,STEPS[3]:edit_page,STEPS[4]:preview_page,STEPS[5]:approval_page,STEPS[6]:download_page}
    pages[S['stage']](job)


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        # Keep the app usable even when loading a damaged job or unexpected UI error.
        perform('ȭ�� ǥ��',lambda:(_ for _ in ()).throw(exc))
        st.error(S.get('last_error','ȭ���� ǥ������ ���߽��ϴ�. �� �۾��� ������ �ּ���.'))


