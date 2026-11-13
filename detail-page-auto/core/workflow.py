"""File-based M2 jobs with immutable inputs, bounded attempts and regeneration."""
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from pydantic import ValidationError

from .facts import ProductFacts
from .copy_schema import CopyDraft
from .schema import Document, Model, Text
from .prompting import make_prompt, make_fix_prompt, VERSION
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


def create_job(facts: ProductFacts, images: Path, output: Path, max_attempts=5, method='paste', locked=None, locked_review=None):
    if type(max_attempts) is not int or max_attempts<1:
        raise ValueError('max_attempts must be a positive integer')
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
        for image in snapshot['images']: image['path']=mapping[image['path']]
        stored=ProductFacts.model_validate(snapshot)
        write_json(job/'facts.json',snapshot)
        write_json(job/'locked.json',locked or {})
        write_json(job/'edits.json',{'locked_sections':list(locked or {})})
        write_json(job/'locked-review.json',locked_review or [])
        (job/'prompt.md').write_text(make_prompt(stored,locked),encoding='utf-8')
        write_json(job/'manifest.json',{'prompt_version':VERSION,'method':method,'source_label':'','attempts':0,'max_attempts':max_attempts,'created_at':now(),'updated_at':now(),'status':'awaiting_answer'})
        return job
    except BaseException:
        shutil.rmtree(job)
        raise


def validation_errors(exc):
    if isinstance(exc,ValidationError):
        return [{'field_path':'.'.join(map(str,e['loc'])),'reason':e['msg'],'type':e['type'],'allowed_range':str(e.get('ctx',{}))} for e in exc.errors(include_url=False)]
    return [{'field_path':'answer','reason':str(exc),'allowed_range':'one JSON object conforming to prompt JSON Schema'}]


def ingest_job(job: Path, answer: str, source_label='', render_output=False, terms=DEFAULT_TERMS):
    job=Path(job)
    manifest=read_json(job/'manifest.json')
    if (job/'draft.json').exists():
        raise ValueError('job already succeeded; use prompt --from-job --regenerate for a new job')
    if manifest['attempts']>=manifest['max_attempts']:
        raise ValueError('attempt limit reached; create a new job')
    attempt=manifest['attempts']+1
    (job/'attempts'/f'answer-{attempt}.txt').write_text(answer,encoding='utf-8')
    manifest.update(attempts=attempt,source_label=source_label,updated_at=now(),status='validating')
    write_json(job/'manifest.json',manifest)
    parsed=answer
    stage=job/'.assembled'
    try:
        parsed=extract_json(answer)
        copy=CopyDraft.model_validate(parsed)
        facts=ProductFacts.model_validate(read_json(job/'facts.json'))
        document,review=assemble(facts,copy,locked=read_json(job/'locked.json'),terms=terms)
        review+=read_json(job/'locked-review.json')
        # Verify all paths including preserved manual sections before publishing success files.
        from .collect import collect_images
        collect_images(document,job)
        stage.mkdir()
        write_json(stage/'draft.json',document.model_dump(exclude_none=True))
        write_json(stage/'review.json',review)
        write_json(stage/'copy.json',parsed)
        if render_output:
            render(document,job,stage/'rendered',png=True)
        for path in stage.iterdir(): path.replace(job/path.name)
        stage.rmdir()
        write_json(job/'attempts'/f'errors-{attempt}.json',[])
        manifest.update(status='complete',updated_at=now())
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
    child=create_job(facts,previous,previous.parent,max_attempts=read_json(previous/'manifest.json')['max_attempts'],locked=locked,locked_review=review)
    try:
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


def generate_job(facts, images, output, provider, max_attempts=3, source_label='', render_output=False, terms=DEFAULT_TERMS):
    job=create_job(facts,images,output,max_attempts=max_attempts,method=f'cli:{provider.name}')
    for attempt in range(max_attempts):
        prompt=(job/('prompt.md' if attempt==0 else 'fix-prompt.md')).read_text(encoding='utf-8')
        answer=provider.generate(prompt)
        try:
            return ingest_job(job,answer,source_label=source_label,render_output=render_output,terms=terms)
        except ValueError:
            if attempt+1==max_attempts: raise
    return job
