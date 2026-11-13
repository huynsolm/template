"""Create original vector-style sample photos with Pillow, never download assets."""
import argparse
import json
from pathlib import Path
import sys
from PIL import Image, ImageDraw
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def photo(width=1440,height=960):
    image=Image.new('RGB',(width,height),'#dfebe4')
    draw=ImageDraw.Draw(image)
    def box(values): return tuple(round(v*(width/720 if i%2==0 else height/480)) for i,v in enumerate(values))
    draw.ellipse(box((160,400,560,450)),fill='#bbcfc1')
    draw.rounded_rectangle(box((265,80,455,415)),radius=round(width*38/720),fill='#426b59')
    draw.rounded_rectangle(box((290,45,430,105)),radius=round(width*16/720),fill='#2b4d3e')
    draw.rounded_rectangle(box((285,180,435,300)),radius=round(width*12/720),fill='#f7f3e7')
    draw.line(box((360,205,360,270)),fill='#426b59',width=max(1,round(width*5/720)))
    draw.ellipse(box((333,205,360,235)),fill='#426b59')
    draw.ellipse(box((360,225,389,255)),fill='#426b59')
    return image


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--fixture',action='store_true')
    parser.add_argument('--output',type=Path,default=ROOT/'outputs/m3-samples')
    args=parser.parse_args()
    if args.fixture:
        path=ROOT/'samples/product-hires.png';photo().save(path);print(path)
    else:
        from core.images import process_image,Processing
        args.output.mkdir(parents=True,exist_ok=True)
        source=args.output/'original.png';photo(2400,1600).save(source)
        result=process_image(source,args.output,Processing(), '#305b46')
        (args.output/'image-manifest.json').write_text(json.dumps(result.metadata,ensure_ascii=False,indent=2))
        print(json.dumps({'original':str(source),'normalized':str(result.normalized_path),'selected':str(result.selected_path)},ensure_ascii=False,indent=2))
