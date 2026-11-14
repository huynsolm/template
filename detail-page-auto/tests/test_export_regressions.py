"""Export output must describe its actual files and preserve every text row."""
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest
from PIL import Image,ImageDraw,ImageChops

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.export import Profile,build_export_zip,current_bundle,export_bundle


def profile(**values):
    return Profile.model_validate({'name':'가짜 규격','status':'verified',
        'source_url':'https://example.invalid/spec','checked_date':'2026-11-15',
        'width':100,'max_height_per_image':100,'max_file_bytes':1000000,
        'max_images':50,'formats':['png'],'jpeg_quality':90,**values})


def snapshot(tmp_path,image):
    from core.themes import theme_styles,contrast_metadata
    folder=tmp_path/'job-render'
    folder.mkdir(parents=True)
    image.save(folder/'page-001.png')
    draft=(ROOT/'samples/product.json').read_bytes()
    (folder/'draft.json').write_bytes(draft)
    (folder/'review.json').write_text('[]')
    (folder/'page.html').write_text('<!doctype html><p>source HTML</p>')
    record={'job_id':folder.name,'width':image.width,'height':image.height,'max_height':4000,
        'theme':'classic',**contrast_metadata(theme_styles('classic','#305b46')),
        'draft_sha256':hashlib.sha256(draft).hexdigest(),'review_accepted':False,
        'sections':[{'id':'test','top':0,'bottom':image.height}],
        'pages':[{'file':'page-001.png','png':'page-001.png','width':image.width,
                  'height':image.height,'top':0,'bottom':image.height}]}
    (folder/'manifest.json').write_text(json.dumps(record))
    return folder,record


@pytest.mark.parametrize('fmt',['jpg','png'])
def test_export_zip_top_manifest_matches_transformed_files(tmp_path,fmt):
    bundle,original=snapshot(tmp_path,Image.new('RGB',(200,300),'white'))
    before=(bundle/'manifest.json').read_bytes()
    result=export_bundle(bundle,profile(formats=[fmt]),tmp_path/'exports')
    assert result['status']=='pass'
    _,data=build_export_zip(result['folder'])
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        meta=json.loads(archive.read('manifest.json'))
        assert meta['width']==100 and meta['height']==150
        assert meta['max_height']==100
        assert meta['source_render']==original
        assert meta['sections']==[{'id':'test','top':0,'bottom':150}]
        assert meta['pages']==meta['export']['files']
        assert sum(p['height'] for p in meta['pages'])==meta['height']
        for page in meta['pages']:
            with Image.open(io.BytesIO(archive.read(page['file']))) as image:
                assert image.size==(page['width'],page['height'])
        assert meta['contrast_policy']==original['contrast_policy']
    assert (bundle/'manifest.json').read_bytes()==before


@pytest.mark.parametrize('background,foreground',[('white',(245,245,245)),((255,0,0),(0,130,0))])
def test_internal_cuts_avoid_faint_and_equal_luminance_text_rows(tmp_path,background,foreground):
    image=Image.new('RGB',(200,300),background)
    ImageDraw.Draw(image).text((10,95),'TEXT TEXT',fill=foreground)
    assert any(low!=high for low,high in image.crop((0,100,200,101)).getextrema())
    bundle,_=snapshot(tmp_path,image)
    result=export_bundle(bundle,profile(width=200),tmp_path/'exports')
    assert result['status']=='pass',result['checks']
    reconstructed=Image.new('RGB',image.size)
    for item in result['files']:
        if item['top']:
            extrema=image.crop((0,item['top'],image.width,item['top']+1)).getextrema()
            assert all(low==high for low,high in extrema),('cut contains glyph pixels',item['top'],extrema)
        with Image.open(Path(result['folder'])/item['file']) as part:
            reconstructed.paste(part,(0,item['top']))
    assert ImageChops.difference(image,reconstructed).getbbox() is None


@pytest.mark.parametrize('mismatch',['draft_sha256','theme','contrast_policy'])
def test_current_bundle_rejects_stale_approved_render(tmp_path,mismatch):
    job=tmp_path/'job-approved';job.mkdir()
    bundle,meta=snapshot(job/'rendered',Image.new('RGB',(200,300),'white'))
    (job/'draft.json').write_bytes((bundle/'draft.json').read_bytes())
    (job/'manifest.json').write_text(json.dumps({'theme':'classic','review_accepted':True,
                                               'rendered_job':str(bundle.relative_to(job))}))
    meta['review_accepted']=True
    meta[mismatch]={'draft_sha256':'0'*64,'theme':'bold','contrast_policy':'aa'}[mismatch]
    (bundle/'manifest.json').write_text(json.dumps(meta))
    with pytest.raises(ValueError,match='미리보기'):
        current_bundle(job)
