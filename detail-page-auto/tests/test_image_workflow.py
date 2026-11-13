import json
from pathlib import Path
import sys
import hashlib
import subprocess
import pytest
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.facts import ProductFacts
from core.workflow import create_job,ingest_job


class FakeRemover:
    cache_key='fake-workflow-v1'
    def remove(self,image):
        image=image.convert('RGBA');alpha=Image.new('L',image.size,0)
        ImageDraw.Draw(alpha).rectangle((image.width//4,image.height//4,image.width*3//4,image.height*3//4),fill=255)
        image.putalpha(alpha);return image


def test_job_uses_derived_and_keeps_original(tmp_path):
    facts=ProductFacts.model_validate_json((ROOT/'samples/facts.json').read_text())
    original=ROOT/'samples'/facts.images[0].path;before=original.read_bytes()
    job=create_job(facts,ROOT/'samples',tmp_path)
    snapshot=json.loads((job/'facts.json').read_text())
    selected=snapshot['images'][0]['derived_path']
    assert selected.startswith('images/derived/') and selected!=snapshot['images'][0]['path']
    assert original.read_bytes()==before==(job/snapshot['images'][0]['path']).read_bytes()
    manifest=json.loads((job/'manifest.json').read_text())
    assert manifest['image_processing'][0]['source_sha256']==hashlib.sha256(before).hexdigest()
    ingest_job(job,(ROOT/'samples/answer.txt').read_text())
    assert json.loads((job/'draft.json').read_text())['sections'][0]['image']==selected


def test_fake_bg_workflow_renders(tmp_path,monkeypatch):
    import core.images
    monkeypatch.setattr(core.images,'get_remover',lambda:FakeRemover())
    facts=ProductFacts.model_validate_json((ROOT/'samples/facts.json').read_text())
    facts.images[0].processing.remove_background=True
    job=create_job(facts,ROOT/'samples',tmp_path)
    ingest_job(job,(ROOT/'samples/answer.txt').read_text(),render_output=True)
    assert list((job/'rendered').glob('job-*/page-001.jpg'))
    manifest=json.loads((job/'manifest.json').read_text())
    assert manifest['image_processing'][0]['background_removed']


def test_image_warnings_survive_reassessment(tmp_path):
    from core.editor import reassess_draft
    image=tmp_path/'small.png';Image.new('RGB',(20,10),'red').save(image)
    facts=ProductFacts.model_validate_json((ROOT/'samples/facts.json').read_text())
    facts.images[0].path='small.png'
    job=create_job(facts,tmp_path,tmp_path/'jobs')
    ingest_job(job,(ROOT/'samples/answer.txt').read_text())
    assert any(i['section_id']=='images' for i in json.loads((job/'review.json').read_text()))
    assert any(i['section_id']=='images' for i in reassess_draft(job))


def test_cli_images_only(tmp_path):
    r=subprocess.run([sys.executable,str(ROOT/'cli.py'),'images','--facts',str(ROOT/'samples/facts.json'),'--images',str(ROOT/'samples'),'--output',str(tmp_path)],capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    job=Path(r.stdout.strip())
    assert json.loads((job/'manifest.json').read_text())['image_processing']
    assert not (job/'draft.json').exists()
