"""M8-B: where each image came from, and the checks a person confirms before approval.

The app never makes or edits images. A seller may upload an image they made with an AI chat
service they subscribe to: a real photo with only the background changed (``ai_edited``), or a
fully generated mood picture (``ai_generated``). Every such image is recorded with its tool and
original photo, is a review item until a person compares it, and must be confirmed one check at a
time before approval. The comparison numbers here are hints only; they never approve anything.
"""
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps

CHECKS = {
    'ai_edited': [('shape', '형태(외곽·비율)가 원본 사진과 같습니다'),
                  ('color', '색상이 원본 사진과 같습니다'),
                  ('composition', '구성(부품·개수·로고·글자)이 원본 사진과 같습니다')],
    'ai_generated': [('no_product', '실제 상품이 나오지 않거나, 나오더라도 실제와 다르게 보이지 않습니다')],
}
SOURCE_NAMES = {'photo': '실제 사진', 'ai_edited': 'AI 배경 변경', 'ai_generated': 'AI 생성'}
ASPECT_TOLERANCE = 0.10
STAGED_NOTE = '연출 이미지입니다'


def _digest(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return ImageOps.exif_transpose(image).size


def provenance_record(facts, index: int, job: Path) -> dict:
    """Provenance and comparison hints for one AI image (stored in ``image_processing``)."""
    image = facts.images[index]
    job = Path(job)
    record = {'source': image.source, 'generator': image.generator, 'source_sha256': _digest(job / image.path)}
    if image.edit_request:
        record['edit_request'] = image.edit_request
    if image.based_on:
        width, height = _size(job / image.path)
        original_width, original_height = _size(job / image.based_on)
        ratio, original = width / height, original_width / original_height
        record.update(based_on=image.based_on, based_on_sha256=_digest(job / image.based_on),
                      comparison={'size': [width, height], 'original_size': [original_width, original_height],
                                  'aspect_difference': round(abs(ratio - original) / original, 4)})
    return record


def provenance_reviews(facts, index: int, record: dict) -> list[dict]:
    image = facts.images[index]
    name = SOURCE_NAMES[image.origin]
    reviews = [{'section_id': 'images', 'field_path': f'images.{index}', 'code': 'AI_IMAGE_UNCONFIRMED',
                'reason': f'사진 {index + 1}은 {name} 이미지입니다({image.generator}). 승인할 때 '
                          + ('원본 사진과 나란히 보고 형태·색상·구성이 같은지 확인하세요.' if image.source == 'ai_edited'
                             else '실제 상품과 다르게 보이는 부분이 없는지 확인하세요.'),
                'detail': '', 'fact_ids': []}]
    difference = record.get('comparison', {}).get('aspect_difference', 0)
    if difference > ASPECT_TOLERANCE:
        reviews.append({'section_id': 'images', 'field_path': f'images.{index}', 'code': 'AI_IMAGE_SHAPE_SUSPECT',
                        'reason': f'사진 {index + 1}의 가로세로 비율이 원본과 {difference:.0%} 다릅니다. '
                                  '상품이 늘어나거나 잘리거나 다시 그려지지 않았는지 꼭 확인하세요.',
                        'detail': '', 'fact_ids': []})
    return reviews


def image_sources(facts) -> list[dict]:
    """Origin of every image, for manifests and the ZIP."""
    rows = []
    for index, image in enumerate(facts.images):
        row = {'index': index, 'path': image.path, 'role': image.role, 'source': image.origin}
        for key in ('based_on', 'generator', 'edit_request'):
            if getattr(image, key):
                row[key] = getattr(image, key)
        rows.append(row)
    return rows


def ai_image_items(facts) -> list[dict]:
    """The AI images a person must confirm, with what to show side by side."""
    paths = {image.path: image for image in facts.images}
    items = []
    for index, image in enumerate(facts.images):
        if image.source is None:
            continue
        original = paths[image.based_on] if image.based_on else None
        items.append({'id': f'image-{index}', 'index': index, 'source': image.source, 'role': image.role,
                      'path': image.effective_path, 'source_path': image.path,
                      'original_path': original.effective_path if original else None,
                      'based_on': image.based_on, 'generator': image.generator,
                      'edit_request': image.edit_request, 'checks': CHECKS[image.source]})
    return items


def confirmed_images(items: list[dict], confirmations: dict | None) -> list[dict]:
    """Every AI image needs every one of its checks; there is no blanket approval."""
    if not items:
        if confirmations:
            raise ValueError('확인할 AI 이미지가 없습니다.')
        return []
    confirmations = confirmations or {}
    known = {item['id'] for item in items}
    unknown = set(confirmations) - known
    if unknown:
        raise ValueError('알 수 없는 이미지 확인 항목: ' + ', '.join(sorted(unknown)))
    missing = []
    for item in items:
        required = {key for key, _ in item['checks']}
        if set(confirmations.get(item['id'], ())) != required:
            missing.append(f"사진 {item['index'] + 1}")
    if missing:
        raise ValueError('AI로 만든 이미지는 이미지마다 모든 항목을 확인해야 승인할 수 있습니다: ' + ', '.join(missing))
    at = datetime.now(timezone.utc).isoformat()
    return [{'id': item['id'], 'index': item['index'], 'source': item['source'], 'path': item['source_path'],
             **({'based_on': item['based_on']} if item['based_on'] else {}), 'generator': item['generator'],
             'checks': [key for key, _ in item['checks']], 'confirmed_at': at} for item in items]
