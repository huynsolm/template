"""Validated local themes and WCAG AA foreground correction, without network IO."""
import re
import tomllib
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictInt

THEMES_ROOT = Path(__file__).resolve().parents[1] / 'themes'
THEME_IDS = ('classic', 'minimal', 'bold')
COLOR = r'^#[0-9a-fA-F]{6}$'


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


class Theme(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    contrast_policy: Literal["legacy", "aa"]
    tokens: Tokens


def validate_css(css: str) -> None:
    # Escapes and comments can conceal tokens; bundled themes require neither.
    if re.search(r'\\|/\*|@import|https?:|//', css, re.I):
        raise ValueError('theme CSS contains forbidden external or obfuscated reference')
    for value in re.findall(r'url\s*\((.*?)\)', css, re.I | re.S):
        if value.strip().strip('\'"') != 'fonts/NotoSansCJK-Regular.ttc':
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
    validate_css((path/'theme.css').read_text(encoding='utf-8'))
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


def contrast_metadata(styles: dict) -> dict:
    """The same applied palette and policy travel with each job and snapshot."""
    return {key:styles[key] for key in (
        'contrast_policy','resolved_colors','contrast_adjustments','contrast_reviews')}


def theme_styles(theme_id: str, brand: str) -> dict:
    theme = load_theme(theme_id)
    if not re.fullmatch(COLOR, brand):
        raise ValueError('invalid brand color')
    tokens = theme.tokens.model_dump()
    css=(THEMES_ROOT/theme_id/'theme.css').read_text(encoding='utf-8')
    adjustments=[]; reviews=[]; pairs=[]
    # Classic is the original fixed stylesheet and original main --brand attribute.
    # Never derive a replacement color or change its HTML, even for poor contrast.
    if theme.contrast_policy=='legacy':
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
    if theme_id=='bold':
        colors['on-brand']=correct('on-brand','#ffffff',[brand])
    variables.update(colors)
    return {'css':css,'variables':'; '.join('--'+k+': '+v for k,v in variables.items()),
            'contrast_policy':'aa','resolved_colors':colors,
            'contrast_adjustments':adjustments,'contrast_reviews':reviews,'contrast_pairs':pairs}
