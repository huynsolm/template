"""Backwards-compatible M1 renderer and M2 file-based copy workflow."""
import argparse
import json
import sys
from pathlib import Path
from core.render import render
from core.schema import Document
from core.facts import ProductFacts
from core.workflow import create_job, ingest_job, regenerate_job, generate_job, accept_job
from core.assemble import DEFAULT_TERMS
from core.themes import THEME_IDS


def read_facts(path):
    return ProductFacts.model_validate_json(path.read_text(encoding='utf-8'))


def m1(argv):
    parser=argparse.ArgumentParser(description='Local JSON → HTML → 860px JPG')
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--images',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--max-height',type=int,default=4000)
    parser.add_argument('--png',action='store_true')
    parser.add_argument('--theme',choices=THEME_IDS,default='classic')
    args=parser.parse_args(argv)
    document=Document.model_validate_json(args.input.read_text(encoding='utf-8'))
    return render(document,args.images,args.output,args.max_height,args.png,theme=args.theme)


def main(argv=None):
    argv=list(sys.argv[1:] if argv is None else argv)
    try:
        if argv and argv[0].startswith('--') and argv[0] not in ('--help',):
            result=m1(argv)
        else:
            parser=argparse.ArgumentParser(description='M2: 상품 사실 → 붙여넣기 프롬프트 → 문구 검증. M1: --input ...')
            sub=parser.add_subparsers(dest='command',required=True)
            images=sub.add_parser('images',help='사진 처리만 실행 (AI 호출 없음)')
            images.add_argument('--facts',type=Path,required=True)
            images.add_argument('--images',type=Path,required=True)
            images.add_argument('--output',type=Path,required=True)
            accept=sub.add_parser('accept',help='현재 draft.json을 승인해 새 작업으로 렌더링 (AI 호출 없음)')
            accept.add_argument('--job',type=Path,required=True)
            prompt=sub.add_parser('prompt')
            choice=prompt.add_mutually_exclusive_group(required=True)
            choice.add_argument('--facts',type=Path)
            choice.add_argument('--from-job',type=Path)
            prompt.add_argument('--images',type=Path)
            prompt.add_argument('--output',type=Path)
            prompt.add_argument('--regenerate',action='store_true')
            prompt.add_argument('--max-attempts',type=int,default=5)
            ingest=sub.add_parser('ingest')
            ingest.add_argument('--job',type=Path,required=True)
            ingest.add_argument('--answer',type=Path,required=True)
            ingest.add_argument('--source-label',default='')
            ingest.add_argument('--render',action='store_true')
            ingest.add_argument('--accept-review',action='store_true',help='검수 항목을 확인했음을 명시하고 일반 이미지 파일명 사용')
            ingest.add_argument('--review-terms',type=Path)
            generate=sub.add_parser('generate')
            generate.add_argument('--facts',type=Path,required=True)
            generate.add_argument('--images',type=Path,required=True)
            generate.add_argument('--output',type=Path,required=True)
            generate.add_argument('--provider',choices=['claude','codex','gemini'],required=True)
            generate.add_argument('--providers-config',type=Path,default=Path(__file__).parent/'providers.toml')
            generate.add_argument('--max-attempts',type=int,default=3)
            generate.add_argument('--timeout',type=float,default=300)
            generate.add_argument('--source-label',default='')
            generate.add_argument('--review-terms',type=Path)
            generate.add_argument('--render',action='store_true')
            generate.add_argument('--accept-review',action='store_true',help='검수 항목을 확인했음을 명시하고 일반 이미지 파일명 사용')
            for themed in (ingest,generate,accept):
                themed.add_argument('--theme',choices=THEME_IDS,default=None)
            export=sub.add_parser('export',help='플랫폼 프로필로 규격 검사 후 ZIP 내보내기 (AI 호출 없음)')
            export.add_argument('--job',type=Path,required=True)
            export.add_argument('--profile',required=True,help='generic, smartstore, coupang 또는 profiles/user/의 사용자 프로필 이름')
            export.add_argument('--format',choices=['jpg','png'],help='생략하면 프로필의 첫 번째 형식')
            export.add_argument('--output',type=Path,help='ZIP 저장 폴더 (기본: 작업 폴더의 exports/)')
            args=parser.parse_args(argv)
            terms=None
            if getattr(args,'review_terms',None):
                terms=json.loads(args.review_terms.read_text(encoding='utf-8'))
                if not isinstance(terms,list) or not all(isinstance(t,str) and t for t in terms):
                    raise ValueError('review-terms must be a JSON array of nonempty strings')
            if args.command=='images':
                result=create_job(read_facts(args.facts),args.images,args.output,method='images')
                meta=json.loads((result/'manifest.json').read_text())
                for warning in meta.get('image_reviews',[]): print('WARNING: '+warning['reason'],file=sys.stderr)
                if any(item.get('settings',{}).get('remove_background') and not item.get('background_removed') for item in meta['image_processing']):
                    print(result.resolve())
                    raise ValueError('배경 제거 실패: 기본 처리본은 출력 작업 폴더에 유지했습니다.')
            elif args.command=='export':
                from core.export import build_export_zip, current_bundle, export_bundle
                outcome=export_bundle(current_bundle(args.job),args.profile,fmt=args.format)
                for check in outcome['checks']:
                    if check['level']!='info': print(('ERROR: ' if check['level']=='error' else 'WARNING: ')+check['message'],file=sys.stderr)
                if outcome['status']=='error':
                    raise ValueError('내보내기 오류: 위 항목을 확인하세요.')
                name,data=build_export_zip(outcome['folder'])
                folder=args.output or Path(args.job)/'exports'
                folder.mkdir(parents=True,exist_ok=True)
                result=folder/name
                result.write_bytes(data)
            elif args.command=='accept':
                result=accept_job(args.job,theme=args.theme)
            elif args.command=='prompt':
                if args.from_job:
                    if not args.regenerate: parser.error('--from-job requires --regenerate')
                    result=regenerate_job(args.from_job)
                else:
                    if args.regenerate: parser.error('--regenerate requires --from-job')
                    if not args.images or not args.output: parser.error('--facts requires --images and --output')
                    result=create_job(read_facts(args.facts),args.images,args.output,max_attempts=args.max_attempts)
            elif args.command=='ingest':
                from core.providers import PasteProvider
                answer=PasteProvider(args.answer).generate('')
                result=ingest_job(args.job,answer,source_label=args.source_label,render_output=args.render,terms=terms,accept_review=args.accept_review,theme=args.theme)
            else:
                from core.providers import CliProvider
                provider=CliProvider(args.provider,config_path=args.providers_config,timeout=args.timeout)
                result=generate_job(read_facts(args.facts),args.images,args.output,provider,max_attempts=args.max_attempts,source_label=args.source_label,render_output=args.render,terms=terms,accept_review=args.accept_review,theme=args.theme)
        print(result.resolve())
        return 0
    except (ValueError,OSError) as exc:
        print(f'error: {exc}',file=sys.stderr)
        return getattr(exc,'exit_code',2)


if __name__=='__main__':
    sys.exit(main())
