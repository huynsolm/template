"""Validate referenced images before any browser or output work."""
from pathlib import Path
from PIL import Image, UnidentifiedImageError
from .schema import Document


def collect_images(document: Document, root: Path) -> dict[str, Path]:
    root=Path(root).resolve(strict=True)
    paths={}
    def visit(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key=='image' and item is not None:
                    paths[item]=None
                else: visit(item)
        elif isinstance(value,list):
            for item in value: visit(item)
    visit(document.model_dump())
    if len(paths)>10: raise ValueError('images: maximum 10 distinct images')
    for name in paths:
        relative=Path(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError(f'images.{name}: path traversal forbidden')
        current=root
        for part in relative.parts:
            current=current/part
            if current.is_symlink(): raise ValueError(f'images.{name}: symlink forbidden')
        try:
            path=current.resolve(strict=True)
            if not path.is_relative_to(root): raise ValueError('outside input directory')
            if not path.is_file() or path.suffix.lower() not in ('.png','.jpg','.jpeg'):
                raise ValueError('PNG/JPEG files only')
            if path.stat().st_size>10*1024*1024: raise ValueError('exceeds 10MB')
            with Image.open(path) as image:
                if image.format not in ('PNG','JPEG'): raise ValueError('PNG/JPEG content only')
                if image.width*image.height>20_000_000: raise ValueError('exceeds 20,000,000 pixels')
                image.verify()
            with Image.open(path) as image: image.load()
        except (OSError,ValueError,UnidentifiedImageError,Image.DecompressionBombError) as exc:
            raise ValueError(f'images.{name}: {exc}') from exc
        paths[name]=path
    return paths
