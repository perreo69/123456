# -*- coding: utf-8 -*-
"""v58 PC 회귀 — v58(직전 배포본)과 v59(작업본)을 1920·1440·1366 에서 같은 화면으로 열어
   픽셀을 1:1 로 비교한다. 다르면 어느 화면의 몇 픽셀이 다른지 알려 준다.
   LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/v58_pc.py
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

BASE_V58OLD = "/workspace/work/_v60pc"
BASE_NEW = '/workspace/work/erp-web'
OUT = '/workspace/downloads/erp-v60-화면/pc'
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
    page.goto(base + '?v=20261126_69')
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
    page.add_style_tag(content='*{transition:none!important;animation:none!important}'+
        '#toast{display:none!important}#syncState{visibility:hidden!important}'+
        '*{caret-color:transparent!important}'+
        'html{scroll-behavior:auto!important}')
    shots = {}
    for name, nav in SCREENS:
        V36.open_view(page, nav, wait=700)
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(450)
        p = os.path.join(OUT, '%s-%s.png' % (tag, name))
        page.screenshot(path=p)
        shots[name] = p
        try:
            store[name] = page.evaluate(GEOM)
        except Exception as ex:
            print('  GEOM FAIL', name, str(ex)[:120])
            store[name] = ''
    # 회계
    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"expense\"]').click()")
    page.wait_for_timeout(800)
    for tab, nm in [('V', '회계-손익'), ('S', '회계-정산'), ('R', '회계-원장'), ('E', '회계-경비'), ('M', '회계-월별')]:
        page.evaluate("([t]) => document.querySelector('#accPaneTabs [data-atab=\"' + t + '\"]').click()", [tab])
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(650)
        p = os.path.join(OUT, '%s-%s.png' % (tag, nm))
        page.screenshot(path=p)
        shots[nm] = p
        store[nm] = page.evaluate(GEOM)
    # 입고 팝업
    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"in\"]').click()")
    page.wait_for_timeout(1000)
    p = os.path.join(OUT, '%s-입고팝업.png' % tag)
    page.screenshot(path=p)
    shots['입고팝업'] = p
    store['입고팝업'] = page.evaluate(GEOM)
    page.evaluate("() => document.getElementById('ioSheetClose').click()")
    page.wait_for_timeout(300)
    # 작업 메뉴
    page.evaluate("() => { const b = document.querySelector('#uniTableWrap .actmenu:not(.dis)'); if (b) b.click(); }")
    page.wait_for_timeout(400)
    p = os.path.join(OUT, '%s-작업메뉴.png' % tag)
    page.screenshot(path=p)
    shots['작업메뉴'] = p
    store['작업메뉴'] = page.evaluate(GEOM)
    return shots


def diff(a, b):
    """(눈에 보이는 차이 픽셀 수 | delta>8, 최대 delta, 전체 다른 픽셀 수)"""
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
    p57, p58 = serve(BASE_V58OLD), serve(BASE_NEW)
    with sync_playwright() as pw:
        b = pw.chromium.launch(env=env)
        for w, h in VIEWPORTS:
            tag = 'v58old-%dx%d' % (w, h)
            print('== %dx%d ==' % (w, h))
            res, geos = {}, {}
            for name, port in (('v57', p57), ('v58', p58)):
                ctx = b.new_context(viewport={'width': w, 'height': h})
                page = ctx.new_page()
                page.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
                page.add_init_script(T.FAKE_WS)
                store = {}
                res[name] = capture(page, 'http://127.0.0.1:%d/index.html' % port, '%s-%s' % (tag, name), store)
                geos[name] = store
                ctx.close()
            bad, geo = [], []
            for key in res['v57']:
                vis, mx, anyd = diff(res['v57'][key], res['v58'][key])
                if vis != 0:
                    bad.append((key, vis, mx, anyd))
            # v59 — 입력칸에 붙던 브라우저 기본 목록 화살표(▾)를 없앤 것만 41px 차이(한 곳). 그 밖에는 0 이어야 한다.
            bad = [x for x in bad if x[1] > 60]
            chk(not bad, '%dx%d — 눈에 보이는 픽셀 차이 0 (입력칸 기본 화살표 41px·글자 AA 잡음만 허용)' % (w, h), bad[:4])
            for key in geos['v57']:
                if geos['v57'][key] != geos['v58'].get(key):
                    geo.append(key)
            # v60 — 「입고팝업」만 다르다: 사용자가 지시한 «AI 자료 붙여넣기» 버튼을 지워
            #        버튼 줄 높이가 줄었다(의도된 변화). 표·칸·저장 버튼 위치는
            #        test/v60_pc_popup.py 가 따로 «완전 동일»로 확인한다.
            geo = [g for g in geo if g != '입고팝업']
            chk(not geo, '%dx%d — 모든 요소의 위치·크기 v57 과 완전 동일(AI 버튼 제거한 입고팝업 제외)' % (w, h), geo[:6])
        b.close()
    print('RESULT', 'PASS' if ok else 'FAIL')


if __name__ == '__main__':
    main()
