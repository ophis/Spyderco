import re,json,sys
def clean(s):
    s=re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]*)\]\]',r'\1',s)
    s=re.sub(r'\[https?://\S+ ([^\]]*)\]',r'\1',s)
    s=re.sub(r"'''?|<[^>]+>",'',s); s=re.sub(r'^valign="top" \|','',s.strip())
    return re.sub(r'\s+',' ',s).strip()
def tables(txt):
    out=[]
    for tb in re.findall(r'\{\|(.*?)\n\|\}',txt,re.S):
        heads=[clean(h) for h in re.findall(r"\{\{Tableheading\}\}(.*)",tb)]
        body=re.split(r'\n\|-',tb)
        for r in body:
            cells=[clean(l[1:]) for l in r.split('\n') if l.startswith('|') and not l.startswith('|-') and not l.startswith('|}')]
            if heads and len(cells)>=len(heads)-2 and cells and re.match(r'C\d',cells[0]):
                out.append(dict(zip(heads,cells)))
    return out
for name,f,start in [('PM2','wt_pm.txt','===Variations of the Paramilitary 2==='),('Para 3','wt_para3.txt','==Variations==')]:
    t=open(f).read(); t=t[t.index(start):t.index('==Most collectible')]
    rows=tables(t)
    json.dump(rows,open(f'rows_{name[:3]}.json','w'),indent=1)
    print(name,len(rows),list(rows[0].keys()) if rows else None)
