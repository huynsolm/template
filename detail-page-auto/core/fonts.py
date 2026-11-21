"""Offline font packages shipped with the application."""
from dataclasses import dataclass
from pathlib import Path
import re
import shutil

FONT_ROOT = Path(__file__).resolve().parents[1] / 'assets/font-library'


@dataclass(frozen=True)
class Font:
    id: str
    family: str
    css: Path
    license: Path
    files: tuple[Path, ...]

    def bundle(self, destination: Path) -> None:
        target = destination / self.id
        target.mkdir()
        for path in (self.css, self.license, *self.files):
            shutil.copyfile(path, target / path.name)


def load_font(font_id: str) -> Font:
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', font_id):
        raise ValueError('invalid font id')
    folder = FONT_ROOT / font_id
    css, license_path = folder / 'fonts.css', folder / 'LICENSE.txt'
    if folder.is_symlink() or not all(p.is_file() and not p.is_symlink() for p in (css, license_path)):
        raise ValueError(f'{font_id}: missing fonts.css or LICENSE.txt')
    text = re.sub(r'/\*.*?\*/', '', css.read_text(encoding='utf-8'), flags=re.S)
    faces = re.findall(r'@font-face\s*\{([^{}]+)\}', text)
    remainder = re.sub(r'@font-face\s*\{[^{}]+\}', '', text).strip()
    if not faces or remainder or re.search(r'\\|local\s*\(', text, re.I):
        raise ValueError(f'{font_id}: invalid font CSS')
    families = set()
    files = set()
    for face in faces:
        family = re.search(r"""font-family:\s*(['"])([\w -]+)\1""", face)
        urls = re.findall(r'url\s*\(([^()]*)\)', face, re.I)
        if not family or not urls or len(urls) != len(re.findall(r'url\s*\(', face, re.I)):
            raise ValueError(f'{font_id}: invalid font face')
        families.add(family[2])
        for value in urls:
            match = re.fullmatch(r"""(['"]?)(?:\./)?([\w-]+\.woff2)\1""", value.strip(), re.ASCII)
            if not match:
                raise ValueError(f'{font_id}: only local WOFF2 files are allowed')
            path = folder / match[2]
            if not path.is_file() or path.is_symlink():
                raise ValueError(f'{font_id}: missing font file {match[2]}')
            files.add(path)
    if len(families) != 1:
        raise ValueError(f'{font_id}: expected one font family')
    return Font(font_id, families.pop(), css, license_path, tuple(sorted(files)))
