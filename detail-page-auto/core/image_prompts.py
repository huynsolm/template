"""M8-B copy-and-paste image prompts.

The app never sends images anywhere. The seller copies a prompt, attaches the photo in the AI
chat they subscribe to, saves the result and uploads it back with its source recorded.
"""
from pathlib import Path

from .prompting import data_block

ROOT = Path(__file__).resolve().parents[1]
BACKGROUNDS = {
    'white_studio': '흰색 스튜디오 배경. 그림자는 상품 아래에 옅게만.',
    'bright_interior': '밝고 깔끔한 실내. 배경은 흐리게(얕은 심도) 처리해 상품이 돋보이게.',
    'usage_place': '상품을 실제로 쓰는 장소. 장소는 아래 데이터의 place를 참고. 배경은 흐리게 처리.',
    'brand_tint': '브랜드 색 {brand_color}을 아주 옅게 깐 단색 배경.',
}
BACKGROUND_NAMES = {'white_studio': '흰 스튜디오', 'bright_interior': '밝은 실내',
                    'usage_place': '사용 장소', 'brand_tint': '브랜드 색 계열'}
# Only seller facts that describe the product or its use; never prices, reviews or claims.
CONTEXT_KINDS = ('feature', 'usage', 'spec')


def _context(facts, extra_key: str, extra: str) -> dict:
    data = {'product': {'name': facts.product.name, 'category': facts.product.category},
            'facts': [f.text for f in facts.facts if f.kind in CONTEXT_KINDS]}
    if extra.strip():
        data[extra_key] = extra.strip()
    return data


def background_prompt(facts, background: str, place: str = '') -> str:
    if background not in BACKGROUNDS:
        raise ValueError('배경은 ' + ', '.join(BACKGROUND_NAMES.values()) + ' 중에서 고르세요.')
    template = (ROOT / 'prompts/image_background_v1.md').read_text(encoding='utf-8')
    text = BACKGROUNDS[background].replace('{brand_color}', facts.product.brand_color)
    return template.replace('{background}', text).replace('{data}', data_block('product_context', _context(facts, 'place', place)))


def mood_prompt(facts, scene: str = '') -> str:
    template = (ROOT / 'prompts/image_mood_v1.md').read_text(encoding='utf-8')
    return (template.replace('{brand_color}', facts.product.brand_color)
            .replace('{data}', data_block('product_context', _context(facts, 'scene', scene))))
