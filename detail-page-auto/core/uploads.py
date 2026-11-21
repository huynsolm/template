"""Stage uploads under a local job using server-generated names and M1 checks."""
import io
import shutil
import tempfile
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from .schema import Document
from .collect import collect_images


def stage_uploads(files, output: Path):
    if not 1 <= len(files) <= 10:
        raise ValueError('사진은 1~10장까지 올릴 수 있습니다.')
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    root=Path(tempfile.mkdtemp(prefix='job-input-',dir=output))
    try:
        refs=[]
        for i,(_,content) in enumerate(files,1):
            if len(content)>10*1024*1024:
                raise ValueError('사진 한 장은 10MB 이하여야 합니다.')
            try:
                with Image.open(io.BytesIO(content)) as image:
                    extension={'PNG':'.png','JPEG':'.jpg'}.get(image.format)
                    if extension is None: raise ValueError('PNG/JPEG 사진만 사용할 수 있습니다.')
            except (OSError,UnidentifiedImageError) as exc:
                raise ValueError('사진의 실제 형식을 읽을 수 없습니다. PNG/JPEG 파일을 확인하세요.') from exc
            name=f'upload-{i:02}{extension}'
            (root/name).write_bytes(content)
            refs.append({'path':name,'role':'hero' if i==1 else 'feature'})
        sections=[{'id':'hero-1','type':'hero','headline':'사진 검증','image':refs[0]['path']}]
        sections += [{'id':f'solution-{i}','type':'solution','title':'사진 검증','body':'사진 검증','image':r['path']} for i,r in enumerate(refs[1:],1)]
        document=Document.model_validate({'schema_version':'1.0','product':{'name':'검증','category':'검증','price':'검증','brand_color':'#000000'},'sections':sections})
        collect_images(document,root)
        return root,refs
    except BaseException:
        shutil.rmtree(root)
        raise
