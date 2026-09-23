import sys,glob
from PIL import Image
def stats(f):
    im=Image.open(f).convert('RGB'); w,h=im.size
    sm=im.resize((64,64)); px=list(sm.getdata())
    colors=len(set((r//16,g//16,b//16) for r,g,b in px))
    sat=sum(max(p)-min(p) for p in px)/len(px)
    dark=sum(1 for p in px if max(p)<200)/len(px)
    return w,h,colors,round(sat,1),round(dark,2)
for f in sys.argv[1:]:
    w,h,c,s,d=stats(f)
    flag='SUSPECT' if (c<25 or (s<6 and d<0.15) or w<300) else ''
    print(f.split('images/')[-1],w,h,c,s,d,flag)
