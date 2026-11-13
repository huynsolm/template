"""Optional local foreground extraction. Importing this module never loads a model."""
import hashlib
import importlib.util
import os
import threading
from pathlib import Path
from typing import Protocol
from PIL import Image

MODEL_NAME = 'u2netp'
MODEL_MD5 = '8e83ca70e441ab06c318d82300c84806'
MODEL_BYTES = 4_574_861
MODEL_URL = 'https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx'
_MODEL_LOCK = threading.RLock()


class BackgroundRemover(Protocol):
    def remove(self, image: Image.Image) -> Image.Image: ...


def available() -> bool:
    """Discover optional packages without importing rembg, ONNX or model code."""
    return all(importlib.util.find_spec(name) is not None for name in ('rembg', 'onnxruntime'))


def model_directory(model_dir: Path | None = None) -> Path:
    return Path(model_dir or os.environ.get('DETAIL_PAGE_MODEL_DIR', 'outputs/models')).expanduser().resolve()


def model_paths(model_dir: Path) -> list[Path]:
    return [model_dir / 'models' / MODEL_NAME / (MODEL_NAME + '.onnx'), model_dir / MODEL_NAME / (MODEL_NAME + '.onnx'), model_dir / (MODEL_NAME + '.onnx')]


def verify_model(path: Path) -> None:
    if hashlib.md5(path.read_bytes()).hexdigest() != MODEL_MD5:
        raise RuntimeError(f'{MODEL_NAME} model checksum mismatch: {path}')


class RemBgRemover:
    cache_key = f'rembg:{MODEL_NAME}:{MODEL_MD5}'

    def __init__(self, model_dir: Path | None = None):
        self.model_dir = model_directory(model_dir)
        self._session = None

    def remove(self, image: Image.Image) -> Image.Image:
        with _MODEL_LOCK:
            if 'MODEL_CHECKSUM_DISABLED' in os.environ:
                raise RuntimeError('MODEL_CHECKSUM_DISABLED is forbidden; model checksum verification is required')
            # rembg 2.0.87 trusts existing files, so verify independently before import.
            for path in model_paths(self.model_dir):
                if path.exists(): verify_model(path)
            if not available():
                raise RuntimeError('Background removal requires the optional requirements-bg.lock dependencies')
            previous = os.environ.get('U2NET_HOME')
            os.environ['U2NET_HOME'] = str(self.model_dir)
            try:
                from onnxruntime import SessionOptions, disable_telemetry_events
                disable_telemetry_events()
                from rembg import remove, new_session
                if self._session is None:
                    # Explicitly select the Apache-2.0 U-2-Net model; never use rembg defaults.
                    options = SessionOptions()
                    options.intra_op_num_threads = 2
                    options.inter_op_num_threads = 2
                    self._session = new_session(MODEL_NAME, sess_opts=options, providers=['CPUExecutionProvider'])
                    found = [p for p in model_paths(self.model_dir) if p.is_file()]
                    if not found:
                        raise RuntimeError('Downloaded model file was not found for checksum verification')
                    for path in found: verify_model(path)
                result = remove(image.convert('RGBA'), session=self._session)
                if not isinstance(result, Image.Image):
                    raise RuntimeError('Background remover returned an invalid image')
                return result.convert('RGBA')
            except Exception as exc:
                raise RuntimeError(f'Local background removal failed ({type(exc).__name__}); check installation, model cache and network availability') from None
            finally:
                if previous is None: os.environ.pop('U2NET_HOME', None)
                else: os.environ['U2NET_HOME'] = previous


def get_remover(model_dir: Path | None = None) -> BackgroundRemover:
    return RemBgRemover(model_dir)
