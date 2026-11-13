"""Verify a relocated sample, reporting direct file:// separately from capture."""
import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

from PIL import Image, ImageChops
from playwright.sync_api import sync_playwright, Error as BrowserError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.render import capture, chromium_path


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ('src', 'href') and value:
                self.urls.append(value)


def validate_expected_geometry(sample: Path, manifest: dict, image_size, geometry: dict):
    """Committed PNGs are a geometry fixture, not a rasterizer fingerprint."""
    assert image_size == (manifest['width'], manifest['height'])
    assert geometry['height'] == manifest['height']
    assert geometry['sections'] == manifest['sections']
    cuts = [0]
    for section in geometry['sections']:
        if section['bottom'] - cuts[-1] > manifest['max_height']:
            cuts.append(section['top'])
    cuts.append(image_size[1])
    assert len(manifest['pages']) == len(cuts)-1
    for part, top, bottom in zip(manifest['pages'], cuts, cuts[1:]):
        assert (part['top'], part['bottom']) == (top, bottom)
        assert (part['width'], part['height']) == (image_size[0], bottom-top)
        with Image.open(sample / part['png']) as png:
            assert png.size == (part['width'], part['height'])


def check(source: Path):
    with tempfile.TemporaryDirectory(prefix='m1-portability-') as temporary:
        copied = Path(temporary) / 'original'
        shutil.copytree(source, copied)
        font = copied / 'assets/fonts/NotoSansCJK-Regular.ttc'
        if not font.exists():
            shutil.copyfile(ROOT / 'assets/fonts/NotoSansCJK-Regular.ttc', font)
        before_image, before_geometry = capture(copied / 'page.html')
        moved = Path(temporary) / '다른 경로 with spaces'
        shutil.move(copied, moved)
        html = moved / 'page.html'
        original_bytes = (source / 'page.html').read_bytes()
        assert html.read_bytes() == original_bytes
        references = References()
        references.feed(html.read_text(encoding='utf-8'))
        checked = []
        def resolve(base, url):
            assert not urlparse(url).scheme and not url.startswith('/'), url
            path = (base / unquote(url)).resolve()
            assert path.is_relative_to(moved) and path.is_file(), url
            checked.append(str(path.relative_to(moved)))
            return path
        for url in references.urls:
            path = resolve(moved, url)
            if path.suffix == '.css':
                for asset in re.findall(r'url\([\'\"]?([^\)\'\"]+)[\'\"]?\)', path.read_text()):
                    resolve(path.parent, asset)
        image, geometry = capture(html)
        manifest = json.loads((moved / 'manifest.json').read_text())
        assert image.size == before_image.size
        assert geometry['sections'] == before_geometry['sections']
        assert ImageChops.difference(image, before_image).getbbox() is None
        validate_expected_geometry(moved, manifest, image.size, geometry)
        direct = {}
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=chromium_path(pw.chromium.executable_path))
            try:
                context = browser.new_context(offline=True, viewport={'width': 860, 'height': 1})
                page = context.new_page()
                page.set_default_timeout(15000)
                try:
                    page.goto(html.as_uri(), wait_until='load')
                    page.evaluate("async () => { await document.fonts.load('22px DetailKorean', '한글'); await document.fonts.ready; await Promise.all([...document.images].map(i => i.decode())); }")
                    state = page.evaluate("() => ({images: [...document.images].every(i => i.complete && i.naturalWidth > 0), font: [...document.fonts].some(f => f.family === 'DetailKorean' && f.status === 'loaded')})")
                    assert state['images'] and state['font']
                    direct = {'status': 'passed', **state}
                except BrowserError as exc:
                    if 'ERR_BLOCKED_BY_ADMINISTRATOR' not in str(exc):
                        raise
                    direct = {'status': 'blocked_by_browser_policy', 'error': 'net::ERR_BLOCKED_BY_ADMINISTRATOR'}
            finally:
                browser.close()
        return {
            'html_unchanged': True,
            'html_sha256': hashlib.sha256(original_bytes).hexdigest(),
            'relative_assets': checked,
            'relative_assets_exist': True,
            'expected_geometry_matches': True,
            'relocated_capture': {
                'status': 'passed', 'font_loaded': geometry['font_loaded'],
                'width': image.width, 'height': image.height,
                'pixel_identical_before_after_move': True,
                'external_requests': geometry['network_requests'],
            },
            'direct_file_url': direct,
        }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--sample', type=Path, default=ROOT / 'samples/expected')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = check(args.sample.resolve())
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.report:
        args.report.write_text(encoded, encoding='utf-8')
    print(encoded, end='')
