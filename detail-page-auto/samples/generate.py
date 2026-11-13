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
