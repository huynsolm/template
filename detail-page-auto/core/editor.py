"""Shared manual editing, read-only review and versioned export operations."""
import copy
import hashlib
import io
import json
import re
from pathlib import Path
import zipfile

from .assemble import DEFAULT_TERMS
from .facts import ProductFacts
from .schema import Document
from .workflow import now, read_json, write_json
from .themes import theme_styles, contrast_metadata, load_theme


def provenance_path(job: Path, name: str) -> Path:
    """Prefer local snapshots; support older accepted jobs with source pointers."""
    current=Path(job).resolve()
    seen=set()
    while current not in seen:
        seen.add(current)
        candidate=current/name
        if candidate.is_file():
            return candidate
        manifest=read_json(current/'manifest.json')
        source=manifest.get('source_job')
        if not source:
            break
        current=Path(source).resolve()
    raise ValueError('missing original snapshot: '+name)


def _seller_check(job, document):
    facts=ProductFacts.model_validate(read_json(provenance_path(job,'facts.json')))
    if document.product!=facts.product:
        raise ValueError('product: seller-owned fields must match facts.json')
    actual={kind:[s.model_dump(exclude_none=True) for s in document.sections if s.type==kind] for kind in ('review','spec','notice')}
    expected={'review':[], 'spec':[], 'notice':[]}
    if facts.reviews:
        expected['review']=[{'id':'review-1','type':'review','items':[r.model_dump() for r in facts.reviews]}]
    rows=[[f.id,f.text] for f in facts.facts if f.kind=='spec']
    if rows:
        expected['spec']=[{'id':'spec-1','type':'spec','rows':rows}]
    if facts.notice:
        expected['notice']=[{'id':'notice-1','type':'notice','body':facts.notice}]
    for kind in expected:
        if actual[kind]!=expected[kind]:
            raise ValueError(kind+': seller-owned section must match facts.json')
    return facts


def _copy_units(document):
    """Yield section, review path, text for each editable evidence unit."""
    for section in document.sections:
        kind=section.type
        if kind=='hero':
            yield section,'hero',' '.join(filter(None,[section.headline,section.subcopy]))
        elif kind=='solution':
            yield section,'solution',section.title+' '+section.body
        elif kind=='pain':
            yield section,'pain.title',section.title
            for n,item in enumerate(section.items):
                yield section,f'pain.items.{n}.text',item
        elif kind in ('features','how_to','faq'):
            for n,item in enumerate(section.steps if kind=='how_to' else section.items):
                text=' '.join(v for k,v in item.model_dump().items() if isinstance(v,str) and k!='image')
                yield section,f'{kind}.{n}',text


def _edited_evidence(job):
    path=Path(job)/'edited-evidence.json'
    return read_json(path) if path.exists() else {}


def evidence_units(job: Path, document_data=None) -> list[dict]:
    """Current evidence selections; canonical keys also disambiguate repeated types."""
    job=Path(job)
    document=Document.model_validate(document_data if document_data is not None else read_json(job/'draft.json'))
    original=read_json(provenance_path(job,'copy.json'))
    preserved=read_json(job/'locked-evidence.json') if (job/'locked-evidence.json').exists() else {}
    edited=_edited_evidence(job)
    result=[]
    for section,path,_ in _copy_units(document):
        kind=section.type
        origin=preserved.get(section.id,original.get(kind,{}) if section.id==kind+'-1' else {})
        if path.startswith('pain.items.'):
            refs=origin.get('items',[]) if isinstance(origin,dict) else []
            n=int(path.split('.')[2]); unit=refs[n] if n<len(refs) else {}
        elif kind in ('features','how_to','faq'):
            n=int(path.split('.')[1]); unit=origin[n] if isinstance(origin,list) and n<len(origin) else {}
        else:
            unit=origin
        ids=unit.get('fact_ids',[]) if isinstance(unit,dict) else []
        ids=edited.get(section.id,{}).get(path,ids)
        result.append({'section_id':section.id,'path':path,'fact_ids':list(ids),'key':section.id+':'+path})
    return result


def change_copy_items(data: dict, section_id: str, action: str, index=None, evidence=None) -> dict:
    """Mutate a copy, validate M1 bounds, and remap all supplied evidence in core."""
    updated=Document.model_validate(data).model_dump(exclude_none=True)
    section=next((s for s in updated['sections'] if s['id']==section_id),None)
    if section is None or section['type'] not in ('pain','features','how_to','faq'):
        raise ValueError('only pain/features/how_to/faq items can be changed')
    kind=section['type']; items=section['steps' if kind=='how_to' else 'items']
    old_indices=list(range(len(items)))
    if action=='add':
        if index is not None: raise ValueError('add appends an item; index must be omitted')
        new='새 문구' if kind=='pain' else ({'q':'새 질문','a':'새 답변'} if kind=='faq' else {'title':'새 제목','desc':'새 설명'})
        items.append(new); old_indices.append(None)
    elif action=='remove':
        if type(index) is not int or index<0 or index>=len(items): raise ValueError('invalid item index')
        items.pop(index); old_indices.pop(index)
    else:
        raise ValueError('action must be add or remove')
    normalized=Document.model_validate(updated).model_dump(exclude_none=True)
    def path(n):
        return f'pain.items.{n}.text' if kind=='pain' else f'{kind}.{n}'
    mapping={path(n):path(old) if old is not None else None for n,old in enumerate(old_indices)}
    if kind=='pain': mapping['pain.title']='pain.title'
    remapped=copy.deepcopy(evidence) if evidence is not None else {}
    if not isinstance(remapped,dict): raise ValueError('evidence must be an object')
    prefix=section_id+':'
    source=copy.deepcopy(remapped)
    for key in list(remapped):
        if key.startswith(prefix): del remapped[key]
    for new_path,old_path in mapping.items():
        remapped[prefix+new_path]=list(source.get(prefix+old_path,[])) if old_path is not None else []
    return {'data':normalized,'path_map':mapping,'evidence':remapped}


def reassess_draft(job: Path, document: Document | None = None, evidence=None) -> list[dict]:
    """Inspect current text using immutable origins and persisted manual selections."""
    job=Path(job)
    document=document or Document.model_validate(read_json(job/'draft.json'))
    facts=_seller_check(job,document)
    terms=read_json(job/'manifest.json').get('review_terms',DEFAULT_TERMS)
    fact_map={f.id:f for f in facts.facts}
    units={u['key']:u['fact_ids'] for u in evidence_units(job,document.model_dump(exclude_none=True))}
    if evidence is not None:
        units.update({sid+':'+path:ids for sid,paths in evidence.items() for path,ids in paths.items()})
    review=[]
    for section,path,text in _copy_units(document):
        ids=units[section.id+':'+path]
        def flag(reason):
            review.append({'section_id':section.id,'field_path':path,'reason':reason,'fact_ids':list(ids)})
        missing=[i for i in ids if i not in fact_map]
        if missing: flag('존재하지 않는 fact_ids: '+', '.join(missing))
        if not ids: flag('근거 fact_ids가 비어 있음')
        if (re.search(r'\d|[%％]',text) or any(term in text for term in terms)) and not any(fact_map[i].kind in ('claim','spec') for i in ids if i in fact_map):
            flag('수치·인증·효능 표현에 claim/spec 근거 확인 필요')
    manifest=read_json(job/'manifest.json')
    styles=theme_styles(manifest.get('theme','classic'),document.product.brand_color)
    return review+manifest.get('image_reviews',[])+styles['contrast_reviews']


def save_draft(job: Path, data: dict, locked_sections: list[str], evidence=None) -> None:
    job=Path(job)
    document=Document.model_validate(data)
    facts=_seller_check(job,document)
    if not isinstance(locked_sections,list) or any(not isinstance(s,str) for s in locked_sections):
        raise ValueError('locked_sections must be a list of section IDs')
    if len(set(locked_sections))!=len(locked_sections) or set(locked_sections)-{s.id for s in document.sections}:
        raise ValueError('unknown or duplicate locked section IDs')
    previous=read_json(job/'draft.json')
    previous_evidence=_edited_evidence(job)
    units=evidence_units(job,data)
    valid={u['key']:u for u in units}
    selected={sid:{path:list(ids) for path,ids in paths.items() if sid+':'+path in valid} for sid,paths in previous_evidence.items()}
    # A list length change without explicit remapping must never attach the old
    # position's evidence to a shifted item. Keep only the unchanged prefix.
    old_sections={s['id']:s for s in previous['sections']}
    for section in document.model_dump(exclude_none=True)['sections']:
        kind=section['type']
        if kind not in ('pain','features','how_to','faq'): continue
        field='steps' if kind=='how_to' else 'items'
        old=old_sections.get(section['id'],{}).get(field,[]); new=section[field]
        if len(old)==len(new): continue
        prefix=0
        while prefix<min(len(old),len(new)) and old[prefix]==new[prefix]: prefix+=1
        for n in range(prefix,len(new)):
            path=f'pain.items.{n}.text' if kind=='pain' else f'{kind}.{n}'
            selected.setdefault(section['id'],{})[path]=[]
    if evidence is not None:
        if not isinstance(evidence,dict): raise ValueError('evidence must be an object')
        fact_ids={f.id for f in facts.facts}
        for key,ids in evidence.items():
            candidates=[u for u in units if key in (u['key'],u['path'])]
            if len(candidates)!=1: raise ValueError('unknown or ambiguous evidence path: '+str(key))
            if not isinstance(ids,list) or any(not isinstance(i,str) or i not in fact_ids for i in ids) or len(set(ids))!=len(ids):
                raise ValueError('fact_ids must be unique existing fact IDs')
            unit=candidates[0]
            selected.setdefault(unit['section_id'],{})[unit['path']]=list(ids)
    selected={sid:paths for sid,paths in selected.items() if paths}
    review=reassess_draft(job,document,evidence=selected)
    from .collect import collect_images
    collect_images(document,job)
    history=read_json(job/'history.json') if (job/'history.json').exists() else []
    normalized=document.model_dump(exclude_none=True)
    history.append({'saved_at':now(),'previous_draft':previous,'draft':normalized,'locked_sections':locked_sections,'review':review,'previous_evidence':previous_evidence,'evidence':selected})
    write_json(job/'history.json',history)
    write_json(job/'draft.json',normalized)
    write_json(job/'edited-evidence.json',selected)
    write_json(job/'edits.json',{'locked_sections':locked_sections})
    write_json(job/'review.json',review)
    manifest=read_json(job/'manifest.json')
    manifest.update(contrast_metadata(theme_styles(manifest.get('theme','classic'),document.product.brand_color)))
    manifest.update(updated_at=now(),needs_review=bool(review),review_accepted=False)
    write_json(job/'manifest.json',manifest)
    if (job/'preview.json').exists(): (job/'preview.json').unlink()


def snapshot_bundle(bundle: Path, draft_bytes: bytes, review: list[dict]) -> None:
    """Attach the exact rendered source version to a completed render directory."""
    (bundle/'draft.json').write_bytes(draft_bytes)
    write_json(bundle/'review.json',review)
    manifest=read_json(bundle/'manifest.json')
    manifest.update(job_id=bundle.name,draft_sha256=hashlib.sha256(draft_bytes).hexdigest(),needs_review=bool(review))
    write_json(bundle/'manifest.json',manifest)


def preview_job(job: Path, theme=None) -> Path:
    from .render import render
    job=Path(job)
    draft_bytes=(job/'draft.json').read_bytes()
    document=Document.model_validate_json(draft_bytes)
    review=[item for item in reassess_draft(job,document) if item.get('section_id')!='theme']
    manifest=read_json(job/'manifest.json')
    theme=theme if theme is not None else manifest.get('theme','classic')
    bundle=render(document,job,job/'rendered',png=True,needs_review=bool(review),force_draft=True,theme=theme)
    rendered=read_json(bundle/'manifest.json')
    review=[item for item in review if item.get('section_id')!='theme']+rendered['contrast_reviews']
    snapshot_bundle(bundle,draft_bytes,review)
    if manifest.get('theme','classic')!=theme or manifest.get('contrast_policy')!=rendered['contrast_policy']:
        manifest.update(review_accepted=False)
        manifest.pop('rendered_job',None)
    manifest.update(contrast_metadata(rendered))
    manifest.update(theme=theme,needs_review=bool(review))
    write_json(job/'review.json',review)
    write_json(job/'manifest.json',manifest)
    write_json(job/'preview.json',{'bundle':str(bundle.relative_to(job))})
    return bundle


def bundle_matches(job: Path, bundle: Path) -> bool:
    """A mutable job may use a snapshot only for its current text and theme."""
    try:
        job=Path(job); bundle=Path(bundle)
        current=read_json(job/'manifest.json')
        snapshot=read_json(bundle/'manifest.json')
        digest=hashlib.sha256((job/'draft.json').read_bytes()).hexdigest()
        return (snapshot.get('draft_sha256')==digest
                and snapshot.get('theme','classic')==current.get('theme','classic')
                and snapshot.get('contrast_policy')==load_theme(current.get('theme','classic')).contrast_policy)
    except (OSError,ValueError):
        return False


def build_zip(bundle: Path) -> bytes:
    """Package only this render's immutable files, never the mutable parent job."""
    bundle=Path(bundle).resolve(strict=True)
    manifest=read_json(bundle/'manifest.json')
    draft=(bundle/'draft.json').read_bytes()
    if manifest.get('job_id')!=bundle.name or manifest.get('draft_sha256')!=hashlib.sha256(draft).hexdigest():
        raise ValueError('render bundle version does not match manifest')
    names={'page.html','draft.json','manifest.json','review.json'}
    for page in manifest['pages']:
        names.add(page['file'])
        if page.get('png'): names.add(page['png'])
    names.update(str(p.relative_to(bundle)) for p in (bundle/'assets').rglob('*') if p.is_file())
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(names):
            path=bundle/name
            if path.is_symlink() or not path.resolve().is_relative_to(bundle) or any(p.is_symlink() for p in path.parents if p!=bundle.parent):
                raise ValueError('unsafe bundle file: '+name)
            archive.writestr(name,path.read_bytes())
    return output.getvalue()


def job_listing(output: Path) -> list[dict]:
    rows=[]
    for job in Path(output).glob('job-*'):
        if not job.is_dir() or job.is_symlink(): continue
        try:
            manifest=read_json(job/'manifest.json')
            facts=read_json(provenance_path(job,'facts.json'))
            rows.append({'path':str(job),'product_name':facts['product']['name'],'created_at':manifest.get('created_at',''),'status':manifest.get('status','unknown')})
        except (OSError,ValueError,KeyError,TypeError):
            continue
    return sorted(rows,key=lambda row:row['created_at'],reverse=True)
