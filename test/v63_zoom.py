# -*- coding: utf-8 -*-
"""v63 zoom — PC 상단 브랜드 영역 확대 컷"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_ui as T
from playwright.sync_api import sync_playwright

OUT = '/workspace/downloads/erp-v63-화면/zoom'
os.makedirs(OUT, exist_ok=True)

with sync_playwright() as pw:
    env = dict(os.environ)
    libs = '/workspace/tool-results/chromelibs'
    if os.path.isdir(libs):
        env['LD_LIBRARY_PATH'] = libs + (':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    b = pw.chromium.launch(env=env)
    ctx = b.new_context(viewport={'width': 1920, 'height': 1080}, device_scale_factor=2)
    page = ctx.new_page()
    page.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
    page.add_init_script(T.FAKE_WS)
    page.goto(T.BASE + '?v=v63zoom')
    page.wait_for_timeout(400)
    page.fill('#liEmail', 'kim@meat.co.kr')
    page.fill('#liPw', 'secret123')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=8000)
    page.wait_for_timeout(1800)
    page.add_style_tag(content='#toast{display:none !important}')
    page.screenshot(path=os.path.join(OUT, 'brand-1920.png'), clip={'x': 0, 'y': 0, 'width': 420, 'height': 300})
    print(page.evaluate("""() => {
      const g = s => { const el = document.querySelector(s); if (!el) return null; const r = el.getBoundingClientRect();
        const cs = getComputedStyle(el);
        return {t: el.innerText.replace(/\\s+/g,' ').trim(), x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height),
                fs: cs.fontSize, lh: cs.lineHeight, color: cs.color, fw: cs.fontWeight}; };
      return {brand: g('.brand'), h1: g('.brand h1'), sig: g('.brandsig'), sigb: g('.brandsig b'), sigs: g('.brandsig span'),
              side: g('#v8Side'), glabel: g('#v8Nav .glabel'), foot: g('.sidefoot')};
    }"""))
    ctx.close()
    b.close()
