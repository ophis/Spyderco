import json,re,os
from norm import norm
IMG={k:v for k,v in (json.load(open('imgs.json')) if os.path.exists('imgs.json') else {}).items() if v.get('file') and os.path.exists('/Users/francis/playground/Spyderco/Catalogs/'+v['file'])}
def tag(t):
    if t=='Regular production': return t
    if 'Sprint' in t: return '🟥 '+t
    if 'excl' in t: return '🟦 '+t
    return '🟪 '+t
def img(s):
    v=IMG.get(s) or {}
    if not v.get('file'): return ''
    return ' '.join(f'<a href="{x}"><img src="{x}" width="160"></a>' for x in v.get('files',[v['file']]))

o=json.load(open('merged.json'))
alt={'C81GWC2':'C81GPWC2','C81GPPR2':'C81GPR2','C81GBN15V2':'C81GPBN15V2','C81GCOFL2':'C81GPCOFL2','C81CFPGRBK2':'C81CFPGR2','C81CFPRDORBK2':'C81CFPRDOR','C223GPNGR':'C223GNGR','C223GRM4':'C223GPGRM4'}
fix={'C223GPRBK':'C223GPPRBK','C223GNGRBK':'C223GPNGRBK'}
extra={'Para 3 Lightweight':[
 dict(sku='C223PFGRCWBK',date='Dec. 2023',steel='Black DLC coated Cru-Wear',handle='Deep Forest Green FRN',type='The Knife Joker excl.',qty=''),
 dict(sku='C223PFG',date='Feb. 2025',steel='CTS-204P',handle='Forest Green FRN',type='KnifeWorks excl.',qty=''),
 dict(sku='C223PGRM4BK',date='Apr. 2025',steel='Black DLC coated CPM-M4',handle='Mint Green FRN',type='BladeHQ excl.',qty='')]}
M={m:i+1 for i,m in enumerate('jan feb mar apr may jun jul aug sep oct nov dec'.split())}
def dkey(s):
    y=re.search(r'20\d\d',s); m=re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',s.lower())
    return (int(y.group()) if y else 9999, M[m.group(1)] if m else 0)
SRC=('Model numbers checked against spyderco.com product listings where the model is still listed. Sources: Spydiewiki "C81 Para-Military" and "C223 Para 3" variation tables; forum thread t=90980 (2019+). "Alt SKU" = number used in the forum thread where it differs.\n\nType: 🟥 Sprint Run · 🟦 Dealer/distributor exclusive · 🟪 Other limited/exclusive · (no mark) Regular production')
FILES={'C81 Para-Military':['# C81 Para-Military — Para-Military, ParaMilitary 2 & ParaMilitary 2 Lightweight','',SRC,''],'C223 Para 3':['# C223 Para 3 — Para 3 & Para 3 Lightweight','',SRC,'']}
seen=set()
pm=[x for x in o['ParaMilitary 2'] if x['src']=='wiki']
o['ParaMilitary 2 Lightweight']=[x for x in pm if 'FRN' in x['handle']]+[dict(sku='C81SBK2',date='Jan. 2026 -',steel='CTS-BD1N (SpyderEdge)',handle='Black FRN',type='Regular production',qty='',src='wiki')]
o['ParaMilitary 2']=[x for x in pm if 'FRN' not in x['handle']]
o['Para-Military']=[dict(sku=r['SKU'],date=r['From/To'],steel=r['Steel'],handle=r['Handle'],type='Sprint Run' if 'print' in r.get('Note','') else 'Regular production',qty='' if r.get('Number made') in ('N/A','?') else r.get('Number made',''),src='wiki') for r in json.load(open('rows_pm1.json'))]
for g in ['Para-Military','ParaMilitary 2','ParaMilitary 2 Lightweight','Para 3','Para 3 Lightweight']:
    rows=[x for x in o[g] if x['src']=='wiki']+extra.get(g,[])
    out=[]
    for x in rows:
        s=x['sku'].split()[0]; a=alt.get(s,'')
        if s in fix: a=s+' (wiki)'; s=fix[s]
        steel,hd,d=x['steel'],x['handle'],x['date']
        if s=='C81GDGYRX76BKP2' and 'Feb' in d: s,a,steel='C81GDGYRX76P2','','Satin CPM REX 76'
        if s=='C81GPNGRBK2': steel='Black DLC coated CPM-20CV'
        typ=norm(x['type'].replace('Lightweight version. ',''))
        d=re.split(r' / |, (?=[A-Z])',d)[0].strip()
        if s in('C223PFGRCWBK','C223PGRM4BK') and typ=='Regular production': continue
        dlc='DLC' in steel or 'black' in steel.lower().split()[-1:]
        o2={'C81GBK2':'C81GPBK2','C81GCMO2':'C81GPCMO2','C81GCMOBK2':'C81GPCMOBK2','C81MCW2':'C81MPCW2','C81GCBL2':'C81GPCBL2',
            'C223GCBL':'C223GPCBL','C223MCW':'C223MPCW','C223GMCBK':'C223GMCBKP','C223GBKYLMC':'C223GBKYLMCP','C223YL':'C223PYL',
            'C223GNDMCPBK':'C223GNDMCBKP','C223GBN15V':'C223GPBN15V','C223BN15V':'C223PBN15V'}
        if s=='C81GBKYLMC2': n='C81GMCBKP2' if 'DLC' in steel else 'C81GBKYLMCP2'
        elif s=='C81BK2': n='C81PBBK2' if 'DLC' in steel else 'C81PBK2'
        elif s=='C223PN': n='C223PPNBK' if 'DLC' in steel else 'C223PPN'
        else: n=o2.get(s,s)
        if n!=s: a=(a+'; ' if a else '')+s+' (wiki)'; s=n
        if s=='C223PFGRCWBK': a='C223PFGRCWBKCRF (spyderco.com, 2026 listing)'
        out.append((dkey(d),s,d,steel,hd,typ,x['qty'].split(' link')[0],a))
    out.sort(key=lambda r:r[0])
    L=FILES['C223 Para 3' if g.startswith('Para 3') else 'C81 Para-Military']
    L+=[f'## {g} ({len(out)})','','| # | Image | Model No. | Released | Steel | Handle | Type | Qty | Alt SKU |','|---|---|---|---|---|---|---|---|---|']
    L+=[f'| {i} | {img(r[1])} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {tag(r[5])} | {r[6]} | {r[7]} |' for i,r in enumerate(out,1)]
    L.append('')
for k,L in FILES.items(): open(f'/Users/francis/playground/Spyderco/Catalogs/{k}.md','w').write('\n'.join(L))
