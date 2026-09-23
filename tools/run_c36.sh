set -x
node img_spy.mjs > spy36.out 2>&1
python3 - <<'PY'
import json,re,glob
sm=json.load(open('smap.json')); sm['bladehq.com']=open('bhq_sitemap.txt').read().split('\n')
alts=json.load(open('alts.json')); imgs=json.load(open('imgs.json'))
import os
has=lambda s:(imgs.get(s) or {}).get('file') and os.path.exists('/Users/francis/playground/Spyderco/Catalogs/'+imgs[s]['file'])
dom={'cutlery shoppe':'cutleryshoppe.com','blade hq':'bladehq.com',"river's edge":'riversedgecutlery.com','knifeworks':'knifeworks.com',"st. nick":'stnicksknives.com','bento box':'bentoboxshop.com'}
cand={}
for l in open('/Users/francis/playground/Spyderco/Catalogs/C36 Military.md'):
    c=[x.strip() for x in l.split('|')]
    if len(c)>9 and re.match(r'\d+$',c[1]):
        s=c[3]
        if has(s) or s in cand: continue
        keys=[s]+re.findall(r'C\d+[A-Z0-9]+',c[9])
        pref=next((v for k,v in dom.items() if k in c[7].lower()),None)
        hits=sorted({(0 if d==pref else 1,u) for d,us in sm.items() for u in us if any(re.search(r'(?<![a-z0-9])'+k.lower()+r'(?![a-z0-9])',u.lower()) for k in keys)})
        if hits: cand[s]=[u for _,u in hits][:5]
json.dump(cand,open('cand36.json','w'),indent=1); print('c36 sitemap candidates',len(cand))
PY
node gallery.mjs cand36.json > gal36.out 2>&1
python3 final.py; python3 gen2.py
echo "spy OK=$(grep -c ' OK ' spy36.out) | sitemap OK=$(grep -c ' OK ' gal36.out) REVIEW=$(grep -c REVIEW gal36.out)"
