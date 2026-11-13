"""Single-user local UI. Business rules and exports live in core/."""
import copy
import hashlib
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

STEPS=['① 상품 정보','② 프롬프트','③ 답변 붙여넣기','④ 검수·수정','⑤ 미리보기','⑥ 승인','⑦ 다운로드']
KINDS={'스펙':'spec','특징':'feature','사용법':'usage','주장':'claim','기타':'other'}
ROLES={'대표':'hero','특징':'feature','해결':'solution','기타':'other'}
NAMES={'hero':'대표 문구','pain':'고객 고민','solution':'해결','features':'특징','how_to':'사용법','review':'후기','spec':'스펙','faq':'자주 묻는 질문','notice':'배송·교환·반품 안내'}
LABELS={'product':'상품 정보','name':'상품명','category':'카테고리','price':'가격','facts':'상품 사실','text':'문구','evidence':'근거','reviews':'후기','permission_confirmed':'사용 허가 확인','hero':'대표 문구','headline':'제목','subcopy':'보조 문구','images':'사진','claim':'주장','body':'본문','features':'특징','how_to':'사용법','faq':'질문·답변','sections':'섹션'}
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
        if key.startswith(('fact_','review_','edit_','lock_','check_')): del S[key]
    for key,value in data['product'].items(): S['product_'+key]=value
    revision=uuid.uuid4().hex[:8]
    S['form_buffer']=copy.deepcopy(data)
    S['fact_rows']=[dict(row,_uid=revision+'-'+str(i)) for i,row in enumerate(data['facts'])]
    S['review_rows']=[dict(row,_uid=revision+'-'+str(i)) for i,row in enumerate(data.get('reviews',[]))]
    S['notice']=data.get('notice','')
    S['image_refs']=copy.deepcopy(data.get('images',[]))
    S['image_root']=str(image_root) if image_root else ''
    S['field_errors']={}; S['upload_error']=''


def open_job(path):
    job=Path(path)
    data=read_json(job/'facts.json')
    form_load(data,job)
    S['job']=str(job); S['bundle']=''; S['last_error']=''
    manifest=read_json(job/'manifest.json')
    if manifest.get('review_accepted') and manifest.get('rendered_job'):
        S['bundle']=str(job/manifest['rendered_job'])
    elif (job/'preview.json').exists():
        info=read_json(job/'preview.json')
        bundle=job/info['bundle']
        if bundle.is_dir(): S['bundle']=str(bundle)
    if S['bundle'] and (job/'draft.json').exists():
        expected=hashlib.sha256((job/'draft.json').read_bytes()).hexdigest()
        if read_json(Path(S['bundle'])/'manifest.json').get('draft_sha256')!=expected: S['bundle']=''


def error_text(exc):
    text=str(exc)
    labels={**NAMES,**LABELS}
    for source in sorted(labels,key=len,reverse=True): text=text.replace(source,labels[source])
    if 'claim requires evidence' in str(exc): text+='\n주장은 근거를 입력해야 저장할 수 있습니다.'
    text=text.replace('Field required','필수 입력입니다.').replace('String should have at least 1 character','한 글자 이상 입력해 주세요.')
    text=text.replace('CLI time limit exceeded.','CLI 제한 시간을 초과했습니다. 붙여넣기 방식으로 진행하세요.').replace('CLI usage limit reached; switch to paste mode.','구독 사용량 한도에 도달했습니다. 붙여넣기 방식으로 전환하세요.')
    if 'permission_confirmed' in str(exc): text+='\n후기의 사용 허가 확인을 체크해 주세요.'
    return text


def perform(name,fn):
    if S.get('busy'): return False,None
    S['busy']=True
    S['last_error']=''; S['field_errors']={}
    try:
        with st.spinner(name+' 중입니다…'):
            return True,fn()
    except ValidationError as exc:
        S['field_errors']={'.'.join(map(str,e['loc'])):error_text(e['msg']) for e in exc.errors()}
        S['last_error']='입력 내용을 확인해 주세요. '+error_text(exc)
    except (ValueError,OSError) as exc:
        S['last_error']=error_text(exc)
    except Exception as exc:
        job=Path(S['job']) if S.get('job') else outputs()/'app-errors'
        job.mkdir(parents=True,exist_ok=True)
        path=job/('ui-error-'+uuid.uuid4().hex+'.log')
        # No input values, environment, CLI output or credential/config dumps.
        path.write_text('operation='+name+'\nexception_type='+type(exc).__name__+'\n',encoding='utf-8')
        S['last_error']='예상치 못한 오류가 발생했습니다. 다시 시도해 주세요. 오류 기록: '+str(path)
    finally:
        S['busy']=False
    return False,None


def field_error(path):
    for key,message in S.get('field_errors',{}).items():
        if key==path or key.startswith(path+'.'): st.error(message)


def sync_rows(kind):
    for row in S[kind+'_rows']:
        uid=row['_uid']
        fields=['id','text','evidence'] if kind=='fact' else ['text','rating','source','permission_confirmed']
        for key in fields:
            widget=f'{kind}_{key}_{uid}'
            if widget in S: row[key]=S[widget]
        if kind=='fact' and f'fact_kind_label_{uid}' in S:
            row['kind']=KINDS[S[f'fact_kind_label_{uid}']]


def move_row(kind,index,delta):
    sync_rows(kind)
    rows=S[kind+'_rows']; other=index+delta
    if 0<=other<len(rows): rows[index],rows[other]=rows[other],rows[index]


def remove_row(kind,index):
    sync_rows(kind); S[kind+'_rows'].pop(index)


def add_row(kind):
    sync_rows(kind)
    uid=uuid.uuid4().hex[:8]
    row={'_uid':uid,'id':'fact-'+uid,'text':'','kind':'feature','evidence':''} if kind=='fact' else {'_uid':uid,'text':'','rating':5,'source':'','permission_confirmed':False}
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
    sync_rows('fact'); sync_rows('review')
    facts=[]
    for row in S['fact_rows']:
        data={k:v for k,v in row.items() if k!='_uid' and v!=''}
        facts.append(data)
    reviews=[{k:v for k,v in row.items() if k!='_uid'} for row in S['review_rows']]
    data={'schema_version':'1.0','product':{key:S['product_'+key] for key in ['name','category','price','brand_color']},'facts':facts,'images':S['image_refs'],'reviews':reviews}
    if S.get('notice','').strip(): data['notice']=S['notice']
    S['form_buffer']=copy.deepcopy(data)
    return data


def input_page():
    for key,value in S.get('form_buffer',{}).get('product',{}).items():
        if 'product_'+key not in S: S['product_'+key]=value
    if 'notice' not in S: S['notice']=S.get('form_buffer',{}).get('notice','')
    st.header('① 상품 정보')
    if st.button('샘플 데이터 넣기',key='sample'):
        form_load(read_json(ROOT/'samples/facts.json'),ROOT/'samples'); st.rerun()
    imported=st.file_uploader('기존 facts.json 불러오기',type=['json'],key='facts_upload')
    if imported and st.button('입력 양식으로 불러오기'):
        ok,data=perform('사실 불러오기',lambda:ProductFacts.model_validate_json(imported.getvalue()).model_dump(exclude_none=True))
        if ok: form_load(data); S['last_error']='사진은 별도로 업로드해 주세요.'
        st.rerun()
    st.text_input('상품명',key='product_name'); field_error('product.name')
    st.text_input('카테고리',key='product_category'); field_error('product.category')
    st.text_input('가격 (표시용)',key='product_price'); field_error('product.price')
    st.color_picker('브랜드 색상',key='product_brand_color')
    st.subheader('상품 사실')
    for index,row in enumerate(S['fact_rows']):
        uid=row['_uid']
        with st.container(border=True):
            st.text_input(f'사실 ID {index+1}',value=row.get('id',''),key=f'fact_id_{uid}')
            st.text_area(f'사실 문구 {index+1}',value=row.get('text',''),key=f'fact_text_{uid}')
            labels=list(KINDS)
            chosen=next(k for k,v in KINDS.items() if v==row.get('kind','feature'))
            label=st.selectbox(f'종류 {index+1}',labels,index=labels.index(chosen),key=f'fact_kind_label_{uid}')
            row['kind']=KINDS[label]
            st.text_input(f'근거 {index+1}',value=row.get('evidence',''),key=f'fact_evidence_{uid}')
            field_error(f'facts.{index}')
            cols=st.columns(3)
            cols[0].button('위로',key=f'up_{uid}',on_click=move_row,args=('fact',index,-1),disabled=index==0)
            cols[1].button('아래로',key=f'down_{uid}',on_click=move_row,args=('fact',index,1),disabled=index==len(S['fact_rows'])-1)
            cols[2].button('삭제',key=f'delete_{uid}',on_click=remove_row,args=('fact',index))
    st.button('사실 행 추가',on_click=add_row,args=('fact',))
    st.subheader('사진')
    st.file_uploader('상품 사진 (PNG/JPEG, 최대 5장, 장당 10MB)',type=['png','jpg','jpeg'],accept_multiple_files=True,key='photos',on_change=uploaded)
    if S.get('upload_error'): st.error(S['upload_error'])
    field_error('images')
    for i,ref in enumerate(S['image_refs']):
        path=Path(S['image_root'])/ref['path']
        if S['image_root'] and path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(Path(S['image_root']).resolve()): st.image(str(path),width=160)
        labels=list(ROLES); current=next(k for k,v in ROLES.items() if v==ref['role'])
        chosen=st.selectbox(f'사진 {i+1} 역할',labels,index=labels.index(current),key=f'image_role_{S["image_root"]}_{i}')
        ref['role']=ROLES[chosen]
    st.subheader('실제 후기 (선택)')
    st.info('AI가 후기를 만들지 않으며 실제 허가받은 후기만 입력하세요.')
    for index,row in enumerate(S['review_rows']):
        uid=row['_uid']
        with st.container(border=True):
            st.text_area(f'후기 문구 {index+1}',value=row.get('text',''),key=f'review_text_{uid}')
            st.number_input(f'후기 별점 {index+1}',min_value=1,max_value=5,value=row.get('rating',5),step=1,key=f'review_rating_{uid}')
            st.text_input(f'후기 출처 {index+1}',value=row.get('source',''),key=f'review_source_{uid}')
            st.checkbox('사용 허가 확인',value=row.get('permission_confirmed',False),key=f'review_permission_confirmed_{uid}')
            field_error(f'reviews.{index}')
            st.button('후기 삭제',key=f'delete_review_{uid}',on_click=remove_row,args=('review',index))
    st.button('후기 추가',on_click=add_row,args=('review',))
    st.text_area('배송·교환·반품 안내 (선택)',key='notice'); field_error('notice')
    data=facts_data()
    st.download_button('facts.json 내보내기',data=json.dumps(data,ensure_ascii=False,indent=2),file_name='facts.json',mime='application/json')
    if st.button('저장하고 프롬프트 만들기',key='create',type='primary',disabled=S.get('busy',False)):
        def create():
            facts=ProductFacts.model_validate(data)
            if not S['image_root']: raise ValueError('상품 사진을 업로드해 주세요.')
            return create_job(facts,Path(S['image_root'] or '.'),outputs())
        ok,job=perform('상품 사실 저장',create)
        if ok: schedule_open(job,1)
        else: st.rerun()


def prompt_page(job):
    st.header('② 프롬프트 복사')
    st.info('Claude·ChatGPT·Gemini 중 하나의 채팅창에 붙여넣고, 답변 전체를 복사해 다음 단계에 붙여넣으세요.')
    text=(job/'prompt.md').read_text(encoding='utf-8')
    st.code(text,language='markdown')
    st.download_button('프롬프트 파일 다운로드',text,file_name='prompt.md')
    if st.button('답변 붙여넣기로 이동'): go(2)
    import tomllib
    from core.providers import CliProvider
    configuration=tomllib.loads((ROOT/'providers.toml').read_text())
    enabled=[name for name,value in configuration.get('providers',{}).items() if value.get('command') and value.get('configured',True)]
    if enabled:
        with st.expander('선택: 로그인된 공식 CLI 사용'):
            name=st.selectbox('구독 CLI',enabled)
            if st.button('CLI로 자동 생성',disabled=S.get('busy',False)):
                def generate():
                    facts=ProductFacts.model_validate(read_json(job/'facts.json'))
                    return generate_job(facts,job,outputs(),CliProvider(name),source_label=name,existing_job=job)
                ok,new=perform('CLI 문구 생성 (오류 시 붙여넣기 방식을 사용하세요)',generate)
                if ok: schedule_open(new,3)
                else:
                    S['last_error']='CLI 실행을 완료하지 못했습니다. 로그인·설정·제한 시간·구독 사용량을 확인하고 붙여넣기 방식으로 진행하세요. '+S['last_error']; st.rerun()


def answer_page(job):
    st.header('③ 답변 붙여넣기')
    manifest=read_json(job/'manifest.json')
    st.caption(f'시도 {manifest.get("attempts",0)} / {manifest.get("max_attempts",5)}')
    text=st.text_area('답변 전체',height=350,key='answer_text')
    source=st.selectbox('답변 출처',['Claude 채팅','ChatGPT','Gemini','기타'])
    if source=='기타': source=st.text_input('출처 직접 입력')
    if st.button('답변 검증·조립',key='ingest',type='primary',disabled=S.get('busy',False)):
        ok,_=perform('답변 검증',lambda:ingest_job(job,text,source_label=source))
        if ok: go(3)
        else: st.rerun()
    if (job/'fix-prompt.md').exists():
        st.warning('이 수정 요청을 같은 채팅에 붙여넣으세요. 고친 답변 전체를 다시 입력해 주세요.')
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


def edit_page(job):
    from core.editor import save_draft
    st.header('④ 검수·문구 수정')
    document=read_json(job/'draft.json'); edited=copy.deepcopy(document)
    reviews=read_json(job/'review.json')
    facts={f['id']:f['text'] for f in read_json(job/'facts.json')['facts']}
    copy_data=read_json(job/'copy.json')
    locks=read_json(job/'edits.json').get('locked_sections',[]) if (job/'edits.json').exists() else []
    selected=[]
    st.info('가격·상품명·후기·스펙·안내 문구는 ① 상품 정보에서 수정하고 새 작업을 시작하세요.')
    for index,section in enumerate(edited['sections']):
        sid=section['id']; kind=section['type']
        with st.container(border=True):
            st.subheader(NAMES[kind])
            for item in reviews:
                if item['section_id']==sid: st.warning('검수: '+error_text(item['reason'])+' · '+item.get('field_path',''))
            fields=editable_fields(section)
            if not fields: st.json(section,expanded=False)
            for path,limit in fields:
                initial=nested(section,path) or ''
                value=st.text_area(f'{NAMES[kind]} · {path} (상한 {limit}자)',value=initial,key=f'edit_{job.name}_{sid}_{path}')
                st.caption(f'{len(value)} / {limit}자')
                if kind=='hero' and path=='subcopy' and not value:
                    section.pop('subcopy',None)
                else:
                    nested(section,path,value,True)
            preserved=read_json(job/'locked-evidence.json') if (job/'locked-evidence.json').exists() else {}
            grounded=preserved.get(sid,copy_data.get(kind,[]))
            def collect_ids(data):
                if isinstance(data,dict): return data.get('fact_ids',[])+[fid for key,val in data.items() if key!='fact_ids' for fid in collect_ids(val)]
                if isinstance(data,list): return [fid for val in data for fid in collect_ids(val)]
                return []
            for fid in dict.fromkeys(collect_ids(grounded)):
                st.caption('근거 '+fid+': '+facts.get(fid,'존재하지 않는 사실 ID'))
            if st.checkbox('잠금 (재생성 시 유지)',value=sid in locks,key=f'lock_{job.name}_{sid}'): selected.append(sid)
    if st.button('수정 저장·재검수',key='save_edits',type='primary',disabled=S.get('busy',False)):
        ok,_=perform('수정 저장 및 근거 재검수',lambda:save_draft(job,edited,selected))
        if ok:
            S['bundle']=''; S['last_error']=''; S['saved_message']='수정과 검수 목록을 저장했습니다.'
        st.rerun()
    if S.get('saved_message'): st.success(S['saved_message'])
    if st.button('잠그지 않은 섹션 다시 쓰기',disabled=S.get('busy',False)):
        ok,new=perform('재생성 프롬프트 만들기',lambda:regenerate_job(job))
        if ok: schedule_open(new,1)
        else: st.rerun()
    if st.button('저장한 문구 미리보기',key='to_preview'): go(4)


def display_bundle(bundle):
    manifest=read_json(bundle/'manifest.json')
    st.caption('작업 버전 ID: '+manifest['job_id'])
    if not manifest.get('review_accepted'):
        st.warning('DRAFT · 승인 전 미리보기입니다. 검수 항목과 문구를 확인하세요.')
    if manifest.get('needs_review'):
        if manifest.get('review_accepted'): st.info('승인 완료 · 검수 기록은 review.json에 보존됩니다.')
        else: st.error('검수 필요: 근거·수치·광고 표현을 확인해 주세요.')
    for page in manifest['pages']: st.image(str(bundle/page['file']),width='stretch')
    return manifest


def preview_page(job):
    from core.editor import preview_job
    st.header('⑤ 미리보기')
    if st.button('저장된 문구로 미리보기 생성',key='preview',disabled=S.get('busy',False)):
        current_hash=hashlib.sha256((job/'draft.json').read_bytes()).hexdigest()
        bundle=Path(S['bundle']) if S.get('bundle') else None
        if not bundle or not (bundle/'manifest.json').exists() or read_json(bundle/'manifest.json').get('draft_sha256')!=current_hash:
            ok,bundle=perform('미리보기 렌더링',lambda:preview_job(job))
            if not ok: st.rerun()
            S['bundle']=str(bundle)
        st.rerun()
    if S.get('bundle'): display_bundle(Path(S['bundle']))
    if st.button('승인 단계로 이동'): go(5)
    if S.get('bundle') and st.button('DRAFT 다운로드 단계로 이동'): go(6)


def approval_page(job):
    st.header('⑥ 승인')
    labels=['사실 일치 확인','후기 출처·허가 확인','효능·수치·광고 표현 확인','대상 플랫폼 업로드 규격은 별도 확인 필요함을 인지']
    checks=[st.checkbox(label,key=f'check_{job.name}_{i}') for i,label in enumerate(labels)]
    if st.button('모두 확인했으며 승인',key='accept',type='primary',disabled=not all(checks) or S.get('busy',False)):
        ok,accepted=perform('승인 결과 렌더링',lambda:accept_job(job))
        if ok:
            schedule_open(accepted,6)
        else: st.rerun()


def download_page(job):
    from core.editor import build_zip
    st.header('⑦ 다운로드')
    if not S.get('bundle'):
        st.info('⑤에서 미리보기를 만들거나 ⑥에서 승인해 주세요.'); return
    bundle=Path(S['bundle'])
    current=hashlib.sha256((job/'draft.json').read_bytes()).hexdigest()
    if read_json(bundle/'manifest.json').get('draft_sha256')!=current:
        st.warning('저장된 문구가 변경되었습니다. ⑤에서 새 미리보기를 만들어 주세요.'); return
    manifest=read_json(bundle/'manifest.json')
    ok,data=perform('ZIP 준비',lambda:build_zip(bundle))
    if ok:
        S['download_zip']=data
        filename=manifest['job_id']+('' if manifest.get('review_accepted') else '.DRAFT')+'.zip'
        st.download_button('ZIP 다운로드',data=data,file_name=filename,mime='application/zip',key='download_zip_button')
    display_bundle(bundle)


def main():
    st.set_page_config(page_title='상세페이지 만들기',page_icon='🛍',layout='wide')
    if 'pending_job' in S: open_job(S.pop('pending_job'))
    if 'fact_rows' not in S: form_load()
    for key,value in [('job',''),('bundle',''),('busy',False),('last_error',''),('stage',STEPS[0])]:
        if key not in S: S[key]=value
    if 'next_stage' in S: S['stage']=S.pop('next_stage')
    st.title('상품 상세페이지 만들기')
    st.caption('상품 사실을 넣고 → 채팅에 붙여넣고 → 검수한 뒤 이미지로 저장하세요. 로컬 전용 · AI API 사용 없음')
    from core.editor import job_listing
    with st.sidebar:
        st.header('작업 이어하기')
        if st.button('새 작업 시작'):
            form_load(); S['job']=''; S['bundle']=''; S['last_error']=''; go(0)
        jobs=job_listing(outputs())
        options=[item['path'] for item in jobs]
        labels={item['path']:f'{item["product_name"]} · {display_time(item["created_at"])} · {item["status"]}' for item in jobs}
        if options:
            selected=st.selectbox('최근 작업',options,format_func=lambda value:labels[value],key='resume_job')
            if st.button('기존 작업 이어하기',key='resume'):
                ok,_=perform('작업 불러오기',lambda:open_job(selected))
                if ok: go(6 if S['bundle'] else (3 if (Path(S['job'])/'draft.json').exists() else 1))
                else: st.rerun()
        st.radio('진행 단계',STEPS,key='stage')
    if S.get('last_error'): st.error(S['last_error'])
    if S['stage']==STEPS[0]: input_page(); return
    if not S.get('job'): st.info('①에서 상품 정보를 저장하거나 기존 작업을 선택하세요.'); return
    job=Path(S['job']); st.caption('작업 폴더: '+job.name)
    if S['stage'] in STEPS[3:] and not (job/'draft.json').exists(): st.info('③에서 답변을 먼저 검증해 주세요.'); return
    pages={STEPS[1]:prompt_page,STEPS[2]:answer_page,STEPS[3]:edit_page,STEPS[4]:preview_page,STEPS[5]:approval_page,STEPS[6]:download_page}
    pages[S['stage']](job)


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        # Keep the app usable even when loading a damaged job or unexpected UI error.
        perform('화면 표시',lambda:(_ for _ in ()).throw(exc))
        st.error(S.get('last_error','화면을 표시하지 못했습니다. 새 작업을 시작해 주세요.'))
