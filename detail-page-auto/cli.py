"""M1 command line entry point."""
import argparse
import json
import sys
from pathlib import Path
from core.render import render
from core.schema import Document


def main():
    parser = argparse.ArgumentParser(description='Local JSON → HTML → 860px JPG')
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--images', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-height', type=int, default=4000)
    parser.add_argument('--png', action='store_true')
    args = parser.parse_args()
    try:
        document = Document.model_validate(json.loads(args.input.read_text(encoding='utf-8')))
        result = render(document, args.images, args.output, args.max_height, args.png)
    except (ValueError, OSError) as exc:
        print(f'error: {exc}', file=sys.stderr)
        return 1
    print(result.resolve())
    return 0


if __name__ == '__main__':
    sys.exit(main())
