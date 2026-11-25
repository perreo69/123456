# -*- coding: utf-8 -*-
"""v61 검증 — 폰(390×844)의 «모든 입력 시트»가 v60 입출고 시트와 같은 동선·같은 규격인지

   · 해동/냉동(이동) · 매입/매출 전표 · 수금/지급 · 경비 · 로트 수정 · 품목 등록 · 거래명세표
   · 입고 시트의 엑셀 버튼이 하단 고정 바에 가리지 않는지
   · 가로 넘침 0 · JS 오류 0 · 저장(스텁 DB) 반영

   LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/v61_mobile.py [tag]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_ui as T
import shot_v36 as V36
from playwright.sync_api import sync_playwright

TAG = sys.argv[1] if len(sys.argv) > 1 else 'run'
OUT = '/workspace/downloads/erp-v61-화면/' + TAG
os.makedirs(OUT, exist_ok=True)
ok = True


def chk(cond, label, extra=''):
    global ok
    print(('  [OK]   ' if cond else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not cond:
        ok = False


VIS = """(sel) => {
  const el = document.querySelector(sel);
  if (!el) return null;
  const r = el.getBoundingClientRect();
  const st = getComputedStyle(el);
  return { top: Math.round(r.top), bottom: Math.round(r.bottom), left: Math.round(r.left),
           right: Math.round(r.right), w: Math.round(r.width), h: Math.round(r.height),
           display: st.display, inView: r.top >= -1 && r.bottom <= window.innerHeight + 1 && r.width > 0 };
}"""

# 팝업 안에서 «가로로 삐져나온 것» 세기
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
    if (over > worst) { worst = over; who = el.tagName + '.' + ((el.className || '').toString().slice(0, 30)); }
  });
  return { open: !m.classList.contains('hidden'), over: Math.round(worst), who: who,
           docOver: document.documentElement.scrollWidth - window.innerWidth };
}"""


def login(page):
    page.fill('#liEmail', 'kim@meat.co.kr')
    page.fill('#liPw', 'secret123')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=8000)
    page.wait_for_timeout(1800)
    page.add_style_tag(content='#toast{display:none !important}')


def order_of(page, sel, pairs):
    """[(키, 선택자)] 의 화면 y 를 {키: y} 로 — 위에서 아래 순서 확인용"""
    return page.evaluate("""([sel, pairs]) => {
      const m = document.querySelector(sel), out = {};
      pairs.forEach(([k, s]) => { const e = m.querySelector(s);
        out[k] = e ? Math.round(e.getBoundingClientRect().top) : -1; });
      return out; }""", [sel, pairs])


def ascending(d, keys):
    ys = [d[k] for k in keys]
    return all(ys[i] < ys[i + 1] for i in range(len(ys) - 1))


def run(pw):
    env = dict(os.environ)
    libs = '/workspace/tool-results/chromelibs'
    if os.path.isdir(libs):
        env['LD_LIBRARY_PATH'] = libs + (':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    errs, bad = [], []
    b = pw.chromium.launch(env=env)
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    page = ctx.new_page()
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.on('console', lambda m: errs.append('console:' + m.text) if m.type == 'error' else None)
    page.on('response', lambda r: bad.append((r.status, r.url.split('/')[-1])) if r.status >= 400 else None)
    page.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
    page.add_init_script(T.FAKE_WS)
    V36.seed_items()
    page.goto(T.BASE + '?v=20261126_70')
    page.wait_for_timeout(400)
    login(page)

    # ================================================== 1. 해동 / 냉동 (이동) 시트
    print('== 1. 해동/냉동(이동) 시트 ==')
    page.evaluate("() => document.querySelector('#mobTabs [data-mtab=\"out\"]').click()")
    page.wait_for_timeout(400)
    page.evaluate("() => document.querySelector('#mobSheet [data-nav=\"move\"]').click()")
    page.wait_for_timeout(800)
    chk(page.evaluate("() => !document.getElementById('uniMoveModal').classList.contains('hidden')"), '① 이동 시트 열림')
    sub = page.evaluate(VIS, '#uniMoveModal .modal-sub')
    chk(sub is None or sub['h'] == 0, '① 위쪽 장황한 설명 숨김', sub)
    o = order_of(page, '#uniMoveModal', [('seg', '#uniMoveSeg'), ('date', '#uniMoveDate'),
                                         ('lot', '#uniMoveLotQ'), ('stat', '#uniMoveStat'), ('kg', '#uniMoveKg'),
                                         ('price', '#uniMovePrice'), ('prod', '#uniMoveProd'), ('note', '#uniMoveNote')])
    print('   순서:', json.dumps(o, ensure_ascii=False))
    chk(ascending(o, ['seg', 'date', 'lot', 'stat', 'kg', 'price', 'prod', 'note']),
        '① 동선: 방향 → 날짜 → 로트 → 현재고 → 수량 → 단가 → 생산품명 → 비고', o)
    hh = page.evaluate("""() => ['uniMoveDate','uniMoveLotQ','uniMoveKg','uniMovePrice','uniMoveProd','uniMoveNote']
        .map(id => Math.round(document.getElementById(id).getBoundingClientRect().height))""")
    chk(min(hh) >= 44 and max(hh) <= 48, '① 입력칸 44~46px', hh)
    page.screenshot(path=os.path.join(OUT, 'V1-이동-첫화면.png'))
    # 로트 검색 목록 — v60 과 같은 규격
    page.click('#uniMoveLotQ')
    page.wait_for_timeout(500)
    lc = page.evaluate("""() => { const p = document.getElementById('uniMoveLotPop');
        if (!p || p.classList.contains('hidden')) return { open: false };
        const it = p.querySelector('.lcitem'), st = getComputedStyle(p);
        return { open: true, n: p.querySelectorAll('.lcitem').length, bg: st.backgroundColor,
                 radius: st.borderTopLeftRadius, rowH: it ? Math.round(it.getBoundingClientRect().height) : 0,
                 inView: p.getBoundingClientRect().bottom <= window.innerHeight + 1 }; }""")
    print('   로트 검색:', json.dumps(lc, ensure_ascii=False))
    chk(lc.get('open') and lc['n'] >= 1, '① 로트 검색 목록이 뜬다', lc.get('n'))
    chk(lc.get('bg') == 'rgb(255, 255, 255)' and str(lc.get('radius', '')).startswith('12px'),
        '① 로트 목록도 순백 · 모서리 12px', [lc.get('bg'), lc.get('radius')])
    chk(lc.get('rowH', 0) >= 48, '① 로트 행 48px 이상', lc.get('rowH'))
    page.screenshot(path=os.path.join(OUT, 'V2-이동-로트검색.png'))
    page.click('#uniMoveLotPop .lcitem')
    page.wait_for_timeout(700)
    pick = page.evaluate("""() => ({ lot: document.getElementById('uniMoveLot').value,
        q: document.getElementById('uniMoveLotQ').value,
        stat: document.getElementById('uniMoveStat').innerText.replace(/\\s+/g, ' '),
        price: document.getElementById('uniMovePrice').value })""")
    chk(bool(pick['lot']) and '현재고' in pick['stat'], '① 로트를 고르면 현재고·소비기한이 바로 보인다', pick['stat'][:80])
    page.screenshot(path=os.path.join(OUT, 'V3-이동-로트선택.png'))
    # 저장
    lotv = pick['lot']
    snap = dict((l['id'], l['frozen_qty']) for l in T.MOCK.lots)
    n_thaw0 = len([l for l in T.MOCK.logs if l.get('tx_type') == 'thaw'])
    page.fill('#uniMoveKg', '2')
    page.fill('#uniMoveProd', '선진바베큐폭립')
    page.wait_for_timeout(250)
    page.click('#uniMoveSave')
    page.wait_for_timeout(2200)
    thaw = [l for l in T.MOCK.logs if l.get('tx_type') == 'thaw']
    newest = thaw[-1] if len(thaw) > n_thaw0 else None
    chk(newest is not None and abs(float(newest.get('qty') or 0) - 2) < 0.001,
        '① 해동 저장 → 새 thaw 1건(2kg) DB 반영', newest and [(newest.get('product_name'), newest.get('qty'))])
    after = [x for x in T.MOCK.lots if newest and x['id'] == newest.get('lot_id')]
    chk(bool(after) and abs(after[0]['frozen_qty'] - (snap[after[0]['id']] - 2)) < 0.01,
        '① 그 로트 냉동 재고가 2kg 줄었다',
        after and [snap[after[0]['id']], after[0]['frozen_qty']])
    chk(page.evaluate("() => document.getElementById('uniMoveModal').classList.contains('hidden')"), '① 저장 뒤 시트 닫힘')
    page.wait_for_timeout(300)

    # ================================================== 2. 매출 전표 시트
    print('== 2. 매출 전표 시트 ==')
    page.evaluate("() => document.getElementById('btnAccSale').click()")
    page.wait_for_timeout(900)
    chk(page.evaluate("() => !document.getElementById('accVoucherModal').classList.contains('hidden')"), '② 매출 전표 열림')
    sub = page.evaluate(VIS, '#accVoucherModal .modal-sub')
    chk(sub is None or sub['h'] == 0, '② 위쪽 장황한 설명 숨김', sub)
    ov = page.evaluate(OVER, '#accVoucherModal')
    chk(ov['open'] and ov['over'] <= 1, '② 팝업 안 가로 넘침 0px', ov)
    chk(page.evaluate("() => document.querySelectorAll('#accVSheetBody tr[data-mcard]').length") == 1,
        '② 처음엔 카드 한 장(폰)', page.evaluate("() => document.querySelectorAll('#accVSheetBody tr[data-mcard]').length"))
    o = order_of(page, '#accVoucherModal', [('type', '#accVoucherSeg'), ('date', '#accVDate'),
                                            ('partner', '#accVPartner'), ('doc', '#accVDoc'),
                                            ('card', '#accVSheetBody tr'), ('add', '#accVAddRow'),
                                            ('note', '#accVNote')])
    print('   순서:', json.dumps(o, ensure_ascii=False))
    chk(ascending(o, ['type', 'date', 'partner', 'doc', 'card', 'add', 'note']),
        '② 동선: 종류 → 전표일 → 거래처 → 세금계산서 → 품목 카드 → +줄 추가 → 비고', o)
    cardh = page.evaluate("""() => { const tr = document.querySelector('#accVSheetBody tr[data-mcard]');
        const q = s => { const e = tr.querySelector(s); return e ? Math.round(e.getBoundingClientRect().top) : -1; };
        return { kind: q('.mcr-top'), name: q('[data-f="name"]'), lot: q('.acr-lot'), qty: q('[data-f="qty"]'),
                 price: q('[data-f="price"]'), total: q('[data-num="total"]') }; }""")
    chk(ascending(cardh, ['kind', 'name', 'lot', 'qty', 'total']) or ascending(cardh, ['kind', 'name', 'lot', 'qty']),
        '② 카드 안 순서: 구분 → 품명 → 로트/창고 → 수량 · 단가 → 합계', cardh)
    chk(cardh['qty'] < cardh['price'] + 4, '② 수량·단가가 나란히', [cardh['qty'], cardh['price']])
    page.screenshot(path=os.path.join(OUT, 'V4-매출전표-첫화면.png'))
    # 품명 검색 목록 규격
    page.click('#accVSheetBody [data-f="name"]')
    page.type('#accVSheetBody [data-f="name"]', '우양지', delay=80)
    page.wait_for_timeout(600)
    pop = page.evaluate("""() => { const p = Array.from(document.querySelectorAll('.acpop'))
          .find(x => !x.classList.contains('hidden') && x.querySelector('.acitem'));
        if (!p) return { open: false };
        const it = p.querySelector('.acitem'), on = p.querySelector('.acitem.on');
        const act = it.querySelector('.act'), acs = it.querySelector('.acs');
        return { open: true, n: p.querySelectorAll('.acitem').length, bg: getComputedStyle(p).backgroundColor,
                 radius: getComputedStyle(p).borderRadius, rowH: Math.round(it.getBoundingClientRect().height),
                 onBg: on ? getComputedStyle(on).backgroundColor : '',
                 onColor: on ? getComputedStyle(on.querySelector('.act')).color : '',
                 tSize: act ? getComputedStyle(act).fontSize : '', tWeight: act ? getComputedStyle(act).fontWeight : '',
                 sSize: acs ? getComputedStyle(acs).fontSize : '', sColor: acs ? getComputedStyle(acs).color : '',
                 inView: p.getBoundingClientRect().bottom <= window.innerHeight + 1 }; }""")
    print('   품명 목록:', json.dumps(pop, ensure_ascii=False))
    chk(pop.get('open') and pop.get('n', 0) >= 1, '② 품명 검색 목록', pop.get('n'))
    chk(pop.get('bg') == 'rgb(255, 255, 255)' and str(pop.get('radius', '')).startswith('12px'),
        '② 목록 순백 · 모서리 12px', [pop.get('bg'), pop.get('radius')])
    chk(pop.get('rowH', 0) >= 48, '② 행 48px 이상', pop.get('rowH'))
    chk(pop.get('tSize') == '15px' and str(pop.get('tWeight')) in ('600', '700'), '② 제목 15px/600', [pop.get('tSize'), pop.get('tWeight')])
    chk(pop.get('sSize') == '12px' and pop.get('sColor') == 'rgb(107, 114, 128)', '② 보조 12px #6B7280', [pop.get('sSize'), pop.get('sColor')])
    page.screenshot(path=os.path.join(OUT, 'V5-매출전표-검색목록.png'))
    page.locator('.acpop:not(.hidden) .acitem').first.click()
    page.wait_for_timeout(700)
    filled = page.evaluate("""() => ({ name: document.querySelector('#accVSheetBody [data-f="name"]').value,
        lot: (document.querySelector('#accVSheetBody [data-f="lot"]') || {}).value || '',
        price: document.querySelector('#accVSheetBody [data-f="price"]').value })""")
    chk(filled['name'] == '우양지', '② 목록에서 품명 선택', filled)
    chk(bool(filled['lot']), '② 보유 로트가 자동으로 잡힘', filled['lot'])
    page.fill('#accVSheetBody [data-f="qty"]', '5')
    page.wait_for_timeout(400)
    tot = page.evaluate("() => document.querySelector('#accVSheetBody [data-num=\"total\"]').textContent")
    ms = page.evaluate("() => document.getElementById('accVMSum').innerText.replace(/\\s+/g, ' ')")
    chk(tot not in ('', '0'), '② 수량을 넣으면 카드 합계가 계산됨', tot)
    chk('합계' in ms, '② 저장 버튼 위 한 줄 합계', ms)
    page.screenshot(path=os.path.join(OUT, 'V6-매출전표-카드입력.png'))
    # + 줄 추가 / 삭제
    page.click('#accVAddRow')
    page.wait_for_timeout(500)
    chk(page.evaluate("() => document.querySelectorAll('#accVSheetBody tr[data-mcard]').length") == 2,
        '② 「+ 줄 추가」로 카드 한 장 더', page.evaluate("() => document.querySelectorAll('#accVSheetBody tr[data-mcard]').length"))
    page.evaluate("() => document.querySelectorAll('#accVSheetBody tr[data-mcard]')[1].querySelector('.vdel').click()")
    page.wait_for_timeout(400)
    chk(page.evaluate("() => document.querySelectorAll('#accVSheetBody tr[data-mcard]').length") == 1, '② × 로 줄 삭제')
    # 저장
    page.fill('#accVPartner', '미트박스')
    page.wait_for_timeout(300)
    nv = len(T.MOCK.vouchers)
    page.click('#accVoucherSave')
    page.wait_for_timeout(2000)
    chk(len(T.MOCK.vouchers) > nv, '② 저장 → 전표 DB 반영', len(T.MOCK.vouchers))
    chk(page.evaluate("() => document.getElementById('accVoucherModal').classList.contains('hidden')"), '② 저장 뒤 시트 닫힘')
    page.wait_for_timeout(300)

    # ================================================== 3. 매입 전표 시트
    print('== 3. 매입 전표 시트 ==')
    page.evaluate("() => document.getElementById('btnAccBuy').click()")
    page.wait_for_timeout(900)
    chk(page.evaluate("() => !document.getElementById('accVoucherModal').classList.contains('hidden')"), '③ 매입 전표 열림')
    ov = page.evaluate(OVER, '#accVoucherModal')
    chk(ov['over'] <= 1, '③ 가로 넘침 0px', ov)
    buy = page.evaluate("""() => { const tr = document.querySelector('#accVSheetBody tr[data-mcard]');
        return { wh: Array.from(tr.querySelectorAll('[data-f="wh"] option')).map(o => o.textContent),
                 exp: !!tr.querySelector('[data-f="expiry"]'),
                 expLabel: (tr.querySelector('.acr-exp .mfl') || {}).textContent || '',
                 h: tr.querySelector('[data-f="expiry"]') ? Math.round(tr.querySelector('[data-f="expiry"]').getBoundingClientRect().height) : 0 }; }""")
    print('   매입 카드:', json.dumps(buy, ensure_ascii=False))
    chk(buy['wh'] == ['냉동고', '냉장고'], '③ 매입 카드에 창고(냉동고·냉장고)', buy['wh'])
    chk(buy['exp'] and buy['expLabel'] == '소비기한', '③ 소비기한 칸에 이름표', [buy['exp'], buy['expLabel']])
    chk(44 <= buy['h'] <= 46, '③ 소비기한 칸 44~46px', buy['h'])
    page.screenshot(path=os.path.join(OUT, 'V7-매입전표-첫화면.png'))
    # 매입 저장 — 재고가 늘고 전표가 생기는지 (스텁 DB)
    page.fill('#accVPartner', '도드람푸드')
    page.click('#accVSheetBody [data-f="name"]')
    page.type('#accVSheetBody [data-f="name"]', '등갈비', delay=80)
    page.wait_for_timeout(600)
    if page.evaluate("() => { const p = Array.from(document.querySelectorAll('.acpop')).find(x => !x.classList.contains('hidden') && x.querySelector('.acitem')); return !!p; }"):
        page.locator('.acpop:not(.hidden) .acitem').first.click()
        page.wait_for_timeout(500)
    page.fill('#accVSheetBody [data-f="expiry"]', '20270630')
    page.fill('#accVSheetBody [data-f="qty"]', '4')
    page.fill('#accVSheetBody [data-f="price"]', '15000')
    page.wait_for_timeout(300)
    nv2 = len(T.MOCK.vouchers)
    frozen0 = sum(l['frozen_qty'] for l in T.MOCK.lots)
    page.click('#accVoucherSave')
    page.wait_for_timeout(2200)
    chk(len(T.MOCK.vouchers) > nv2, '③ 매입 저장 → 전표 DB 반영', len(T.MOCK.vouchers))
    frozen1 = sum(l['frozen_qty'] for l in T.MOCK.lots)
    chk(frozen1 - frozen0 > 3.99, '③ 매입 저장 → 원료육 냉동 재고 +4kg', [round(frozen0, 2), round(frozen1, 2)])
    page.wait_for_timeout(300)

    # ================================================== 4. 수금 / 지급 · 경비
    print('== 4. 수금·지급 / 경비 시트 ==')
    for btn, mod, nm in (('btnAccPayIn', 'accPayModal', '수금'), ('btnAccPayOut', 'accPayModal', '지급'),
                         ('btnAccExpense', 'accExpModal', '경비')):
        page.evaluate("(id) => document.getElementById(id).click()", btn)
        page.wait_for_timeout(700)
        head = page.evaluate(VIS, '#' + mod + ' .modal-head')
        seg = page.evaluate(VIS, '#' + mod + ' .seg')
        sub = page.evaluate(VIS, '#' + mod + ' .modal-sub')
        ov = page.evaluate(OVER, '#' + mod)
        print('   %s: head=%s seg=%s' % (nm, head and head['top'], seg and seg['top']))
        chk(head and seg and head['bottom'] <= seg['top'] + 2, '④ %s — 제목이 맨 위(구분보다 위)' % nm, [head and head['bottom'], seg and seg['top']])
        chk(sub is None or sub['h'] == 0, '④ %s — 위쪽 설명 숨김' % nm, sub)
        chk(ov['over'] <= 1 and ov['docOver'] == 0, '④ %s — 가로 넘침 0px' % nm, ov)
        page.screenshot(path=os.path.join(OUT, 'V8-%s시트.png' % nm))
        page.evaluate("(m) => document.querySelector('#' + m + ' .modal-x').click()", mod)
        page.wait_for_timeout(300)

    # ================================================== 5. 로트 수정 시트
    print('== 5. 로트 수정 시트 ==')
    page.evaluate("() => document.querySelector('#mobTabs [data-mtab=\"more\"]').click()")
    page.wait_for_timeout(400)
    page.evaluate("() => document.querySelector('#mobSheet [data-nav=\"stock:meat\"]').click()")
    page.wait_for_timeout(1400)
    page.evaluate("() => document.querySelector('#tableWrap .actmenu').click()")
    page.wait_for_timeout(400)
    page.evaluate("""() => { const bs = Array.from(document.querySelectorAll('#rowMenu button[data-mi]'));
        const b = bs.find(x => x.textContent.trim() === '수정'); if (b) b.click(); }""")
    page.wait_for_timeout(800)
    chk(page.evaluate("() => !document.getElementById('lotModal').classList.contains('hidden')"), '⑤ 로트 수정 열림')
    o = order_of(page, '#lotModal', [('name', '#ltName'), ('vendor', '#ltVendor'), ('date', '#ltInDate'),
                                     ('stock', '#ltFrozen'), ('price', '#ltPrice'), ('why', '#ltWhy'),
                                     ('meat', '#ltMeat')])
    print('   순서:', json.dumps(o, ensure_ascii=False))
    chk(ascending(o, ['name', 'vendor', 'date', 'stock', 'price', 'why', 'meat']),
        '⑤ 동선: 품명 → 업체 → 입고일 → 재고 → 단가 → 사유 → (분류)', o)
    ov = page.evaluate(OVER, '#lotModal')
    chk(ov['over'] <= 1, '⑤ 가로 넘침 0px', ov)
    page.screenshot(path=os.path.join(OUT, 'V9-로트수정-첫화면.png'))
    # 재고 수정 저장
    lotid = page.evaluate("() => { const s = document.getElementById('lotModal'); return s ? 1 : 1; }")
    cur = page.evaluate("() => document.getElementById('ltFrozen').value")
    page.fill('#ltFrozen', '150.5')
    page.fill('#ltWhy', '실사 조정')
    page.wait_for_timeout(200)
    page.click('#lotSave')
    page.wait_for_timeout(1800)
    saved = [l['frozen_qty'] for l in T.MOCK.lots if abs(float(l['frozen_qty']) - 150.5) < 0.001]
    chk(bool(saved), '⑤ 재고 수정 저장 → DB 반영(냉동 150.5kg)', (cur, saved[:3]))
    page.wait_for_timeout(300)

    # ================================================== 6. 품목 등록 시트
    print('== 6. 품목 등록 시트 ==')
    page.evaluate("() => document.querySelector('#mobTabs [data-mtab=\"more\"]').click()")
    page.wait_for_timeout(300)
    page.evaluate("() => document.querySelector('#mobSheet [data-nav=\"items\"]').click()")
    page.wait_for_timeout(1200)
    page.evaluate("() => document.getElementById('itemsBtnNew').click()")
    page.wait_for_timeout(800)
    chk(page.evaluate("() => !document.getElementById('fgNewModal').classList.contains('hidden')"), '⑥ 품목 등록 열림')
    o = order_of(page, '#fgNewModal', [('name', '#fgNewName'), ('spec', '#fgNewSpec'), ('code', '#fgNewCode'),
                                       ('price', '#fgNewIn'), ('stock', '#fgNewStock'), ('flag', '#fgNewFlag')])
    print('   순서:', json.dumps(o, ensure_ascii=False))
    chk(ascending(o, ['name', 'spec', 'code', 'price', 'stock', 'flag']),
        '⑥ 동선: 상품명 → 규격/단위 → 코드/분류 → 단가 → 초기재고 → 자체/매입', o)
    ov = page.evaluate(OVER, '#fgNewModal')
    chk(ov['over'] <= 1, '⑥ 가로 넘침 0px', ov)
    page.screenshot(path=os.path.join(OUT, 'V10-품목등록-첫화면.png'))
    page.fill('#fgNewName', '검증용 떡갈비')
    page.fill('#fgNewSpec', '500g*2')
    page.fill('#fgNewIn', '9000')
    page.wait_for_timeout(200)
    page.click('#fgNewSave')
    page.wait_for_timeout(1500)
    made = [p for p in T.MOCK.fp_products if p.get('name') == '검증용 떡갈비']
    chk(bool(made), '⑥ 등록 저장 → 품목 DB 반영', len(T.MOCK.fp_products))
    page.wait_for_timeout(300)

    # ================================================== 7. 입고 시트 — 엑셀 버튼
    print('== 7. 입고 시트 엑셀 버튼 ==')
    page.evaluate("() => document.querySelector('#mobTabs [data-mtab=\"in\"]').click()")
    page.wait_for_timeout(1200)
    page.evaluate("() => { const c = document.querySelector('#ioSheetModal .modal-card'); c.scrollTop = c.scrollHeight; }")
    page.wait_for_timeout(400)
    eg = page.evaluate("""() => { const g = s => { const e = document.querySelector(s);
          if (!e) return null; const r = e.getBoundingClientRect();
          return { top: Math.round(r.top), bottom: Math.round(r.bottom), h: Math.round(r.height), w: Math.round(r.width),
                   disp: getComputedStyle(e).display }; };
        return { up: g('#ioBulkUpload'), tpl: g('#ioBulkTemplate'), add: g('#ioSheetAdd'),
                 act: g('#ioSheetModal .modal-actions'), vh: window.innerHeight }; }""")
    print('   ', json.dumps(eg, ensure_ascii=False))
    chk(eg['up'] and eg['up']['h'] > 0 and eg['tpl'] and eg['tpl']['h'] > 0, '⑦ 입고에 엑셀 일괄 업로드 · 양식 받기가 보인다')
    chk(eg['up']['bottom'] <= eg['act']['top'] + 1 and eg['tpl']['bottom'] <= eg['act']['top'] + 1,
        '⑦ 엑셀 버튼이 하단 고정 바에 가리지 않는다', [eg['up']['bottom'], eg['tpl']['bottom'], eg['act']['top']])
    chk(eg['add']['bottom'] <= eg['up']['top'] + 1, '⑦ 「+ 품목 추가」가 엑셀 버튼 위(주 동작 먼저)',
        [eg['add']['bottom'], eg['up']['top']])
    page.screenshot(path=os.path.join(OUT, 'V11-입고-엑셀버튼.png'))
    page.click('#ioSheetClose')
    page.wait_for_timeout(300)

    # ================================================== 8. 마무리
    print('== 8. 마무리 ==')
    over = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    chk(over == 0, '⑧ 화면 가로 넘침 0px', over)
    real_errs = [e for e in errs if 'Failed to load resource' not in e]
    chk(not real_errs, '⑧ JS 오류 0', real_errs[:3])
    own = [x for x in bad if any(k in x[1] for k in ('app.js', 'mobile.css', 'style.css', 'index.html', 'partners_data.js'))]
    chk(not own, '⑧ 우리 자산 404 없음', own[:3])
    ctx.close()
    b.close()


with sync_playwright() as pw:
    run(pw)

print('RESULT', 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
