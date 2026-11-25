"""Single-user local UI. Business rules and exports live in core/."""
import copy
import json
import re
import os
import sys
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd
import streamlit as st
from pydantic import ValidationError

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.facts import ProductFacts
from core.workflow import create_job,ingest_job,regenerate_job,overflow_regenerate_job,generate_job,accept_job,read_json,COPY_SECTION_TYPES
from core.uploads import stage_uploads
from core.themes import THEME_IDS, effective_brand, load_theme
from core.editor import bundle_matches,resume_bundle

STEPS=['① 상품 정보','② 프롬프트','③ 답변 붙여넣기','④ 검수·수정','⑤ 미리보기','⑥ 승인','⑦ 다운로드']
KINDS={'스펙':'spec','특징':'feature','사용법':'usage','주장':'claim','기타':'other'}
ROLES={'대표':'hero','특징':'feature','해결':'solution','디테일':'detail','사용 장면':'lifestyle','구조도':'diagram','기타':'other'}
REFERENCE_KINDS={'경쟁사':'competitor','고객 목소리':'customer_voice','기타':'other'}
NAMES={'cases':'적용 사례','hero':'대표 문구','pain':'고객 고민','solution':'해결','features':'특징','how_to':'사용법','review':'후기','spec':'스펙','stats':'숫자 띠','targets':'추천 대상','structure':'구조와 구성','gallery':'상품 사진','image':'사용 장면','faq':'자주 묻는 질문','notice':'배송·교환·반품 안내'}
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
        if key.startswith(('fact_','review_','reference_','rich_','edit_','lock_','check_','evidence_')): del S[key]
    for key,value in data['product'].items(): S['product_'+key]=value
    revision=uuid.uuid4().hex[:8]
    S['form_buffer']=copy.deepcopy(data)
    S['rich_baseline'] = copy.deepcopy(data)
    S['rich_input'] = {key:copy.deepcopy(data[key]) for key in ('highlights','targets','structure','spec_table','use_cases','target_industries','target_uses') if key in data}
    S['rich_revision'] = revision
    S['verified_table_digest'] = json.dumps(data.get('spec_table'),ensure_ascii=False,sort_keys=True)
    S['fact_rows']=[dict(row,_uid=revision+'-'+str(i)) for i,row in enumerate(data['facts'])]
    S['review_rows']=[dict(row,_uid=revision+'-'+str(i)) for i,row in enumerate(data.get('reviews',[]))]
    S['reference_rows']=[dict(row,_uid=revision+'-'+str(i)) for i,row in enumerate(data.get('references',[]))]
    S['reference_names_text']=', '.join(data.get('reference_names',[]))
    S['input_metadata'] = {key:copy.deepcopy(data[key]) for key in
                           ('pending_claims','uncertain','price_candidate','spec_from_import','spec_verified') if key in data}
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
    from core.render import job_design_version
    S['design_choice']=job_design_version(manifest)
    S['preview_brand']=effective_brand(manifest,data['product']['brand_color'])
    bundle=resume_bundle(job)
    S['bundle']=str(bundle) if bundle else ''


def error_text(exc):
    text=str(exc)
    labels={**NAMES,**LABELS}
    for source in sorted(labels,key=len,reverse=True): text=text.replace(source,labels[source])
    if 'claim requires evidence' in str(exc): text+='\n주장은 근거를 입력해야 저장할 수 있습니다.'
    text=re.sub(r'List should have at most (\d+) items.*', r'최대 \1개까지 입력할 수 있습니다.', text)
    text=re.sub(r'List should have at least (\d+) items.*', r'최소 \1개를 입력해 주세요.', text)
    text=text.replace('String should match pattern', '빈칸 없이 올바른 형식으로 입력해 주세요. 기준')
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
    data.update(S.get('rich_input', {}))
    data.update(S.get('input_metadata', {}))
    S['form_buffer']=copy.deepcopy(data)
    return data


SOURCE_LABELS={'실제 사진':None,'AI로 배경만 바꾼 사진':'ai_edited','AI 생성 분위기 이미지':'ai_generated'}


def image_source_panel(ref, i):
    """M8-B: where this image came from. Nothing is generated or sent anywhere by the app."""
    root=S['image_root']
    labels=list(SOURCE_LABELS); current=next(k for k,v in SOURCE_LABELS.items() if v==ref.get('source'))
    chosen=SOURCE_LABELS[st.selectbox(f'사진 {i+1} 출처',labels,index=labels.index(current),key=f'image_source_{root}_{i}')]
    for key in ('source','based_on','generator','edit_request'): ref.pop(key,None)
    if chosen is None: return
    ref['source']=chosen
    if chosen=='ai_edited':
        photos=[(j,other['path']) for j,other in enumerate(S['image_refs']) if j!=i and not other.get('source')]
        if not photos:
            st.warning('원본 실제 사진도 함께 올려 주세요. AI로 배경을 바꾼 사진은 원본과 나란히 비교해 승인합니다.')
        else:
            names=[f'사진 {j+1}' for j,_ in photos]
            picked=st.selectbox(f'사진 {i+1}의 원본 사진',names,key=f'image_based_{root}_{i}')
            ref['based_on']=photos[names.index(picked)][1]
    else:
        st.caption('AI 생성 이미지는 사용 장면(분위기) 역할에만 쓸 수 있고, 페이지에 "연출 이미지입니다"가 표시됩니다.')
    generator=st.text_input(f'사진 {i+1} 만든 도구 (예: ChatGPT, Gemini)',key=f'image_generator_{root}_{i}',max_chars=40)
    if generator.strip(): ref['generator']=generator.strip()
    request=st.text_input(f'사진 {i+1} 요청 내용 요약 (선택)',key=f'image_request_{root}_{i}',max_chars=300)
    if request.strip(): ref['edit_request']=request.strip()


def image_prompt_panel():
    """Copy-and-paste prompts for a subscribed AI chat (background change, mood picture)."""
    from core.image_prompts import BACKGROUND_NAMES, background_prompt, mood_prompt
    with st.expander('AI로 사진 배경 바꾸기·분위기 이미지 만들기 (프롬프트 복사)'):
        st.caption('프롬프트를 복사해 구독 중인 AI 채팅에 붙여넣고, 배경 변경은 원본 사진을 직접 첨부하세요. '
                   '받은 이미지를 위에서 함께 업로드하고 출처를 고르면 됩니다. 앱은 사진을 외부로 보내지 않습니다.')
        try:
            facts=ProductFacts.model_validate(facts_data())
        except (ValueError,TypeError):
            st.info('상품 정보와 사실을 먼저 입력하면 프롬프트를 만들 수 있습니다.')
            return
        kinds=list(BACKGROUND_NAMES); names=list(BACKGROUND_NAMES.values())
        background=kinds[names.index(st.selectbox('배경',names,key='image_prompt_background'))]
        place=st.text_input('사용 장소 (사용 장소 배경일 때, 예: 작은 작업실)',key='image_prompt_place',max_chars=100) if background=='usage_place' else ''
        st.markdown('**배경 변경 프롬프트** — 원본 사진 1장을 첨부해 사용')
        st.code(background_prompt(facts,background,place),language=None)
        scene=st.text_input('분위기 이미지 장면 설명 (선택)',key='image_prompt_scene',max_chars=200)
        st.markdown('**분위기 이미지 프롬프트** — 상품은 그리지 않는 장면용')
        st.code(mood_prompt(facts,scene),language=None)


THEME_LABEL={'ok':'그대로','adjusted':'글자색 보정','warning':'대비 경고'}


def color_choices(candidates, target_key, prefix):
    """Show candidate swatches; a click only sets the colour widget (nothing changes until chosen)."""
    from core.colors import swatch
    if not candidates:
        st.caption('사진에서 강조색으로 쓸 만한 색을 찾지 못했습니다(흰색·회색 위주).'); return
    columns=st.columns(len(candidates))
    for i,(column,item) in enumerate(zip(columns,candidates)):
        column.image(swatch(item['color']),caption=f"{item['color']} · {item['share']:.0%}")
        column.caption(f"흰 바탕 대비 {item['contrast_on_white']}:1")
        notes=[f'{theme} {THEME_LABEL[state]}' for theme,state in item['themes'].items() if state!='ok']
        if notes: column.caption(' · '.join(notes))
        column.button('이 색 사용',key=f'{prefix}_{i}',on_click=lambda c=item['color']:S.__setitem__(target_key,c))


def color_candidates_input():
    from core.colors import suggest_colors
    refs=[ref for ref in S.get('image_refs',[]) if ref.get('source')!='ai_generated']
    if not refs or not S.get('image_root'): return
    with st.expander('사진에서 브랜드 색 후보 찾기'):
        st.caption('대표 사진부터 살펴 배경을 뺀 주요 색을 제안합니다. 고르기 전에는 바뀌지 않습니다. AI 생성 이미지는 쓰지 않습니다.')
        refs.sort(key=lambda ref:ref['role']!='hero')
        key=(S['image_root'],tuple(ref['path'] for ref in refs))
        if S.get('color_input_key')!=key:
            S['color_input_key']=key; S['color_input']=None
        if S['color_input'] is None and st.button('색 후보 찾기',key='find_colors'):
            ok,found=perform('색 후보 찾기',lambda:suggest_colors([Path(S['image_root'])/ref['path'] for ref in refs]))
            if ok: S['color_input']=found
        if S['color_input'] is not None:
            color_choices(S['color_input'],'product_brand_color','use_color')


def color_candidates_job(job):
    from core.colors import job_color_suggestions
    with st.expander('사진에서 뽑은 브랜드 색 후보'):
        st.caption('고르면 미리보기 브랜드 색에 들어가고 다시 렌더링합니다. 테마별 대비 처리도 함께 보여 줍니다.')
        manifest=read_json(job/'manifest.json')
        record=manifest.get('color_suggestions')
        if record is None and st.button('색 후보 찾기',key='find_job_colors'):
            ok,record=perform('색 후보 찾기',lambda:job_color_suggestions(job))
            if not ok: record=None
        if record is not None:
            color_choices(record['candidates'],'preview_brand','use_preview_color')


def photo_previews():
    source=S.get('photo_preview_job') or (S.get('job') if S.get('image_root')==S.get('job') else '')
    if not source or not (Path(source)/'manifest.json').exists(): return
    manifest=read_json(Path(source)/'manifest.json')
    for i,record in enumerate(manifest.get('image_processing',[])):
        cols=st.columns(2)
        cols[0].image(str(Path(source)/record['source_path']),caption=f'사진 {i+1} 처리 전',width=220)
        settings=S['image_refs'][i].get('processing',{}) if i<len(S['image_refs']) else {}
        path=record['selected_path'] if settings.get('remove_background') else record['normalized_path']
        cols[1].image(str(Path(source)/path),caption=f'사진 {i+1} 처리 후',width=220)
        if settings.get('remove_background') and record.get('mask_preview_path'):
            st.image(str(Path(source)/record['mask_preview_path']),caption='배경 제거 마스크 (체크무늬)',width=220)
    for item in manifest.get('image_reviews',[]): st.warning(item['reason'])


def rich_inputs():
    revision = S['rich_revision']
    if f'rich_highlights_{revision}' not in S and S.get('rich_input'):
        S['rich_baseline'] = copy.deepcopy(S['rich_input'])
    baseline = S['rich_baseline']

    def table(key, fields, rows, visible=None):
        edited = st.data_editor(
            pd.DataFrame(rows, columns=list(fields), dtype=object),
            column_config={field: (st.column_config.TextColumn(label) if visible is None or index < visible else None)
                           for index, (field, label) in enumerate(fields.items())},
            num_rows='dynamic', hide_index=True, key=f'rich_{key}_{revision}',
        )
        return edited.fillna('').to_dict('records')

    rich = {}
    with st.expander('상세 섹션 입력 (선택)'):
        st.markdown('**숫자 띠 · 최대 4개**')
        rich['highlights'] = table('highlights', {'value':'값','label':'라벨','fact_id':'근거 사실 ID'}, baseline.get('highlights', []))
        field_error('highlights')
        st.markdown('**추천 대상 · 최대 12개**')
        targets = table('targets', {'name':'장소 또는 대상'}, [{'name':value} for value in baseline.get('targets', [])])
        rich['targets'] = [row['name'] for row in targets]
        field_error('targets')
        st.markdown('**추천 업종 · 용도 (선택, 각 최대 12개)** — 입력하면 디자인 v2에서 업종과 용도를 나눠 보여 줍니다.')
        industries = table('target_industries', {'name':'업종'}, [{'name':value} for value in baseline.get('target_industries') or []])
        uses = table('target_uses', {'name':'용도'}, [{'name':value} for value in baseline.get('target_uses') or []])
        if industries: rich['target_industries'] = [row['name'] for row in industries]
        if uses: rich['target_uses'] = [row['name'] for row in uses]
        field_error('target_industries'); field_error('target_uses')
        st.markdown('**적용 사례 (선택, 최대 6개)** — 서로 다른 시공·사용 사례. 순서대로 하는 작업 단계가 아닙니다.')
        cases = table('use_cases', {'name':'사례 이름','desc':'설명'}, baseline.get('use_cases') or [])
        if cases: rich['use_cases'] = cases
        field_error('use_cases')
        st.markdown('**구조와 구성 · 최대 8개**')
        rich['structure'] = table('structure', {'name':'구성 이름','desc':'설명'}, baseline.get('structure', []))
        field_error('structure')
        st.markdown('**다열 사양표 · 열 2~8개, 행 1~30개**')
        spec = baseline.get('spec_table') or {}
        columns = table('columns', {'name':'열 이름'}, [{'name':value} for value in spec.get('columns', [])])
        names = [row['name'] for row in columns]
        width = min(8, max(2, len(names)))
        row_fields = {f'c{i}':f'{i+1}열' for i in range(8)}
        baseline_rows = [dict(zip(row_fields,row)) for row in spec.get('rows', [])]
        rows = table('spec', row_fields, baseline_rows, visible=width)
        notes = table('notes', {'text':'사양표 주석'}, [{'text':value} for value in spec.get('notes', [])])
        if names or rows or notes:
            rich['spec_table'] = {'columns': names, 'rows': [list(row.values())[:width] for row in rows],
                                  'notes': [row['text'] for row in notes]}
        field_error('spec_table')
    S['rich_input'] = rich


def input_page():
    for key,value in S.get('form_buffer',{}).get('product',{}).items():
        if 'product_'+key not in S: S['product_'+key]=value
    if 'rich_baseline' not in S:
        S['rich_baseline'] = copy.deepcopy(S.get('form_buffer', {}))
        S['rich_revision'] = uuid.uuid4().hex[:8]
    if 'notice' not in S: S['notice']=S.get('form_buffer',{}).get('notice','')
    st.header('① 상품 정보')
    readiness_panel = st.container()
    from app.input_tools import extraction_panel, pending_claims_panel
    extraction_panel(facts_data, form_load)
    pending_claims_panel(facts_data, form_load)
    if st.button('샘플 데이터 넣기',key='sample'):
        form_load(read_json(ROOT/'samples/facts.json'),ROOT/'samples'); st.rerun()
    if st.button('상세 섹션 샘플 넣기',key='sample_rich'):
        form_load(read_json(ROOT/'samples/facts-rich.json'),ROOT/'samples'); st.rerun()
    from core.extract import validate_form_draft
    imported=st.file_uploader('기존 facts.json 불러오기',type=['json'],key='facts_upload')
    if imported and st.button('입력 양식으로 불러오기'):
        ok,data=perform('사실 불러오기',lambda:validate_form_draft(json.loads(imported.getvalue())))
        if ok: form_load(data); S['last_error']='사진은 별도로 업로드해 주세요.'
        st.rerun()
    st.markdown('### 기본 정보')
    st.text_input('상품명',key='product_name'); field_error('product.name')
    st.text_input('카테고리',key='product_category'); field_error('product.category')
    st.text_input('가격 (표시용)',key='product_price',help='비우면 상세페이지에 가격 칸이 나오지 않습니다. "판매하지 않음"처럼 적은 판매 상태는 그대로 표시합니다.'); field_error('product.price')
    st.color_picker('브랜드 색상',key='product_brand_color')
    color_candidates_input()
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
    st.subheader('참고 자료 (선택)')
    st.info('저작권이 있는 남의 문구는 참고만 하고 그대로 쓰지 않습니다. 주소는 출처 메모로만 저장하며 접속하지 않습니다.')
    st.text_input('경쟁사·브랜드 이름 (쉼표로 구분)',key='reference_names_text')
    sync_rows('reference')
    for index,row in enumerate(S['reference_rows']):
        uid=row['_uid']
        with st.container(border=True):
            st.text_input(f'참고 자료 ID {index+1}',value=row.get('id',''),key=f'reference_id_{uid}')
            st.text_input(f'참고 자료 이름 {index+1}',value=row.get('label',''),key=f'reference_label_{uid}')
            labels=list(REFERENCE_KINDS)
            chosen=next(k for k,v in REFERENCE_KINDS.items() if v==row.get('kind','other'))
            label=st.selectbox(f'참고 자료 종류 {index+1}',labels,index=labels.index(chosen),key=f'reference_kind_label_{uid}')
            row['kind']=REFERENCE_KINDS[label]
            st.text_area(f'참고 자료 본문 {index+1} (최대 5,000자)',value=row.get('text',''),key=f'reference_text_{uid}')
            st.text_input(f'출처 메모 {index+1} (URL도 기록만 함)',value=row.get('source_note',''),key=f'reference_source_note_{uid}')
            field_error(f'references.{index}')
            st.button('참고 자료 삭제',key=f'delete_reference_{uid}',on_click=remove_row,args=('reference',index))
    st.button('참고 자료 추가',on_click=add_row,args=('reference',))
    sync_rows('reference')
    from core.similarity import personal_data_warnings
    warning_names={'email':'이메일','phone':'전화번호','order_number':'주문번호'}
    for finding in personal_data_warnings(S['reference_rows']):
        st.warning(f"{warning_names[finding['kind']]} 형태가 있습니다: {finding['reference_label'] or finding['reference_id']} · 저장 전에 확인하고 지워 주세요.")
    st.markdown('### 상세 섹션 입력')
    rich_inputs()
    if S.get('input_metadata',{}).get('spec_from_import'):
        table_digest = json.dumps(S['rich_input'].get('spec_table'),ensure_ascii=False,sort_keys=True)
        if S.get('verified_table_digest') != table_digest:
            S['input_metadata']['spec_verified'] = False
            S['verified_table_digest'] = table_digest
            S.pop('spec_verified_'+S['rich_revision'],None)
        verified = st.checkbox('원본 자료와 대조했습니다',value=S['input_metadata'].get('spec_verified',False),
                               key='spec_verified_'+S['rich_revision'])
        S['input_metadata']['spec_verified'] = verified
    st.subheader('사진')
    st.file_uploader('상품 사진 (PNG/JPEG, 최대 10장, 장당 10MB)',type=['png','jpg','jpeg'],accept_multiple_files=True,key='photos',on_change=uploaded)
    if S.get('upload_error'): st.error(S['upload_error'])
    field_error('images')
    from core.background import available
    bg_ready=available()
    if not bg_ready: st.caption('배경 제거는 선택 설치입니다. requirements-bg.lock을 설치하면 활성화됩니다.')
    for i,ref in enumerate(S['image_refs']):
        path=Path(S['image_root'])/ref['path']
        if S['image_root'] and path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(Path(S['image_root']).resolve()): st.image(str(path),width=160)
        labels=list(ROLES); current=next(k for k,v in ROLES.items() if v==ref['role'])
        chosen=st.selectbox(f'사진 {i+1} 역할',labels,index=labels.index(current),key=f'image_role_{S["image_root"]}_{i}')
        ref['role']=ROLES[chosen]
        from core.images import Processing
        settings=Processing.model_validate(ref.get('processing',{})).model_dump()
        settings['remove_background']=st.checkbox(f'사진 {i+1} 배경 제거 (선택)',value=bool(settings['remove_background'] and bg_ready),disabled=not bg_ready,key=f'bg_{S["image_root"]}_{i}') and bg_ready
        from app.input_tools import crop_panel
        settings = crop_panel(ref, path, settings, i)
        ref['processing']=settings
        image_source_panel(ref, i)
    image_prompt_panel()
    if S['image_refs'] and st.button('사진 처리 미리보기',key='photo_preview',disabled=S.get('busy',False)):
        def preview_photos():
            facts=ProductFacts.model_validate(facts_data())
            if not S['image_root']: raise ValueError('상품 사진을 업로드해 주세요.')
            return create_job(facts,Path(S['image_root']),outputs(),method='image-preview')
        ok,preview=perform('사진 처리',preview_photos)
        if ok: S['photo_preview_job']=str(preview)
        st.rerun()
    photo_previews()
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
    st.markdown('### 안내 문구')
    st.text_area('배송·교환·반품 안내 (선택)',key='notice'); field_error('notice')
    data=facts_data()
    from core.readiness import check_readiness
    findings = check_readiness(data,Path(S.get('image_root') or '.'),{})
    from app.input_tools import readiness_results
    with readiness_panel:
        readiness_results(findings)
    required = any(item['level']=='필수' for item in findings)
    st.download_button('facts.json 내보내기',data=json.dumps(data,ensure_ascii=False,indent=2),file_name='facts.json',mime='application/json')
    if data.get('spec_from_import') and not data.get('spec_verified'):
        st.warning('가져온 사양표를 원본 자료와 대조해 주세요.')
    if st.button('저장하고 프롬프트 만들기',key='create',type='primary',disabled=required or S.get('busy',False)):
        def create():
            facts=ProductFacts.model_validate(data)
            if not S['image_root']: raise ValueError('상품 사진을 업로드해 주세요.')
            from core.render import DEFAULT_DESIGN_VERSION
            return create_job(facts,Path(S['image_root'] or '.'),outputs(),design_version=DEFAULT_DESIGN_VERSION)
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
    from core.editor import save_draft,evidence_units,change_copy_items,latest_measurement,COPY_CODES
    st.header('④ 검수·문구 수정')
    document=read_json(job/'draft.json')
    reviews=read_json(job/'review.json')
    state=latest_measurement(job)
    metrics,fresh=state['metrics'],state['fresh']
    metric_map={(m['section_id'],m['field_path']):m for m in metrics}
    measured_sections={s['id']:s for s in (state['draft'] or {}).get('sections',[])}
    overflow=[item for item in reviews if item.get('code') in COPY_CODES]
    kinds={s['id']:s['type'] for s in document['sections']}
    ai_overflow=[item for item in overflow if kinds.get(item['section_id']) in COPY_SECTION_TYPES]
    if metrics and not fresh:
        st.info('지난 미리보기 뒤에 문구·테마·브랜드 색이 바뀌었습니다. 아래 줄 수는 지난 미리보기 기준입니다. ⑤에서 다시 미리보기해야 줄 수를 다시 잽니다.')
    elif not metrics:
        st.caption('⑤ 미리보기를 만들면 문구마다 실제 줄 수가 표시됩니다 (1 섹션 1 메시지 점검).')
    if overflow:
        st.warning(f'줄 수 초과 {len(overflow)}건 · 아래 표시된 칸을 줄이거나 "초과한 문구만 다시 쓰기 요청"을 사용하세요. 문구는 자동으로 자르지 않습니다.')
        names={s['id']:NAMES.get(s['type'],s['type']) for s in document['sections']}
        st.markdown('\n'.join(f"- [{names.get(item['section_id'],item['section_id'])} · {item['field_path']}](#sec-{item['section_id']}): {item['reason']}" for item in overflow))
    for item in reviews:
        if item['section_id']=='images': st.warning('사진 검수: '+item['reason'])
    facts={f['id']:f['text'] for f in read_json(job/'facts.json')['facts']}
    units=evidence_units(job,document)
    edited,references=editor_snapshot(job,document,units,facts)
    locks=read_json(job/'edits.json').get('locked_sections',[]) if (job/'edits.json').exists() else []
    selected=[]
    st.info('가격·상품명·후기·스펙·안내 문구와 상세 섹션 입력은 ① 상품 정보에서 수정하고 새 작업을 시작하세요.')
    for index,section in enumerate(edited['sections']):
        sid=section['id']; kind=section['type']
        with st.container(border=True):
            st.subheader(NAMES[kind],anchor=f'sec-{sid}')
            for item in reviews:
                if item['section_id']==sid and item.get('code') not in COPY_CODES:
                    st.warning('검수: '+error_text(item['reason'])+' · '+item.get('field_path',''))
                    if item.get('reason')=='참고 자료와 표현 유사' and item.get('detail'):
                        st.code(item['detail'].get('text',''),language=None)
            fields=editable_fields(section)
            if not fields: st.json(section,expanded=False)
            for path,limit in fields:
                initial=nested(section,path) or ''
                value=st.text_area(f'{NAMES[kind]} · {path} (상한 {limit}자)',value=initial,key=edit_key(job,sid,path))
                st.caption(f'{len(value)} / {limit}자')
                measured=metric_map.get((sid,path))
                try: was=nested(measured_sections[sid],path)
                except (KeyError,IndexError,ValueError,TypeError): was=None
                if measured and (not fresh or value!=was):
                    step='문구를 고쳤으니 저장 후 ⑤에서 다시 미리보기 필요' if value!=was else '⑤에서 다시 미리보기 필요'
                    st.caption(f"지난 미리보기 기준 {measured['lines']}줄 / 허용 {measured['limit']}줄 · {step}")
                elif measured and measured['over']:
                    from core.measure import target_chars
                    st.warning(f"{measured['lines']}줄 / 허용 {measured['limit']}줄 · 약 {target_chars(measured['chars'],measured['lines'],measured['limit'])}자 이하로 줄이기 권장")
                elif measured:
                    st.caption(f"{measured['lines']}줄 / 허용 {measured['limit']}줄")
                if kind=='hero' and path=='subcopy' and not value:
                    section.pop('subcopy',None)
                else:
                    nested(section,path,value,True)
            for unit in units:
                if unit['section_id']==sid:
                    references[unit['key']]=st.multiselect(f'{NAMES[kind]} · {unit["path"]} 근거 사실',options=list(facts),default=[fid for fid in unit['fact_ids'] if fid in facts],format_func=lambda fid:fid+': '+facts[fid],key=evidence_key(job,unit))
            if kind in ('pain','features','how_to','faq'):
                array='steps' if kind=='how_to' else 'items'
                def mutate(action,item_index=None):
                    snapshot,refs=editor_snapshot(job,document,units,facts)
                    changed=change_copy_items(snapshot,sid,action,item_index,evidence=refs)
                    locked=[part['id'] for part in document['sections'] if S.get(f'lock_{job.name}_{part["id"]}',part['id'] in locks)]
                    save_draft(job,changed['data'],locked,evidence=changed['evidence'])
                for number in range(len(section[array])):
                    if st.button(f'{NAMES[kind]} 항목 {number+1} 삭제',key=f'remove_{sid}_{number}'):
                        ok,_=perform('목록 항목 삭제 및 재검수',lambda n=number:mutate('remove',n))
                        if ok: S['editor_revision']=uuid.uuid4().hex[:8];S['bundle']=''
                        st.rerun()
                if st.button(f'{NAMES[kind]} 항목 추가',key=f'add_{sid}'):
                    ok,_=perform('목록 항목 추가',lambda:mutate('add'))
                    if ok: S['editor_revision']=uuid.uuid4().hex[:8];S['bundle']=''
                    st.rerun()
            if st.checkbox('잠금 (재생성 시 유지)',value=sid in locks,key=f'lock_{job.name}_{sid}'): selected.append(sid)
    if st.button('수정 저장·재검수',key='save_edits',type='primary',disabled=S.get('busy',False)):
        ok,_=perform('수정 저장 및 근거 재검수',lambda:save_draft(job,edited,selected,evidence=references))
        if ok:
            S['bundle']=''; S['last_error']=''; S['saved_message']='수정과 검수 목록을 저장했습니다.'
        st.rerun()
    if S.get('saved_message'): st.success(S['saved_message'])
    if overflow and not ai_overflow:
        st.caption('초과한 내용이 모두 판매자 입력(숫자 띠·적용 대상·구성)입니다. ① 상품 정보에서 고치고 새 작업을 시작하세요.')
    if st.button('초과한 문구만 다시 쓰기 요청',key='overflow_rewrite',disabled=S.get('busy',False) or not ai_overflow,
                 help='AI가 쓴 섹션 중 줄 수를 넘은 섹션만 다시 쓰도록 요청하는 프롬프트를 만듭니다. 나머지 섹션은 잠긴 채 그대로 유지됩니다.'):
        ok,new=perform('초과 문구 다시 쓰기 프롬프트 만들기',lambda:overflow_regenerate_job(job))
        if ok: schedule_open(new,1)
        else: st.rerun()
    if st.button('잠그지 않은 섹션 다시 쓰기',disabled=S.get('busy',False)):
        ok,new=perform('재생성 프롬프트 만들기',lambda:regenerate_job(job))
        if ok: schedule_open(new,1)
        else: st.rerun()
    if st.button('저장한 문구 미리보기',key='to_preview'): go(4)


def display_bundle(bundle):
    manifest=read_json(bundle/'manifest.json')
    st.caption('작업 버전 ID: '+manifest['job_id'])
    if manifest.get('contrast_adjustments'):
        st.info('브랜드 색 대비 보정됨')
    if not manifest.get('review_accepted'):
        st.warning('DRAFT · 승인 전 미리보기입니다. 검수 항목과 문구를 확인하세요.')
    if manifest.get('needs_review'):
        if manifest.get('review_accepted'): st.info('승인 완료 · 검수 기록은 review.json에 보존됩니다.')
        else: st.error('검수 필요: 근거·수치·광고 표현을 확인해 주세요.')
    from core.image_checks import SOURCE_NAMES
    ai=[item for item in manifest.get('image_sources',[]) if item['source']!='photo']
    confirmed={check['index'] for check in manifest.get('image_checks',[])}
    name=lambda item:f"사진 {item['index']+1} {SOURCE_NAMES[item['source']]}({item.get('generator','')})"
    done=[name(item) for item in ai if item['index'] in confirmed]
    pending=[name(item) for item in ai if item['index'] not in confirmed]
    if done:
        st.info('AI로 만든 이미지 · 이미지별 확인 완료: '+', '.join(done)+(' (페이지 승인은 별도)' if not manifest.get('review_accepted') else ''))
    if pending:
        st.warning('AI로 만든 이미지 '+str(len(pending))+'장 · 확인 전: '+', '.join(pending)+'. ⑥ 승인에서 원본과 나란히 보고 이미지마다 확인해야 합니다.')
    if manifest.get('ai_images') and manifest.get('image_sources') is None:
        st.error('이 결과에는 AI 이미지의 출처 기록이 없어 내보낼 수 없습니다. 다시 미리보기하세요.')
    for page in manifest['pages']: st.image(str(bundle/page['file']),width='stretch')
    return manifest


def design_gallery(job, selected):
    from core.editor import gallery_thumbnail
    from streamlit.elements.lib.image_utils import image_to_url
    from streamlit.elements.lib.layout_utils import LayoutConfig

    st.html('''<style>
        .st-key-theme_gallery button img {
            display: block;
            max-height: none;
            height: auto;
            width: 100%;
            margin: 0 auto .55rem;
        }
        .st-key-theme_gallery button:disabled img { opacity: 1; }
    </style>''')
    with st.container(key='theme_gallery'), st.spinner('현재 상품으로 테마 7종을 비교하는 중입니다…'):
        for start in range(0, len(THEME_IDS), 4):
            themes = THEME_IDS[start:start+4]
            for column, theme in zip(st.columns(len(themes)), themes):
                with column:
                    name = load_theme(theme).name
                    label = name + (' · 선택됨' if theme == selected else ' 선택')
                    try:
                        thumbnail = gallery_thumbnail(job, theme)
                        url = image_to_url(thumbnail, LayoutConfig(width=270), False, 'RGB', 'PNG', f'gallery_{theme}')
                        if url:
                            label = f'![]({url}) {label}'
                    except (OSError, ValueError) as exc:
                        st.error(error_text(exc))
                    if st.button(label, key=f'gallery_{theme}', disabled=theme == selected, width='stretch'):
                        S['gallery_selection'] = theme
                        st.rerun()


def preview_page(job):
    from core.editor import preview_job
    st.header('⑤ 미리보기')
    manifest = read_json(job/'manifest.json')
    current_theme = manifest.get('theme','classic')
    current_brand = effective_brand(manifest,read_json(job/'facts.json')['product']['brand_color'])
    if 'gallery_selection' in S:
        S['theme_choice'] = S.pop('gallery_selection')
    if 'preview_brand' not in S:
        S['preview_brand'] = current_brand
    if 'theme_choice' not in S: S['theme_choice']=current_theme
    from core.render import job_design_version
    current_version=job_design_version(manifest)
    if S.get('design_choice') not in (1,2): S['design_choice']=current_version
    version=st.radio('디자인 버전',[2,1],key='design_choice',horizontal=True,
                     format_func=lambda v:'v2 · 새 디자인' if v==2 else 'v1 · 이전 디자인',
                     help='기존 작업은 만들 때의 v1을 그대로 씁니다. 바꾸면 미리보기를 다시 만들고 승인도 다시 받아야 합니다.')
    selected=st.selectbox('디자인 테마',THEME_IDS,key='theme_choice')
    color_candidates_job(job)
    brand = st.color_picker('미리보기 브랜드 색', key='preview_brand')
    if selected != current_theme or brand.lower() != current_brand.lower() or version != current_version:
        ok,bundle=perform('디자인 미리보기 렌더링',lambda:preview_job(job,theme=selected,brand_color=brand,design_version=version))
        if ok:
            S['bundle']=str(bundle)
            for key in list(S):
                if key.startswith('check_'): del S[key]
        else:
            return
    if st.toggle('디자인 갤러리', key='show_gallery'):
        design_gallery(job, selected)
    if st.button('저장된 문구로 미리보기 생성',key='preview',disabled=S.get('busy',False)):
        bundle=Path(S['bundle']) if S.get('bundle') else None
        if bundle is None or not bundle_matches(job,bundle):
            ok,bundle=perform('미리보기 렌더링',lambda:preview_job(job,theme=selected))
            if not ok: st.rerun()
            S['bundle']=str(bundle)
        st.rerun()
    if S.get('bundle'): display_bundle(Path(S['bundle']))
    if st.button('승인 단계로 이동'): go(5)
    if S.get('bundle') and st.button('DRAFT 다운로드 단계로 이동'): go(6)


def approval_page(job):
    st.header('⑥ 승인')
    manifest = read_json(job/'manifest.json')
    theme = manifest.get('theme','classic')
    from core.claims import claim_items
    numeric_items = claim_items(job)
    from core.editor import provenance_path
    from core.image_checks import ai_image_items, SOURCE_NAMES
    image_items = ai_image_items(ProductFacts.model_validate(read_json(provenance_path(job,'facts.json'))))
    context = (str(job), theme, manifest.get('brand_color'),
               (job/'draft.json').read_bytes(),tuple(item['id'] for item in numeric_items),
               tuple((item['id'],item['path']) for item in image_items))
    if S.get('approval_context')!=context:
        for key in list(S):
            if key.startswith('check_'): del S[key]
        S['approval_context']=context
    st.caption('선택한 테마: '+theme)
    labels=['사실 일치 확인','후기 출처·허가 확인','효능·수치·광고 표현 확인','대상 플랫폼 업로드 규격은 별도 확인 필요함을 인지','상품 사진의 형태·색상이 실제와 다르게 바뀌지 않았는지 확인']
    checks=[st.checkbox(label,key=f'check_{job.name}_{i}') for i,label in enumerate(labels)]
    st.subheader('수치·비교 표현 확인')
    confirmations = []
    for item in numeric_items:
        with st.container(border=True):
            st.write(item['text'])
            st.caption('표현: '+', '.join(item['expressions']))
            for fact in item['facts']:
                st.write(fact['id']+' · '+fact['text'])
                st.caption('근거: '+str(fact.get('evidence') or '등록된 근거 없음'))
            if not item['has_evidence']:
                st.warning('연결된 사실의 근거가 부족합니다. 원본 자료와 근거를 확인하세요.')
            for reason in item['review_reasons']:
                st.caption('기존 검수: '+reason)
            checked = st.checkbox('이 수치·비교 표현과 근거를 확인했습니다',
                                  key=f'check_claim_{job.name}_{item["id"]}')
            checks.append(checked)
            if checked:
                confirmations.append(item['id'])
    image_confirmations = {}
    if image_items:
        st.subheader('AI로 만든 이미지 확인')
        st.caption('이미지마다 항목을 하나씩 확인하세요. 하나라도 다르면 승인하지 말고 ①에서 이미지를 바꾸세요.')
        hints = {record.get('source_path'): record for record in manifest.get('image_processing',[])}
    for item in image_items:
        with st.container(border=True):
            st.write(f"사진 {item['index']+1} · {SOURCE_NAMES[item['source']]} · {item['generator']}")
            if item.get('edit_request'): st.caption('요청 내용: '+item['edit_request'])
            if item['original_path']:
                left,right=st.columns(2)
                left.image(str(job/item['original_path']),caption='원본 실제 사진',width='stretch')
                right.image(str(job/item['path']),caption='AI로 배경을 바꾼 사진',width='stretch')
                difference=hints.get(item['source_path'],{}).get('comparison',{}).get('aspect_difference')
                if difference is not None:
                    st.caption(f'참고: 가로세로 비율 차이 {difference:.0%} (판정이 아니라 확인을 돕는 수치입니다)')
            else:
                st.image(str(job/item['path']),caption='AI 생성 이미지 (페이지에 "연출 이미지입니다" 표시)',width=320)
            done=[]
            for key,label in item['checks']:
                checked=st.checkbox(label,key=f"check_image_{job.name}_{item['id']}_{key}")
                checks.append(checked)
                if checked: done.append(key)
            image_confirmations[item['id']]=done
    if st.button('모두 확인했으며 승인',key='accept',type='primary',disabled=not all(checks) or S.get('busy',False)):
        ok,accepted=perform('승인 결과 렌더링',lambda:accept_job(job,claim_confirmations=confirmations,image_confirmations=image_confirmations or None))
        if ok:
            schedule_open(accepted,6)
        else: st.rerun()


def download_page(job):
    from core.editor import build_zip
    st.header('⑦ 다운로드')
    if not S.get('bundle'):
        st.info('⑤에서 미리보기를 만들거나 ⑥에서 승인해 주세요.'); return
    bundle=Path(S['bundle'])
    if not bundle_matches(job,bundle):
        st.warning('저장된 문구 또는 테마가 변경되었습니다. ⑤에서 새 미리보기를 만들어 주세요.'); return
    manifest=read_json(bundle/'manifest.json')
    ok,data=perform('ZIP 준비',lambda:build_zip(bundle))
    if ok:
        S['download_zip']=data
        filename=manifest['job_id']+('' if manifest.get('review_accepted') else '.DRAFT')+'.zip'
        st.download_button('ZIP 다운로드',data=data,file_name=filename,mime='application/zip',key='download_zip_button')
    pdf_section(bundle)
    export_section(bundle)
    display_bundle(bundle)


def pdf_section(bundle):
    """M8-C: PDF with selectable text (the rules live in core/pdf.py)."""
    from core.pdf import make_pdf
    st.subheader('PDF (글자 선택·캔바 편집용)')
    st.caption('JPG와 같은 위치에서 쪽을 나눈 PDF입니다. 글자가 이미지가 아니라 글자로 들어가는지 검사하고 만듭니다. 만든 뒤 ZIP 다운로드에도 포함됩니다.')
    manifest=read_json(bundle/'manifest.json')
    if not manifest.get('pdf') and st.button('PDF 만들기',key='make_pdf',disabled=S.get('busy',False)):
        ok,_=perform('PDF 만들기',lambda:make_pdf(bundle))
        st.rerun()
    manifest=read_json(bundle/'manifest.json')
    if manifest.get('pdf'):
        info=manifest['pdf']
        st.caption(f"{info['pages']}쪽 · 글자 {info['text_check']['runs']}곳 확인 · 글꼴: {', '.join(info['fonts'])}")
        st.download_button('PDF 다운로드',data=(bundle/info['file']).read_bytes(),file_name=manifest['job_id']+'-'+info['file'],
                           mime='application/pdf',key='download_pdf_button')


def export_section(bundle):
    """Platform profile check and per-profile ZIP. All rules live in core/export.py."""
    from core.export import build_export_zip, export_bundle, list_profiles, load_profile
    st.subheader('올릴 곳 규격 검사·내보내기')
    st.caption('프로필의 폭·분할 높이·용량·장수·형식으로 검사해 따로 ZIP을 만듭니다. 공식 문서로 확인되지 않은 프로필은 "규격 미확인"으로 표시하며, 실제 등록 규격은 올릴 곳에서 다시 확인해야 합니다.')
    profiles=list_profiles()
    # A newly saved profile is selected on the next run (a widget's value cannot change after it is drawn).
    if 'export_profile_next' in S: S['export_profile']=S.pop('export_profile_next')
    names={p['id']:p['name']+(' · 규격 미확인' if p['status']!='verified' else ' · 공식 문서 확인됨')+(' · 사용자 프로필' if p['user'] else '') for p in profiles}
    profile_id=st.selectbox('내보내기 프로필',[p['id'] for p in profiles],format_func=lambda value:names[value],key='export_profile')
    broken=next(p['error'] for p in profiles if p['id']==profile_id)
    profile=None
    if broken:
        st.error('프로필 파일 오류: '+broken)
    else:
        profile=load_profile(profile_id)
        if profile.status=='verified':
            st.caption(f'출처: {profile.source_url} · 확인 날짜: {profile.checked_date}')
        if profile.notes: st.caption(profile.notes)
    export_key=(str(bundle),profile_id,json.dumps(profile.record(),sort_keys=True) if profile else None)
    if S.get('export_for')!=export_key:
        S['export_result']=None
        S['export_zip']=None
    if st.button('규격 검사 후 내보내기',key='export_run',disabled=bool(broken) or S.get('busy',False)):
        ok,result=perform('규격 검사·내보내기',lambda:export_bundle(bundle,profile_id))
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
            st.error('내보내기 오류: 위 항목을 고친 뒤 다시 시도하세요. ZIP을 만들지 않았습니다.')
        elif S.get('export_zip'):
            if result['status']=='pass':
                st.success('이 프로필의 기준 검사를 통과했습니다. 실제 등록 규격은 올릴 곳에서 다시 확인하세요.')
            name,data=S['export_zip']
            st.download_button(name+' 다운로드',data=data,file_name=name,mime='application/zip',key='export_zip_button')
    with st.expander('새 프로필 만들기'):
        st.caption('공식 판매자 도움말에서 직접 확인한 값만 입력하세요. 비워 둔 값은 검사하지 않고 "규격 미확인"으로 표시합니다. 사용자 프로필은 이 컴퓨터에만 저장됩니다.')
        new_id=st.text_input('프로필 이름(영문 소문자·숫자·-·_)',key='new_profile_id')
        new_name=st.text_input('표시 이름',key='new_profile_name')
        status=st.selectbox('확인 상태',['unverified','verified'],format_func=lambda v:{'unverified':'규격 미확인','verified':'공식 문서로 확인함 (모든 값·출처·날짜 필요)'}[v],key='new_profile_status')
        source=st.text_input('공식 문서 주소 (https://, 접속하지 않고 기록만 함)',key='new_profile_source')
        checked=st.text_input('확인 날짜 (YYYY-MM-DD)',key='new_profile_date')
        width=st.number_input('이미지 폭(px)',min_value=100,max_value=4000,value=None,step=10,key='new_profile_width')
        height=st.number_input('이미지 1장 최대 높이(px)',min_value=100,max_value=30000,value=None,step=100,key='new_profile_max_height')
        size=st.number_input('이미지 1장 최대 용량(바이트)',min_value=1,value=None,step=100000,key='new_profile_max_bytes')
        count=st.number_input('최대 장수',min_value=1,max_value=1000,value=None,step=1,key='new_profile_max_images')
        formats=st.multiselect('허용 형식',['jpg','png'],key='new_profile_formats')
        quality=st.number_input('JPEG 품질',min_value=1,max_value=100,value=None,step=1,key='new_profile_quality')
        notes=st.text_area('메모',key='new_profile_notes')
        if st.button('프로필 저장',key='new_profile_save',disabled=S.get('busy',False)):
            from core.export import save_user_profile
            data={'name':new_name,'status':status,'source_url':source.strip() or None,'checked_date':checked.strip() or None,
                  'width':width,'max_height_per_image':height,'max_file_bytes':size,'max_images':count,
                  'formats':formats or None,'jpeg_quality':quality,'notes':notes}
            ok,_=perform('프로필 저장',lambda:save_user_profile(new_id.strip(),{k:(int(v) if isinstance(v,float) else v) for k,v in data.items()}))
            if ok:
                S['export_profile_next']=new_id.strip()
                st.rerun()


STATUS_TEXT={'input_error':'입력 오류','awaiting_answer':'프롬프트 대기','answer_error':'답변 오류','needs_review':'검수 필요','approved':'승인됨'}
BADGES={'input_error':'🔴 입력 오류','awaiting_answer':'🟡 프롬프트 대기','answer_error':'🟠 답변 오류','needs_review':'🔵 검수 필요','approved':'🟢 승인됨'}

def stage_batch_upload(files):
    """Save the uploaded sheet(s) inside outputs only, with fixed safe names."""
    from core.batch import HEADERS
    folder=outputs()/'.batch-uploads'/uuid.uuid4().hex
    folder.mkdir(parents=True)
    if len(files)==1 and files[0].name.lower().endswith('.xlsx'):
        path=folder/'products.xlsx'; path.write_bytes(files[0].getvalue()); return path
    if any(not f.name.lower().endswith('.csv') for f in files):
        raise ValueError('XLSX 파일 1개 또는 CSV 파일(products.csv, facts.csv, images.csv, reviews.csv, references.csv)을 올려 주세요. 매크로 파일(.xlsm)은 받지 않습니다.')
    for f in files:
        name=Path(f.name).name.lower()
        if name.removesuffix('.csv') not in HEADERS: raise ValueError(f'알 수 없는 CSV 파일 이름: {f.name} (products/facts/images/reviews/references.csv)')
        (folder/name).write_bytes(f.getvalue())
    return folder


def open_batch_product(entry,batch):
    """Open one product's job in the normal ①~⑦ screens (approval stays per product)."""
    target=batch/(entry['accepted_job'] or entry['job'])
    index={'approved':6,'needs_review':3,'answer_error':2}.get(entry['status'],1)
    S['mode_next']='상품 하나씩'
    schedule_open(target,index)


def batch_page():
    from core import batch as B
    st.header('일괄 작업')
    st.caption('표(XLSX 또는 CSV)로 여러 상품의 작업을 한 번에 만들고, 상품별로 붙여넣기·검수·승인합니다. 일괄 승인은 없습니다. 승인된 상품만 묶어 내보냅니다.')
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        template=B.write_template(Path(folder)/'상품목록.xlsx').read_bytes()
    st.download_button('빈 상품 목록 템플릿(XLSX) 받기',data=template,file_name='상품목록.xlsx',key='batch_template')
    with st.expander('새 일괄 작업 가져오기',expanded=not S.get('batch')):
        files=st.file_uploader('상품 목록: XLSX 1개 또는 CSV 4개(UTF-8)',type=['xlsx','csv'],accept_multiple_files=True,key='batch_upload')
        root=st.text_input('사진 루트 폴더 (이 컴퓨터의 폴더 경로, 사진 폴더 열은 이 아래만 허용)',key='batch_photo_root')
        if st.button('가져오기',key='batch_import',disabled=S.get('busy',False)):
            def run():
                if not files: raise ValueError('상품 목록 파일을 올려 주세요.')
                if not root.strip(): raise ValueError('사진 루트 폴더를 입력해 주세요.')
                return B.import_batch(stage_batch_upload(files),Path(root.strip()).expanduser(),outputs())
            ok,folder=perform('일괄 가져오기',run)
            if ok: S['batch']=str(folder); st.rerun()
    batches=B.list_batches(outputs())
    if batches:
        labels={b['path']:f"{Path(b['path']).name} · {b['source']} · {b['count']}개 · {display_time(b['created_at'])}" for b in batches}
        chosen=st.selectbox('이전 일괄 작업',list(labels),format_func=lambda v:labels[v],key='batch_resume')
        if st.button('일괄 작업 열기',key='batch_open'):
            S['batch']=chosen; st.rerun()
    if not S.get('batch'): return
    batch=Path(S['batch'])
    try:
        entries=B.batch_status(batch); data=B.load_batch(batch)
    except (OSError,ValueError) as exc:
        st.error('일괄 작업을 열 수 없습니다: '+str(exc)); return
    st.subheader('상품 목록 · '+batch.name)
    for error in data['errors']:
        st.error(f"{error['sheet']} 시트 {error['row']}행 · {error['column']} 열: {error['reason']}")
    st.dataframe([{'상품':e['product_id'],'상품명':e['name'],'상태':BADGES[e['status']],'테마':e['theme'],'프로필':e['profile'],'메시지':e.get('message','')} for e in entries],hide_index=True,width='stretch')
    for entry in entries:
        pid=entry['product_id']
        for error in entry['errors']:
            st.error(f"{pid}: {error['sheet']} 시트 {error['row']}행 · {error['column']} 열: {error['reason']}")
        if entry['job'] and st.button(f'{pid} 열기 ({STATUS_TEXT[entry["status"]]})',key=f'batch_product_{pid}'):
            open_batch_product(entry,batch)
    st.subheader('붙여넣기 방식')
    if st.button('대기 중인 상품의 프롬프트 ZIP 만들기',key='batch_prompts'):
        ok,result=perform('프롬프트 묶기',lambda:B.export_prompts(batch))
        if ok: S['batch_prompts_zip']=(result[1],result[2])
    if S.get('batch_prompts_zip'):
        name,payload=S['batch_prompts_zip']
        st.download_button('프롬프트 ZIP 다운로드 (상품마다 별도 채팅에 붙여넣기)',data=payload,file_name=name,key='batch_prompts_download')
    answers=st.file_uploader('답변 파일: <product_id>.txt (상품마다 하나)',type=['txt'],accept_multiple_files=True,key='batch_answers')
    if st.button('답변 수집·검증',key='batch_ingest',disabled=S.get('busy',False)):
        def run():
            uploads=[(Path(f.name).name,f.getvalue()) for f in answers or []]
            return B.ingest_uploaded_answers(batch,uploads)
        ok,report=perform('답변 수집',run)
        if ok: S['batch_ingest_report']=report; st.rerun()
    report=S.get('batch_ingest_report') or {}
    for name in report.get('unknown_files',[]): st.warning('상품이 없는 답변 파일: '+name)
    import tomllib
    configuration=tomllib.loads((ROOT/'providers.toml').read_text())
    enabled=[name for name,value in configuration.get('providers',{}).items() if value.get('command') and value.get('configured',True)]
    if enabled:
        with st.expander('선택: 로그인된 공식 CLI로 순차 생성'):
            st.caption('대기 중인 상품을 하나씩 처리합니다. 사용량 한도에 걸리면 즉시 멈추고 남은 상품은 대기로 둡니다.')
            name=st.selectbox('구독 CLI',enabled,key='batch_provider')
            if st.button('순차 생성',key='batch_generate',disabled=S.get('busy',False)):
                from core.providers import CliProvider
                ok,result=perform('구독 CLI 순차 생성',lambda:B.generate_batch(batch,CliProvider(name)))
                if ok and result['stopped']:
                    S['last_error']='구독 CLI가 중단되어 남은 상품은 프롬프트 대기로 두었습니다. 붙여넣기 방식으로 이어가세요.'
                st.rerun()
    st.subheader('승인된 상품 내보내기')
    st.caption('상품마다 열어서 ⑥ 확인 항목을 체크해 승인한 상품만 묶습니다. 각 상품의 프로필로 검사하며 "규격 미확인" 경고는 상품 폴더의 manifest에 남습니다.')
    if st.button('승인된 상품 ZIP 만들기',key='batch_export',disabled=S.get('busy',False)):
        ok,result=perform('승인된 상품 내보내기',lambda:B.export_batch(batch))
        S['batch_export_result']=result if ok else None
    if S.get('batch_export_result'):
        name,payload,outcome=S['batch_export_result']
        for pid,item in outcome.items():
            if item['result']!='ok': st.warning(f'{pid}: {item["message"]}')
            for warning in item.get('warnings',[]): st.warning(f'{pid}: {warning}')
        st.download_button('승인된 상품 ZIP 다운로드',data=payload,file_name=name,key='batch_export_download')


def main():
    st.set_page_config(page_title='상세페이지 만들기',page_icon='🛍',layout='wide')
    if 'pending_job' in S: open_job(S.pop('pending_job'))
    if 'fact_rows' not in S: form_load()
    for key,value in [('job',''),('bundle',''),('busy',False),('last_error',''),('stage',STEPS[0])]:
        if key not in S: S[key]=value
    if 'next_stage' in S: S['stage']=S.pop('next_stage')
    if 'mode_next' in S: S['mode']=S.pop('mode_next')
    st.title('상품 상세페이지 만들기')
    st.caption('상품 사실을 넣고 → 채팅에 붙여넣고 → 검수한 뒤 이미지로 저장하세요. 로컬 전용 · AI API 사용 없음')
    from core.editor import job_listing
    with st.sidebar:
        mode=st.selectbox('작업 방식',['상품 하나씩','일괄 작업'],key='mode')
    if mode=='일괄 작업':
        if S.get('last_error'): st.error(S['last_error'])
        batch_page(); return
    with st.sidebar:
        st.header('작업 이어하기')
        if st.button('새 작업 시작'):
            form_load(); S['job']=''; S['bundle']=''; S['last_error']=''; go(0)
        jobs=job_listing(outputs())
        options=[item['path'] for item in jobs]
        labels={item['path']:f'{item["product_name"]} · {display_time(item["created_at"])} · {item["status"]} · {Path(item["path"]).name}' for item in jobs}
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

