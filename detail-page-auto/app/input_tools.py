"""Seller input helpers using the shared core import and photo operations."""
import hashlib
from pathlib import Path
import streamlit as st
from core.extract import extraction_prompt, ingest_facts, apply_import, promote_claim


def extraction_panel(facts_data, form_load):
    state = st.session_state
    with st.expander('자료에서 입력 만들기'):
        st.info('브로슈어 페이지 이미지를 채팅에 첨부하고 이 프롬프트를 함께 보내세요. 가져온 값은 반드시 원본과 대조하세요.')
        st.code(extraction_prompt(), language='markdown')
        st.caption('코드 상자 오른쪽 복사 버튼으로 프롬프트를 복사하세요.')
        answer = st.text_area('정리 답변 붙여넣기',key='extract_answer')
        digest = hashlib.sha256(answer.encode()).hexdigest()
        if st.button('가져오기',key='extract_parse'):
            state['extract_price_confirmed'] = False
            state['extract_result'] = ingest_facts(answer)
            state['extract_digest'] = digest
        result = state.get('extract_result')
        if not result or state.get('extract_digest') != digest:
            return
        if not result['ok']:
            st.error('답변 형식을 확인하세요. 수정 요청을 같은 채팅에 보내세요.')
            st.code(result['fix_prompt'],language='markdown')
            return
        data = result['data']
        table = data.get('spec_table') or {}
        st.write(f"사실 {len(data['facts'])}개 · 숫자 띠 {len(data['highlights'])}개 · 표 {len(table.get('rows',[]))}행 · 근거 필요 주장 {len(data['pending_claims'])}개")
        st.json(data,expanded=False)
        for message in [*result['warnings'], *data['uncertain']]:
            st.warning(message)
        confirm_price = False
        if result.get('price_candidate'):
            st.write('가격 후보',result['price_candidate'])
            confirm_price = st.checkbox('원본의 가격을 확인했으며 입력에 적용합니다',key='extract_price_confirmed')
        mode = st.radio('적용 방식',['덮어쓰기','비어 있는 칸만 채우기'],key='extract_mode')
        if st.button('미리보기 값을 입력에 적용',key='extract_apply'):
            updated = apply_import(facts_data(),result,mode='replace' if mode=='덮어쓰기' else 'empty',confirm_price=confirm_price)
            root = state.get('image_root')
            form_load(updated,root)
            st.rerun()


def pending_claims_panel(facts_data, form_load):
    state = st.session_state
    metadata = state.get('input_metadata',{})
    candidate = metadata.get('price_candidate')
    if candidate:
        st.write('자료에서 가져온 가격 후보',candidate)
        if st.button('원본 가격을 확인하고 후보를 입력',key='apply_saved_price'):
            data = facts_data()
            data['product']['price'] = candidate
            form_load(data,state.get('image_root'))
            st.rerun()
    claims = metadata.get('pending_claims',[])
    if not claims:
        return
    st.markdown('### 근거가 필요한 주장')
    with st.expander('주장 목록',expanded=True):
        for index, claim in enumerate(claims):
            st.write(claim['text'])
            evidence = st.text_input(f'주장 {index+1} 근거',key=f'pending_evidence_{state["rich_revision"]}_{index}')
            if st.button('근거를 입력한 주장을 사실로 옮기기',key=f'promote_{index}',disabled=not evidence.strip()):
                updated = promote_claim(facts_data(),index,evidence)
                form_load(updated,state.get('image_root'))
                st.rerun()


def crop_panel(ref, path, settings, index):
    from core.images import preview_crop
    state = st.session_state
    token = f'{state["image_root"]}_{index}'
    crop = dict(settings['crop'])
    keys = {side:f'crop_{side}_{token}' for side in ('top','bottom','left','right')}
    with st.expander(f'사진 {index+1} 자르기'):
        if st.button('자르기 초기화',key=f'crop_reset_{token}'):
            for key in keys.values():
                state[key] = 0
        for side, label in (('top','위'),('bottom','아래'),('left','왼쪽'),('right','오른쪽')):
            crop[side] = st.slider(f'사진 {index+1} {label} 자르기 (%)',0,45,
                                   value=round(crop[side]*100),step=1,key=keys[side])/100
        settings['crop'] = crop
        if path.is_file() and not path.is_symlink() and state.get('image_root') and path.resolve().is_relative_to(Path(state['image_root']).resolve()):
            try:
                st.image(preview_crop(path,settings),caption='자른 결과 미리보기',width=300)
            except (OSError, ValueError) as exc:
                st.error(str(exc))
    ref['document_confirmed'] = st.checkbox(f'사진 {index+1} 이대로 사용 (문서형 경고 끄기)',
                                            value=ref.get('document_confirmed',False),key=f'document_ok_{token}')
    return settings


def readiness_results(findings):
    st.subheader('입력 점검 결과')
    destinations = {'product':'기본 정보','facts':'상품 사실','images':'사진',
                    'highlights':'상세 섹션 입력','targets':'상세 섹션 입력',
                    'structure':'상세 섹션 입력','spec_table':'상세 섹션 입력',
                    'pending_claims':'근거가 필요한 주장','notice':'배송·교환·반품 안내'}
    for item in findings:
        text = f"{item['level']} · {item['message']}"
        if item['level'] == '필수':
            st.error(text)
        elif item['level'] == '권장':
            st.warning(text)
        else:
            st.caption(text)
        field = item['field'].split('.')[0]
        destination = destinations.get(field,'상품 정보')
        # Static destination names only, never insert seller text into links.
        anchors = {'기본 정보':'기본-정보','상품 사실':'상품-사실','사진':'사진','상세 섹션 입력':'상세-섹션-입력',
                   '근거가 필요한 주장':'근거가-필요한-주장','배송·교환·반품 안내':'안내-문구'}
        if destination in anchors:
            st.markdown(f'[{destination}로 이동](#{anchors[destination]})')
        else:
            st.caption(f'① {destination} 칸에서 확인하세요.')
