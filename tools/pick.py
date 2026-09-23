import sys
from PIL import Image
def white(f):
    im=Image.open(f)
    if im.mode in ('RGBA','LA','P'):
        im=im.convert('RGBA'); bg=Image.new('RGBA',im.size,(255,255,255,255)); bg.alpha_composite(im); im=bg
    im=im.convert('RGB'); w,h=im.size; k=max(4,w//50)
    px=[im.getpixel((x,y)) for x,y in [(k,k),(w-k,k),(k,h-k),(w-k,h-k)]]
    return all(min(p)>235 for p in px)
for f in sys.argv[1:]: sz=Image.open(f).size; print(f, 'WHITE' if white(f) else 'OTHER', sz[0], round(sz[0]/sz[1],2))
