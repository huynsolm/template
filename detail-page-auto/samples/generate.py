"""Generate an original sample illustration; no external images."""
from pathlib import Path
from PIL import Image, ImageDraw
root=Path(__file__).parent
im=Image.new('RGB',(720,480),'#dfebe4')
d=ImageDraw.Draw(im)
d.ellipse((160,400,560,450),fill='#bbcfc1')
d.rounded_rectangle((265,80,455,415),radius=38,fill='#426b59')
d.rounded_rectangle((290,45,430,105),radius=16,fill='#2b4d3e')
d.rounded_rectangle((285,180,435,300),radius=12,fill='#f7f3e7')
d.line((360,205,360,270),fill='#426b59',width=5)
d.ellipse((333,205,360,235),fill='#426b59')
d.ellipse((360,225,389,255),fill='#426b59')
im.save(root/'product.png')


def generate_rich():
    """Illustrate the fictitious portable enclosure from several viewpoints."""
    palettes = {
        'hero': ('#d8e7e4', '#2c6156'),
        'lifestyle': ('#eadfd2', '#2c6156'),
        'detail': ('#cddbdc', '#34695d'),
        'feature': ('#e7e6dd', '#335c53'),
        'diagram': ('#eef1eb', '#4b6f64'),
    }
    for role, (background, casing) in palettes.items():
        image = Image.new('RGB', (860, 610), background)
        draw = ImageDraw.Draw(image)
        if role == 'lifestyle':
            draw.rectangle((0, 390, 860, 610), fill='#c09e80')
            draw.rounded_rectangle((80, 55, 235, 280), 10, fill='#f6eee3')
            draw.rounded_rectangle((654, 290, 782, 402), 18, fill='#526956')
        if role == 'diagram':
            draw.rounded_rectangle((150, 100, 710, 505), 42, outline=casing, width=8)
            for x in (250, 420, 590):
                draw.rectangle((x, 150, x+85, 415), outline=casing, width=5)
                draw.line((x+42, 415, x+42, 555), fill=casing, width=3)
        else:
            box = (150, 65, 710, 545) if role == 'detail' else (270, 90, 605, 470)
            x1,y1,x2,y2 = box
            draw.ellipse((x1-55,y2-20,x2+55,min(600,y2+85)),fill='#9daea4')
            draw.rounded_rectangle(box, 52, fill=casing, outline='#1a3932',width=6)
            draw.rounded_rectangle((x1+55,y1+52,x2-55,y1+160),20,fill='#e6eee7')
            draw.ellipse((x1+77,y1+84,x1+116,y1+123),fill='#d59d49')
            for offset in range(0, 96, 24):
                draw.line((x1+62,y2-130+offset,x2-62,y2-130+offset), fill='#183c35', width=7)
        image.save(root/f'rich-{role}.png')


if __name__ == '__main__':
    generate_rich()
