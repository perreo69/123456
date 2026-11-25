# -*- coding: utf-8 -*-
"""v61 PC 회귀 — v60(작업 전 사본 /workspace/work/_v61pc)과 v61(작업본)을
   1920·1440·1366 에서 같은 화면으로 열어 픽셀과 요소 위치를 1:1 로 비교한다.
   LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/v61_pc.py
"""
import os
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_ui as T
import shot_v36 as V36
from playwright.sync_api import sync_playwright
from PIL import Image
import numpy as np

BASE_OLD = '/workspace/work/_v61pc'
BASE_NEW = '/workspace/work/erp-web'
OUT = '/workspace/downloads/erp-v61-화면/pc'
ok = True


def chk(cond, label, extra=''):
    global ok
    print(('  [OK]   ' if cond else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not cond:
        ok = False


def serve(root):
    class H(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=root, **kw)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(('127.0.0.1', 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


GEOM = """() => {
  const root = document.getElementById('appView');
  const out = [];
  const walk = (el) => {
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden' || el.classList.contains('hidden')) return;
    const r = el.getBoundingClientRect();
    if (r.width < 1 && r.height < 1) return;
    out.push(el.tagName + '|' + Math.round(r.left) + ',' + Math.round(r.top) + ',' + Math.round(r.width) + ',' + Math.round(r.height));
    for (const c of el.children) walk(c);
  };
  walk(root);
  return out.join(' ;; ');
}"""

SCREENS = [
    ('원료육전체', 'stock:meat'),
    ('냉동고', 'stock:meat:F'),
    ('완제품', 'stock:fg'),
    ('부자재', 'stock:sub'),
    ('전체재고', 'stock:all'),
    ('입출고내역', 'tx'),
    ('매입내역', 'buy-list'),
    ('매출내역', 'sale-list'),
    ('미지급금', 'buy-status'),
    ('미수금', 'sale-status'),
    ('품목관리', 'items'),
]
VIEWPORTS = [(1920, 1080), (1440, 900), (1366, 768)]


def seed_acc():
    w = {'worker_name': '김검증', 'worker_email': 'kim@meat.co.kr', 'created_at': '2026-11-18T00:00:00Z'}
    T.MOCK.vouchers += [
        dict(id=1, source='manual', source_kind='', source_id=None, v_date='2026-11-20', v_type='sale',
             partner='도드람푸드', tax_type='tax', supply_amount=1200000, vat_amount=120000, total_amount=1320000,
             tax_status='issued', note='11월 납품분', **w),
        dict(id=2, source='manual', source_kind='', source_id=None, v_date='2026-11-22', v_type='purchase',
             partner='하림', tax_type='tax', supply_amount=860000, vat_amount=86000, total_amount=946000,
             tax_status='none', note='닭고기 매입', **w),
    ]
    T.MOCK.seq_v = 2


def capture(page, base, tag, store):
    page.goto(base + '?v=20261126_70')
    page.wait_for_timeout(500)
    page.fill('#liEmail', 'kim@meat.co.kr')
    page.fill('#liPw', 'secret123')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=8000)
    page.wait_for_timeout(2200)
    try:
        page.evaluate("async () => { if (document.fonts && document.fonts.ready) { await document.fonts.ready; } }")
    except Exception:
        pass
    page.wait_for_timeout(400)
    page.add_style_tag(content='*{transition:none!important;animation:none!important}' +
                       '#toast{display:none!important}#syncState{visibility:hidden!important}' +
                       '*{caret-color:transparent!important}' +
                       'html{scroll-behavior:auto!important}')
    shots = {}

    def shot(name):
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(320)
        p = os.path.join(OUT, '%s-%s.png' % (tag, name))
        page.screenshot(path=p)
        shots[name] = p
        store[name] = page.evaluate(GEOM)

    for name, nav in SCREENS:
        V36.open_view(page, nav, wait=700)
        shot(name)
    # 회계
    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"expense\"]').click()")
    page.wait_for_timeout(800)
    for tab, nm in [('V', '회계-손익'), ('S', '회계-정산'), ('R', '회계-원장'), ('E', '회계-경비'), ('M', '회계-월별')]:
        page.evaluate("([t]) => document.querySelector('#accPaneTabs [data-atab=\"' + t + '\"]').click()", [tab])
        page.wait_for_timeout(600)
        shot(nm)
    # 팝업들 — v61 에서 손댄 시트 전부
    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"in\"]').click()")
    page.wait_for_timeout(900)
    shot('입고팝업')
    page.evaluate("() => document.getElementById('ioSheetClose').click()")
    page.wait_for_timeout(300)

    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"move\"]').click()")
    page.wait_for_timeout(700)
    shot('이동팝업')
    page.evaluate("() => document.getElementById('uniMoveClose').click()")
    page.wait_for_timeout(300)

    for btn, nm, close in (('btnAccSale', '매출전표', 'accVoucherClose'),
                           ('btnAccBuy', '매입전표', 'accVoucherClose'),
                           ('btnAccPayIn', '수금', 'accPayClose'),
                           ('btnAccExpense', '경비', 'accExpClose')):
        page.evaluate("(id) => document.getElementById(id).click()", btn)
        page.wait_for_timeout(700)
        shot(nm)
        page.evaluate("(id) => document.getElementById(id).click()", close)
        page.wait_for_timeout(300)

    # 로트 수정 팝업
    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"stock:meat\"]').click()")
    page.wait_for_timeout(1200)
    page.evaluate("() => { const b = document.querySelector('#uniTableWrap .actmenu:not(.dis), #tableWrap .actmenu:not(.dis)'); if (b) b.click(); }")
    page.wait_for_timeout(400)
    page.evaluate("""() => { const bs = Array.from(document.querySelectorAll('#rowMenu button[data-mi]'));
        const b = bs.find(x => x.textContent.trim() === '수정'); if (b) b.click(); }""")
    page.wait_for_timeout(800)
    shot('로트수정')
    page.evaluate("() => document.getElementById('lotClose').click()")
    page.wait_for_timeout(300)

    # 품목 등록 팝업
    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"items\"]').click()")
    page.wait_for_timeout(1000)
    page.evaluate("() => document.getElementById('itemsBtnNew').click()")
    page.wait_for_timeout(700)
    shot('품목등록')
    page.evaluate("() => document.getElementById('fgNewClose').click()")
    page.wait_for_timeout(300)

    # 작업 메뉴
    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"stock:meat\"]').click()")
    page.wait_for_timeout(1000)
    page.evaluate("() => { const b = document.querySelector('#uniTableWrap .actmenu:not(.dis), #tableWrap .actmenu:not(.dis)'); if (b) b.click(); }")
    page.wait_for_timeout(400)
    shot('작업메뉴')
    return shots


def diff(a, b):
    ia = np.asarray(Image.open(a).convert('RGB')).astype(np.int16)
    ib = np.asarray(Image.open(b).convert('RGB')).astype(np.int16)
    if ia.shape != ib.shape:
        return -1, 999, -1
    d = np.abs(ia - ib).max(axis=2)
    return int((d > 8).sum()), int(d.max()) if d.size else 0, int((d > 0).sum())


def main():
    os.makedirs(OUT, exist_ok=True)
    V36.seed_items()
    seed_acc()
    env = dict(os.environ)
    libs = '/workspace/tool-results/chromelibs'
    if os.path.isdir(libs):
        env['LD_LIBRARY_PATH'] = libs + (':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    p_old, p_new = serve(BASE_OLD), serve(BASE_NEW)
    with sync_playwright() as pw:
        b = pw.chromium.launch(env=env)
        for w, h in VIEWPORTS:
            tag = 'v61-%dx%d' % (w, h)
            print('== %dx%d ==' % (w, h))
            res, geos = {}, {}
            for nm, port in (('v60', p_old), ('v61', p_new)):
                ctx = b.new_context(viewport={'width': w, 'height': h})
                page = ctx.new_page()
                page.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
                page.add_init_script(T.FAKE_WS)
                st = {}
                res[nm] = capture(page, 'http://127.0.0.1:%d/index.html' % port, tag + '-' + nm, st)
                geos[nm] = st
                ctx.close()
            bad, geo = [], []
            for key in res['v60']:
                vis, mx, anyd = diff(res['v60'][key], res['v61'][key])
                if vis != 0:
                    bad.append((key, vis, mx, anyd))
            print('   다른 화면:', bad)
            chk(not bad, '%dx%d — PC 픽셀 차이 0 (모든 화면·팝업)' % (w, h), bad[:5])
            miss = [k for k in geos['v60'] if geos['v60'][k] != geos['v61'].get(k)]
            print('   위치가 다른 화면:', miss)
            chk(not miss, '%dx%d — 모든 요소의 위치·크기 v60 과 완전 동일' % (w, h), miss[:5])
        b.close()
    print('RESULT', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
