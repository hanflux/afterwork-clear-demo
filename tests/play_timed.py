"""Free independent-grid browser acceptance for timed and fixed challenge previews."""
import json,re,time
from collections import deque
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT='http://127.0.0.1:8765/'
KEY='nc-mg-001-timed-v1'
Path('test-results').mkdir(exist_ok=True)
def occupied(c):
 return [(c['x']+(i if c['direction'] in 'EW' else 0),c['y']+(i if c['direction'] in 'NS' else 0)) for i in range(c['length'])]
def allowed(l,removed,c):
 if c['id'] in removed:return False
 boss=l.get('boss')
 if boss and boss['id']==c['id'] and any(v not in removed for v in boss['after']):return False
 grid={p for v in l['cars'] if v['id'] not in removed and v['id']!=c['id'] for p in occupied(v)}
 grid.update((g['x'],g['y']) for g in l['gates'] if g['trigger'] in removed)
 dx,dy={'N':(0,-1),'E':(1,0),'S':(0,1),'W':(-1,0)}[c['direction']]
 x=c['x']+(c['length'] if dx==1 else -1 if dx==-1 else 0)
 y=c['y']+(c['length'] if dy==1 else -1 if dy==-1 else 0)
 while 0<=x<l['width'] and 0<=y<l['height']:
  if (x,y) in grid:return False
  x+=dx;y+=dy
 return True
def solve(l,start=()):
 q=deque([(frozenset(start),[])]);seen={frozenset(start)}
 while q:
  removed,path=q.popleft()
  if len(removed)==len(l['cars']):return path
  for c in l['cars']:
   if allowed(l,removed,c):
    nxt=removed|{c['id']}
    if nxt not in seen:seen.add(nxt);q.append((nxt,path+[c['id']]))
 return None
def bad_path(l):
 q=deque([(frozenset(),[])]);seen={frozenset()}
 while q:
  removed,path=q.popleft()
  for c in l['cars']:
   if allowed(l,removed,c):
    nxt=removed|{c['id']};route=path+[c['id']]
    if solve(l,nxt) is None:return route
    if nxt not in seen:seen.add(nxt);q.append((nxt,route))
 raise AssertionError('No genuine strategic mistake')
def click_car(page,l,id,wait=True):
 c=next(v for v in l['cars'] if v['id']==id);b=page.locator('#board').bounding_box();h=c['direction'] in 'EW'
 page.mouse.click(b['x']+(24+(c['x']+(c['length']/2 if h else .5))*52)*b['width']/360,b['y']+(58+(c['y']+(.5 if h else c['length']/2))*52)*b['height']/384)
 if wait:page.wait_for_function("!['exiting','gate-closing','undoing'].includes(document.querySelector('#board').dataset.phase)")
def saved(page):return page.evaluate('(k)=>JSON.parse(localStorage.getItem(k))',KEY)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 for path,name in [('challenge/m1/','challenge'),('challenge/events/','events')]:
  page.goto(ROOT+path+'?test');source=page.locator('script').first.inner_text();match=re.search(r'var '+name+r'_default = (\[.*?\]);',source,re.S);assert match
  levels=page.evaluate("(s)=>new Function('return ('+s+')')()",match.group(1));assert len(levels)==10
  for i,l in enumerate(levels):
   page.select_option('#choose',str(i));bad=bad_path(l)
   for id in bad:click_car(page,l,id)
   assert page.locator('#board').get_attribute('data-phase')=='trapped'
   page.locator('#restart').click()
   for id in solve(l):click_car(page,l,id)
   assert page.locator('#board').get_attribute('data-phase')=='complete'
   print(f'PASS {name} {i+1}/10 correct + independent losing prefix',flush=True)
  page.screenshot(path=f'test-results/{name}-complete.png')
 page.goto(ROOT+'timed/?test')
 for difficulty,seed in [('easy',10001),('normal',17920),('hard',25839)]:
  page.select_option('#difficulty',difficulty);page.locator('#seed').fill(str(seed));page.locator('#playSeed').click();g=saved(page);l=g['board']['level'];path=bad_path(l)
  for id in path[:-1]:click_car(page,l,id)
  for n in range(1,4):
   click_car(page,l,path[-1],False);g=saved(page);assert g['run']['errors']==n and g['run']['penaltyMs']==10000*n;assert g['board']['progress']['removed']==path[:-1]
   page.reload();g=saved(page);assert g['run']['errors']==n and g['board']['progress']['removed']==path[:-1]
  assert g['run']['status']=='failed';stopped=g['run']['elapsedMs'];page.wait_for_timeout(200);page.reload();assert saved(page)['run']['elapsedMs']==stopped
  page.screenshot(path=f'test-results/timed-{difficulty}-three-errors.png');page.locator('#restart').click();assert saved(page)['run']['elapsedMs']==0;assert saved(page)['board']['seed']==seed
  for id in solve(l):click_car(page,l,id)
  page.wait_for_function("document.querySelector('#board').dataset.phase==='won'");g=saved(page);assert g['run']['errors']==0
  records=page.evaluate("JSON.parse(localStorage.getItem('nc-mg-001-timed-best-v1')).records");assert any(v['totalMs']==g['run']['elapsedMs']+g['run']['penaltyMs'] for v in records.values())
  page.screenshot(path=f'test-results/timed-{difficulty}-complete.png');print(f'PASS timed {difficulty}: clear, three atomic undos, reload, stopped timer, best',flush=True)
 assert not errors,errors
 print('PASS independent challenge+timed browser acceptance; automated, zero human players',flush=True);browser.close()
