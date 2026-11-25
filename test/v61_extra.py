# -*- coding: utf-8 -*-
"""v61 — 완제품 로트 수정 · 기존 전표 수정(vsimple) 화면 확인용"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_ui as T
import shot_v36 as V36
from playwright.sync_api import sync_playwright

OUT = '/workspace/downloads/erp-v61-화면/final4'
os.makedirs(OUT, exist_ok=True)


def login(page):
    page.fill('#liEmail', 'kim@meat.co.kr')
    page.fill('#liPw', 'secret123')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=8000)
    page.wait_for_timeout(1800)
    page.add_style_tag(content='#toast{display:none !important}')


def order_of(page, sel, pairs):
    return page.evaluate("""([sel, pairs]) => {
      const m = document.querySelector(sel), out = {};
      pairs.forEach(([k, s]) => { const e = m.querySelector(s);
        out[k] = e ? Math.round(e.getBoundingClientRect().top) : -1; });
      return out; }""", [sel, pairs])


with sync_playwright() as pw:
    env = dict(os.environ)
    libs = '/workspace/tool-results/chromelibs'
    if os.path.isdir(libs):
        env['LD_LIBRARY_PATH'] = libs + (':' + env.get('LD_LIBRARY_PATH', ''))
    b = pw.chromium.launch(env=env)
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    page = ctx.new_page()
    errs = []
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
    page.add_init_script(T.FAKE_WS)
    V36.seed_items()
    page.goto(T.BASE + '?v=20261126_70')
    page.wait_for_timeout(400)
    login(page)

    # 완제품 로트 수정
    page.evaluate("() => document.querySelector('#mobTabs [data-mtab=\"more\"]').click()")
    page.wait_for_timeout(400)
    page.evaluate("() => document.querySelector('#mobSheet [data-nav=\"stock:fg\"]').click()")
    page.wait_for_timeout(1500)
    page.evaluate("""() => { const bs = Array.from(document.querySelectorAll('.actmenu'))
          .filter(b => b.getBoundingClientRect().height > 0 && !b.classList.contains('dis'));
        if (bs[0]) bs[0].click(); }""")
    page.wait_for_timeout(400)
    items = page.evaluate("() => Array.from(document.querySelectorAll('#rowMenu button[data-mi]')).map(b => b.textContent.trim())")
    print('  완제품 작업 메뉴:', items)
    page.evaluate("""() => { const bs = Array.from(document.querySelectorAll('#rowMenu button[data-mi]'));
        const b = bs.find(x => x.textContent.trim() === '정보 수정') || bs.find(x => x.textContent.trim() === '수정');
        if (b) b.click(); }""")
    page.wait_for_timeout(900)
    o = order_of(page, '#fpLotModal', [('stock', '#fpLotQty'), ('why', '#fpLotWhy'), ('meta', '#fpLotNo')])
    print('  완제품 로트 수정 순서:', json.dumps(o, ensure_ascii=False))
    page.screenshot(path=os.path.join(OUT, 'K1-완제품로트수정.png'))
    page.evaluate("() => document.getElementById('fpLotClose').click()")
    page.wait_for_timeout(300)

    # 기존 전표 수정 (vsimple)
    page.evaluate("() => document.getElementById('btnAccSale').click()")
    page.wait_for_timeout(800)
    page.fill('#accVPartner', '미트박스')
    page.evaluate("() => document.querySelector('#accVSheetBody [data-f=\"name\"]').focus()")
    page.type('#accVSheetBody [data-f="name"]', '우양지', delay=80)
    page.wait_for_timeout(600)
    try:
        page.locator('.acpop:not(.hidden) .acitem').first.click(timeout=3000)
    except Exception as ex:
        print('  acpick fail', str(ex)[:80])
    page.wait_for_timeout(400)
    page.fill('#accVSheetBody [data-f="qty"]', '3')
    page.wait_for_timeout(300)
    page.click('#accVoucherSave')
    page.wait_for_timeout(1800)
    page.evaluate("() => document.querySelector('#mobTabs [data-mtab=\"more\"]').click()")
    page.wait_for_timeout(400)
    page.evaluate("() => document.querySelector('#mobSheet [data-nav=\"sale-list\"]').click()")
    page.wait_for_timeout(1500)
    page.evaluate("() => document.querySelector('#saleTableWrap .actmenu').click()")
    page.wait_for_timeout(400)
    page.evaluate("""() => { const bs = Array.from(document.querySelectorAll('#rowMenu button[data-mi]'));
        const b = bs.find(x => x.textContent.trim() === '수정'); if (b) b.click(); }""")
    page.wait_for_timeout(1000)
    vs = page.evaluate("""() => { const m = document.getElementById('accVoucherModal');
        const vis = s => { const e = m.querySelector(s); return !!e && e.getBoundingClientRect().height > 0; };
        return { open: !m.classList.contains('hidden'), simple: vis('#accVSimpleBox'),
                 sheet: vis('#accVSheetWrap'), hint: vis('#accVHint'),
                 amt: vis('#accVAmount'), ord: document.getElementById('accVSimpleBox').getBoundingClientRect().top }; }""")
    print('  기존 전표 수정:', json.dumps(vs, ensure_ascii=False))
    page.screenshot(path=os.path.join(OUT, 'K2-전표수정.png'))
    print('  errs', errs[:3])
    b.close()
