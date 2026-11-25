# -*- coding: utf-8 -*-
"""v61 사전 점검 — 폰(390×844)에서 남은 입력 시트들이 지금 어떻게 보이는지 재 본다.
   (수정 전/후 비교용. 판정 없음, 수치와 스크린샷만)
   LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/v61_probe.py [tag]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_ui as T
import shot_v36 as V36
from playwright.sync_api import sync_playwright

TAG = sys.argv[1] if len(sys.argv) > 1 else 'before'
OUT = '/workspace/downloads/erp-v61-화면/' + TAG
os.makedirs(OUT, exist_ok=True)

GEOM = """(sel) => {
  const m = document.querySelector(sel);
  if (!m || m.classList.contains('hidden')) return { open: false };
  const card = m.querySelector('.modal-card');
  const cr = card.getBoundingClientRect();
  const wide = [];
  card.querySelectorAll('*').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width > 0 && (r.right > cr.right + 1.5 || r.left < cr.left - 1.5)) {
      wide.push({ tag: el.tagName, cls: (el.className && el.className.toString().slice(0, 40)) || '',
                  l: Math.round(r.left), r: Math.round(r.right) });
    }
  });
  return {
    open: true, cardH: Math.round(cr.height), cardW: Math.round(cr.width),
    scrollH: card.scrollHeight, clientH: card.clientHeight,
    docOver: document.documentElement.scrollWidth - window.innerWidth,
    wideN: wide.length, wide: wide.slice(0, 6)
  };
}"""


def login(page):
    page.fill('#liEmail', 'kim@meat.co.kr')
    page.fill('#liPw', 'secret123')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=8000)
    page.wait_for_timeout(1800)
    page.add_style_tag(content='#toast{display:none !important}')


def show(page, sel, name):
    g = page.evaluate(GEOM, sel)
    print('  %-18s %s' % (name, json.dumps(g, ensure_ascii=False)))
    page.screenshot(path=os.path.join(OUT, name + '.png'))
    return g


def run(pw):
    env = dict(os.environ)
    libs = '/workspace/tool-results/chromelibs'
    if os.path.isdir(libs):
        env['LD_LIBRARY_PATH'] = libs + (':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
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

    # 1. 해동/냉동 이동 시트
    page.evaluate("() => document.querySelector('#mobTabs [data-mtab=\"out\"]').click()")
    page.wait_for_timeout(500)
    page.evaluate("() => document.querySelector('#mobSheet [data-nav=\"move\"]').click()")
    page.wait_for_timeout(900)
    show(page, '#uniMoveModal', 'A1-이동시트-첫화면')
    page.evaluate("() => { const c = document.querySelector('#uniMoveModal .modal-card'); c.scrollTop = 400; }")
    page.wait_for_timeout(300)
    page.screenshot(path=os.path.join(OUT, 'A2-이동시트-아래.png'))
    order = page.evaluate("""() => {
      const m = document.getElementById('uniMoveModal');
      const y = s => { const e = m.querySelector(s); if (!e) return -1;
        const r = e.getBoundingClientRect(); return r.height ? Math.round(r.top) : -1; };
      return { seg: y('#uniMoveSeg'), date: y('#uniMoveDate'), lot: y('#uniMoveLotQ'),
               kg: y('#uniMoveKg'), prod: y('#uniMoveProd'), note: y('#uniMoveNote'),
               price: y('#uniMovePrice'), stat: y('#uniMoveStat'),
               subH: Math.round(document.querySelector('#uniMoveModal .modal-sub').getBoundingClientRect().height) }; }""")
    print('   이동 순서:', json.dumps(order, ensure_ascii=False))
    page.click('#uniMoveClose')
    page.wait_for_timeout(300)

    # 2. 매출 전표 시트
    page.evaluate("() => document.getElementById('btnAccSale').click()")
    page.wait_for_timeout(900)
    show(page, '#accVoucherModal', 'B1-매출전표-첫화면')
    page.evaluate("() => { const c = document.querySelector('#accVoucherModal .modal-card'); c.scrollTop = 420; }")
    page.wait_for_timeout(300)
    page.screenshot(path=os.path.join(OUT, 'B2-매출전표-아래.png'))
    page.evaluate("() => { const c = document.querySelector('#accVoucherModal .modal-card'); c.scrollTop = 0; }")
    page.wait_for_timeout(250)
    vor = page.evaluate("""() => {
      const m = document.getElementById('accVoucherModal');
      const y = s => { const e = m.querySelector(s); if (!e) return -1;
        const r = e.getBoundingClientRect(); return r.height ? Math.round(r.top) : -1; };
      const tbl = m.querySelector('#accVSheet');
      return { date: y('#accVDate'), partner: y('#accVPartner'), seg: y('#accVoucherSeg'),
               doc: y('#accVDoc'), note: y('#accVNote'), row: y('#accVSheetBody tr'),
               add: y('#accVAddRow'), subH: Math.round(m.querySelector('.modal-sub').getBoundingClientRect().height),
               tblW: Math.round(tbl.getBoundingClientRect().width),
               tblScroll: m.querySelector('.vsheet-scroll') ? Math.round(m.querySelector('.vsheet-scroll').scrollWidth) : -1 }; }""")
    print('   매출전표 순서:', json.dumps(vor, ensure_ascii=False))
    # 품명 검색 드롭다운
    page.click('#accVSheetBody [data-f="name"]')
    page.type('#accVSheetBody [data-f="name"]', '우양지', delay=80)
    page.wait_for_timeout(600)
    pop = page.evaluate("""() => { const p = document.querySelector('.acpop');
        if (!p || p.classList.contains('hidden')) return { open: false };
        const r = p.getBoundingClientRect(), it = p.querySelector('.acitem');
        return { open: true, n: p.querySelectorAll('.acitem').length, l: Math.round(r.left), r: Math.round(r.right),
                 bottom: Math.round(r.bottom), vh: window.innerHeight,
                 rowH: it ? Math.round(it.getBoundingClientRect().height) : 0 }; }""")
    print('   매출전표 검색목록:', json.dumps(pop, ensure_ascii=False))
    page.screenshot(path=os.path.join(OUT, 'B3-매출전표-검색목록.png'))
    page.click('#accVoucherClose')
    page.wait_for_timeout(300)

    # 3. 매입 전표 시트
    page.evaluate("() => document.getElementById('btnAccBuy').click()")
    page.wait_for_timeout(900)
    show(page, '#accVoucherModal', 'C1-매입전표-첫화면')
    page.click('#accVoucherClose')
    page.wait_for_timeout(300)

    # 4. 수금 입력 시트
    page.evaluate("() => document.getElementById('btnAccPayIn').click()")
    page.wait_for_timeout(800)
    show(page, '#accPayModal', 'D1-수금시트')
    page.click('#accPayClose')
    page.wait_for_timeout(300)

    # 5. 경비 시트
    page.evaluate("() => document.getElementById('btnAccExpense').click()")
    page.wait_for_timeout(800)
    show(page, '#accExpModal', 'D2-경비시트')
    page.click('#accExpClose')
    page.wait_for_timeout(300)

    # 6. 원료육 로트 수정 시트
    page.evaluate("() => document.querySelector('#mobTabs [data-mtab=\"stock\"]').click()")
    page.wait_for_timeout(1200)
    page.evaluate("() => document.querySelector('#mobTabs [data-mtab=\"more\"]').click()")
    page.wait_for_timeout(500)
    page.evaluate("() => document.querySelector('#mobSheet [data-nav=\"stock:meat\"]').click()")
    page.wait_for_timeout(1200)
    has = page.evaluate("() => document.querySelectorAll('#tableWrap .actmenu').length")
    print('   재고 작업 버튼 수:', has)
    if has:
        page.evaluate("() => document.querySelector('#tableWrap .actmenu').click()")
        page.wait_for_timeout(500)
        page.screenshot(path=os.path.join(OUT, 'E0-로트-작업메뉴.png'))
        page.evaluate("""() => { const bs = Array.from(document.querySelectorAll('#rowMenu button[data-mi]'));
            const b = bs.find(x => x.textContent.trim() === '수정'); if (b) b.click(); }""")
        page.wait_for_timeout(900)
        show(page, '#lotModal', 'E1-로트수정')
        page.evaluate("() => { const c = document.querySelector('#lotModal .modal-card'); c.scrollTop = 500; }")
        page.wait_for_timeout(300)
        page.screenshot(path=os.path.join(OUT, 'E2-로트수정-아래.png'))
        page.click('#lotClose')
        page.wait_for_timeout(300)

    # 7. 품목 등록 시트
    page.evaluate("() => document.getElementById('btnFgNew') && document.getElementById('btnFgNew').click()")
    page.wait_for_timeout(300)
    page.evaluate("() => { const b = document.querySelector('[data-io=\"fp-new\"]'); if (b) b.click(); }")
    page.wait_for_timeout(800)
    show(page, '#fgNewModal', 'F1-품목등록')
    page.evaluate("() => { const c = document.querySelector('#fgNewModal .modal-card'); c.scrollTop = 600; }")
    page.wait_for_timeout(300)
    page.screenshot(path=os.path.join(OUT, 'F2-품목등록-아래.png'))
    page.click('#fgNewClose')
    page.wait_for_timeout(300)

    # 8. 거래명세표 (전표 저장 후 매출 내역에서)
    page.evaluate("() => document.getElementById('btnAccSale').click()")
    page.wait_for_timeout(800)
    page.fill('#accVPartner', '미트박스')
    page.click('#accVSheetBody [data-f="name"]')
    page.type('#accVSheetBody [data-f="name"]', '우양지', delay=70)
    page.wait_for_timeout(500)
    if page.evaluate("() => { const p = document.querySelector('.acpop'); return !!p && !p.classList.contains('hidden'); }"):
        page.evaluate("() => document.querySelector('.acpop .acitem').click()")
        page.wait_for_timeout(500)
    page.fill('#accVSheetBody [data-f="qty"]', '5')
    page.fill('#accVSheetBody [data-f="price"]', '12000')
    page.wait_for_timeout(300)
    page.click('#accVoucherSave')
    page.wait_for_timeout(1600)
    print('   저장된 전표:', json.dumps([{k: v for k, v in x.items() if k in ('id', 'v_type', 'partner', 'total')}
                                   for x in T.MOCK.vouchers], ensure_ascii=False))
    page.evaluate("() => document.querySelector('#mobTabs [data-mtab=\"more\"]').click()")
    page.wait_for_timeout(400)
    page.evaluate("() => document.querySelector('#mobSheet [data-nav=\"sale-list\"]').click()")
    page.wait_for_timeout(1500)
    page.screenshot(path=os.path.join(OUT, 'G0-매출내역.png'))
    nm = page.evaluate("() => document.querySelectorAll('#saleTableWrap .actmenu').length")
    print('   매출내역 작업 버튼 수:', nm)
    if nm:
        page.evaluate("() => document.querySelector('#saleTableWrap .actmenu').click()")
        page.wait_for_timeout(500)
        page.evaluate("""() => { const bs = Array.from(document.querySelectorAll('#rowMenu button[data-mi]'));
            const b = bs.find(x => x.textContent.trim() === '거래명세표'); if (b) b.click(); }""")
        page.wait_for_timeout(1200)
        show(page, '#stmtModal', 'G1-거래명세표')
        page.click('#stmtClose')
        page.wait_for_timeout(300)

    print('   JS 오류:', errs[:4])
    over = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    print('   화면 가로 넘침:', over)
    ctx.close()
    b.close()


with sync_playwright() as pw:
    run(pw)
print('DONE')
