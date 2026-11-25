# -*- coding: utf-8 -*-
"""v58 폰 — 거래명세표(A4) 팝업·인쇄 화면이 시트 안에서 깨지지 않는지."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_ui as T, shot_v36 as V36
from playwright.sync_api import sync_playwright
OUT = '/workspace/downloads/erp-v58-화면/final4'
env = dict(os.environ); env['LD_LIBRARY_PATH'] = '/workspace/tool-results/chromelibs'
ok = True
def chk(c, l, e=''):
    global ok
    print(('  [OK]   ' if c else '  [FAIL] ') + l + (('  ' + str(e)) if e != '' else ''))
    if not c: ok = False
with sync_playwright() as pw:
    b = pw.chromium.launch(env=env)
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    p = ctx.new_page()
    errs = []
    p.on('pageerror', lambda e: errs.append(str(e)))
    p.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
    p.add_init_script(T.FAKE_WS)
    V36.seed_items()
    p.goto(T.BASE + '?v=20261125_67')
    p.wait_for_timeout(400)
    p.fill('#liEmail', 'kim@meat.co.kr'); p.fill('#liPw', 'secret123')
    p.click('#btnLogin'); p.wait_for_selector('#appView:not(.hidden)')
    p.wait_for_timeout(2000)
    p.add_style_tag(content='#toast{display:none!important}')
    # 매출 화면의 「A4 거래명세표」 단추로 연다
    p.evaluate("() => document.querySelector('#v8Side [data-nav=\"sale-list\"]').click()")
    p.wait_for_timeout(1200)
    p.evaluate("() => { const b = document.getElementById('btnSaleStmt'); if (b) b.click(); }")
    p.wait_for_timeout(1200)
    info = p.evaluate("""() => {
      const ms = Array.from(document.querySelectorAll('.modal, dialog')).filter(m => !m.classList.contains('hidden') && m.offsetHeight > 0);
      const over = document.documentElement.scrollWidth - window.innerWidth;
      return {open: ms.map(m => m.id), over: over,
              box: ms.map(m => { const c = m.querySelector('.modal-card') || m; const r = c.getBoundingClientRect();
                return [m.id, Math.round(r.width), Math.round(r.left), Math.round(r.bottom), Math.round(window.innerHeight)]; })};
    }""")
    print('  ', info)
    chk(info['over'] == 0, '명세표 팝업에서도 화면 가로 넘침 0', info['over'])
    chk(not errs, 'JS 오류 0', errs[:2])
    p.screenshot(path=os.path.join(OUT, 'M-거래명세표.png'))
    b.close()
print('RESULT', 'PASS' if ok else 'FAIL')
