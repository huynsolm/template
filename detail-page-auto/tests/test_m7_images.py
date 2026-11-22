import hashlib
from pathlib import Path
import sys
import pytest
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def test_crop_preserves_source_and_changes_cache(tmp_path):
    from core.images import process_image
    source=tmp_path/'brochure.png'
    Image.new('RGB',(1000,1400),'white').save(source)
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    first=process_image(source,tmp_path/'job',{'crop':{'left':.1,'right':.2,'top':.1,'bottom':.2},'resize':False},'#305b46')
    second=process_image(source,tmp_path/'job',{},'#305b46')
    assert Image.open(first.normalized_path).size==(700,980)
    assert first.normalized_path != second.normalized_path
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    with pytest.raises(ValueError,match='200'):
        process_image(source,tmp_path/'job',{'crop':{'left':.45,'right':.45}},'#305b46')


def test_crop_defaults_preserve_small_existing_images(tmp_path):
    from core.images import process_image
    source=tmp_path/'small.png'
    Image.new('RGB',(120,100),'white').save(source)
    result=process_image(source,tmp_path/'job',{},'#305b46')
    assert Image.open(result.normalized_path).size==(120,100)
