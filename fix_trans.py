import re, polib, time
from pathlib import Path
from deep_translator import GoogleTranslator

lang_map = {'ar':'ar','bn':'bn','de':'de','en':'en','es':'es','fr':'fr','hi':'hi','hy':'hy','id':'id','it':'it','ja':'ja','ka':'ka','ko':'ko','nl':'nl','pl':'pl','pt':'pt','ru':'ru','th':'th','tr':'tr','uk':'uk','vi':'vi','zh_Hans':'zh-CN'}
percent_pat = re.compile(r'%\([^)]+\)s')
brace_pat = re.compile(r'\{[^{}]+\}')

def is_app(e):
    return any(p in o[0] for o in e.occurrences for p in ['pixelwar','users/','Notifications'])

def protect(t):
    toks = []
    t2 = percent_pat.sub(lambda m: (toks.append(m.group(0)) or f'__P{len(toks)}__'), t)
    return brace_pat.sub(lambda m: (toks.append(m.group(0)) or f'__B{len(toks)}__'), t2), toks

def restore(t, toks):
    for i, tok in enumerate(toks):
        t = t.replace(f'__P{i}__', tok).replace(f'__B{i}__', tok)
    return t

for lc in sorted(lang_map.keys()):
    if lc == 'en': continue
    p = Path(f'locale/{lc}/LC_MESSAGES/django.po')
    if not p.exists(): continue
    print(f'{lc}...', flush=True)
    po = polib.pofile(str(p))
    tr = GoogleTranslator(source='en', target=lang_map[lc])
    c = 0
    for e in po:
        if not is_app(e) or not e.msgid or not e.msgid.strip(): continue
        try:
            st, toks = protect(e.msgid)
            ed = tr.translate(st)
            ed = restore(ed, toks)
            e.msgstr = ed
            c += 1
            time.sleep(0.05)
        except: pass
    po.save(str(p))
    print(f'✓ {c}', flush=True)
print('Done!')
