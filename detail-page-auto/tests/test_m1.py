import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

@pytest.fixture
def data():
    return json.loads((ROOT / 'samples/product.json').read_text())


def test_schema_available():
    from core.schema import Document
    assert Document is not None

@pytest.mark.parametrize('case', ['version','unknown','type','duplicate','nohero','twohero','permission','color','emptyimage','longtitle','rating','whitespace'])
def test_invalid_schema(data, case):
    from core.schema import Document
    from pydantic import ValidationError
    if case == 'version': data['schema_version']='2.0'
    if case == 'unknown': data['extra']=1
    if case == 'type': data['sections'][0]['type']='unknown'
    if case == 'duplicate': data['sections'][1]['id']=data['sections'][0]['id']
    if case == 'nohero': data['sections']=data['sections'][1:]
    if case == 'twohero':
        second=copy.deepcopy(data['sections'][0]); second['id']='hero-2'; data['sections'].append(second)
    if case == 'permission': next(s for s in data['sections'] if s['type']=='review')['items'][0].pop('permission_confirmed')
    if case == 'color': data['product']['brand_color']='red'
    if case == 'emptyimage': data['sections'][0]['image']=''
    if case == 'longtitle': data['sections'][0]['headline']='가'*81
    if case == 'rating': next(s for s in data['sections'] if s['type']=='review')['items'][0]['rating']=True
    if case == 'whitespace': data['product']['name']='  '
    with pytest.raises(ValidationError): Document.model_validate(data)


def test_schema_boundaries(data):
    from core.schema import Document
    data['sections'][0]['headline']='가'*80
    Document.model_validate(data)
    data['sections'][0]['headline']='가'*81
    with pytest.raises(ValueError): Document.model_validate(data)

@pytest.mark.parametrize('case',['escape','symlink','missing','corrupt','bytes','pixels','count'])
def test_bad_images(tmp_path, data, case):
    from core.schema import Document
    from core.collect import collect_images
    root=tmp_path/'input'; root.mkdir()
    shutil.copy(ROOT/'samples/product.png',root/'product.png')
    if case=='escape': data['sections'][0]['image']='../outside.png'
    if case=='symlink':
        (root/'link.png').symlink_to(root/'product.png'); data['sections'][0]['image']='link.png'
    if case=='missing': (root/'product.png').unlink()
    if case=='corrupt': (root/'product.png').write_bytes(b'broken')
    if case=='bytes':
        with (root/'product.png').open('ab') as f: f.write(b'0'*(10*1024*1024))
    if case=='pixels': Image.new('1',(5000,4001)).save(root/'product.png')
    if case=='count':
        for i in range(6):
            shutil.copy(ROOT/'samples/product.png',root/f'{i}.png')
            data['sections'].append({'id':f'x{i}','type':'solution','title':'특징','body':'설명','image':f'{i}.png'})
    with pytest.raises(ValueError): collect_images(Document.model_validate(data),root)


def test_render_and_portability(tmp_path, data):
    from core.render import render, capture
    from core.schema import Document
    data['sections'][0]['headline']='<script>alert(1)</script>'
    data['sections'][1]['items']=['긴 한글 문구를 자연스럽게 줄바꿈합니다. '*8]
    out=render(Document.model_validate(data),ROOT/'samples',tmp_path,max_height=1400,png=True)
    manifest=json.loads((out/'manifest.json').read_text())
    assert len(manifest['pages'])>1
    assert sum(p['height'] for p in manifest['pages'])==manifest['height']
    assert manifest['network_requests']==[]
    assert manifest['horizontal_overflow'] is False
    assert '&lt;script&gt;' in (out/'page.html').read_text()
    assert not (out/'page.html').read_text().count('<script>')
    assembled=Image.new('RGB',(860,manifest['height']))
    y=0
    for i,p in enumerate(manifest['pages'],1):
        assert p['file']==f'page-{i:03}.jpg'
        with Image.open(out/p['file']) as jpg:
            assert jpg.size==(860,p['height']); assert jpg.info.get('icc_profile')
        with Image.open(out/p['png']) as part: assembled.paste(part,(0,y))
        y+=p['height']
    moved=tmp_path/'moved'; shutil.move(out,moved)
    full,geometry=capture(moved/'page.html')
    assert ImageChops.difference(assembled,full).getbbox() is None
    assert geometry['font_loaded']

@pytest.mark.parametrize('case',['section','total'])
def test_render_limits(tmp_path,data,case):
    from core.render import render
    from core.schema import Document
    if case=='total':
        data['sections']=[data['sections'][0]]+[{'id':f'n{i}','type':'notice','body':'가\n'*1000} for i in range(19)]
    with pytest.raises(ValueError,match='30,000|section|섹션'):
        render(Document.model_validate(data), ROOT/'samples',tmp_path,max_height=100 if case=='section' else 4000)
    assert not list(tmp_path.glob('job-*'))


def test_cli_failure(tmp_path):
    r=subprocess.run([sys.executable,str(ROOT/'cli.py'),'--input',str(tmp_path/'missing.json'),'--images',str(ROOT/'samples'),'--output',str(tmp_path)],capture_output=True,text=True)
    assert r.returncode!=0
    assert 'error:' in r.stderr

@pytest.mark.parametrize('field,limit', [('headline',80),('subcopy',300)])
def test_hero_string_limits(data,field,limit):
    from core.schema import Document
    data['sections'][0][field]='한'*limit
    Document.model_validate(data)
    data['sections'][0][field]+='글'
    with pytest.raises(ValueError): Document.model_validate(data)

@pytest.mark.parametrize('section,field,limit', [('solution','body',2000),('solution','title',80),('notice','body',2000)])
def test_section_string_limits(data,section,field,limit):
    from core.schema import Document
    target=next(s for s in data['sections'] if s['type']==section)
    target[field]='한'*limit
    Document.model_validate(data)
    target[field]+='글'
    with pytest.raises(ValueError): Document.model_validate(data)

@pytest.mark.parametrize('section,field,limit', [('features','desc',300),('faq','q',200),('faq','a',1000),('review','text',1000)])
def test_item_string_limits(data,section,field,limit):
    from core.schema import Document
    target=next(s for s in data['sections'] if s['type']==section)['items'][0]
    target[field]='한'*limit
    Document.model_validate(data)
    target[field]+='글'
    with pytest.raises(ValueError): Document.model_validate(data)

@pytest.mark.parametrize('field', ['sections','items','rows','rating','permission','unknown_section_field'])
def test_collection_and_nested_constraints(data,field):
    from core.schema import Document
    if field=='sections':
        data['sections']=[data['sections'][0]]+[{'id':f'n{i}','type':'notice','body':'안내'} for i in range(19)]
        Document.model_validate(data)
        data['sections'].append({'id':'overflow','type':'notice','body':'안내'})
    elif field=='items':
        data['sections'][1]['items']=['고민']*10
        Document.model_validate(data)
        data['sections'][1]['items'].append('초과')
    elif field=='rows': next(s for s in data['sections'] if s['type']=='spec')['rows']=[['하나']]
    elif field=='rating': next(s for s in data['sections'] if s['type']=='review')['items'][0]['rating']=6
    elif field=='permission': next(s for s in data['sections'] if s['type']=='review')['items'][0]['permission_confirmed']=False
    else: data['sections'][0]['extra']='forbidden'
    with pytest.raises(ValueError): Document.model_validate(data)


def test_forbidden_requests_and_broken_font(tmp_path):
    from core.render import capture
    page=tmp_path/'page.html'
    page.write_text('<html><img src="https://example.com/a.png"></html>')
    with pytest.raises(ValueError,match='failed|forbidden'): capture(page)
    page.write_text('<html><p>한글</p></html>')
    with pytest.raises(ValueError,match='font'): capture(page)


def test_repeatable_and_rerunnable(tmp_path,data):
    from core.render import render
    from core.schema import Document
    first=render(Document.model_validate(data),ROOT/'samples',tmp_path)
    before=(first/'page-001.jpg').read_bytes()
    second=render(Document.model_validate_json((first/'input.json').read_text()),first,tmp_path)
    assert first!=second
    assert (first/'page-001.jpg').read_bytes()==before
    with Image.open(first/'page-001.jpg') as a, Image.open(second/'page-001.jpg') as b:
        assert ImageChops.difference(a.convert('RGB'),b.convert('RGB')).getbbox() is None


def test_short_page_respects_split_limit(tmp_path,data):
    from core.render import render
    from core.schema import Document
    images=tmp_path/'images'; images.mkdir()
    Image.new('RGB',(1,1),'white').save(images/'product.png')
    data['sections']=data['sections'][:1]
    out=render(Document.model_validate(data),images,tmp_path/'out',max_height=800)
    manifest=json.loads((out/'manifest.json').read_text())
    assert all(p['height']<=800 for p in manifest['pages'])
    assert manifest['height']==manifest['sections'][-1]['bottom']
