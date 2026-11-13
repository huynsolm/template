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


def capture(html: Path, max_height: int = 4000):
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
                page.evaluate('''async () => {
                    let timer;
                    try {
                        await Promise.race([
                            (async () => {
                                await document.fonts.load('22px DetailKorean', '한글');
                                await document.fonts.ready;
                                await Promise.all([...document.images].map(image => image.decode()));
                            })(),
                            new Promise((_, reject) => { timer = setTimeout(() => reject(new Error('asset loading timeout (15000ms)')), 15000); })
                        ]);
                    } finally { clearTimeout(timer); }
                }''')
                geometry = page.evaluate('''() => ({
                    height: Math.ceil(document.documentElement.scrollHeight),
                    horizontal_overflow: document.documentElement.scrollWidth > 860,
                    font_loaded: [...document.fonts].some(f => f.family === 'DetailKorean' && f.status === 'loaded'),
                    sections: [...document.querySelectorAll('main > section')].map(s => ({id:s.dataset.section, top:Math.ceil(s.getBoundingClientRect().top), bottom:Math.ceil(s.getBoundingClientRect().bottom)}))
                })''')
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
                geometry['browser_version'] = browser.version
                geometry['network_requests'] = network
                raw = page.screenshot(full_page=True, animations='disabled')
                return Image.open(io.BytesIO(raw)).convert('RGB'), geometry
            finally:
                browser.close()
    except BrowserError as exc:
        raise ValueError(f'Chromium asset loading/rendering failed: {exc}') from exc


def render(document: Document, image_dir: Path, output_dir: Path, max_height: int = 4000, png: bool = False, *, needs_review: bool = False, accept_review: bool = False) -> Path:
    if type(max_height) is not int or not 1 <= max_height <= 30000:
        raise ValueError('max_height must be an integer in 1..30000')
    started = time.perf_counter()
    images = collect_images(document, image_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    job = Path(tempfile.mkdtemp(prefix='.pending-', dir=output_dir))
    try:
        assets = job / 'assets'
        assets.mkdir()
        shutil.copytree(ROOT / 'assets/fonts', assets / 'fonts')
        shutil.copy(ROOT / 'templates/theme.css', assets / 'theme.css')
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
        data = rewrite(data)
        env = Environment(loader=FileSystemLoader(ROOT / 'templates'), autoescape=select_autoescape(['html']), undefined=StrictUndefined)
        (job / 'page.html').write_text(env.get_template('page.html').render(**data), encoding='utf-8')
        # The bundled JSON references bundled images, so it can be rerun with --images JOB.
        (job / 'input.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        full, geometry = capture(job / 'page.html', max_height)
        if full.width != 860 or full.height != geometry['height']:
            raise ValueError('screenshot geometry mismatch')
        cuts = [0]
        for section in geometry['sections']:
            if section['bottom'] - cuts[-1] > max_height:
                cuts.append(section['top'])
        cuts.append(full.height)
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()
        pages = []
        draft_suffix = '.DRAFT' if needs_review and not accept_review else ''
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
        manifest = {'needs_review': bool(needs_review), 'review_accepted': bool(needs_review and accept_review), 'schema_version': '1.0', 'width': 860, 'height': full.height, 'max_height': max_height,
                    'pages': pages, 'sections': geometry['sections'], 'horizontal_overflow': False,
                    'font_loaded': geometry['font_loaded'], 'network_requests': geometry['network_requests'],
                    'versions': {'python': platform.python_version(), 'chromium': geometry['browser_version'],
                                 **{name: version(name) for name in ['pydantic', 'jinja2', 'playwright', 'pillow']}},
                    'elapsed_seconds': round(time.perf_counter()-started, 3)}
        (job / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        final = job.with_name('job-' + job.name.removeprefix('.pending-'))
        job.rename(final)
        return final
    except BaseException:
        shutil.rmtree(job)
        raise
