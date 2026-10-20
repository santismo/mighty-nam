#!/usr/bin/env python3
"""Validate local pages, IDs and relative links; no network needed."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit,unquote
root=Path(__file__).resolve().parents[1]/'docs'
class Page(HTMLParser):
 def __init__(self):super().__init__();self.ids=set();self.links=[];self.errors=[];self.title=False;self.viewport=False;self.lang=False
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if 'id' in a:
   if a['id'] in self.ids:self.errors.append('duplicate id '+a['id'])
   self.ids.add(a['id'])
  if tag=='title':self.title=True
  if tag=='html':self.lang=bool(a.get('lang'))
  if tag=='meta' and a.get('name')=='viewport':self.viewport=True
  if tag=='img' and 'alt' not in a:self.errors.append('image missing alt')
  if tag=='a' and 'href' in a:self.links.append(a['href'])
  if tag in {'script','link','img'}:
   v=a.get('src') or a.get('href')
   if v:self.links.append(v)
parsed={}
for path in root.rglob('*.html'):
 q=Page();q.feed(path.read_text());parsed[path.resolve()]=q
errors=[]
for p,q in parsed.items():
 errors += [p.name+': '+e for e in q.errors]
 if not(q.title and q.viewport and q.lang):errors.append(p.name+': missing title, viewport or language')
 for v in q.links:
  u=urlsplit(v)
  if u.scheme or u.netloc:continue
  target=(p.parent/unquote(u.path)).resolve() if u.path else p
  if not target.is_relative_to(root.resolve()):errors.append(p.name+': link escapes docs '+v);continue
  if target.is_dir():target=target/'index.html'
  if not target.exists():errors.append(p.name+': missing '+v)
  elif u.fragment and target in parsed and unquote(u.fragment) not in parsed[target].ids:errors.append(p.name+': missing anchor '+v)
if errors:raise SystemExit('\n'.join(errors))
print(f'PASS site: {len(parsed)} pages; local links, anchors, image labels and document metadata')
