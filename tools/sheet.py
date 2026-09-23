import sys,glob,os
from PIL import Image,ImageDraw
fs=sorted(glob.glob('/Users/francis/playground/Spyderco/Catalogs/images/*/*'))
T=180; C=8; R=5; n=C*R
for p in range(0,len(fs),n):
    sh=Image.new('RGB',(C*T,R*(T+18)),'white'); d=ImageDraw.Draw(sh)
    for i,f in enumerate(fs[p:p+n]):
        try: im=Image.open(f).convert('RGB'); im.thumbnail((T,T))
        except Exception: continue
        x=(i%C)*T; y=(i//C)*(T+18); sh.paste(im,(x+(T-im.width)//2,y+(T-im.height)//2)); d.text((x+2,y+T+2),os.path.basename(f)[:28],fill='red')
    sh.save(f'sheet_{p//n}.jpg',quality=80)
print(len(fs), (len(fs)+n-1)//n)
