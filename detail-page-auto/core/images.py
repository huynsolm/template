"""Immutable local photo normalization, foreground placement and verified caching."""
from dataclasses import dataclass
import hashlib
import importlib.metadata
import io
import json
from pathlib import Path
import re
import shutil
import struct
from typing import Annotated, Literal
from PIL import Image, ImageCms, ImageOps, __version__ as PILLOW_VERSION
from pydantic import Field
from .schema import Model, Document
from .collect import collect_images
from .background import BackgroundRemover, RemBgRemover, get_remover


# LittleCMS stamps new profiles with the current time. Fix that informational
# header so identical pixel/settings inputs produce identical PNG bytes.
_profile_bytes=bytearray(ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes())
_profile_bytes[24:36]=struct.pack('>6H',2020,1,1,0,0,0)
SRGB_PROFILE=bytes(_profile_bytes)


class Crop(Model):
    left: float = Field(default=0.0, ge=0, le=0.45, allow_inf_nan=False)
    top: float = Field(default=0.0, ge=0, le=0.45, allow_inf_nan=False)
    right: float = Field(default=0.0, ge=0, le=0.45, allow_inf_nan=False)
    bottom: float = Field(default=0.0, ge=0, le=0.45, allow_inf_nan=False)


class Processing(Model):
    crop: Crop = Field(default_factory=Crop)
    auto_orient: bool = True
    resize: bool = True
    remove_background: bool = False
    max_edge: Annotated[int, Field(ge=1)] = 1720
    background: Literal['brand', 'white'] = 'brand'
    padding: Annotated[float, Field(ge=0, le=0.4)] = 0.08


@dataclass
class ImageResult:
    normalized_path: Path
    selected_path: Path
    mask_preview_path: Path | None
    metadata: dict
    reviews: list[dict]


def validate_source(source: Path) -> Path:
    """Use the same format, size, decode and path checks as M1."""
    source = Path(source)
    document = Document.model_validate({
        'schema_version':'1.0',
        'product':{'name':'validation','category':'validation','price':'validation','brand_color':'#000000'},
        'sections':[{'id':'hero','type':'hero','headline':'validation','image':source.name}],
    })
    return collect_images(document, source.parent)[source.name]


def crop_box(size: tuple[int, int], crop: Crop) -> tuple[int, int, int, int]:
    width, height = size
    box = (round(width*crop.left), round(height*crop.top),
           width-round(width*crop.right), height-round(height*crop.bottom))
    if box[2]-box[0] < 200 or box[3]-box[1] < 200:
        raise ValueError('자른 뒤 사진의 폭과 높이는 각각 200px 이상이어야 합니다.')
    return box


def preview_crop(source: Path, processing: dict) -> Image.Image:
    settings = Processing.model_validate(processing).model_copy(update={'resize':False,'remove_background':False})
    return _normalize(validate_source(source),settings)


def _normalize(source: Path, settings: Processing) -> Image.Image:
    with Image.open(source) as original:
        original.load()
        profile = original.info.get('icc_profile')
        image = ImageOps.exif_transpose(original) if settings.auto_orient else original.copy()
        if any(settings.crop.model_dump().values()):
            image = image.crop(crop_box(image.size, settings.crop))
        alpha = image.convert('RGBA').getchannel('A') if image.mode in ('RGBA','LA') or 'transparency' in image.info else None
        if profile:
            try:
                target = ImageCms.createProfile('sRGB')
                # ICC transforms operate on color channels, never palette indices
                # or alpha. Keep grayscale samples in their source profile space.
                if image.mode in ('P', 'PA', 'RGBA'):
                    image = image.convert('RGB')
                elif image.mode == 'LA':
                    image = image.getchannel('L')
                image = ImageCms.profileToProfile(image, ImageCms.ImageCmsProfile(io.BytesIO(profile)), target, outputMode='RGB')
            except (OSError, ValueError, ImageCms.PyCMSError) as exc:
                raise ValueError(f'Invalid or unsupported ICC profile: {exc}') from exc
        else:
            image = image.convert('RGB')
        if alpha is not None: image.putalpha(alpha)
        if settings.resize:
            image.thumbnail((settings.max_edge, settings.max_edge), Image.Resampling.LANCZOS)
        # Copy pixels into a fresh image so no EXIF, text, GPS or source ICC survives.
        clean = Image.new(image.mode, image.size)
        clean.paste(image)
        clean.info['icc_profile']=SRGB_PROFILE
        return clean


def _checkerboard(image: Image.Image) -> Image.Image:
    result = Image.new('RGB', image.size, '#eeeeee')
    from PIL import ImageDraw
    draw = ImageDraw.Draw(result)
    for y in range(0,image.height,20):
        for x in range(0,image.width,20):
            if (x//20+y//20)%2: draw.rectangle((x,y,x+19,y+19), fill='#cccccc')
    result.paste(image,(0,0),image.getchannel('A'))
    return result


def _place(image: Image.Image, settings: Processing, brand_color: str) -> Image.Image:
    color = (255,255,255) if settings.background=='white' else tuple(round(int(brand_color[n:n+2],16)*0.12+255*0.88) for n in (1,3,5))
    canvas=Image.new('RGB',image.size,color)
    box=image.getchannel('A').getbbox()
    if box:
        foreground=image.crop(box)
        available=(max(1,int(image.width*(1-2*settings.padding))),max(1,int(image.height*(1-2*settings.padding))))
        foreground.thumbnail(available,Image.Resampling.LANCZOS)
        canvas.paste(foreground,((image.width-foreground.width)//2,(image.height-foreground.height)//2),foreground.getchannel('A'))
    return canvas


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _version(name: str) -> str:
    try: return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError: return 'not-installed'


def _cached(folder: Path, identity: dict) -> dict | None:
    try:
        data=json.loads((folder/'metadata.json').read_text())
        if data['identity']!=identity or not data.get('cacheable'): return None
        for name,digest in data['files'].items():
            if Path(name).name!=name or _digest(folder/name)!=digest: return None
        if not data['files']: return None
        required=[data['normalized'],data['selected']]
        if data['mask_preview'] is not None: required.append(data['mask_preview'])
        if any(name not in data['files'] for name in required): return None
        if not isinstance(data['reviews'],list): return None
        return data
    except (OSError, ValueError, KeyError, TypeError): return None


def process_image(source: Path, job: Path, processing: Processing | dict, brand_color: str,
                  remover: BackgroundRemover | None = None, cache_dir: Path | None = None) -> ImageResult:
    settings=processing if isinstance(processing,Processing) else Processing.model_validate(processing)
    if not re.fullmatch(r'#[0-9a-fA-F]{6}',brand_color): raise ValueError('brand_color must be #RRGGBB')
    source=validate_source(source)
    provider=RemBgRemover.cache_key if settings.remove_background and remover is None else (None if remover is None else getattr(remover,'cache_key',f'{type(remover).__module__}.{type(remover).__qualname__}'))
    identity={'source_sha256':_digest(source),'settings':settings.model_dump(),'brand_color':brand_color.lower(),
              'tool_versions':{'pipeline':'4','pillow':PILLOW_VERSION,'rembg':_version('rembg') if settings.remove_background else None},'provider':provider}
    key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    folder=Path(job)/'images'/'derived'/key
    folder.mkdir(parents=True,exist_ok=True)
    cache=Path(cache_dir)/key if cache_dir is not None else None
    data=_cached(folder,identity)
    if data is None and cache is not None:
        data=_cached(cache,identity)
        if data:
            for name in data['files']: shutil.copyfile(cache/name,folder/name)
            (folder/'metadata.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
    if data is None:
        image=_normalize(source,settings)
        normalized=f'{key[:16]}-normalized.png'
        image.save(folder/normalized)
        selected=normalized; preview=None; reviews=[]
        def review(reason,message): reviews.append({'reason':reason,'message':message,'needs_review':True})
        if image.width<860:
            review('image_low_resolution','Image width is below 860px; inspect photo sharpness. No upscaling was applied.')
        removed=False
        if settings.remove_background:
            try:
                active_remover=remover if remover is not None else get_remover()
                foreground=active_remover.remove(image.copy())
                if not isinstance(foreground,Image.Image) or foreground.mode!='RGBA' or foreground.size!=image.size:
                    raise ValueError('remover must return a same-sized RGBA image')
                alpha=foreground.getchannel('A')
                area=sum(alpha.histogram()[1:])/(image.width*image.height)
                if area<0.05 or area>0.98:
                    review('background_suspect',f'Inspect background removal: foreground covers {area:.1%} of photo.')
                preview=f'{key[:16]}-mask-preview.png'
                _checkerboard(foreground).save(folder/preview)
                foreground.save(folder/f'{key[:16]}-foreground.png')
                selected=f'{key[:16]}-placed.png'
                _place(foreground,settings,brand_color).save(folder/selected)
                removed=True
            except Exception as exc:
                review('background_failed',f'Local background removal failed ({type(exc).__name__}); normalized photo retained. Check optional installation, model checksum and offline availability.')
        names=[normalized]
        if removed: names += [preview,selected,f'{key[:16]}-foreground.png']
        data={**identity,'identity':identity,'normalized':normalized,'selected':selected,'mask_preview':preview,
              'background_removed':removed,'dimensions':list(image.size),
              'steps':(['auto_orient'] if settings.auto_orient else [])+(['crop'] if any(settings.crop.model_dump().values()) else [])+['convert_srgb','strip_private_metadata']+(['resize_without_upscaling'] if settings.resize else [])+(['background_remove','placement'] if removed else []),
              'reviews':reviews,'cacheable':not settings.remove_background or removed,
              'files':{name:_digest(folder/name) for name in names}}
        (folder/'metadata.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
        if cache is not None and data['cacheable']:
            cache.mkdir(parents=True,exist_ok=True)
            for name in data['files']: shutil.copyfile(folder/name,cache/name)
            (cache/'metadata.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
    return ImageResult(folder/data['normalized'],folder/data['selected'],folder/data['mask_preview'] if data['mask_preview'] else None,data,data['reviews'])
