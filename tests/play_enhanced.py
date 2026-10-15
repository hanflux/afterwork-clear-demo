import json,re
from collections import deque
from playwright.sync_api import sync_playwright

ROOT="http://127.0.0.1:8765/enhanced/?test"
KEY="nc-mg-001-enhanced-v1"
def ray(c,l):
 d={"N":(0,-1),"S":(0,1),"E":(1,0),"W":(-1,0)}[c["direction"]]
 x=c["x"]+(c["length"] if c["direction"]=="E" else -1 if c["direction"]=="W" else 0)
 y=c["y"]+(c["length"] if c["direction"]=="S" else -1 if c["direction"]=="N" else 0)
 p=[]
 while 0<=x<l["width"] and 0<=y<l["height"]:
  p.append((x,y));x+=d[0];y+=d[1]
 return p
def cells(c):
 return {(c["x"]+(i if c["direction"] in "EW" else 0),c["y"]+(i if c["direction"] in "NS" else 0)) for i in range(c["length"])}
def trapped(l,removed):
 return [c["id"] for c in l["cars"] if c["id"] not in removed and any((g["x"],g["y"]) in ray(c,l) and g["trigger"] in removed for g in l["gates"])]
def blockers(l,removed,c):
 occupied=set().union(*(cells(v) for v in l["cars"] if v["id"] not in removed and v["id"]!=c["id"]))
 return any(p in occupied or any((g["x"],g["y"])==p and g["trigger"] in removed for g in l["gates"]) for p in ray(c,l))
def solve(l):
 q=deque([(frozenset(),[])])
 seen={frozenset()}
 while q:
  removed,path=q.popleft()
  if len(removed)==len(l["cars"]):return path
  if trapped(l,removed):continue
  for c in l["cars"]:
   if c["id"] not in removed and not blockers(l,removed,c):
    nxt=removed|{c["id"]}
    if nxt not in seen:seen.add(nxt);q.append((nxt,path+[c["id"]]))
 return None
def tap(page,c):
 b=page.locator("#board").bounding_box()
 hor=c["direction"] in "EW"
 x=24+(c["x"]+(c["length"]/2 if hor else .5))*52
 y=58+(c["y"]+(.5 if hor else c["length"]/2))*52
 page.mouse.click(b["x"]+x*b["width"]/360,b["y"]+y*b["height"]/384)
 page.wait_for_function("!['exiting','gate-closing'].includes(document.querySelector('#board').dataset.phase)")
def save(page):
 return page.evaluate("(key)=>JSON.parse(localStorage.getItem(key))",KEY)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=["--no-sandbox"])
 page=browser.new_page(viewport={"width":390,"height":844})
 errors=[]
 page.on("pageerror",lambda e:errors.append(str(e)))
 page.goto(ROOT)
 src=page.locator("script").first.inner_text()
 m=re.search(r"var enhanced_default = (\[.*?\]);\s*// src/core/game.ts",src,re.S)
 assert m,"Cannot extract live level data"
 levels=page.evaluate("(s)=>new Function('return ('+s+')')()",m.group(1))
 assert len(levels)==10
 for n,l in enumerate(levels):
  path=solve(l)
  assert path,f"No path level {n+1}"
  page.select_option("#choose",str(n))
  for id in path:
   tap(page,next(c for c in l["cars"] if c["id"]==id))
   assert id in save(page)["removed"],f"Car {id} failed level {n+1}"
  assert l["level_id"] in save(page)["completed"]
  print(f"PASS enhanced {n+1}/10 {l['level_id']} clicks={len(path)} path={' '.join(path)}",flush=True)
  if n==0:
   page.screenshot(path="test-results/enhanced-level1.png")
 # wrong order: find state that produces trapped cars, then exercise browser
 for n,l in enumerate(levels):
  if "K" not in [c["id"] for c in l["cars"]]: continue
  if not blockers(l,frozenset(),next(c for c in l["cars"] if c["id"]=="K")) and trapped(l,frozenset({"K"})):
   page.select_option("#choose",str(n))
   tap(page,next(c for c in l["cars"] if c["id"]=="K"))
   assert "免费重开" in page.locator("#status").inner_text()
   page.locator("#restart").click()
   assert not save(page)["removed"]
   print(f"PASS wrong-order trapped/restart at level {n+1}",flush=True)
   break
 else:
  print("NOTICE: No immediately clickable K wrong-order fixture",flush=True)
 assert not errors,errors
 print("PASS all enhanced levels + browser input, no JavaScript exceptions",flush=True)
 browser.close()
