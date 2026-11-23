"""Offline HTML rendering and section-boundary image export."""
import io
import json
import mimetypes
import os
import platform
import shutil
import tempfile
import time
from importlib.metadata import version
from pathlib import Path
from urllib.parse import unquote, urlparse

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape
from PIL import Image, ImageCms
from playwright.sync_api import sync_playwright, Error as BrowserError

from .collect import collect_images
from .schema import Document

ROOT = Path(__file__).resolve().parents[1]


def chromium_path(playwright_default):
    explicit = os.environ.get('M1_CHROMIUM_PATH')
    if explicit:
        return explicit
    if Path(playwright_default).is_file():
        return playwright_default
    bundled = Path('/opt/pw-browsers/chromium')
    for candidate in [bundled, bundled / 'chrome-linux/chrome', bundled / 'chrome-linux64/chrome']:
        if candidate.is_file():
            return str(candidate)
    return shutil.which('chromium')


def capture(html: Path, max_height: int = 4000, families=('DetailKorean',), *, top_only=False, measure=None):
    """Load only this export's files, await assets, and return image + geometry."""
    html = Path(html).resolve()
    network = []
    failures = []
    try:
        with sync_playwright() as pw:
            executable = chromium_path(pw.chromium.executable_path)
            browser = pw.chromium.launch(executable_path=executable, headless=True)
            try:
                context = browser.new_context(viewport={'width': 860, 'height': 1}, device_scale_factor=1, service_workers='block', offline=True)
                page = context.new_page()
                page.set_default_timeout(15000)
                def route(request_route):
                    url = request_route.request.url
                    parsed = urlparse(url)
                    local_path = (html.parent / unquote(parsed.path).lstrip('/')).resolve()
                    allowed = parsed.scheme == 'http' and parsed.netloc == '127.0.0.1:18600' and local_path.is_relative_to(html.parent) and local_path.is_file()
                    if allowed:
                        request_route.fulfill(body=local_path.read_bytes(), content_type=mimetypes.guess_type(str(local_path))[0] or 'application/octet-stream')
                    else:
                        network.append(url)
                        request_route.abort()
                page.route('**/*', route)
                page.on('requestfailed', lambda r: failures.append(r.url))
                # Virtual loopback origin: requests are fulfilled from disk; no socket is opened.
                page.goto('http://127.0.0.1:18600/page.html', wait_until='load')
                page.evaluate('''async (families) => {
                    let timer;
                    try {
                        await Promise.race([
                            (async () => {
                                await Promise.all(families.map(family =>
                                    document.fonts.load('22px "' + family + '"', '한글Aa012')));
                                await document.fonts.ready;
                                await Promise.all([...document.images].map(image => image.decode()));
                            })(),
                            new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('asset loading timeout (15000ms)')), 15000); })
                        ]);
                    } finally { clearTimeout(timer); }
                }''', families)
                # M8-A layout script (new themes) sets alignment after fonts load; wait for it.
                page.evaluate('''async () => {
                    if (!document.querySelector('script[src="assets/layout.js"]')) return;
                    const start = Date.now();
                    while (!document.documentElement.hasAttribute('data-layout-done')) {
                        if (Date.now() - start > 15000) throw new Error('layout script timeout');
                        await new Promise(resolve => setTimeout(resolve, 20));
                    }
                }''')
                geometry = page.evaluate('''families => ({
                    height: Math.ceil(document.documentElement.scrollHeight),
                    horizontal_overflow: document.documentElement.scrollWidth > 860,
                    font_loaded: families.every(name => [...document.fonts].some(f => f.family === name && f.status === 'loaded')),
                    sections: [...document.querySelectorAll('main > section')].map(s => ({id:s.dataset.section, top:Math.ceil(s.getBoundingClientRect().top), bottom:Math.ceil(s.getBoundingClientRect().bottom)}))
                })''', families)
                if failures or network:
                    raise ValueError(f'asset loading failed or forbidden request: {failures + network}')
                if not geometry['font_loaded']:
                    raise ValueError('local Korean font failed to load')
                if geometry['height'] > 30000:
                    raise ValueError('page exceeds 30,000px')
                if geometry['horizontal_overflow']:
                    raise ValueError('horizontal overflow exceeds 860px')
                for section in geometry['sections']:
                    if section['bottom'] - section['top'] > max_height:
                        raise ValueError(f"section {section['id']} exceeds maximum height {max_height}")
                if measure is not None:
                    from .measure import MEASURE_JS
                    geometry['copy_metrics'] = page.evaluate(MEASURE_JS, measure)
                geometry['browser_version'] = browser.version
                geometry['network_requests'] = network
                if top_only:
                    page.set_viewport_size({'width': 860, 'height': min(1800, geometry['height'])})
                raw = page.screenshot(full_page=not top_only, animations='disabled')
                return Image.open(io.BytesIO(raw)).convert('RGB'), geometry
            finally:
                browser.close()
    except BrowserError as exc:
        raise ValueError(f'Chromium asset loading/rendering failed: {exc}') from exc


def render(document: Document, image_dir: Path, output_dir: Path, max_height: int = 4000, png: bool = False, *, needs_review: bool = False, accept_review: bool = False, force_draft: bool = False, theme: str = "classic", brand_color: str | None = None, thumbnail: bool = False) -> Path | bytes:
    if type(max_height) is not int or not 1 <= max_height <= 30000:
        raise ValueError('max_height must be an integer in 1..30000')
    from .themes import theme_styles, contrast_metadata, load_theme
    from .fonts import load_font
    brand = brand_color if brand_color is not None else document.product.brand_color
    styles = theme_styles(theme, brand)
    design = load_theme(theme)
    roles = {role: load_font(font_id) for role, font_id in
             (design.fonts.model_dump(exclude_none=True) if design.fonts else {}).items()}
    fonts = {font.id: font for font in roles.values()}
    needs_review = bool(needs_review or styles['contrast_reviews'])
    started = time.perf_counter()
    images = collect_images(document, image_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    job = Path(tempfile.mkdtemp(prefix='.pending-', dir=output_dir))
    try:
        assets = job / 'assets'
        assets.mkdir()
        css = styles['css']
        variables = styles['variables']
        if fonts:
            (assets / 'fonts').mkdir()
            for font in fonts.values():
                font.bundle(assets / 'fonts')
            variables += ''.join(f'; --font-{role}: "{font.family}"' for role, font in roles.items())
        else:
            shutil.copytree(ROOT / 'assets/fonts', assets / 'fonts')
            if document.schema_version == '1.1':
                css += '\n' + (ROOT / 'templates/rich.css').read_text(encoding='utf-8')
        if document.schema_version == '1.1':
            shutil.copyfile(ROOT/'templates/fit-stats.js', assets/'fit-stats.js')
        (assets / 'theme.css').write_text(css, encoding='utf-8')
        mapping = {}
        for index, (name, source) in enumerate(images.items()):
            target = f'assets/image-{index:03}{source.suffix.lower()}'
            shutil.copyfile(source, job / target)
            mapping[name] = target
        data = document.model_dump(exclude_none=True)
        def rewrite(value):
            if isinstance(value, dict):
                return {key: mapping[item] if key == 'image' else rewrite(item) for key, item in value.items()}
            if isinstance(value, list): return [rewrite(item) for item in value]
            return value
        data['product']['brand_color'] = brand
        data = rewrite(data)
        env = Environment(loader=FileSystemLoader(ROOT / 'templates'), autoescape=select_autoescape(['html']), undefined=StrictUndefined)
        from .themes import ALIGNABLE
        (job / 'page.html').write_text(env.get_template('page.html').render(**data, theme_variables=variables, contrast_policy=styles['contrast_policy'], fonts=fonts.values(), variants=design.variants, align=design.align, alignable=ALIGNABLE), encoding='utf-8')
        if design.variants:
            shutil.copyfile(ROOT/'templates/layout.js', assets/'layout.js')
        # The bundled JSON references bundled images, so it can be rerun with --images JOB.
        (job / 'input.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        families = [font.family for font in fonts.values()] or ['DetailKorean']
        from .measure import measure_spec, annotate, copy_reviews, MEASURE_VERSION
        spec = None if thumbnail else measure_spec()
        full, geometry = (capture(job / 'page.html', max_height, families, top_only=thumbnail, measure=spec)
                          if fonts or thumbnail else capture(job / 'page.html', max_height, measure=spec))
        if thumbnail:
            full.thumbnail((270, 570), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            full.save(buffer, format='PNG')
            shutil.rmtree(job)
            return buffer.getvalue()
        if full.width != 860 or full.height != geometry['height']:
            raise ValueError('screenshot geometry mismatch')
        metrics = annotate(geometry.get('copy_metrics', []))
        measured = copy_reviews(metrics, document)
        # M8-A rules apply to the M6 themes. Legacy themes only report measurements,
        # so their review state, file names and pixels stay as before.
        enforce_copy_rules = design.type is not None
        reviews_copy = measured if enforce_copy_rules else []
        needs_review = bool(needs_review or reviews_copy)
        cuts = [0]
        for section in geometry['sections']:
            if section['bottom'] - cuts[-1] > max_height:
                cuts.append(section['top'])
        cuts.append(full.height)
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
        pages = []
        draft_suffix = '.DRAFT' if (force_draft or needs_review) and not accept_review else ''
        for index, (top, bottom) in enumerate(zip(cuts, cuts[1:]), 1):
            if not 0 < bottom-top <= max_height:
                raise ValueError('output page exceeds maximum height or is empty')
            crop = full.crop((0, top, 860, bottom))
            filename = f'page-{index:03}{draft_suffix}.jpg'
            crop.save(job / filename, quality=90, icc_profile=profile)
            item = {'file': filename, 'width': 860, 'height': bottom-top, 'top': top, 'bottom': bottom}
            if png:
                item['png'] = f'page-{index:03}{draft_suffix}.png'
                crop.save(job / item['png'], icc_profile=profile)
            pages.append(item)
        manifest = {'theme': theme, **contrast_metadata(styles), 'needs_review': bool(needs_review), 'review_accepted': bool(accept_review), 'schema_version': document.schema_version, 'brand_color': brand,
                    'fonts': [{'id':font.id, 'family':font.family} for font in fonts.values()] or [{'id':'noto-sans-cjk','family':'DetailKorean'}], 'width': 860, 'height': full.height, 'max_height': max_height,
                    'pages': pages, 'sections': geometry['sections'], 'horizontal_overflow': False,
                    'copy_metrics': metrics, 'copy_reviews': reviews_copy,
                    'copy_rules_enforced': enforce_copy_rules, 'copy_measure_version': MEASURE_VERSION,
                    **({} if enforce_copy_rules else {'copy_reviews_informational': measured}),
                    'font_loaded': geometry['font_loaded'], 'network_requests': geometry['network_requests'],
                    'versions': {'python': platform.python_version(), 'chromium': geometry['browser_version'],
                                 **{name: version(name) for name in ['pydantic', 'jinja2', 'playwright', 'pillow']}},
                    'elapsed_seconds': round(time.perf_counter()-started, 3)}
        (job / 'review.json').write_text(json.dumps(styles['contrast_reviews'] + reviews_copy, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (job / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        final = job.with_name('job-' + job.name.removeprefix('.pending-'))
        job.rename(final)
        return final
    except BaseException:
        shutil.rmtree(job)
        raise
