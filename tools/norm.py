import re
ALIAS={'knifecenter':'KnifeCenter','bladehq':'Blade HQ','blade hq':'Blade HQ','knifeworks':'KnifeWorks',"st. nick's":"St. Nick's Knives","st. nick's knives":"St. Nick's Knives",'dlt':'DLT Trading','dlt trading':'DLT Trading','blade ops':'BladeOps','bladeops':'BladeOps','knife joy':'KnifeJoy','knifejoy':'KnifeJoy','the knifejoker':'The Knife Joker','the knife joker':'The Knife Joker','knife joker':'The Knife Joker','knifejoker':'The Knife Joker','smokey mountain knifeworks':'Smoky Mountain Knife Works','fradon lock company':'Fradon Lock','fradon lock':'Fradon Lock','knife center':'KnifeCenter','knifeworks.com':'KnifeWorks','h.l. dalis inc.':'H.L. Dalis','h.l. dalis':'H.L. Dalis'}
def norm(t):
    if not t.endswith(' excl.'): return t
    n=re.split(r'(?<=[a-z]{3})\. ',t[:-6])[-1].strip()
    return ALIAS.get(n.lower(),n)+' excl.'
