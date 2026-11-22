"""Paste-only extraction drafts and explicit seller-controlled application."""
import copy
import json
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationError
from .schema import Model, Text, Highlight, StructureItem, SpecTable, Title, Body
from .facts import PendingClaim
from .ingest import extract_json
from .prompting import make_fix_prompt


class DraftProduct(Model):
    name: str
    category: str
    price: str | None = None


class DraftFact(Model):
    id: Text
    text: Text = Field(max_length=500)
    kind: Literal['spec', 'feature', 'usage', 'other']


class FactsDraft(Model):
    product: DraftProduct
    facts: list[DraftFact]
    claims: list[PendingClaim] = Field(default_factory=list)
    highlights: list[Highlight] = Field(default_factory=list, max_length=4)
    targets: list[Title] = Field(default_factory=list, max_length=12)
    structure: list[StructureItem] = Field(default_factory=list, max_length=8)
    spec_table: SpecTable | None = None
    notice: Body | None = None
    uncertain: list[Text] = Field(default_factory=list)


def extraction_prompt() -> str:
    template = (Path(__file__).resolve().parents[1]/'prompts/extract_v1.md').read_text(encoding='utf-8')
    example = {
        'product': {'name':'가상 모듈형 보관함', 'category':'가상 설비'},
        'facts':[{'id':'width','text':'폭 320 mm','kind':'spec'}],
        'claims':[{'text':'반영구적 사용'}],
        'highlights':[{'value':'320 mm','label':'폭','fact_id':'width'}],
        'targets':['가상 작업실'], 'structure':[{'name':'외함','desc':'분리형 케이스'}],
        'spec_table':{'columns':['항목','값'],'rows':[['폭','320 mm']],'notes':[]},
        'uncertain':['모델명이 흐릿해 확인 필요'],
    }
    return (template + '\n\n## 출력 구조\n' + json.dumps(FactsDraft.model_json_schema(),ensure_ascii=False,indent=2)
            + '\n\n## 가상 예시 JSON\n' + json.dumps(example,ensure_ascii=False,indent=2))


def _unique_id(proposed, used, warnings, reserved=()):
    value = proposed
    suffix = 2
    while value in used or (value != proposed and value in reserved):
        value = f'{proposed}-{suffix}'
        suffix += 1
    used.add(value)
    if value != proposed:
        warnings.append(f'사실 ID {proposed}를 {value}로 정리했습니다.')
    return value


def ingest_facts(answer: str) -> dict:
    try:
        draft = FactsDraft.model_validate(extract_json(answer))
    except (ValueError, ValidationError) as exc:
        return {'ok':False, 'error':str(exc),
                'fix_prompt':make_fix_prompt(extraction_prompt(),answer,[{'field_path':'answer','reason':str(exc)}])}
    warnings, used, facts, pending = [], set(), [], []
    original_ids = {fact.id for fact in draft.facts}
    for fact in draft.facts:
        row = fact.model_dump()
        row['id'] = _unique_id(fact.id, used, warnings, original_ids)
        facts.append(row)
    for claim in draft.claims:
        if claim.evidence:
            facts.append({'id':_unique_id('claim',used,warnings),'kind':'claim', **claim.model_dump(exclude_none=True)})
        else:
            pending.append(claim.model_dump(exclude_none=True))
    highlights = []
    for item in draft.highlights:
        if item.fact_id in original_ids:
            highlights.append(item.model_dump())
        else:
            warnings.append(f'숫자 띠 {item.label}: 사실 ID {item.fact_id}가 없어 제외했습니다.')
    data = {'schema_version':'1.0',
            'product':{'name':draft.product.name,'category':draft.product.category,'price':'','brand_color':'#305b46'},
            'facts':facts, 'images':[], 'pending_claims':pending, 'uncertain':draft.uncertain,
            'highlights':highlights,'targets':draft.targets,
            'structure':[item.model_dump() for item in draft.structure],
            'price_candidate':draft.product.price,
            'spec_from_import':bool(draft.spec_table), 'spec_verified':False}
    if draft.spec_table:
        data['spec_table'] = draft.spec_table.model_dump()
    if draft.notice:
        data['notice'] = draft.notice
    return {'ok':True, 'data':data, 'price_candidate':draft.product.price,
            'warnings':warnings, 'fix_prompt':''}


def apply_import(existing: dict, result: dict, *, mode='replace', confirm_price=False) -> dict:
    if not result.get('ok') or mode not in ('replace','empty'):
        raise ValueError('가져오기 결과와 적용 방식을 확인하세요.')
    if not isinstance(existing,dict) or not isinstance(existing.get('product',{}),dict):
        raise ValueError('기존 상품 입력의 JSON 형식을 확인하세요.')
    current = copy.deepcopy(existing)
    incoming = copy.deepcopy(result['data'])
    incoming['product']['brand_color'] = current.get('product',{}).get('brand_color','#305b46')
    # Imported drafts never supply photos, reviews, references, or an unconfirmed price.
    incoming['images'] = current.get('images',[])
    used = {row['id'] for row in current.get('references',[])}
    remap = {}
    original_ids = {row['id'] for row in incoming['facts']}
    for row in incoming['facts']:
        original = row['id']
        row['id'] = _unique_id(original,used,result['warnings'],original_ids)
        remap[original] = row['id']
    for row in incoming.get('highlights',[]):
        row['fact_id'] = remap.get(row['fact_id'],row['fact_id'])
    incoming['product']['price'] = current.get('product',{}).get('price','')
    if confirm_price and result.get('price_candidate'):
        incoming['product']['price'] = result['price_candidate']
    for key in ('reviews','references','reference_names'):
        if key in current:
            incoming[key] = current[key]
    if mode == 'replace':
        return incoming
    if not any(str(row.get('text','')).strip() for row in current.get('facts',[])):
        current['facts'] = []
    original_highlights = copy.deepcopy(current.get('highlights'))
    for key, value in incoming.items():
        if key == 'product':
            product = current.setdefault('product', {})
            for field, candidate in value.items():
                if not product.get(field):
                    product[field] = candidate
        elif not current.get(key):
            current[key] = value
    # An imported table is only flagged when that table was actually applied.
    if current.get('spec_table') != incoming.get('spec_table'):
        current['spec_from_import'] = existing.get('spec_from_import',False)
        current['spec_verified'] = existing.get('spec_verified',False)
    if not original_highlights:
        retained = {row['id']:row for row in current.get('facts',[])}
        imported = {row['id']:row for row in incoming['facts']}
        highlights = []
        for row in incoming.get('highlights',[]):
            fact_id = row['fact_id']
            if retained.get(fact_id) == imported.get(fact_id) and fact_id in retained:
                highlights.append(row)
            else:
                result['warnings'].append(f"숫자 띠 {row['label']}: 원래 사실을 적용하지 않아 제외했습니다.")
        current['highlights'] = highlights
    return current


def promote_claim(data: dict, index: int, evidence: str) -> dict:
    if not evidence.strip():
        raise ValueError('주장을 사실로 옮기려면 근거를 입력하세요.')
    result = copy.deepcopy(data)
    claim = result['pending_claims'][index]
    used = {fact['id'] for fact in result['facts']} | {ref['id'] for ref in result.get('references',[])}
    fact_id = _unique_id('claim',used,[])
    result['facts'].append({'id':fact_id,'text':claim['text'],'kind':'claim','evidence':evidence})
    result['pending_claims'].pop(index)
    return result


def validate_form_draft(data: dict) -> dict:
    """Validate a saved input draft while allowing unfinished product text."""
    from .facts import ProductFacts
    if not isinstance(data,dict) or not isinstance(data.get('product'),dict):
        raise ValueError('상품 정보 JSON 형식을 확인하세요.')
    validated = copy.deepcopy(data)
    blanks = {}
    for key in ('name','category','price'):
        value = validated['product'].get(key,'')
        if isinstance(value,str) and not value.strip():
            blanks[key] = value
            validated['product'][key] = '입력 대기'
    result = ProductFacts.model_validate(validated).model_dump(exclude_none=True)
    result['product'].update(blanks)
    return result
