# -*- coding: utf-8 -*-
"""v57 — 작은 노트북 화면(1366x650)에서 목록이 화면/카드 밖으로 나가지 않는지 (읽기 전용)"""
import json, os, sys
os.environ.setdefault('LD_LIBRARY_PATH', '/workspace/tool-results/chromelibs')
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'https://perreo69.github.io/123456/?v=20261125_66'
OUT = '/workspace/downloads/erp-v57-live'
os.makedirs(OUT, exist_ok=True)
errors = []

POP = """() => { const p = document.getElementById('uniMoveLotPop');
  const c = document.querySelector('#uniMoveModal .modal-card');
  return {rect: (r => [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)])(p.getBoundingClientRect()),
          card: (r => [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)])(c.getBoundingClientRect()),
          vh: innerHeight, vw: innerWidth, n: p.querySelectorAll('.lcitem').length}; }"""

with sync_playwright() as pw:
    b = pw.chromium.launch(env=dict(os.environ))
    for w, h, tag in [(1366, 650, 'small'), (1024, 600, 'tiny')]:
        page = b.new_page(viewport={'width': w, 'height': h})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(BASE)
        page.wait_for_timeout(1200)
        page.fill('#liEmail', 'perreo@nate.com')
        page.fill('#liPw', '123456')
        page.click('#btnLogin')
        page.wait_for_selector('#appView:not(.hidden)', timeout=45000)
        page.wait_for_timeout(7000)
        page.evaluate("() => { const b = document.querySelector('#v8Side [data-nav=\"move\"]'); if (b) b.click(); }")
        page.wait_for_timeout(2000)
        page.click('#uniMoveLotQ')
        page.wait_for_timeout(800)
        d = page.evaluate(POP)
        ok_r = d['rect'][0] >= 0 and d['rect'][0] + d['rect'][2] <= d['vw'] + 1
        ok_b = d['rect'][1] + d['rect'][3] <= d['vh'] + 1
        print(tag, json.dumps(d, ensure_ascii=False), '좌우OK', ok_r, '아래OK', ok_b)
        page.screenshot(path=os.path.join(OUT, '07-%s.png' % tag))
        page.close()
    print('JS 오류', errors[:3])
    b.close()
