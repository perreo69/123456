# -*- coding: utf-8 -*-
"""v61 실서버 확인 (읽기 전용 — 저장·수정·삭제 버튼은 절대 누르지 않는다)

  LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/live_v61.py [URL] [OUT]

· 새 토큰 ?v=20261126_70 이 app.js · style.css · mobile.css 에 실제로 걸렸는지
· PC 1920: 매입/매출 전표가 «11칸 표» 그대로인지(폰 카드가 PC 로 새지 않았는지)
· 폰 390: 이동 시트 동선 · 매출 전표 카드(1장·가로 넘침 0) · 수금 시트 제목 위치 · 로트 수정 동선 ·
          품목 등록 동선 · 입고 엑셀 버튼이 하단 바에 가리지 않는지 · JS 오류 0
"""
import json
import os
import sys

os.environ.setdefault('LD_LIBRARY_PATH', '/workspace/tool-results/chromelibs')
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'https://perreo69.github.io/123456/?v=20261126_70'
TOKEN = BASE.split('v=')[1].split('&')[0] if 'v=' in BASE else ''
OUT = sys.argv[2] if len(sys.argv) > 2 else '/workspace/downloads/erp-v61-실서버'
os.makedirs(OUT, exist_ok=True)
errors, fails = [], []


def chk(cond, label, extra=''):
    print(('  [OK]   ' if cond else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not cond:
        fails.append(label)


OVER = """(sel) => {
  const m = document.querySelector(sel);
  if (!m) return { open: false };
  const card = m.querySelector('.modal-card');
  const cr = card.getBoundingClientRect();
  let worst = 0, who = '';
  card.querySelectorAll('*').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width <= 0) return;
    const over = Math.max(r.right - cr.right, cr.left - r.left);
    if (over > worst) { worst = over; who = el.tagName + '.' + ((el.className || '').toString().slice(0, 24)); }
  });
  return { open: !m.classList.contains('hidden'), over: Math.round(worst), who: who,
           docOver: document.documentElement.scrollWidth - window.innerWidth };
}"""


def login(page):
    page.fill('#liEmail', 'perreo@nate.com')
    page.fill('#liPw', '123456')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=45000)
    page.wait_for_timeout(6000)
    for _ in range(20):
        n = page.evaluate("() => (window.st && st.lots) ? st.lots.length : 0")
        if n > 0:
            break
        page.wait_for_timeout(1000)


def order_of(page, sel, pairs):
    return page.evaluate("""([sel, pairs]) => {
      const m = document.querySelector(sel), out = {};
      pairs.forEach(([k, s]) => { const e = m.querySelector(s);
        out[k] = e ? Math.round(e.getBoundingClientRect().top) : -1; });
      return out; }""", [sel, pairs])


def asc(d, keys):
    ys = [d[k] for k in keys]
    return all(ys[i] < ys[i + 1] for i in range(len(ys) - 1))


with sync_playwright() as pw:
    b = pw.chromium.launch(env=dict(os.environ))
    # ---------------------------------------------------------------- PC 1920
    page = b.new_page(viewport={'width': 1920, 'height': 1080})
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('dialog', lambda d: d.dismiss())
    page.goto(BASE)
    page.wait_for_timeout(1200)
    login(page)
    src = page.evaluate("() => (document.querySelector('script[src*=\"app.js\"]') || {}).src || ''")
    chk(TOKEN and TOKEN in src, '실서버 app.js 토큰 ' + TOKEN, src)
    chk(TOKEN and TOKEN in page.evaluate("() => (document.querySelector('link[href*=\"style.css\"]') || {}).href || ''"),
        '실서버 style.css 토큰 ' + TOKEN)
    chk(TOKEN and TOKEN in page.evaluate("() => (document.querySelector('link[href*=\"mobile.css\"]') || {}).href || ''"),
        '실서버 mobile.css 토큰 ' + TOKEN)
    page.evaluate("() => document.getElementById('btnAccSale').click()")
    page.wait_for_timeout(1200)
    pc = page.evaluate("""() => { const m = document.getElementById('accVoucherModal');
        const rows = m.querySelectorAll('#accVSheetBody tr');
        return { open: !m.classList.contains('hidden'), rows: rows.length,
                 tds: rows.length ? rows[0].children.length : 0,
                 mcard: m.querySelectorAll('#accVSheetBody tr[data-mcard]').length,
                 sum: getComputedStyle(document.getElementById('accVMSum')).display,
                 mob: matchMedia('(max-width: 768px)').matches }; }""")
    print('   PC 전표:', json.dumps(pc, ensure_ascii=False))
    chk(pc['open'] and pc['tds'] == 11 and pc['mcard'] == 0, 'PC — 전표는 지금까지의 11칸 표 그대로', pc)
    chk(pc['sum'] == 'none', 'PC — 폰 전용 합계줄은 숨김', pc['sum'])
    page.screenshot(path=os.path.join(OUT, 'L1-PC-매출전표.png'))
    page.evaluate("() => document.getElementById('accVoucherClose').click()")
    page.wait_for_timeout(400)
    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"move\"]').click()")
    page.wait_for_timeout(1000)
    page.screenshot(path=os.path.join(OUT, 'L2-PC-이동팝업.png'))
    page.evaluate("() => document.getElementById('uniMoveClose').click()")
    page.wait_for_timeout(300)
    page.close()

    # ---------------------------------------------------------------- 폰 390
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    page = ctx.new_page()
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('dialog', lambda d: d.dismiss())
    page.goto(BASE)
    page.wait_for_timeout(1000)
    login(page)
    page.add_style_tag(content='#toast{display:none !important}')

    # 이동 시트
    page.evaluate("() => document.querySelector('#mobTabs [data-mtab=\"out\"]').click()")
    page.wait_for_timeout(500)
    page.evaluate("() => document.querySelector('#mobSheet [data-nav=\"move\"]').click()")
    page.wait_for_timeout(1200)
    ov = page.evaluate(OVER, '#uniMoveModal')
    o = order_of(page, '#uniMoveModal', [('seg', '#uniMoveSeg'), ('date', '#uniMoveDate'), ('lot', '#uniMoveLotQ'),
                                         ('stat', '#uniMoveStat'), ('kg', '#uniMoveKg'), ('price', '#uniMovePrice'),
                                         ('prod', '#uniMoveProd'), ('note', '#uniMoveNote')])
    print('   이동 순서:', json.dumps(o, ensure_ascii=False))
    chk(ov['open'] and ov['over'] <= 1 and ov['docOver'] == 0, '폰 — 이동 시트 가로 넘침 0px', ov)
    chk(asc(o, ['seg', 'date', 'lot', 'stat', 'kg', 'price', 'prod', 'note']),
        '폰 — 이동 동선: 방향 → 날짜 → 로트 → 현재고 → 수량 → 단가 → 생산품명 → 비고', o)
    page.screenshot(path=os.path.join(OUT, 'M1-폰-이동시트.png'))
    page.evaluate("() => document.getElementById('uniMoveClose').click()")
    page.wait_for_timeout(400)

    # 매출 전표
    page.evaluate("() => document.getElementById('btnAccSale').click()")
    page.wait_for_timeout(1400)
    ov = page.evaluate(OVER, '#accVoucherModal')
    ncards = page.evaluate("() => document.querySelectorAll('#accVSheetBody tr[data-mcard]').length")
    o = order_of(page, '#accVoucherModal', [('type', '#accVoucherSeg'), ('date', '#accVDate'),
                                            ('partner', '#accVPartner'), ('card', '#accVSheetBody tr'),
                                            ('add', '#accVAddRow'), ('note', '#accVNote')])
    print('   전표 순서:', json.dumps(o, ensure_ascii=False))
    chk(ov['open'] and ov['over'] <= 1 and ov['docOver'] == 0, '폰 — 매출 전표 가로 넘침 0px', ov)
    chk(ncards == 1, '폰 — 전표 카드 1장으로 시작', ncards)
    chk(asc(o, ['type', 'date', 'partner', 'card', 'add', 'note']),
        '폰 — 전표 동선: 종류 → 전표일 → 거래처 → 품목 카드 → +줄 추가 → 비고', o)
    page.screenshot(path=os.path.join(OUT, 'M2-폰-매출전표.png'))
    page.evaluate("() => document.getElementById('accVoucherClose').click()")
    page.wait_for_timeout(400)

    # 수금
    page.evaluate("() => document.getElementById('btnAccPayIn').click()")
    page.wait_for_timeout(900)
    head = page.evaluate("() => { const h = document.querySelector('#accPayModal .modal-head').getBoundingClientRect();"
                         " const s = document.querySelector('#accPayModal .seg').getBoundingClientRect();"
                         " return { head: Math.round(h.bottom), seg: Math.round(s.top) }; }")
    chk(head['head'] <= head['seg'] + 2, '폰 — 수금 시트 제목이 맨 위', head)
    page.screenshot(path=os.path.join(OUT, 'M3-폰-수금시트.png'))
    page.evaluate("() => document.getElementById('accPayClose').click()")
    page.wait_for_timeout(400)

    # 로트 수정
    page.evaluate("() => document.querySelector('#mobTabs [data-mtab=\"more\"]').click()")
    page.wait_for_timeout(400)
    page.evaluate("() => document.querySelector('#mobSheet [data-nav=\"stock:meat\"]').click()")
    page.wait_for_timeout(1600)
    page.evaluate("() => document.querySelector('#tableWrap .actmenu').click()")
    page.wait_for_timeout(500)
    page.evaluate("""() => { const bs = Array.from(document.querySelectorAll('#rowMenu button[data-mi]'));
        const b = bs.find(x => x.textContent.trim() === '수정'); if (b) b.click(); }""")
    page.wait_for_timeout(1000)
    o = order_of(page, '#lotModal', [('name', '#ltName'), ('vendor', '#ltVendor'), ('date', '#ltInDate'),
                                     ('stock', '#ltFrozen'), ('price', '#ltPrice'), ('why', '#ltWhy'), ('meat', '#ltMeat')])
    print('   로트 수정 순서:', json.dumps(o, ensure_ascii=False))
    chk(asc(o, ['name', 'vendor', 'date', 'stock', 'price', 'why', 'meat']),
        '폰 — 로트 수정 동선: 품명 → 업체 → 입고일 → 재고 → 단가 → 사유', o)
    page.screenshot(path=os.path.join(OUT, 'M4-폰-로트수정.png'))
    page.evaluate("() => document.getElementById('lotClose').click()")
    page.wait_for_timeout(400)

    # 품목 등록
    page.evaluate("() => document.querySelector('#mobTabs [data-mtab=\"more\"]').click()")
    page.wait_for_timeout(400)
    page.evaluate("() => document.querySelector('#mobSheet [data-nav=\"items\"]').click()")
    page.wait_for_timeout(1600)
    page.evaluate("() => document.getElementById('itemsBtnNew').click()")
    page.wait_for_timeout(900)
    o = order_of(page, '#fgNewModal', [('name', '#fgNewName'), ('spec', '#fgNewSpec'), ('code', '#fgNewCode'),
                                       ('price', '#fgNewIn'), ('stock', '#fgNewStock'), ('flag', '#fgNewFlag')])
    print('   품목 등록 순서:', json.dumps(o, ensure_ascii=False))
    chk(asc(o, ['name', 'spec', 'code', 'price', 'stock', 'flag']),
        '폰 — 품목 등록 동선: 상품명 → 규격 → 코드 → 단가 → 초기재고 → 자체/매입', o)
    page.screenshot(path=os.path.join(OUT, 'M5-폰-품목등록.png'))
    page.evaluate("() => document.getElementById('fgNewClose').click()")
    page.wait_for_timeout(400)

    # 입고 시트 — 엑셀 버튼
    page.evaluate("() => document.querySelector('#mobTabs [data-mtab=\"in\"]').click()")
    page.wait_for_timeout(1500)
    page.evaluate("() => { const c = document.querySelector('#ioSheetModal .modal-card'); c.scrollTop = c.scrollHeight; }")
    page.wait_for_timeout(500)
    eg = page.evaluate("""() => { const g = s => { const e = document.querySelector(s); if (!e) return null;
          const r = e.getBoundingClientRect(); return { top: Math.round(r.top), bottom: Math.round(r.bottom), h: Math.round(r.height) }; };
        return { up: g('#ioBulkUpload'), tpl: g('#ioBulkTemplate'), act: g('#ioSheetModal .modal-actions') }; }""")
    print('   입고 하단:', json.dumps(eg, ensure_ascii=False))
    chk(eg['up'] and eg['up']['h'] > 0 and eg['tpl'] and eg['tpl']['h'] > 0, '폰 — 입고 엑셀 버튼 두 개 보임')
    chk(eg['up']['bottom'] <= eg['act']['top'] + 1 and eg['tpl']['bottom'] <= eg['act']['top'] + 1,
        '폰 — 엑셀 버튼이 저장 바에 가리지 않는다', [eg['up']['bottom'], eg['act']['top']])
    page.screenshot(path=os.path.join(OUT, 'M6-폰-입고엑셀.png'))
    page.evaluate("() => document.getElementById('ioSheetClose').click()")
    page.wait_for_timeout(400)

    over = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    chk(over == 0, '폰 — 화면 가로 넘침 0px', over)
    real = [e for e in errors if 'Failed to load resource' not in e]
    chk(not real, 'JS 오류 0', real[:3])
    b.close()

print('RESULT', 'PASS' if not fails else 'FAIL ' + str(fails))
sys.exit(0 if not fails else 1)
