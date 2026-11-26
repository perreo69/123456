# -*- coding: utf-8 -*-
"""v63 가벼운 회귀 — 머리 높이(64px) 변경 뒤 팝업·다른 화면이 그대로인지 (무거운 test_ui 는 돌리지 않는다)"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_ui as T
from playwright.sync_api import sync_playwright

OUT = '/workspace/downloads/erp-v63-화면/smoke'
os.makedirs(OUT, exist_ok=True)
fails = []
errors = []


def chk(c, label, extra=''):
    print(('  [OK]   ' if c else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not c:
        fails.append(label)


with sync_playwright() as pw:
    env = dict(os.environ)
    libs = '/workspace/tool-results/chromelibs'
    if os.path.isdir(libs):
        env['LD_LIBRARY_PATH'] = libs + (':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    b = pw.chromium.launch(env=env)
    page = b.new_page(viewport={'width': 1920, 'height': 1080})
    page.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
    page.add_init_script(T.FAKE_WS)
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(T.BASE + '?v=v63smoke')
    page.wait_for_timeout(400)
    page.fill('#liEmail', 'kim@meat.co.kr')
    page.fill('#liPw', 'secret123')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=10000)
    page.wait_for_timeout(1600)
    page.add_style_tag(content='#toast{display:none !important}')

    # 입고 팝업
    page.click('#v8Side [data-nav="in"]')
    page.wait_for_timeout(1200)
    g = page.evaluate("""() => { const m = document.getElementById('ioSheetModal');
        const card = m.querySelector('.modal-card'); const r = card.getBoundingClientRect();
        const rows = document.querySelectorAll('#ioSheetBody tr').length;
        return {open: !m.classList.contains('hidden'), top: Math.round(r.top), bottom: Math.round(r.bottom),
                vh: innerHeight, over: document.documentElement.scrollWidth - innerWidth, rows: rows}; }""")
    chk(g['open'] and g['rows'] > 0 and g['over'] == 0, '입고 팝업 정상 · 넘침 0', g)
    chk(g['bottom'] <= g['vh'], '팝업이 화면 안에', g)
    page.screenshot(path=os.path.join(OUT, 'popup.png'))
    page.keyboard.press('Escape')
    page.wait_for_timeout(600)

    for nav, name in (('items', '품목관리'), ('stock:fg', '완제품'), ('buy-list', '매입')):
        page.evaluate("(n) => document.querySelector('#v8Side [data-nav=\"' + n + '\"]').click()", nav)
        page.wait_for_timeout(1200)
        s = page.evaluate("""() => ({title: (document.getElementById('v8Title')||{}).textContent,
            over: document.documentElement.scrollWidth - innerWidth,
            sideTop: Math.round(document.getElementById('v8Side').getBoundingClientRect().top),
            brand: !document.querySelector('.brand .logo') ? 'none' : getComputedStyle(document.querySelector('.brand .logo')).display})""")
        chk(s['over'] == 0 and s['sideTop'] >= 64, '%s 화면 정상(넘침 0 · 사이드바 %dpx)' % (name, s['sideTop']), s)
        page.screenshot(path=os.path.join(OUT, name + '.png'))
    page.close()
    b.close()

print('JS errors:', errors)
chk(not errors, 'JS 오류 0건', errors[:2])
print('=== %s ===' % ('ALL OK' if not fails else 'FAIL: %s' % fails))
sys.exit(0 if not fails else 1)
