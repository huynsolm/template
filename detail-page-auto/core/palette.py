"""Design v2 colour schemes: solid, same-family gradient (tone) or two-colour gradient (duo).

The secondary colours are computed from the seller's brand colour unless a secondary colour is
given (advanced setting). Gradients are used only in a few places: the first screen and the key
message. Tables, long text and the purchase notice keep plain backgrounds, and photos are never
recoloured. Wherever text sits on a gradient, contrast is checked along the whole gradient
(start, end and every point between); if the lowest value misses the minimum, the text colour or
the gradient is adjusted. The brand colour as entered is always kept in the record.
"""
import colorsys

from .themes import contrast_ratio

MODES = ('solid', 'tone', 'duo')
MODE_NAMES = {'solid': '단색', 'tone': '같은 계열 그라데이션', 'duo': '두 색 그라데이션'}
THEME_DEFAULT_MODE = {'classic': 'tone', 'minimal': 'tone', 'natural': 'tone', 'industrial': 'tone',
                      'bold': 'duo', 'modern': 'duo', 'impact': 'duo'}
VERSION = 'palette-1'
MINIMUM = 4.5
SAMPLES = 21   # points checked along each gradient, ends included


def _rgb(color: str) -> tuple[float, float, float]:
    return tuple(int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))


def _hex(rgb) -> str:
    return '#%02x%02x%02x' % tuple(round(min(1, max(0, v)) * 255) for v in rgb)


def shift(color: str, hue=0.0, light=0.0, saturation=0.0) -> str:
    h, l, s = colorsys.rgb_to_hls(*_rgb(color))
    return _hex(colorsys.hls_to_rgb((h + hue) % 1, min(1, max(0, l + light)), min(1, max(0, s + saturation))))


def mix(a: str, b: str, t: float) -> str:
    """The colour a CSS linear-gradient draws at position t (sRGB interpolation)."""
    return _hex(tuple(x + (y - x) * t for x, y in zip(_rgb(a), _rgb(b))))


def lowest_contrast(text: str, stops: list[str]) -> float:
    """Lowest contrast of the text colour over the whole gradient, midpoints included."""
    points = [mix(stops[0], stops[-1], i / (SAMPLES - 1)) for i in range(SAMPLES)] if len(stops) > 1 else stops
    return min(contrast_ratio(text, point) for point in points)


def secondary_colors(brand: str, secondary: str | None = None) -> dict:
    """Colours derived from the brand colour; a given secondary replaces the computed partner."""
    return {'light': shift(brand, light=0.07), 'deep': shift(brand, light=-0.13),
            'partner': secondary or shift(brand, hue=0.15, light=-0.03, saturation=0.08),
            'tint': shift(brand, light=0.55, saturation=-0.15)}


def _fit(area: str, text: str, stops: list[str], adjustments: list, checks: list, minimum=MINIMUM):
    """Make the text readable over the gradient: first the other text colour, then darken or
    lighten the gradient a step at a time. Returns (text, stops)."""
    original_text, original_stops = text, list(stops)
    ratio = lowest_contrast(text, stops)
    if ratio < minimum:
        other = '#ffffff' if text.lower() != '#ffffff' else '#111111'
        if lowest_contrast(other, stops) >= minimum:
            text = other
        else:
            step = -0.03 if contrast_ratio(text, '#000000') > contrast_ratio(text, '#ffffff') else 0.03
            for _ in range(20):
                stops = [shift(color, light=step) for color in stops]
                if lowest_contrast(text, stops) >= minimum:
                    break
        ratio = lowest_contrast(text, stops)
        adjustments.append({'area': area, 'text': [original_text, text], 'stops': [original_stops, stops],
                            'contrast_ratio': round(ratio, 2)})
    checks.append({'area': area, 'text': text, 'stops': stops, 'lowest_contrast': round(ratio, 2),
                   'minimum': minimum, 'samples': SAMPLES if len(stops) > 1 else 1})
    return text, stops


def color_scheme(theme_id: str, brand: str, colors: dict, mode: str | None = None, secondary: str | None = None) -> dict:
    """The colour scheme of one v2 render: CSS variables and the record for the manifest.

    ``colors`` are the theme's resolved colours (background, alternate, text, on-brand, ...)."""
    import re
    mode = mode or THEME_DEFAULT_MODE[theme_id]
    if secondary is not None and not re.fullmatch(r'#[0-9a-fA-F]{6}', secondary):
        raise ValueError('secondary color must be #RRGGBB')
    if mode not in MODES:
        raise ValueError('color mode must be one of ' + ', '.join(MODES))
    secondary = secondary.lower() if secondary else None
    derived = secondary_colors(brand, secondary)
    adjustments, checks, gradients, variables = [], [], {}, {}
    on_brand = colors.get('on-brand', '#ffffff')
    if mode == 'solid':
        key = [brand]
    elif mode == 'tone':
        key = [derived['light'], derived['deep']]
    else:
        key = [brand, derived['partner']]
    text, key = _fit('key-message', on_brand, key, adjustments, checks)
    gradients['key-message'] = key
    variables['key-bg'] = key[0] if len(key) == 1 else f'linear-gradient(120deg, {key[0]} 0%, {key[-1]} 100%)'
    variables['on-key'] = text
    if mode != 'solid':
        # Behind the photo only (no text): a soft tint, photos themselves are untouched.
        panel = [derived['tint'], colors['background']]
        gradients['hero-photo-panel'] = panel
        variables['hero-panel-bg'] = f'linear-gradient(170deg, {panel[0]} 0%, {panel[1]} 100%)'
    if theme_id == 'bold':
        band = [colors['text']] if mode == 'solid' else [colors['text'], derived['deep'] if mode == 'tone' else shift(derived['partner'], light=-0.12)]
        band_text, band = _fit('hero-copy', colors['background'], band, adjustments, checks)
        gradients['hero-copy'] = band
        variables['hero-band-bg'] = band[0] if len(band) == 1 else f'linear-gradient(135deg, {band[0]} 0%, {band[-1]} 100%)'
        variables['on-hero-band'] = band_text
        stats = [brand] if mode == 'solid' else ([derived['light'], derived['deep']] if mode == 'tone' else [brand, derived['partner']])
        stats_text, stats = _fit('key-specs', on_brand, stats, adjustments, checks)
        gradients['key-specs'] = stats
        variables['stats-band-bg'] = stats[0] if len(stats) == 1 else f'linear-gradient(120deg, {stats[0]} 0%, {stats[-1]} 100%)'
        variables['on-stats-band'] = stats_text
    if theme_id == 'impact':
        band = [colors['alternate']] if mode == 'solid' else [colors['alternate'], shift(colors['alternate'], hue=-0.05, light=-0.07, saturation=0.1)]
        band_text, band = _fit('hero-copy', colors['text'], band, adjustments, checks)
        gradients['hero-copy'] = band
        variables['hero-band-bg'] = band[0] if len(band) == 1 else f'linear-gradient(135deg, {band[0]} 0%, {band[-1]} 100%)'
        variables['on-hero-band'] = band_text
    record = {'version': VERSION, 'mode': mode, 'mode_default': THEME_DEFAULT_MODE[theme_id],
              'brand_original': brand, 'secondary_source': 'manual' if secondary else 'auto',
              'secondary': {k: v for k, v in derived.items()}, 'gradients': gradients,
              'contrast_checks': checks, 'contrast_adjustments': adjustments}
    return {'variables': '; '.join(f'--{k}: {v}' for k, v in variables.items()), 'record': record}


def color_args(manifest: dict) -> dict:
    """The job's colour settings as render arguments (absent: theme default mode, auto secondary)."""
    return {'color_mode': manifest.get('color_mode'), 'secondary_color': manifest.get('secondary_color')}


def color_matches(snapshot: dict, current: dict) -> bool:
    """A v2 snapshot is reusable only if it was drawn with the job's current colour settings."""
    record = snapshot.get('color_scheme')
    if record is None:
        return False
    theme = current.get('theme', 'classic')
    mode = current.get('color_mode') or THEME_DEFAULT_MODE[theme]
    secondary = current.get('secondary_color')
    drawn = record['secondary']['partner'] if record['secondary_source'] == 'manual' else None
    return record['mode'] == mode and (drawn or None) == (secondary.lower() if secondary else None) and record.get('version') == VERSION
