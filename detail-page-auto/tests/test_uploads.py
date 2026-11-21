import io
from pathlib import Path
import sys
import pytest
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def png():
    data=io.BytesIO(); Image.new('RGB',(10,10),'green').save(data,format='PNG'); return data.getvalue()


def test_upload_names_are_generated(tmp_path):
    from core.uploads import stage_uploads
    root,refs=stage_uploads([('../x.png',png())],tmp_path)
    assert root.parent==tmp_path
    assert refs[0]['path']=='upload-01.png'
    assert (root/refs[0]['path']).is_file()
    assert not (tmp_path.parent/'x.png').exists()

@pytest.mark.parametrize('case',['disguise','bytes','count','pixels'])
def test_upload_rejects_bad_images(tmp_path,case):
    from core.uploads import stage_uploads
    files=[('a.png',png())]
    if case=='disguise': files=[('image.png',b'not an image')]
    if case=='bytes': files=[('a.png',png()+b'0'*(10*1024*1024))]
    if case=='count': files=files*11
    if case=='pixels':
        data=io.BytesIO(); Image.new('1',(5000,4001)).save(data,format='PNG'); files=[('big.png',data.getvalue())]
    with pytest.raises(ValueError): stage_uploads(files,tmp_path)
    assert not list(tmp_path.iterdir())
