import json,re,os
from norm import norm
IMG={k:v for k,v in (json.load(open('imgs.json')) if os.path.exists('imgs.json') else {}).items() if v.get('file') and os.path.exists('/Users/francis/playground/Spyderco/Catalogs/'+v['file'])}
def img(s):
    v=IMG.get(s) or {}
    return f'<a href="{v["file"]}"><img src="{v["file"]}" width="160"></a>' if v.get('file') else ''
def tag(t):
    if t=='Regular production': return t
    if 'Sprint' in t: return '🟥 '+t
    if 'excl' in t: return '🟦 '+t
    return '🟪 '+t
M={m:i+1 for i,m in enumerate('jan feb mar apr may jun jul aug sep oct nov dec'.split())}
def dkey(s):
    y=re.search(r'(19|20)\d\d',s); m=re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',s.lower())
    return (int(y.group()) if y else 9999, M[m.group(1)] if m else 0)
def kind(note,num):
    note=re.sub(r'\s*\([^)]*\)','',note)
    t=(note+' '+num).lower()
    if re.match(r'regular',num,re.I) or 'salt series' in t: return 'Regular production'
    if t.startswith('limited. originally slated'): return 'Limited'
    m=re.search(r"([\w.'& -]+?)\s+(dealer |distributor )exclusive",note,re.I)
    if m: return m.group(1).strip()+' excl.'
    if 'sprint' in t: return 'Sprint Run'
    m=re.search(r"([\w.'& -]+?)\s+(dealer |distributor )?exclusive",note,re.I)
    if m and m.group(1).strip().lower() not in ('distributor','dealer'): return m.group(1).strip().replace('Smokey Mountain Knifeworks','Smoky Mountain Knife Works')+' excl.'
    if 'exclusive' in t: return 'Exclusive'
    return 'Limited'
FIX={'mx':{('C101GPRBK2','2021'):'C101GPPRBK2','C101MGR2':'C101PMGR2','C101GODFDE2':'C101GPODFDE2','C101GBN15V2':'C101GPBN15V2','C101BN15V2':'C101PBN15V2',
           'C101JGRBK2':'C101PJGRBK2','C101YL2':'C101PYL2','C101MCW2':'C101MPCW2','C101GMCBK2':'C101GMCBKP2'},
     'sh':{'C229GFGBK':'C229GPFGBK','C229GORBK':'C229GPORBK','C229GOR':'C229GPOR','C229GODFDE':'C229GPODFDE','C229MM4':'C229MPM4','C229BMBN':'C229BMBNP',
           'C229GGY':'C229GPGY','C229GBN15V':'C229GPBN15V','C229BK':'C229PBK','C229BBK':'C229PBBK','C229GCBL':'C229GPCBL','C229GRDBK':'C229GPRDBK'}}
EXTRA={'sh':[dict(SKU='C229SBK',**{'From/To':'Oct. 2025 -','Steel':'CTS-BD1N (SpyderEdge)','Handle':'Black FRN','Note':'','Number made':'Regular production'}),
             dict(SKU='C229SBBK',**{'From/To':'Jun. 2026 -','Steel':'Black DLC-coated CTS-BD1N (SpyderEdge)','Handle':'Black FRN','Note':'','Number made':'Regular production'})]}
SRC='Model numbers checked against spyderco.com product listings where the model is still listed. Sources: Spydiewiki variation tables; forum thread t=90980 (2019+). "Alt SKU" = number used on the wiki where it was corrected. Rows sharing a model number are the same model in different steel generations.\n\nType: 🟥 Sprint Run · 🟦 Dealer/distributor exclusive · 🟪 Other limited/exclusive · (no mark) Regular production'
def clean(v): return re.sub(r'^\|\s*','',v or '').strip()
def build(key,fname,title,names):
    rows=json.load(open(f'rows_{key}.json'))+EXTRA.get(key,[])
    secs={names[0]:[],names[1]:[]}
    for r in rows:
        s=r['SKU'].split()[0]; d=clean(r.get('From/To','')); steel=clean(r.get('Steel','')); hd=clean(r.get('Handle','')); note=clean(r.get('Note','')); num=clean(r.get('Number made',''))
        typ=kind(note,num)
        if key=='sh' and s=='C229BMBNP' and '2024' in d: typ='KnifeCenter excl.'
        n=FIX[key].get((s,d[-4:]), FIX[key].get(s,s)) if not (key=='mx' and s=='C101GPRBK2' and '2021' not in d) else s
        a=s+' (wiki)' if n!=s else ''
        qty='' if re.match(r'(limited|sprint|regular)',num,re.I) and len(num)<20 else num
        d=re.split(r' / |, (?=[A-Z])',d)[0].strip()
        lw=bool(re.search(r'FRCP|FRN|Moonglow',hd))
        secs[names[1] if lw else names[0]].append((dkey(d),n,d,steel,hd,norm(typ),qty,a))
    L=[f'# {title}','',SRC,'']
    for g,out in secs.items():
        out.sort(key=lambda r:r[0])
        L+=[f'## {g} ({len(out)})','','| # | Image | Model No. | Released | Steel | Handle | Type | Qty | Alt SKU |','|---|---|---|---|---|---|---|---|---|']
        L+=[f'| {i} | {img(r[1])} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {tag(r[5])} | {r[6]} | {r[7]} |' for i,r in enumerate(out,1)]
        L.append('')
    open(f'/Users/francis/playground/Spyderco/Catalogs/{fname}.md','w').write('\n'.join(L))
build('mx','C101 Manix 2','C101 Manix 2 — Manix 2 & Manix 2 Lightweight',['Manix 2','Manix 2 Lightweight'])
build('sh','C229 Shaman','C229 Shaman — Shaman & Shaman Lightweight',['Shaman','Shaman Lightweight'])

def build_mil():
    R=json.load(open('rows_mil.json'))
    FIXM={'C36G2':'C36GP2','C36GBK2':'C36GPBK2','C36GCMO2':'C36GPCMO2','C36GCMOBK2':'C36GPCMOBK2','C36GDBL2':'C36GPDBL2','C36MCW2':'C36MPCW2','C36CF2':'C36CFP2','C36GCBL2':'C36GPCBL2','C36GBN15V2':'C36GPBN15V2','C36GMCBK2':'C36GMCBKP2'}
    reg=lambda s,d,st,h: dict(SKU=s,**{'From/To':d,'Steel':st,'Handle':h,'Note':'','Number made':'Regular production'})
    extra={'Military':[reg('C36GPS','2004-2013','CPM-S30V (CombinationEdge)','Black G-10'),reg('C36GPSBK','2005-2013','CPM-S30V black coated (CombinationEdge)','Black G-10')],
           'Military 2':[reg('C36GPS2','2023-','CPM-S30V (CombinationEdge)','Black G-10'),reg('C36GPSBK2','2023-','Black DLC-coated CPM-S30V (CombinationEdge)','Black G-10'),reg('C36GS2','2023-','CPM-S30V (SpyderEdge)','Black G-10'),reg('C36GSBK2','2023-','Black DLC-coated CPM-S30V (SpyderEdge)','Black G-10')]}
    secs={'Military':R['Variations']+extra['Military'],'Military 2':R['Variations of the Military 2']+extra['Military 2']}
    L=['# C36 Military — Military & Military 2','',SRC,'']; seen=set()
    for g,rows in secs.items():
        out=[]
        for r in rows:
            raw=r['SKU']; s=raw.split()[0]; d=clean(r.get('From/To','')); steel=clean(r.get('Steel','')); hd=clean(r.get('Handle','')); note=clean(r.get('Note','')); num=clean(r.get('Number made',''))
            if s=='C36GMCBK2' and '2025' in d and 'March' not in d: continue
            typ=kind(note,num)
            if '(' in raw: typ='Spyderco Forum 2000 excl.'
            n=FIXM.get(s,s); a=s+' (wiki)' if n!=s else ''
            if s=='C36G' and 'S30V' in steel: a='C36GPE (spyderco.com)'
            if s=='C36GBK' and 'S30V' in steel: n,a='C36GPBK','C36GBK (wiki)'
            if s in('C36GCMOBK2',) and num=='6': typ='Factory Seconds Sale'
            qty='' if re.match(r'(limited|sprint|regular)',num,re.I) and len(num)<20 else num
            d=re.split(r' / |, (?=[A-Z])',d)[0].strip()
            out.append((dkey(d),n,d,steel,hd,norm(typ),qty,a))
        out.sort(key=lambda r:r[0])
        L+=[f'## {g} ({len(out)})','','| # | Image | Model No. | Released | Steel | Handle | Type | Qty | Alt SKU |','|---|---|---|---|---|---|---|---|---|']
        L+=[f'| {i} | {img(r[1])} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {tag(r[5])} | {r[6]} | {r[7]} |' for i,r in enumerate(out,1)]
        L.append('')
    open('/Users/francis/playground/Spyderco/Catalogs/C36 Military.md','w').write('\n'.join(L))
build_mil()
