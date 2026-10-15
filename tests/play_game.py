import json
import os
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = os.environ.get("GAME_URL", "http://127.0.0.1:8765/parking/")
ARTIFACTS = Path("test-results")
ARTIFACTS.mkdir(exist_ok=True)

def click_board(page, x, y):
    rect = page.locator("canvas").bounding_box()
    assert rect, "Canvas missing"
    page.mouse.click(rect["x"] + x * rect["width"] / 360,
                     rect["y"] + y * rect["height"] / 640)

def saved(page):
    value = page.evaluate("localStorage.getItem('nc-mg-001')")
    return json.loads(value) if value else {}

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(URL, wait_until="load")
    assert page.locator("canvas").count() == 1
    source = page.locator("script").first.inner_text()
    match = re.search(r"var prototype_default = (\[.*?\]);\s*// src/core/game.ts", source, re.S)
    assert match, "Cannot discover levels from bundled source"
    levels = page.evaluate("(src) => (new Function('return (' + src + ')'))()", match.group(1))
    assert len(levels) == 24, f"Expected 24 levels; got {len(levels)}"
    print(f"Testing {len(levels)} levels using real browser pointer events")

    try:
        for index, level in enumerate(levels):
            assert saved(page).get("current", 0) == index, f"Wrong current level at {index+1}"
            for car_id in level["solution"]:
                car = next(c for c in level["cars"] if c["id"] == car_id)
                horizontal = car["direction"] in ("E", "W")
                cx = 24 + (car["x"] + (car["length"] / 2 if horizontal else .5)) * 52
                cy = 142 + (car["y"] + (.5 if horizontal else car["length"] / 2)) * 52
                click_board(page, cx, cy)
                page.wait_for_timeout(310)
                state = saved(page)
                assert car_id in state.get("removed", []), (
                    f"Level {index+1} car {car_id} did not leave: {state}")
            state = saved(page)
            assert state.get("completed", 0) >= index + 1, (
                f"Level {index+1} not completed: {state}")
            print(f"PASS level {index+1:02d} {level['level_id']} ({len(level['solution'])} moves)")
            if index < len(levels) - 1:
                click_board(page, 290, 504)
                page.wait_for_timeout(80)
        page.screenshot(path=str(ARTIFACTS / "all-levels-passed.png"))
        assert not errors, f"Browser JavaScript errors: {errors}"
        print("PASS: all 24 levels completed by genuine canvas pointer clicks")
    except Exception:
        page.screenshot(path=str(ARTIFACTS / "failure.png"))
        print("Browser errors:", errors)
        print("Current save:", saved(page))
        raise
    finally:
        browser.close()
