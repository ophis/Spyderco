import json,re,sys
exec(open('parse.py').read().split('for name,f,start')[0])
for name,f,start in [('mx','wt_mx.txt','===Variations of the Manix 2==='),('sh','wt_sh.txt','==Variations==')]:
    t=open(f).read(); t=t[t.index(start):t.index('==Most collectible')]
    rows=tables(t); json.dump(rows,open(f'rows_{name}.json','w'),indent=1)
    print(name,len(rows))
    for r in rows: print(' ',r['SKU'],'|',r.get('From/To','')[:25],'|',r.get('Steel',''),'|',r.get('Handle','')[:35],'|',r.get('Note','')[:60],'|',r.get('Number made','')[:20])
