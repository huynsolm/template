"""File-based M2 jobs with immutable inputs, bounded attempts and regeneration."""
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from pydantic import ValidationError

from .facts import ProductFacts
from .copy_schema import CopyDraft
from .schema import Document, Model, Text
from .prompting import make_prompt, make_fix_prompt, prompt_version
from .ingest import extract_json
from .assemble import assemble, DEFAULT_TERMS
from .render import render


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path,value):
    path=Path(path)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temporary.replace(path)


def prepare_images(facts: ProductFacts, job: Path, cache_dir: Path | None = None):
    """Shared processing for saved jobs and the input screen's explicit preview."""
    from .images import process_image
    stored=facts.model_copy(deep=True)
    metadata=[]; reviews=[]
    reasons={
        'image_low_resolution':'���� �ػ� ����: �ʺ� 860px �̸��Դϴ�. Ȯ������ �ʾ����Ƿ� �������� Ȯ���ϼ���.',
        'background_suspect':'��� ���� ���� �ǽ�: ���� ������ �ʹ� �۰ų� Ů�ϴ�. ��ǰ ���¸� Ȯ���ϼ���.',
        'background_failed':'��� ���ſ� �����߽��ϴ�. �⺻ ó������ �����߽��ϴ�. ��ġ���𵨡���Ʈ��ũ ���¸� Ȯ���ϼ���.',
    }
    for index,image in enumerate(stored.images):
        result=process_image(Path(job)/image.path,job,image.processing,stored.product.brand_color,cache_dir=cache_dir)
        relative=lambda path:str(Path(path).relative_to(job)) if path else None
        image.derived_path=relative(result.selected_path)
        record={**result.metadata,'source_path':image.path,'normalized_path':relative(result.normalized_path),
                'selected_path':image.derived_path,'mask_preview_path':relative(result.mask_preview_path),
                'file_paths':[relative(result.normalized_path.parent/name) for name in result.metadata['files']]}
        metadata.append(record)
        for item in result.reviews:
            reviews.append({'section_id':'images','field_path':f'images.{index}',
                            'reason':reasons.get(item['reason'],item['reason']),
                            'detail':item.get('message',''),'fact_ids':[]})
    return stored,metadata,reviews


def create_job(facts: ProductFacts, images: Path, output: Path, max_attempts=5, method='paste', locked=None, locked_review=None, theme="classic"):
    if type(max_attempts) is not int or max_attempts<1:
        raise ValueError('max_attempts must be a positive integer')
    from .themes import theme_styles, contrast_metadata
    styles=theme_styles(theme,facts.product.brand_color)
    paths=facts.validate_images(images)
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    job=Path(tempfile.mkdtemp(prefix='job-',dir=output))
    try:
        (job/'images').mkdir(); (job/'attempts').mkdir()
        mapping={}
        for i,(name,path) in enumerate(paths.items()):
            target=f'images/image-{i:03}{path.suffix.lower()}'
            shutil.copyfile(path,job/target); mapping[name]=target
        snapshot=facts.model_dump(exclude_none=True)
        for image in snapshot['images']:
            image['path']=mapping[image['path']]
            image.pop('derived_path',None)
        stored=ProductFacts.model_validate(snapshot)
        stored,image_metadata,image_reviews=prepare_images(stored,job,output/'.image-cache')
        snapshot=stored.model_dump(exclude_none=True)
        write_json(job/'facts.json',snapshot)
        write_json(job/'locked.json',locked or {})
        write_json(job/'edits.json',{'locked_sections':list(locked or {})})
        write_json(job/'locked-review.json',locked_review or [])
        (job/'prompt.md').write_text(make_prompt(stored,locked),encoding='utf-8')
        write_json(job/'manifest.json',{'theme':theme,**contrast_metadata(styles),'prompt_version':prompt_version(stored),'method':method,'source_label':'','attempts':0,'max_attempts':max_attempts,'created_at':now(),'updated_at':now(),'status':'awaiting_answer','image_processing':image_metadata,'image_reviews':image_reviews})
        return job
    except BaseException:
        shutil.rmtree(job)
        raise


def validation_errors(exc):
    if isinstance(exc,ValidationError):
        return [{'field_path':'.'.join(map(str,e['loc'])),'reason':e['msg'],'type':e['type'],'allowed_range':str(e.get('ctx',{}))} for e in exc.errors(include_url=False)]
    return [{'field_path':'answer','reason':str(exc),'allowed_range':'one JSON object conforming to prompt JSON Schema'}]


def ingest_job(job: Path, answer: str, source_label='', render_output=False, terms=None, accept_review=False, theme=None):
    job=Path(job)
    manifest=read_json(job/'manifest.json')
    from .themes import load_theme, theme_styles, contrast_metadata
    theme=theme if theme is not None else manifest.get('theme','classic')
    load_theme(theme)
    if (job/'draft.json').exists():
        raise ValueError('job already succeeded; use accept --job to approve or prompt --from-job --regenerate for new copy')
    if manifest['attempts']>=manifest['max_attempts']:
        raise ValueError('attempt limit reached; create a new job')
    facts=ProductFacts.model_validate(read_json(job/'facts.json'))
    styles=theme_styles(theme,facts.product.brand_color)
    terms=tuple(manifest.get('review_terms',DEFAULT_TERMS)) if terms is None else tuple(terms)
    attempt=manifest['attempts']+1
    (job/'attempts'/f'answer-{attempt}.txt').write_text(answer,encoding='utf-8')
    manifest.update(contrast_metadata(styles))
    manifest.update(theme=theme,attempts=attempt,source_label=source_label,updated_at=now(),status='validating',review_terms=list(terms))
    write_json(job/'manifest.json',manifest)
    parsed=answer
    stage=job/'.assembled'
    try:
        parsed=extract_json(answer)
        copy=CopyDraft.model_validate(parsed)
        document,review=assemble(facts,copy,locked=read_json(job/'locked.json'),terms=terms)
        review+=read_json(job/'locked-review.json')
        review+=manifest.get('image_reviews',[])
        # Verify all paths including preserved manual sections before publishing success files.
        from .collect import collect_images
        collect_images(document,job)
        stage.mkdir()
        write_json(stage/'draft.json',document.model_dump(exclude_none=True))
        write_json(stage/'copy.json',parsed)
        review+=styles['contrast_reviews']
        write_json(stage/'review.json',review)
        manifest.update(contrast_metadata(styles))
        needs_review=bool(review)
        if render_output:
            if needs_review:
                print('\n'+'!'*72+'\nWARNING: �˼� �ʿ� ? '+str(len(review))+'�� �׸�. '+str(job/'review.json')+' Ȯ�� �ʼ�.\n'+('������ --accept-review �������� �Ϲ� ���ϸ��� ����մϴ�.' if accept_review else '�̽��� �ʾ�: .DRAFT ���ϸ����� �����մϴ�. �˼� �� cli.py accept --job '+str(job)+' �� �����ϼ���.')+'\n'+'!'*72+'\n',file=sys.stderr)
            render(document,job,stage/'rendered',png=True,needs_review=needs_review,accept_review=accept_review,theme=theme)
        for path in stage.iterdir(): path.replace(job/path.name)
        stage.rmdir()
        write_json(job/'attempts'/f'errors-{attempt}.json',[])
        manifest.update(status='complete',updated_at=now(),needs_review=needs_review,review_accepted=bool(accept_review))
        write_json(job/'manifest.json',manifest)
        return job
    except (ValueError,OSError) as exc:
        if stage.exists(): shutil.rmtree(stage)
        errors=validation_errors(exc)
        write_json(job/'attempts'/f'errors-{attempt}.json',errors)
        (job/'fix-prompt.md').write_text(make_fix_prompt((job/'prompt.md').read_text(),parsed,errors),encoding='utf-8')
        manifest.update(status='needs_correction',updated_at=now())
        write_json(job/'manifest.json',manifest)
        raise ValueError('; '.join(e['field_path']+': '+e['reason'] for e in errors)) from exc


def accept_job(source: Path, theme=None):
    """Validate the current manual draft and publish an independent accepted job."""
    from .collect import collect_images
    source=Path(source).resolve(strict=True)
    draft_bytes=(source/'draft.json').read_bytes()
    document=Document.model_validate_json(draft_bytes)
    images=collect_images(document,source)
    from .editor import reassess_draft, provenance_path, snapshot_bundle
    review=reassess_draft(source,document)
    seller=ProductFacts.model_validate(read_json(provenance_path(source,'facts.json')))
    images.update(seller.validate_images(source))
    original_manifest=read_json(source/'manifest.json')
    from .themes import theme_styles, contrast_metadata
    theme=theme if theme is not None else original_manifest.get('theme','classic')
    styles=theme_styles(theme,document.product.brand_color)
    review=[item for item in review if item.get('section_id')!='theme']+styles['contrast_reviews']
    if not isinstance(review,list) or not all(isinstance(item,dict) for item in review):
        raise ValueError('review.json must be an array of review items')
    if not isinstance(original_manifest,dict):
        raise ValueError('manifest.json must be an object')
    staging=Path(tempfile.mkdtemp(prefix='.pending-accept-',dir=source.parent))
    try:
        for name,path in images.items():
            destination=staging/name
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(path,destination)
        (staging/'draft.json').write_bytes(draft_bytes)
        write_json(staging/'review.json',review)
        for name in ('facts.json','copy.json'):
            shutil.copyfile(provenance_path(source,name),staging/name)
        for record in original_manifest.get('image_processing',[]):
            for name in record.get('file_paths',[]):
                from .images import validate_source
                path=source/name
                if not path.resolve().is_relative_to(source): raise ValueError('derived path outside source job')
                validate_source(path)
                destination=staging/name;destination.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(path,destination)
        for name in ('edits.json','locked-evidence.json','edited-evidence.json'):
            if (source/name).is_file():
                shutil.copyfile(source/name,staging/name)
        rendered=render(document,staging,staging/'rendered',png=True,
                        needs_review=bool(review),accept_review=True,theme=theme)
        snapshot_bundle(rendered,draft_bytes,review)
        accepted_at=now()
        rendered_manifest=read_json(rendered/'manifest.json')
        rendered_manifest.update(source_job=str(source),accepted_at=accepted_at)
        write_json(rendered/'manifest.json',rendered_manifest)
        write_json(staging/'manifest.json',{
            'theme':theme,
            **contrast_metadata(rendered_manifest),
            'image_processing':original_manifest.get('image_processing',[]),
            'image_reviews':original_manifest.get('image_reviews',[]),
            'method':'accept','attempts':0,'max_attempts':original_manifest.get('max_attempts',5),
            'review_terms':original_manifest.get('review_terms',list(DEFAULT_TERMS)),
            'prompt_version':original_manifest.get('prompt_version'),
            'source_label':original_manifest.get('source_label',''),
            'source_job':str(source),
            'created_at':accepted_at,'accepted_at':accepted_at,
            'status':'complete','needs_review':bool(review),'review_accepted':True,
            'rendered_job':str(rendered.relative_to(staging)),
        })
        final=staging.with_name('job-'+staging.name.removeprefix('.pending-accept-'))
        if final.exists():
            raise ValueError('accepted job destination already exists')
        staging.rename(final)
        return final
    except BaseException:
        shutil.rmtree(staging)
        raise


class Edits(Model):
    locked_sections: list[Text]


def regenerate_job(previous: Path):
    previous=Path(previous)
    document=Document.model_validate(read_json(previous/'draft.json'))
    edits=Edits.model_validate(read_json(previous/'edits.json')) if (previous/'edits.json').exists() else Edits(locked_sections=[])
    by_id={section.id:section.model_dump(exclude_none=True) for section in document.sections}
    unknown=set(edits.locked_sections)-by_id.keys()
    if unknown: raise ValueError('unknown locked section IDs: '+', '.join(sorted(unknown)))
    locked={sid:by_id[sid] for sid in edits.locked_sections}
    review=[i for i in read_json(previous/'review.json') if i['section_id'] in locked]
    facts=ProductFacts.model_validate(read_json(previous/'facts.json'))
    from .collect import collect_images
    locked_assets={}
    if locked:
        sections=list(locked.values())
        if not any(s['type']=='hero' for s in sections):
            sections.append(next(s.model_dump(exclude_none=True) for s in document.sections if s.type=='hero'))
        checked=Document.model_validate({'schema_version':'1.0','product':facts.product.model_dump(),'sections':sections})
        locked_assets=collect_images(checked,previous)
    child=create_job(facts,previous,previous.parent,max_attempts=read_json(previous/'manifest.json').get('max_attempts',5),locked=locked,locked_review=review,theme=read_json(previous/'manifest.json').get('theme','classic'))
    try:
        child_manifest=read_json(child/'manifest.json')
        child_manifest['review_terms']=read_json(previous/'manifest.json').get('review_terms',list(DEFAULT_TERMS))
        write_json(child/'manifest.json',child_manifest)
        if (previous/'edited-evidence.json').exists():
            edited_refs=read_json(previous/'edited-evidence.json')
            write_json(child/'edited-evidence.json',{sid:refs for sid,refs in edited_refs.items() if sid in locked})
        original=read_json(previous/'copy.json')
        preserved=read_json(previous/'locked-evidence.json') if (previous/'locked-evidence.json').exists() else {}
        write_json(child/'locked-evidence.json',{sid:preserved.get(sid,original.get(section['type'],{}) if sid==section['type']+'-1' else {}) for sid,section in locked.items()})
        for name,source in locked_assets.items():
            destination=child/name
            destination.parent.mkdir(parents=True,exist_ok=True)
            if destination.exists() and destination.read_bytes()!=source.read_bytes():
                raise ValueError('locked image path collides with snapshot image: '+name)
            shutil.copyfile(source,destination)
        return child
    except BaseException:
        shutil.rmtree(child)
        raise


def generate_job(facts, images, output, provider, max_attempts=3, source_label='', render_output=False, terms=None, accept_review=False, existing_job: Path | None = None, theme=None):
    if type(max_attempts) is not int or max_attempts<1:
        raise ValueError('max_attempts must be a positive integer')
    if existing_job is None:
        job=create_job(facts,images,output,max_attempts=max_attempts,method=f'cli:{provider.name}',theme=theme if theme is not None else 'classic')
    else:
        job=Path(existing_job)
        if (job/'draft.json').exists():
            raise ValueError('job already succeeded; regenerate a new prompt job')
        manifest=read_json(job/'manifest.json')
        cap=min(max_attempts,manifest['max_attempts'])
        if manifest['attempts']>=cap:
            raise ValueError('attempt limit reached; create a new job')
        manifest.update(method=f'cli:{provider.name}',source_label=source_label,max_attempts=cap,updated_at=now())
        write_json(job/'manifest.json',manifest)
    manifest=read_json(job/'manifest.json')
    for attempt in range(manifest['attempts'],manifest['max_attempts']):
        prompt=(job/('prompt.md' if attempt==0 else 'fix-prompt.md')).read_text(encoding='utf-8')
        answer=provider.generate(prompt)
        try:
            return ingest_job(job,answer,source_label=source_label,render_output=render_output,terms=terms,accept_review=accept_review,theme=theme)
        except ValueError:
            if attempt+1==manifest['max_attempts']: raise
    return job


