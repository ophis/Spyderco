import json,re
M={m:i+1 for i,m in enumerate('jan feb mar apr may jun jul aug sep oct nov dec'.split())}
def dkey(s):
    y=re.search(r'(19|20)\d\d',s); m=re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',s.lower())
    return (int(y.group()) if y else 9999, M[m.group(1)] if m else 0)
def kind(r):
    t=(r.get('Note','')+' '+r.get('Number made','')).lower()
    if 'sprint' in t: return 'Sprint Run'
    m=re.search(r'([\w.\'& -]+?)\s+(dealer|distributor)\s+exclusive',r.get('Note',''),re.I)
    if m: return m.group(1).strip()+' excl.'
    if 'exclusive' in t: return 'Exclusive'
    return 'Limited'
def lw(r): return bool(re.search(r'\bFRN\b|FRCP|lightweight',r.get('Handle','')+' '+r.get('Note',''),re.I))
out={'ParaMilitary 2':[], 'Para 3':[], 'Para 3 Lightweight':[]}
skus=set()
for f,base in [('rows_PM2.json','ParaMilitary 2'),('rows_Par.json','Para 3')]:
    for r in json.load(open(f)):
        reg=bool(re.match(r'regular',r.get('Number made',''),re.I))
        g=base
        if base=='Para 3' and lw(r): g='Para 3 Lightweight'
        if base=='ParaMilitary 2' and lw(r): g='ParaMilitary 2'  # flag below
        skus.add(r['SKU'].split()[0])
        qty='' if reg else r.get('Number made','')
        qty='' if re.match(r'(limited|sprint)',qty,re.I) and len(qty)<12 else qty
        out[g].append(dict(sku=r['SKU'],date=r.get('From/To',''),steel=r.get('Steel',''),handle=r.get('Handle',''),type='Regular production' if reg else kind(r),qty=qty,src='wiki'))
# forum entries not on wiki
for l in open('pm.txt'):
    l=l.strip(); m=re.search(r'\b(C(?:81|223)[A-Z0-9]+)\b',l)
    if m and m.group(1) in skus: continue
    g='ParaMilitary 2' if l.lower().startswith('paramilitary') else ('Para 3 Lightweight' if 'Lightweight' in l or 'FRN' in l else 'Para 3')
    d=re.search(r'- ([A-Z]{3} 20\d\d)$',l).group(1)
    out[g].append(dict(sku=m.group(1) if m else '?',date=d,steel='',handle='',type='(forum) '+re.sub(r' - [A-Z]{3} 20\d\d$','',l),qty='',src='forum'))
json.dump(out,open('merged.json','w'),indent=1)
for g,v in out.items():
    v.sort(key=lambda x:dkey(x['date']))
    print(g,len(v),'forum-only:',sum(x['src']=='forum' for x in v))
