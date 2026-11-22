"""Fictional brochure regression data, created only in the supplied output folder."""
from pathlib import Path
import shutil

from PIL import Image, ImageDraw
from core.extract import ingest_facts, apply_import
from core.facts import ProductFacts
from core.workflow import create_job, ingest_job, read_json
from core.editor import preview_job

ROOT = Path(__file__).resolve().parents[1]


def run_scenario(output: Path):
    output.mkdir(parents=True,exist_ok=True)
    source = output/'fictional-brochure.png'
    photo = Image.new('RGB',(793,1122),'#f5f2e9')
    draw = ImageDraw.Draw(photo)
    draw.rectangle((40,40,753,180),outline='#52675f',width=3)
    draw.text((65,65),'FICTIONAL MODULE / DEMO ONLY',fill='#243c31')
    draw.text((65,110),'AC 220V | 320 mm | 2.4 kg | 3 modules',fill='#243c31')
    draw.rounded_rectangle((170,275,630,820),45,fill='#35655b')
    draw.rounded_rectangle((240,340,560,470),20,fill='#dbe9df')
    for row in range(4):
        y=540+row*42
        draw.line((250,y,550,y),fill='#143b30',width=8)
    draw.rectangle((40,945,753,1080),outline='#52675f',width=3)
    draw.text((65,980),'Specifications / seller verification required',fill='#243c31')
    photo.save(source)
    diagram = output/'fictional-diagram.png'
    drawing=Image.new('RGB',(900,600),'#f5f2e9')
    lines=ImageDraw.Draw(drawing)
    lines.rectangle((70,70,830,530),outline='#35655b',width=6)
    for x in (170,400,630):
        lines.rectangle((x,150,x+100,460),outline='#35655b',width=5)
    drawing.save(diagram)

    imported=ingest_facts((ROOT/'samples/extract-answer.txt').read_text())
    data=apply_import({'product':{'price':'판매자 확인용 가상 가격','brand_color':'#35655b'}},imported)
    data['images']=[
        {'path':source.name,'role':'hero','processing':{'crop':{'top':.2,'bottom':.2,'left':.1,'right':.1}}},
        {'path':diagram.name,'role':'diagram'},
    ]
    data['spec_verified']=True
    facts=ProductFacts.model_validate(data)
    job=create_job(facts,output,output/'jobs')
    ingest_job(job,(ROOT/'samples/answer-rich.txt').read_text())
    bundle=preview_job(job)
    stored=read_json(job/'facts.json')
    cropped=job/stored['images'][0]['derived_path']
    shutil.copyfile(cropped,output/'cropped-photo.png')
    manifest=read_json(bundle/'manifest.json')
    assert {'stats','structure','spec'} <= {s['id'].rsplit('-',1)[0] for s in manifest['sections']}
    return {'source':source,'cropped':output/'cropped-photo.png','bundle':bundle,
            'summary':{'facts':len(data['facts']),'highlights':len(data['highlights']),
                       'table_rows':len(data['spec_table']['rows']),'pending_claims':len(data['pending_claims'])},
            'job':job}
