"""Shared manual editing, read-only review and versioned export operations."""
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


def reassess_draft(job: Path, document: Document | None = None) -> list[dict]:
    """Inspect current text with original evidence references, without writing files."""
    job=Path(job)
    document=document or Document.model_validate(read_json(job/'draft.json'))
    facts=_seller_check(job,document)
    original=read_json(provenance_path(job,'copy.json'))
    preserved=read_json(job/'locked-evidence.json') if (job/'locked-evidence.json').exists() else {}
    terms=read_json(job/'manifest.json').get('review_terms',DEFAULT_TERMS)
    fact_map={f.id:f for f in facts.facts}
    review=[]
    def check(section, path, text, unit):
        ids=unit.get('fact_ids',[]) if isinstance(unit,dict) else []
        def flag(reason):
            review.append({'section_id':section.id,'field_path':path,'reason':reason,'fact_ids':list(ids)})
        missing=[i for i in ids if i not in fact_map]
        if missing: flag('존재하지 않는 fact_ids: '+', '.join(missing))
        if not ids: flag('근거 fact_ids가 비어 있음')
        if (re.search(r'\d|[%％]',text) or any(term in text for term in terms)) and not any(fact_map[i].kind in ('claim','spec') for i in ids if i in fact_map):
            flag('수치·인증·효능 표현에 claim/spec 근거 확인 필요')
    for section in document.sections:
        kind=section.type
        # An added section has no known original evidence, even of the same type.
        origin=preserved.get(section.id,original.get(kind,{}) if section.id==kind+'-1' else {})
        if kind=='hero': check(section,'hero',' '.join(filter(None,[section.headline,section.subcopy])),origin)
        elif kind=='solution': check(section,'solution',section.title+' '+section.body,origin)
        elif kind=='pain':
            check(section,'pain.title',section.title,origin)
            refs=origin.get('items',[]) if isinstance(origin,dict) else []
            for n,item in enumerate(section.items): check(section,f'pain.items.{n}.text',item,refs[n] if n<len(refs) else {})
        elif kind in ('features','how_to','faq'):
            units=section.steps if kind=='how_to' else section.items
            refs=origin if isinstance(origin,list) else []
            for n,item in enumerate(units):
                text=' '.join(v for k,v in item.model_dump().items() if isinstance(v,str) and k!='image')
                check(section,f'{kind}.{n}',text,refs[n] if n<len(refs) else {})
    return review


def save_draft(job: Path, data: dict, locked_sections: list[str]) -> None:
    job=Path(job)
    document=Document.model_validate(data)
    if not isinstance(locked_sections,list) or any(not isinstance(s,str) for s in locked_sections):
        raise ValueError('locked_sections must be a list of section IDs')
    if len(set(locked_sections))!=len(locked_sections) or set(locked_sections)-{s.id for s in document.sections}:
        raise ValueError('unknown or duplicate locked section IDs')
    review=reassess_draft(job,document)
    from .collect import collect_images
    collect_images(document,job)
    history=read_json(job/'history.json') if (job/'history.json').exists() else []
    normalized=document.model_dump(exclude_none=True)
    history.append({'saved_at':now(),'previous_draft':read_json(job/'draft.json'),'draft':normalized,'locked_sections':locked_sections,'review':review})
    write_json(job/'history.json',history)
    write_json(job/'draft.json',normalized)
    write_json(job/'edits.json',{'locked_sections':locked_sections})
    write_json(job/'review.json',review)
    manifest=read_json(job/'manifest.json')
    manifest.update(updated_at=now(),needs_review=bool(review),review_accepted=False)
    write_json(job/'manifest.json',manifest)
    if (job/'preview.json').exists(): (job/'preview.json').unlink()


def snapshot_bundle(bundle: Path, draft_bytes: bytes, review: list[dict]) -> None:
    """Attach the exact rendered source version to a completed render directory."""
    (bundle/'draft.json').write_bytes(draft_bytes)
    write_json(bundle/'review.json',review)
    manifest=read_json(bundle/'manifest.json')
    manifest.update(job_id=bundle.name,draft_sha256=hashlib.sha256(draft_bytes).hexdigest())
    write_json(bundle/'manifest.json',manifest)


def preview_job(job: Path) -> Path:
    from .render import render
    job=Path(job)
    draft_bytes=(job/'draft.json').read_bytes()
    document=Document.model_validate_json(draft_bytes)
    review=reassess_draft(job,document)
    bundle=render(document,job,job/'rendered',png=True,needs_review=bool(review),force_draft=True)
    snapshot_bundle(bundle,draft_bytes,review)
    write_json(job/'preview.json',{'bundle':str(bundle.relative_to(job))})
    return bundle


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
