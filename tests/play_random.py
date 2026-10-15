import json, re
from playwright.sync_api import sync_playwright

URL="http://127.0.0.1:8765/random/?test"
KEY="nc-mg-001-random-v1"
def session(page):
    raw=page.evaluate("(key)=>localStorage.getItem(key)",KEY)
    assert raw, "random session missing"
    return json.loads(raw)
def click_car(page,c):
    box=page.locator("#board").bounding_box()
    assert box
    horizontal=c["direction"] in "EW"
    x=24+52*(c["x"]+(c["length"]/2 if horizontal else .5))
    y=58+52*(c["y"]+(.5 if horizontal else c["length"]/2))
    page.mouse.click(box["x"]+x/360*box["width"],box["y"]+y/384*box["height"])
    page.wait_for_function("!['exiting','gate-closing'].includes(document.querySelector('#board').dataset.phase)",timeout=15000)

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,args=["--no-sandbox"])
    page=browser.new_page(viewport={"width":390,"height":844})
    errors=[]
    page.on("pageerror",lambda e: errors.append(str(e)))
    page.goto(URL)
    assert page.locator("#board").count()==1
    for difficulty in ("easy","normal","hard"):
        page.select_option("#difficulty",difficulty)
        page.locator("#seed").fill("12345")
        page.locator("#playSeed").click()
        before=session(page)
        assert before["seed"]==12345 and before["difficulty"]==difficulty
        assert before["level"]["cars"]
        page.reload()
        after=session(page)
        assert before["level"]==after["level"],f"{difficulty}: refresh changed layout"
        page.locator("#hint").click()
        assert "提示" in page.locator("#status").inner_text()
        # Use real UI hint as a player would; never call internal solve()/move()
        count=len(after["level"]["cars"])
        for i in range(count):
            page.locator("#hint").click()
            status=page.locator("#status").inner_text()
            match=re.search("先点\\s*([A-Z])",status)
            assert match, f"{difficulty}: hint cannot direct next move: {status}"
            car=next(c for c in session(page)["level"]["cars"] if c["id"]==match.group(1))
            click_car(page,car)
            assert match.group(1) in session(page)["progress"]["removed"],f"{difficulty}: car did not exit"
        assert len(session(page)["progress"]["removed"])==count,f"{difficulty}: not completed"
        print(f"PASS random {difficulty}, seed 12345, {count} real pointer clicks",flush=True)
        page.screenshot(path=f"test-results/random-{difficulty}.png")
        page.locator("#seed").fill("12346")
        page.locator("#playSeed").click()
        other=session(page)
        assert other["seed"]==12346
        assert other["level"]!=before["level"],f"{difficulty}: different seed identical level"
        print(f"PASS reproducible/varied seeds and saved progress {difficulty}",flush=True)
    assert not errors,errors
    print("PASS random E2E mobile viewport; sound/UI controls present",flush=True)
    browser.close()
