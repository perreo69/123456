# -*- coding: utf-8 -*-
"""v57 — 업체 열 폭/글자 폭 실측 (읽기 전용)"""
import json, os, sys
os.environ.setdefault('LD_LIBRARY_PATH', '/workspace/tool-results/chromelibs')
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'https://perreo69.github.io/123456/?v=20261125_66'
M = """() => { const p = document.getElementById('uniMoveLotPop');
  const rows = Array.from(p.querySelectorAll('.lcitem'));
  return rows.slice(0, 8).map(r => {
    const v = r.querySelector('.lcv'), n = r.querySelector('.lcn');
    return {v: v.textContent, vw: Math.round(v.clientWidth), vs: Math.round(v.scrollWidth),
            n: n.textContent, nw: Math.round(n.clientWidth), ns: Math.round(n.scrollWidth),
            cols: getComputedStyle(r).gridTemplateColumns, gap: getComputedStyle(r).columnGap};
  }); }"""

with sync_playwright() as pw:
    b = pw.chromium.launch(env=dict(os.environ))
    page = b.new_page(viewport={'width': 1920, 'height': 1080})
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
    print(json.dumps(page.evaluate(M), ensure_ascii=False, indent=1))
    b.close()
