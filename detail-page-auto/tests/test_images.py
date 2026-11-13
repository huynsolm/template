import hashlib
from pathlib import Path
import pytest
from PIL import Image, ImageOps
from core.images import Processing, process_image
from core.facts import ImageRef


def photo(tmp_path, mode='RGB', size=(1800, 900), suffix='.png'):
    path=tmp_path/('source'+suffix)
    Image.new(mode,size).save(path)
    return path


def test_processing_backward_compatible():
    ref=ImageRef(path='a.png',role='hero')
    assert ref.processing==Processing()
    assert ref.effective_path=='a.png'
    assert ref.model_copy(update={'derived_path':'images/derived/a.png'}).effective_path=='images/derived/a.png'
    with pytest.raises(ValueError): Processing(max_edge=0)


@pytest.mark.parametrize('orientation',range(1,9))
def test_orientation_and_privacy(tmp_path,orientation):
    source=tmp_path/'source.jpg'
    image=Image.new('RGB',(40,20),'red')
    image.paste('blue',(0,0,20,10))
    exif=Image.Exif(); exif[274]=orientation; exif[315]='private owner'
    image.save(source,exif=exif)
    original=source.read_bytes()
    with Image.open(source) as im: expected=ImageOps.exif_transpose(im).convert('RGB')
    result=process_image(source,tmp_path/'job',{},'#123456')
    with Image.open(result.normalized_path) as actual:
        assert actual.size==expected.size
        assert actual.tobytes()==expected.tobytes()
        assert not actual.getexif()
        assert 'exif' not in actual.info
    assert source.read_bytes()==original


@pytest.mark.parametrize('mode,suffix',[('RGB','.png'),('RGBA','.png'),('CMYK','.jpg'),('L','.png'),('P','.png')])
def test_modes_and_resize(tmp_path,mode,suffix):
    source=photo(tmp_path,mode,suffix=suffix)
    result=process_image(source,tmp_path/'job',{},'#123456')
    with Image.open(result.selected_path) as image:
        assert image.size==(1720,860)
        assert image.mode==('RGBA' if mode=='RGBA' else 'RGB')


def test_small_alpha_cache_and_source_immutable(tmp_path,monkeypatch):
    source=photo(tmp_path,'RGBA',(50,70))
    original=hashlib.sha256(source.read_bytes()).hexdigest()
    first=process_image(source,tmp_path/'one',{},'#123456',cache_dir=tmp_path/'cache')
    assert first.reviews and first.metadata['source_sha256']==original
    with Image.open(first.selected_path) as image:
        assert image.size==(50,70) and image.getpixel((0,0))[3]==0
    monkeypatch.setattr('core.images._normalize',lambda *a: pytest.fail('cache missed'))
    second=process_image(source,tmp_path/'two',{},'#123456',cache_dir=tmp_path/'cache')
    assert second.selected_path.read_bytes()==first.selected_path.read_bytes()
    assert second.selected_path.is_relative_to(tmp_path/'two/images/derived')
    assert hashlib.sha256(source.read_bytes()).hexdigest()==original


class FakeRemover:
    cache_key='fake-v1'
    def remove(self,image):
        result=Image.new('RGBA',image.size)
        result.paste((255,0,0,255),(image.width//4,image.height//4,image.width*3//4,image.height*3//4))
        return result


def test_background_composite_and_checkerboard(tmp_path):
    source=photo(tmp_path,size=(900,900))
    result=process_image(source,tmp_path/'job',{'remove_background':True},'#123456',FakeRemover())
    assert result.selected_path!=result.normalized_path
    assert result.mask_preview_path.exists()
    assert result.metadata['background_removed'] is True
    with Image.open(result.selected_path) as image:
        assert image.getpixel((450,450))[:3]==(255,0,0)
        assert image.getpixel((0,0))[:3]!=(255,255,255)


@pytest.mark.parametrize('area',[0,255])
def test_background_suspicious_area(tmp_path,area):
    class Empty:
        def remove(self,image): return Image.new('RGBA',image.size,(0,0,0,area))
    result=process_image(photo(tmp_path),tmp_path/'job',{'remove_background':True},'#123456',Empty())
    assert any(r['reason']=='background_suspect' for r in result.reviews)


def test_background_failure_preserves_normalized(tmp_path):
    class Broken:
        def remove(self,image): raise RuntimeError('offline')
    result=process_image(photo(tmp_path),tmp_path/'job',{'remove_background':True},'#123456',Broken())
    assert result.selected_path==result.normalized_path
    assert result.metadata['background_removed'] is False
    assert result.reviews[0]['reason']=='background_failed'


def test_invalid_and_pixel_limit(tmp_path):
    source=tmp_path/'bad.png'; source.write_bytes(b'broken')
    with pytest.raises(ValueError): process_image(source,tmp_path/'job',{},'#123456')
    Image.new('L',(5000,4001)).save(source)
    with pytest.raises(ValueError,match='20,000,000'): process_image(source,tmp_path/'job',{},'#123456')


def test_valid_icc_becomes_srgb_and_strips_private_metadata(tmp_path):
    from PIL import ImageCms, PngImagePlugin
    source=tmp_path/'profile.png'
    image=Image.new('RGB',(900,900),(30,60,90))
    info=PngImagePlugin.PngInfo(); info.add_text('GPS','private location')
    profile=ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
    image.save(source,icc_profile=profile,pnginfo=info)
    result=process_image(source,tmp_path/'job',{},'#123456')
    with Image.open(result.selected_path) as actual:
        assert actual.getpixel((0,0))==(30,60,90)
        assert 'GPS' not in actual.info and not actual.getexif()


def test_cache_tampering_reprocesses(tmp_path):
    source=photo(tmp_path)
    first=process_image(source,tmp_path/'one',{},'#123456',cache_dir=tmp_path/'cache')
    key=first.selected_path.parent.name
    (tmp_path/'cache'/key/first.selected_path.name).write_bytes(b'corrupt')
    second=process_image(source,tmp_path/'two',{},'#123456',cache_dir=tmp_path/'cache')
    assert second.selected_path.read_bytes()==first.selected_path.read_bytes()


def test_processing_flags_and_white_background(tmp_path):
    source=photo(tmp_path,size=(1800,900))
    result=process_image(source,tmp_path/'job',{'resize':False,'remove_background':True,'background':'white'},'#123456',FakeRemover())
    with Image.open(result.selected_path) as image:
        assert image.size==(1800,900)
        assert image.getpixel((0,0))==(255,255,255)


def test_cache_selected_path_must_be_checked_member(tmp_path):
    import json
    source=photo(tmp_path)
    first=process_image(source,tmp_path/'one',{},'#123456',cache_dir=tmp_path/'cache')
    metadata=tmp_path/'cache'/first.selected_path.parent.name/'metadata.json'
    data=json.loads(metadata.read_text()); data['selected']='../../outside.png'
    metadata.write_text(json.dumps(data))
    second=process_image(source,tmp_path/'two',{},'#123456',cache_dir=tmp_path/'cache')
    assert second.selected_path.is_relative_to(tmp_path/'two/images/derived')
    assert second.selected_path.exists()


def test_provider_initialization_failure_preserves_image(tmp_path,monkeypatch):
    def broken(): raise RuntimeError('download https://secret@example.invalid/token')
    monkeypatch.setattr('core.images.get_remover',broken)
    result=process_image(photo(tmp_path),tmp_path/'job',{'remove_background':True},'#123456')
    assert result.selected_path==result.normalized_path
    assert result.metadata['background_removed'] is False
    assert 'secret' not in str(result.reviews)


def test_normalized_embeds_srgb(tmp_path):
    result=process_image(photo(tmp_path),tmp_path/'job',{},'#123456')
    with Image.open(result.selected_path) as image:
        assert image.info.get('icc_profile')


def test_gps_exif_is_removed(tmp_path):
    source=tmp_path/'gps.jpg'
    exif=Image.Exif(); exif[34853]={1:'N',3:'E'}
    Image.new('RGB',(900,900)).save(source,exif=exif)
    with Image.open(source) as image: assert 34853 in image.getexif()
    result=process_image(source,tmp_path/'job',{},'#123456')
    with Image.open(result.selected_path) as image: assert 34853 not in image.getexif()


def test_background_pipeline_renders_in_real_chromium(tmp_path):
    import json
    from core.render import render
    from core.schema import Document
    job=tmp_path/'job'
    result=process_image(photo(tmp_path,size=(900,900)),job,{'remove_background':True},'#123456',FakeRemover())
    document=Document.model_validate({'schema_version':'1.0','product':{'name':'상품','category':'상품','price':'판매자 가격','brand_color':'#123456'},'sections':[{'id':'hero','type':'hero','headline':'상품 사진','image':str(result.selected_path.relative_to(job))}]})
    output=render(document,job,tmp_path/'rendered')
    manifest=json.loads((output/'manifest.json').read_text())
    assert manifest['network_requests']==[]
    with Image.open(output/manifest['pages'][0]['file']) as image:
        assert image.format=='JPEG' and image.width==860


def test_palette_srgb_profile_preserves_color_and_transparency(tmp_path):
    from core.images import SRGB_PROFILE
    source=tmp_path/'palette-profile.png'
    image=Image.new('P',(900,900),0)
    image.putpalette([255,0,0,0,128,255]+[0]*762)
    image.paste(1,(450,0,900,900))
    image.save(source,icc_profile=SRGB_PROFILE,transparency=0)
    result=process_image(source,tmp_path/'job',{},'#123456')
    with Image.open(result.normalized_path) as actual:
        assert actual.mode=='RGBA'
        assert actual.getpixel((0,0))==(255,0,0,0)
        assert actual.getpixel((899,0))==(0,128,255,255)


def test_grayscale_profile_with_alpha_preserves_both(tmp_path):
    import base64
    import io
    from PIL import ImageCms
    from core.images import SRGB_PROFILE
    # Locally generated LittleCMS D50, gamma 2.2 grayscale profile (no external asset).
    profile=base64.b64decode('AAABXGxjbXMEQAAAbW50ckdSQVlYWVogB+oACwANAAcAJgALYWNzcEFQUEwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAPbWAAEAAAAA0y1sY21zAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAEZGVzYwAAALQAAAA2Y3BydAAAAOwAAABMd3RwdAAAATgAAAAUa1RSQwAAAUwAAAAQbWx1YwAAAAAAAAABAAAADGVuVVMAAAAaAAAAHABnAHIAYQB5ACAAYgB1AGkAbAB0AC0AaQBuAABtbHVjAAAAAAAAAAEAAAAMZW5VUwAAADAAAAAcAE4AbwAgAGMAbwBwAHkAcgBpAGcAaAB0ACwAIAB1AHMAZQAgAGYAcgBlAGUAbAB5WFlaIAAAAAAAAPbWAAEAAAAA0y1wYXJhAAAAAAAAAAAAAjMz')
    source=tmp_path/'gray-profile.png'
    image=Image.new('LA',(900,900),(128,77))
    image.save(source,icc_profile=profile)
    expected=ImageCms.profileToProfile(image.getchannel('L'),ImageCms.ImageCmsProfile(io.BytesIO(profile)),ImageCms.ImageCmsProfile(io.BytesIO(SRGB_PROFILE)),outputMode='RGB').getpixel((0,0))
    result=process_image(source,tmp_path/'job',{},'#123456')
    with Image.open(result.normalized_path) as actual:
        assert actual.mode=='RGBA'
        assert actual.getpixel((0,0))==(*expected,77)
