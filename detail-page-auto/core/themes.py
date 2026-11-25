"""Validated local themes and WCAG AA foreground correction, without network IO."""
import re
import tomllib
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

THEMES_ROOT = Path(__file__).resolve().parents[1] / 'themes'
LEGACY_THEMES = ('classic', 'minimal', 'bold')
THEME_IDS = (*LEGACY_THEMES, 'modern', 'natural', 'impact', 'industrial')
DEFAULT_THEME = 'modern'
VARIANTS = {
    'hero': ('overlay', 'arch', 'poster'),
    'pain': ('cards', 'lines', 'checklist'),
    'solution': ('standard', 'quote'),
    'features': ('numbered', 'cards', 'centered'),
    'stats': ('band', 'tiles'),
    'spec': ('dark', 'card', 'plain'),
}
COLOR = r'^#[0-9a-fA-F]{6}$'
ALIGNABLE = ('pain', 'solution', 'features', 'how_to', 'faq')


class Tokens(BaseModel):
    model_config = ConfigDict(extra='forbid')
    background: str = Field(pattern=COLOR)
    alternate: str = Field(pattern=COLOR)
    hero: str = Field(pattern=COLOR)
    text: str = Field(pattern=COLOR)
    muted: str = Field(pattern=COLOR)
    border: str = Field(pattern=COLOR)
    padding_y: StrictInt = Field(ge=0, le=100)
    padding_x: StrictInt = Field(ge=0, le=100)
    font_scale: float = Field(ge=0.8, le=1.5)
    radius: StrictInt = Field(ge=0, le=100)


# Headings are 800 or heavier. A heading face whose heaviest bundled weight is lower must use
# that weight instead (user decision 2026-11-24): Black Han Sans is a single 400 display face,
# Gowun Batang ships 400 and 700 only.
HEADING_WEIGHT_CEILING = {'black-han-sans': 400, 'gowun-batang': 700}


def required_heading_weight(font_id: str) -> int:
    return min(800, HEADING_WEIGHT_CEILING.get(font_id, 900))


class TypeScale(BaseModel):
    """M8-A type hierarchy for the M6 themes (pixels)."""
    model_config = ConfigDict(extra='forbid')
    hero_head: StrictInt = Field(ge=64, le=82)
    head: StrictInt = Field(ge=40, le=52)
    item_head: StrictInt = Field(ge=26, le=40)
    sub: StrictInt = Field(ge=22)
    body: StrictInt = Field(ge=22, le=30)
    heading_weight: StrictInt = Field(ge=100, le=900)
    sub_weight: StrictInt = Field(ge=500, le=600)
    body_line_height: float = Field(ge=1.6, le=1.75)
    hero_line_height: float = Field(ge=1.2, le=1.3)

    @model_validator(mode='after')
    def hierarchy(self):
        low, high = self.head * 0.5, self.head * 0.6
        if not (low <= self.sub <= high or (self.sub == 22 and low < 22)):
            raise ValueError('type.sub must be 50-60% of type.head (22px minimum)')
        if self.item_head >= self.head:
            raise ValueError('type.item_head must be smaller than type.head')
        return self


class FontRoles(BaseModel):
    model_config = ConfigDict(extra='forbid')
    heading: str
    body: str
    display: str | None = None


class Theme(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    contrast_policy: Literal["legacy", "aa"]
    tokens: Tokens
    fonts: FontRoles | None = None
    variants: dict[str, str] = Field(default_factory=dict)
    type: TypeScale | None = None
    align: dict[str, Literal['auto', 'center', 'left']] = Field(default_factory=dict)


def validate_css(css: str, *, allow_legacy_font=True) -> None:
    # Escapes and comments can conceal tokens; bundled themes require neither.
    if re.search(r'\\|/\*|@import|https?:|//', css, re.I):
        raise ValueError('theme CSS contains forbidden external or obfuscated reference')
    for value in re.findall(r'url\s*\((.*?)\)', css, re.I | re.S):
        if not allow_legacy_font or value.strip().strip('\'"') != 'fonts/NotoSansCJK-Regular.ttc':
            raise ValueError('theme CSS permits only the bundled Korean font URL')
    if re.search(r'url\s*\(', re.sub(r'url\s*\([^)]*\)', '', css, flags=re.I), re.I):
        raise ValueError('malformed theme CSS URL')


def load_theme(theme_id: str) -> Theme:
    if theme_id not in THEME_IDS:
        raise ValueError('unknown theme id: ' + str(theme_id))
    path = THEMES_ROOT / theme_id
    theme = Theme.model_validate(tomllib.loads((path/'theme.toml').read_text(encoding='utf-8')))
    if theme.id != theme_id:
        raise ValueError('theme id does not match directory')
    expected='legacy' if theme_id=='classic' else 'aa'
    if theme.contrast_policy!=expected:
        raise ValueError('theme contrast policy does not match its compatibility mode')
    if theme_id not in LEGACY_THEMES and (theme.fonts is None or set(theme.variants) != set(VARIANTS) or theme.type is None):
        raise ValueError('new theme must specify fonts, variants and type scale')
    if theme.type and theme.type.heading_weight < required_heading_weight(theme.fonts.heading):
        raise ValueError(f'type.heading_weight must be {required_heading_weight(theme.fonts.heading)} or more')
    unknown_align = set(theme.align) - set(ALIGNABLE)
    if unknown_align:
        raise ValueError('align may only name: ' + ', '.join(ALIGNABLE))
    for kind, variant in theme.variants.items():
        if variant not in VARIANTS.get(kind, ()):
            raise ValueError(f'invalid layout: {kind}/{variant}')
    if theme.fonts:
        from .fonts import load_font
        for font_id in set(theme.fonts.model_dump(exclude_none=True).values()):
            load_font(font_id)
    validate_css((path/'theme.css').read_text(encoding='utf-8'), allow_legacy_font=theme_id in LEGACY_THEMES)
    return theme


def contrast_ratio(foreground: str, background: str) -> float:
    def luminance(color):
        if not re.fullmatch(COLOR, color):
            raise ValueError('invalid contrast color')
        channels = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
        linear = [v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4 for v in channels]
        return sum(c*w for c,w in zip(linear, (.2126,.7152,.0722)))
    a,b = sorted((luminance(foreground), luminance(background)))
    return (b+.05)/(a+.05)


def effective_brand(manifest: dict, fallback: str) -> str:
    return manifest.get('brand_color', manifest.get('resolved_colors', {}).get('brand-original', fallback))


def contrast_metadata(styles: dict) -> dict:
    """The same applied palette and policy travel with each job and snapshot."""
    return {key:styles[key] for key in (
        'contrast_policy','resolved_colors','contrast_adjustments','contrast_reviews')}


def theme_styles(theme_id: str, brand: str, policy: str | None = None) -> dict:
    """Theme CSS, variables and contrast handling. ``policy='aa'`` (design v2) applies the aa
    rules even to classic; v1 calls never pass it, so classic v1 stays legacy."""
    theme = load_theme(theme_id)
    if not re.fullmatch(COLOR, brand):
        raise ValueError('invalid brand color')
    tokens = theme.tokens.model_dump()
    css=(THEMES_ROOT/theme_id/'theme.css').read_text(encoding='utf-8')
    if theme.fonts:
        shared = (THEMES_ROOT/'design-system.css').read_text(encoding='utf-8')
        rich = (THEMES_ROOT.parent/'templates/rich.css').read_text(encoding='utf-8')
        css = rich + '\n' + shared + '\n' + css
        validate_css(css, allow_legacy_font=False)
    adjustments=[]; reviews=[]; pairs=[]
    # Classic is the original fixed stylesheet and original main --brand attribute.
    # Never derive a replacement color or change its HTML, even for poor contrast.
    if theme.contrast_policy=='legacy' and policy!='aa':
        colors={'background':'#ffffff','alternate':'#f1f6f1','hero':'#e5eee7',
                'text':'#172c2a','muted':'#465650','border':'#dce5de',
                'brand':brand,'brand-text':brand,'brand-original':brand}
        for background,minimum in [('#ffffff',3),('#f1f6f1',3),('#e5eee7',4.5)]:
            pairs.append({'token':'brand-text','foreground':brand,'background':background,'minimum':minimum})
        failed=[{**pair,'contrast_ratio':contrast_ratio(brand,pair['background'])}
                for pair in pairs if contrast_ratio(brand,pair['background'])<pair['minimum']]
        if failed:
            reviews.append({'section_id':'theme','field_path':'brand-text',
                'code':'BRAND_COLOR_LOW_CONTRAST','severity':'warning',
                'reason':'BRAND_COLOR_LOW_CONTRAST: 브랜드 색 대비가 부족합니다. classic 기존 호환 모드이므로 색을 변경하지 않았습니다.',
                'fact_ids':[],'brand_color':brand,'contrast_pairs':failed})
        return {'css':css,'variables':'--brand: '+brand,'contrast_policy':'legacy',
                'resolved_colors':colors,'contrast_adjustments':[],
                'contrast_reviews':reviews,'contrast_pairs':pairs}

    backgrounds=[tokens['background'], tokens['alternate'], tokens['hero']]
    def correct(token, original, backgrounds, minimum=4.5):
        value=original
        old=min(contrast_ratio(value,bg) for bg in backgrounds)
        if old < minimum:
            # Foregrounds only. Decorations/backgrounds never call this function.
            value=max(('#000000','#ffffff'), key=lambda c:min(contrast_ratio(c,bg) for bg in backgrounds))
            ratio=min(contrast_ratio(value,bg) for bg in backgrounds)
            adjustments.append({'token':token,'original':original,'adjusted':value,
                                'backgrounds':backgrounds,'minimum':minimum,
                                'original_contrast_ratio':old,'contrast_ratio':ratio})
            if ratio < minimum:
                reviews.append({'section_id':'theme','field_path':token,'reason':'글자색 대비 기준 미달','fact_ids':[]})
        for bg in backgrounds:
            pairs.append({'token':token,'foreground':value,'background':bg,'minimum':minimum})
        return value
    for name in ('text','muted'):
        tokens[name]=correct(name,tokens[name],backgrounds)
    accent=correct('brand-text',brand,backgrounds)
    variables={k.replace('_','-'):str(v)+('px' if k in ('padding_y','padding_x','radius') else '') for k,v in tokens.items()}
    colors={k.replace('_','-'):v for k,v in tokens.items() if isinstance(v,str) and v.startswith('#')}
    colors.update({'brand':brand,'brand-original':brand,'brand-text':accent,'brand-background':brand})
    if theme_id=='bold' or theme.fonts or policy=='aa':
        colors['on-brand']=correct('on-brand','#ffffff',[brand])
    if theme.fonts:
        colors['dark-text'] = correct('dark-text', '#ffffff', ['#172421'])
        colors['dark-surface'] = '#172421'
    variables.update(colors)
    if theme.type:
        t = theme.type
        variables.update({'type-hero-head': f'{t.hero_head}px', 'type-head': f'{t.head}px',
                          'type-item-head': f'{t.item_head}px', 'type-sub': f'{t.sub}px',
                          'type-body': f'{t.body}px', 'type-heading-weight': str(t.heading_weight),
                          'type-sub-weight': str(t.sub_weight), 'type-body-line': str(t.body_line_height),
                          'type-hero-line': str(t.hero_line_height)})
    return {'css':css,'variables':'; '.join('--'+k+': '+v for k,v in variables.items()),
            'contrast_policy':'aa','resolved_colors':colors,
            'contrast_adjustments':adjustments,'contrast_reviews':reviews,'contrast_pairs':pairs}
