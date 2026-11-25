"""M8-C: brand colour candidates from the product photos.

Only suggestions: nothing changes until the seller picks one. The background is estimated from
each photo's edge band and left out, near-white/black/grey colours are not accent candidates, and
the result is deterministic (same photos → same candidates in the same order). Fully AI-generated
pictures are never used. Photos are read, never modified.
"""
import colorsys
import hashlib
from pathlib import Path

from PIL import Image, ImageOps

VERSION = 'colors-3'
SAMPLE_EDGE = 240        # photos are reduced to this size before counting colours
EDGE_BAND = 0.06         # share of width/height treated as background evidence
BACKGROUND_DISTANCE = 48 # RGB distance within which a pixel counts as background
MAX_CANDIDATES = 5


def _hex(rgb) -> str:
    return '#%02x%02x%02x' % tuple(int(v) for v in rgb[:3])


def _distance(a, b) -> float:
    return sum((x - y) ** 2 for x, y in zip(a[:3], b[:3])) ** 0.5


def _neutral(rgb) -> bool:
    h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in rgb[:3]))
    return s < 0.18 or l > 0.92 or l < 0.08


def _pixels(path: Path) -> list[tuple]:
    """Foreground pixels of one photo.

    With transparency (alpha channel or a transparent palette entry), the opaque pixels are the
    foreground and the colour hidden under fully transparent pixels is never read: RGBA is resized
    with premultiplied alpha, and no background is estimated. Without transparency, the most
    common colours of the edge band are taken as background and left out."""
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image)
        transparent = image.mode in ('RGBA', 'LA', 'PA') or 'transparency' in image.info
        if transparent:
            # Only an alpha channel that actually hides something is a foreground mask.
            image = image.convert('RGBA')
            transparent = image.getchannel('A').getextrema()[0] < 255
        image = image.convert('RGBA' if transparent else 'RGB')
        image.thumbnail((SAMPLE_EDGE, SAMPLE_EDGE), Image.Resampling.BOX)
    if transparent:
        raw = image.tobytes()
        return [tuple(raw[i:i + 3]) for i in range(0, len(raw), 4) if raw[i + 3] > 128]
    width, height = image.size
    band_x, band_y = max(1, int(width * EDGE_BAND)), max(1, int(height * EDGE_BAND))
    raw = image.tobytes()
    data = [tuple(raw[i:i + 3]) for i in range(0, len(raw), 3)]
    edge = [data[y * width + x] for y in range(height) for x in range(width)
            if x < band_x or x >= width - band_x or y < band_y or y >= height - band_y]
    counts = {}
    for color in edge:
        key = tuple(v // 16 * 16 + 8 for v in color)
        counts[key] = counts.get(key, 0) + 1
    backgrounds = [color for color, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3] if n >= len(edge) * 0.1]
    return [color for color in data if not any(_distance(color, bg) < BACKGROUND_DISTANCE for bg in backgrounds)]


def suggest_colors(paths: list[Path], themes: tuple[str, ...] | None = None) -> list[dict]:
    """Up to five accent candidates with share, contrast on white and per-theme contrast handling."""
    from .themes import THEME_IDS, contrast_ratio, theme_styles
    pixels = []
    for path in paths:
        pixels += _pixels(Path(path))
    if not pixels:
        return []
    sample = Image.new('RGB', (len(pixels), 1))
    sample.putdata(pixels)
    palette = sample.quantize(colors=12, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    colors = palette.getpalette()[:12 * 3]
    counts = sorted(palette.getcolors() or [], key=lambda c: (-c[0], c[1]))
    total = len(pixels)
    candidates = []
    for count, index in counts:
        rgb = tuple(colors[index * 3:index * 3 + 3])
        if _neutral(rgb) or count < total * 0.02:
            continue
        if any(_distance(rgb, other['rgb']) < 40 for other in candidates):
            continue
        candidates.append({'rgb': rgb, 'share': count / total})
        if len(candidates) == MAX_CANDIDATES:
            break
    result = []
    for candidate in candidates:
        color = _hex(candidate['rgb'])
        handling = {}
        for theme in themes or THEME_IDS:
            styles = theme_styles(theme, color)
            handling[theme] = ('warning' if styles['contrast_reviews'] else
                               'adjusted' if styles['contrast_adjustments'] else 'ok')
        result.append({'color': color, 'share': round(candidate['share'], 3),
                       'contrast_on_white': round(contrast_ratio(color, '#ffffff'), 2), 'themes': handling})
    return result


def photo_paths(facts, root: Path) -> list[Path]:
    """Representative photo first; real photos and background-changed photos only (never generated)."""
    usable = [image for image in facts.images if image.source != 'ai_generated']
    usable.sort(key=lambda image: (image.role != 'hero',))
    return [Path(root) / image.effective_path for image in usable]


def color_record(facts, root: Path) -> dict:
    paths = photo_paths(facts, root)
    return {'version': VERSION, 'photos': [hashlib.sha256(p.read_bytes()).hexdigest() for p in paths],
            'candidates': suggest_colors(paths)}


def job_color_suggestions(job: Path) -> dict:
    """The job's candidates, computed once and kept in its manifest (``color_suggestions``)."""
    import json
    from .facts import ProductFacts
    job = Path(job)
    manifest = json.loads((job / 'manifest.json').read_text(encoding='utf-8'))
    facts = ProductFacts.model_validate_json((job / 'facts.json').read_text(encoding='utf-8'))
    record = color_record(facts, job)
    if manifest.get('color_suggestions') != record:
        manifest['color_suggestions'] = record
        temporary = job / 'manifest.json.tmp'
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temporary.replace(job / 'manifest.json')
    return record


def swatch(color: str, size=(72, 36)) -> Image.Image:
    return Image.new('RGB', size, color)
