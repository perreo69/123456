# -*- coding: utf-8 -*-
"""v59 조사 — 폰 출고 시트 「생산품목」·「거래처」 칸에 글자를 쳤을 때 목록이 뜨는지 본다.
   LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/v59_probe.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_ui as T
import shot_v36 as V36
from playwright.sync_api import sync_playwright

TAG = sys.argv[1] if len(sys.argv) > 1 else 'probe'
OUT = '/workspace/downloads/erp-v59-화면/' + TAG
os.makedirs(OUT, exist_ok=True)


def state(page):
    return page.evaluate("""() => {
      const p = document.querySelector('.acpop');
      const open = p && !p.classList.contains('hidden');
      const items = p ? Array.from(p.querySelectorAll('.acitem .act')).map(e => e.textContent) : [];
      const cs = p ? getComputedStyle(p) : null;
      const r = p ? p.getBoundingClientRect() : null;
      const vv = window.visualViewport;
      return { pop: !!p, open: !!open, n: p ? p.querySelectorAll('.acitem').length : 0,
               z: cs ? cs.zIndex : '', items: items,
               rect: r ? [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)] : null,
               maxH: cs ? cs.maxHeight : '', scrollH: p ? p.scrollHeight : 0,
               vv: vv ? [Math.round(vv.height), Math.round(vv.offsetTop)] : null, ih: window.innerHeight };
    }""")


def run_mobile(pw):
    env = dict(os.environ)
    libs = '/workspace/tool-results/chromelibs'
    if os.path.isdir(libs):
        env['LD_LIBRARY_PATH'] = libs + (':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    errs = []
    b = pw.chromium.launch(env=env)
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    page = ctx.new_page()
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.on('console', lambda m: errs.append('console:' + m.text) if m.type == 'error' else None)
    page.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
    page.add_init_script(T.FAKE_WS)
    V36.seed_items()
    page.goto(T.BASE + '?v=20261125_67')
    page.wait_for_timeout(400)
    page.fill('#liEmail', 'kim@meat.co.kr')
    page.fill('#liPw', 'secret123')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=8000)
    page.wait_for_timeout(1800)
    page.add_style_tag(content='#toast{display:none !important}')
    page.click('#mobTabs [data-mtab="out"]')
    page.wait_for_timeout(500)
    page.click('#mobSheet [data-nav="out"]')
    page.wait_for_timeout(900)
    print('MODAL', page.evaluate("() => { const m = document.getElementById('ioSheetModal'); return m.className; }"))
    # 현장(생산) 상태에서 생산품목 칸
    print('DEST', page.evaluate("() => (document.querySelector('#ioSheetDestSeg button.active')||{}).getAttribute?.('data-dest')"))
    print('LIST ATTR', page.evaluate("() => document.getElementById('ioSheetPartner').getAttribute('list')"))
    page.click('#ioSheetPartner')
    page.type('#ioSheetPartner', '슈프', delay=90)
    page.wait_for_timeout(700)
    print('STATE site', state(page))
    page.screenshot(path=os.path.join(OUT, 'M1-생산품목-슈프.png'))
    page.fill('#ioSheetPartner', '')
    # 업체(판매)로 바꾸고 거래처
    page.click('#ioSheetDestSeg button[data-dest="vendor"]')
    page.wait_for_timeout(300)
    page.click('#ioSheetPartner')
    page.type('#ioSheetPartner', '도드람', delay=90)
    page.wait_for_timeout(700)
    print('STATE vendor', state(page))
    page.screenshot(path=os.path.join(OUT, 'M2-거래처-도드람.png'))
    # 품목 줄 이름 칸(입고)
    page.click('#ioSheetClose')
    page.wait_for_timeout(300)
    page.click('#mobTabs [data-mtab="in"]')
    page.wait_for_timeout(900)
    ni = '#ioSheetBody tr[data-r="0"] input[data-f="name"]'
    page.click(ni)
    page.type(ni, '등갈', delay=90)
    page.wait_for_timeout(700)
    print('STATE row', state(page))
    page.screenshot(path=os.path.join(OUT, 'M3-품목줄-등갈.png'))
    print('ERRS', errs[:8])
    b.close()


def run_pc(pw):
    env = dict(os.environ)
    libs = '/workspace/tool-results/chromelibs'
    if os.path.isdir(libs):
        env['LD_LIBRARY_PATH'] = libs + (':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    errs = []
    b = pw.chromium.launch(env=env)
    ctx = b.new_context(viewport={'width': 1920, 'height': 1080})
    page = ctx.new_page()
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.on('console', lambda m: errs.append('console:' + m.text) if m.type == 'error' else None)
    page.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
    page.add_init_script(T.FAKE_WS)
    V36.seed_items()
    page.goto(T.BASE + '?v=20261125_67')
    page.wait_for_timeout(400)
    page.fill('#liEmail', 'kim@meat.co.kr')
    page.fill('#liPw', 'secret123')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=8000)
    page.wait_for_timeout(1800)
    page.add_style_tag(content='#toast{display:none !important}')
    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"out\"]').click()")
    page.wait_for_timeout(900)
    print('PC MODAL', page.evaluate("() => { const m = document.getElementById('ioSheetModal'); return m.className; }"))
    print('PC LIST ATTR', page.evaluate("() => document.getElementById('ioSheetPartner').getAttribute('list')"))
    page.click('#ioSheetPartner')
    page.type('#ioSheetPartner', '슈프', delay=70)
    page.wait_for_timeout(600)
    print('PC STATE', state(page))
    page.screenshot(path=os.path.join(OUT, 'PC1-생산품목-슈프.png'))
    print('PC ERRS', errs[:8])
    b.close()


with sync_playwright() as pw:
    run_mobile(pw)
    run_pc(pw)
