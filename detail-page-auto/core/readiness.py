"""Shared pre-generation checks for raw forms and validated seller facts."""
import colorsys
from functools import lru_cache
import json
from pathlib import Path

from PIL import Image
from .images import Processing, crop_box, validate_source


@lru_cache(maxsize=1)
def _sample_values():
    values = {'name':set(), 'price':set(), 'notice':set()}
    for path in (Path(__file__).resolve().parents[1]/'samples').glob('*.json'):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            for key in ('name','price'):
                if data.get('product',{}).get(key):
                    values[key].add(data['product'][key])
            if data.get('notice'):
                values['notice'].add(data['notice'])
        except (ValueError, OSError, AttributeError, TypeError):
            continue
    return values


def photo_dimensions(image, root):
    """Read oriented source dimensions without trusting a supplied derived path."""
    folder = Path(root).resolve()
    path = (folder/image['path']).resolve()
    if Path(image['path']).is_absolute() or '..' in Path(image['path']).parts or not path.is_relative_to(folder) or not path.is_file():
        raise ValueError('사진 파일 경로를 확인하세요.')
    settings = Processing.model_validate(image.get('processing',{}))
    validate_source(folder/image['path'])
    with Image.open(path) as source:
        width, height = source.size
        if settings.auto_orient and source.getexif().get(274) in (5,6,7,8):
            width, height = height, width
    cropped = any(settings.crop.model_dump().values())
    if cropped:
        left, top, right, bottom = crop_box((width,height), settings.crop)
        width, height = right-left, bottom-top
    return width, height, cropped


def check_readiness(facts, images, settings=None) -> list[dict]:
    data = facts.model_dump(exclude_none=True) if hasattr(facts,'model_dump') else facts
    settings = settings or {}
    if (not isinstance(data,dict) or not isinstance(data.get('product',{}),dict)
            or any(not isinstance(data.get(key,[]),list) or any(not isinstance(row,dict) for row in data.get(key,[]))
                   for key in ('facts','images'))):
        return [{'level':'필수','code':'INVALID_INPUT','message':'상품 정보·사실·사진의 JSON 형식을 확인하세요.','field':'product'}]
    product, rows, photos = data.get('product',{}), data.get('facts',[]), data.get('images',[])
    result = []
    def add(level, code, message, field):
        result.append({'level':level,'code':code,'message':message,'field':field})

    if not any(photo.get('role') == 'hero' for photo in photos):
        add('필수','NO_HERO','대표(hero) 사진을 지정하세요.','images')
    for key, code, label in [('name','EMPTY_NAME','상품명'),('price','EMPTY_PRICE','가격')]:
        if not str(product.get(key) or '').strip():
            add('필수',code,f'{label}을 입력하세요.',f'product.{key}')
    if len(rows) < 8:
        add('권장','FEW_FACTS','상품 사실을 8개 이상 입력하면 문구를 풍부하게 구성할 수 있습니다.','facts')
    if sum(row.get('kind') == 'feature' for row in rows) < 3:
        add('권장','FEW_FEATURES','특징 사실을 3개 이상 입력해 주세요.','facts')
    if not data.get('highlights'):
        add('권장','NO_HIGHLIGHTS','숫자 띠에 핵심 값을 입력해 주세요.','highlights')
    if not data.get('spec_table') and not any(row.get('kind') == 'spec' for row in rows):
        add('권장','NO_SPEC','스펙 사실 또는 사양표를 입력해 주세요.','spec_table')
    if any(photo.get('role') == 'diagram' for photo in photos) and not data.get('structure'):
        add('권장','NO_STRUCTURE','구조도와 함께 보여 줄 구조 설명을 입력해 주세요.','structure')
    if not data.get('targets'):
        add('권장','NO_TARGETS','적용 장소나 추천 대상을 입력해 주세요.','targets')
    if data.get('pending_claims') or settings.get('pending_claims'):
        add('권장','PENDING_CLAIMS','근거가 필요한 주장이 남아 있습니다. 근거를 확인해 주세요.','pending_claims')
    if str(product.get('price','')).strip().isdigit():
        add('참고','NUMERIC_PRICE','가격을 130,000원처럼 적으면 보기 좋습니다.','product.price')
    sample = _sample_values()
    for key in ('name','price','notice'):
        value = data.get(key) if key == 'notice' else product.get(key)
        if isinstance(value,str) and value and value in sample[key]:
            add('참고','SAMPLE_TEXT','가상 샘플 문구가 남아 있습니다. 실제 입력인지 확인하세요.',
                key if key == 'notice' else f'product.{key}')
    try:
        color = product.get('brand_color','')
        rgb = tuple(int(color[i:i+2],16)/255 for i in (1,3,5))
        if colorsys.rgb_to_hsv(*rgb)[1] < .15:
            add('참고','GREY_BRAND','브랜드 색이 회색 계열이라 강조가 약할 수 있습니다.','product.brand_color')
    except (ValueError, TypeError):
        pass
    for index, photo in enumerate(photos):
        field = f'images.{index}'
        try:
            width, height, cropped = photo_dimensions(photo,images)
        except (OSError, ValueError, TypeError, KeyError, Image.DecompressionBombError) as exc:
            add('필수','INVALID_PHOTO',f'사진 {index+1}: {exc}',field)
            continue
        if (photo.get('role') in ('hero','feature','lifestyle','detail')
                and not cropped and not photo.get('document_confirmed')
                and 1.33 <= height/width <= 1.50):
            add('권장','DOCUMENT_PHOTO',f'사진 {index+1}: 브로슈어·문서 페이지로 보입니다. 글자 없는 부분만 잘라서 쓰세요.',field)
        if width < 860:
            add('참고','LOW_RESOLUTION',f'사진 {index+1}: 자른 뒤 폭이 {width}px입니다. 상세페이지에서 선명도를 확인하세요.',field)
    return result
