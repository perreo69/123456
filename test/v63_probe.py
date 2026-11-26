# -*- coding: utf-8 -*-
"""v63 probe — PC 사이드바/상단 브랜드 영역 지금 모습 기록 + 스크린샷

  LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/v63_probe.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_ui as T
from playwright.sync_api import sync_playwright

OUT = '/workspace/downloads/erp-v63-화면/probe'
os.makedirs(OUT, exist_ok=True)

DUMP = """() => {
  const pick = sel => { const el = document.querySelector(sel); if (!el) return null;
    const r = el.getBoundingClientRect();
    return {sel, text: el.innerText.replace(/\\s+/g,' ').trim(), x: Math.round(r.left), y: Math.round(r.top),
            w: Math.round(r.width), h: Math.round(r.height), display: getComputedStyle(el).display}; };
  return {
    top: pick('.top'), brand: pick('.brand'), logo: pick('.brand .logo'), h1: pick('.brand h1'),
    bp: pick('.brand p'),
    side: pick('#v8Side'), sideTop: pick('.side-top'), nav: pick('#v8Nav'),
    firstCard: pick('#v8Nav .nav-card'), glabel: pick('#v8Nav .glabel'),
    foot: pick('.sidefoot'), sfbrand: pick('.sfbrand'), sflinks: pick('.sflinks'),
  };
}"""


def main():
    errors = []
    with sync_playwright() as pw:
        env = dict(os.environ)
        libs = '/workspace/tool-results/chromelibs'
        if os.path.isdir(libs):
            env['LD_LIBRARY_PATH'] = libs + (':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
        b = pw.chromium.launch(env=env)
        for w, h in ((1920, 1080), (1440, 900)):
            ctx = b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=1)
            page = ctx.new_page()
            page.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
            page.add_init_script(T.FAKE_WS)
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto(T.BASE + '?v=v63probe')
            page.wait_for_timeout(400)
            page.fill('#liEmail', 'kim@meat.co.kr')
            page.fill('#liPw', 'secret123')
            page.click('#btnLogin')
            page.wait_for_selector('#appView:not(.hidden)', timeout=8000)
            page.wait_for_timeout(1800)
            page.add_style_tag(content='#toast{display:none !important}')
            import json
            print(w, json.dumps(page.evaluate(DUMP), ensure_ascii=False, indent=1))
            page.screenshot(path=os.path.join(OUT, 'pc-%d-top.png' % w))
            page.screenshot(path=os.path.join(OUT, 'pc-%d-side.png' % w),
                            clip={'x': 0, 'y': 0, 'width': 320, 'height': min(h, 700)})
            ctx.close()
        b.close()
    print('JS errors:', errors)


if __name__ == '__main__':
    main()
