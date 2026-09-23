import re,subprocess,json,sys
def get(u):
    return subprocess.run(['curl','-sL','-m','60','-A','Mozilla/5.0',u],capture_output=True,text=True,errors='ignore').stdout
out={}
for dom in sys.argv[1:]:
    locs=set(); todo=[f'https://www.{dom}/sitemap.xml',f'https://{dom}/sitemap.xml',f'https://www.{dom}/xmlsitemap.php'];seen=set()
    while todo:
        u=todo.pop(); 
        if u in seen or len(seen)>80: continue
        seen.add(u); x=get(u)
        for l in re.findall(r'<loc>\s*([^<\s]+)',x):
            l=l.replace('&amp;','&')
            if re.search(r'sitemap|\.xml',l,re.I) and (re.search(r'product',l,re.I) or not re.search(r'blog|page|collection|categor|brand|image|post',l,re.I)): todo.append(l)
            else: locs.add(l)
    out[dom]=sorted(locs); print(dom,len(locs),len(seen),file=sys.stderr)
json.dump(out,open('smap.json','w'))
