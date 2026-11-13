#!/usr/bin/env python3
"""Manual local model smoke check. Never called by the automated test suite."""
import argparse
from pathlib import Path
import resource
import sys
import time
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw
from core.background import available, get_remover, model_directory, model_paths, verify_model, MODEL_NAME, MODEL_BYTES
from core.images import process_image


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-dir',type=Path)
    parser.add_argument('--output',type=Path,default=Path('outputs/bg-check'))
    parser.add_argument('--download-model',action='store_true',help='Permit the initial official u2netp model download (4,574,861 bytes)')
    args=parser.parse_args(argv)
    if not available():
        print('FAILED: optional rembg/onnxruntime dependencies are not installed.',file=sys.stderr)
        return 1
    directory=model_directory(args.model_dir)
    existing=[path for path in model_paths(directory) if path.is_file()]
    if not existing and not args.download_model:
        print('FAILED: u2netp model is missing. Supply --download-model to permit its initial official download.',file=sys.stderr)
        return 1
    try:
        for path in existing: verify_model(path)
        args.output.mkdir(parents=True,exist_ok=True)
        run=Path(tempfile.mkdtemp(prefix='run-',dir=args.output))
        source=run/'original-generated.png'
        # Original drawing made locally with Pillow: no external photo or service.
        image=Image.new('RGB',(900,900),'#e8edf2')
        draw=ImageDraw.Draw(image)
        draw.rounded_rectangle((260,150,640,750),radius=35,fill='#3485ab',outline='#15384d',width=8)
        draw.rectangle((300,320,600,560),fill='white')
        draw.text((365,425),'LOCAL SAMPLE',fill='#15384d')
        image.save(source)
        start=time.perf_counter()
        result=process_image(source,run,{'remove_background':True},'#3485ab',get_remover(directory))
        elapsed=time.perf_counter()-start
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
        print(f'elapsed_seconds={elapsed:.3f} peak_rss_mib={rss:.1f}')
        if not result.metadata['background_removed']:
            for review in result.reviews: print(review['message'],file=sys.stderr)
            print('FAILED: model did not produce a foreground; normalized image retained.',file=sys.stderr)
            return 1
        print(f'OK: model={MODEL_NAME} model_bytes={MODEL_BYTES}')
        print(f'original={source}\nnormalized={result.normalized_path}\nresult={result.selected_path}\nmask_preview={result.mask_preview_path}')
        for review in result.reviews: print(f'REVIEW: {review["message"]}')
        return 0
    except Exception as exc:
        print(f'FAILED: local background model check ({type(exc).__name__}); check optional dependencies, model checksum and network availability.',file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
