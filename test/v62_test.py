# -*- coding: utf-8 -*-
"""v62 검증 — 원료육 「입고 등록」의 원산지 · 브랜드 칸 (PC 표 + 폰 카드) + 실제 저장

  LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/v62_test.py [tag]

· PC 1920/1366: 입고 팝업에 원산지·브랜드 두 칸(원료육 줄만), 표가 옆으로 밀리지 않음
· 폰 390: 카드에서 원산지 | 브랜드 2열 나란히(44px · 16px), 가로 넘침 0
· 원산지·브랜드 실시간 검색 드롭다운(지금까지 쓴 값)
· 저장 → 스텁 DB(tx_apply)의 lots.origin / lots.brand 에 들어감(새 로트 · 기존 로트 둘 다)
· 완제품 줄에서는 칸이 사라짐(«—»), 출고에서는 고른 로트의 값을 읽기 전용으로 보여 줌
· 엑셀 일괄 업로드의 원산지·브랜드 열 → 줄 → 저장
· 다른 화면 회귀 0(전표는 11칸 · 1080px 그대로), JS 오류 0
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_ui as T
import shot_v36 as V36
from playwright.sync_api import sync_playwright

TAG = sys.argv[1] if len(sys.argv) > 1 else 'run'
OUT = '/workspace/downloads/erp-v62-화면/' + TAG
os.makedirs(OUT, exist_ok=True)
ok = True


def chk(cond, label, extra=''):
    global ok
    print(('  [OK]   ' if cond else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not cond:
        ok = False


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

PC_GEOM = """() => {
  const box = document.querySelector('#ioSheetWrap .vsheet-scroll');
  const tb = document.getElementById('ioSheetTable');
  const ths = [...tb.querySelectorAll('thead th')].map(th => th.textContent.trim());
  const tr = document.querySelector('#ioSheetBody tr[data-r="0"]');
  const g = el => { if (!el) return null; const r = el.getBoundingClientRect();
    return { h: Math.round(r.height), w: Math.round(r.width), top: Math.round(r.top), left: Math.round(r.left) }; };
  return { ths: ths,
           box: box ? Math.round(box.clientWidth) : -1,
           scroll: box ? Math.round(box.scrollWidth) : -1,
           table: Math.round(tb.getBoundingClientRect().width),
           origin: g(tr && tr.querySelector('[data-f="origin"]')),
           brand: g(tr && tr.querySelector('[data-f="brand"]')),
           rowH: tr ? Math.round(tr.getBoundingClientRect().height) : 0 };
}"""


def login(page, mob=False):
    page.fill('#liEmail', 'kim@meat.co.kr')
    page.fill('#liPw', 'secret123')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=10000)
    page.wait_for_timeout(2000)
    page.add_style_tag(content='#toast{display:none !important}')


def lot_by_name(name):
    return [l for l in T.MOCK.lots if l['product_name'] == name]


def run(pw):
    env = dict(os.environ)
    libs = '/workspace/tool-results/chromelibs'
    if os.path.isdir(libs):
        env['LD_LIBRARY_PATH'] = libs
    errs, bad = [], []
    b = pw.chromium.launch(env=env)

    # ============================================================ PC 1920
    print('== 1. PC 입고 팝업 ==')
    page = b.new_page(viewport={'width': 1920, 'height': 1080})
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.on('console', lambda m: errs.append('console:' + m.text) if m.type == 'error' else None)
    page.on('response', lambda r: bad.append((r.status, r.url.split('/')[-1])) if r.status >= 400 else None)
    page.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
    page.add_init_script(T.FAKE_WS)
    V36.seed_items()
    page.goto(T.BASE + '?v=20261126_71')
    page.wait_for_timeout(400)
    login(page)

    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"in\"]').click()")
    page.wait_for_timeout(1000)
    g = page.evaluate(PC_GEOM)
    print('   표:', json.dumps(g, ensure_ascii=False))
    chk(g['ths'][2:4] == ['원산지', '브랜드'], '① PC 표 머리글에 원산지 · 브랜드(품목명 바로 뒤)', g['ths'][:5])
    chk(g['origin'] and g['brand'] and g['origin']['h'] >= 24, '① 원료육 줄에 원산지·브랜드 입력칸', [g['origin'], g['brand']])
    chk(g['origin']['left'] < g['brand']['left'] and abs(g['origin']['top'] - g['brand']['top']) <= 1,
        '① 두 칸이 나란히(같은 줄)', [g['origin']['left'], g['brand']['left']])
    chk(g['box'] >= g['table'] and g['box'] == g['scroll'], '① 표가 옆으로 밀리지 않는다(가로 스크롤 0)', [g['box'], g['scroll'], g['table']])
    ov = page.evaluate(OVER, '#ioSheetModal')
    chk(ov['over'] <= 1, '① 팝업 가로 넘침 0px', ov)
    page.screenshot(path=os.path.join(OUT, 'P1-입고-원산지브랜드.png'))

    # --- 실시간 검색 드롭다운(지금까지 쓴 원산지)
    page.click('#ioSheetBody tr[data-r="0"] [data-f="origin"]')
    page.type('#ioSheetBody tr[data-r="0"] [data-f="origin"]', '아일', delay=90)
    page.wait_for_timeout(700)
    ac = page.evaluate("""() => { const p = document.querySelector('.acpop');
        if (!p || p.classList.contains('hidden')) return { open: false };
        const items = [...p.querySelectorAll('.acitem, [data-i], .acrow')].map(x => x.textContent.trim());
        return { open: true, n: items.length, items: items.slice(0, 5) }; }""")
    print('   드롭다운:', json.dumps(ac, ensure_ascii=False))
    chk(ac.get('open') and ac.get('n', 0) >= 1, '① 두 글자만 쳐도 원산지 목록이 뜬다', ac.get('items'))
    chk(any('아일랜드' in (x or '') for x in (ac.get('items') or [])), '① 지금까지 쓴 원산지(아일랜드)가 후보에', ac.get('items'))
    page.screenshot(path=os.path.join(OUT, 'P2-원산지-드롭다운.png'))
    page.keyboard.press('Escape')
    page.wait_for_timeout(200)

    # --- 완제품 줄에서는 칸이 사라진다
    page.evaluate("""() => { const tr = document.querySelector('#ioSheetBody tr[data-r="0"]');
        const s = tr.querySelector('[data-f="kind"]'); s.value = 'fg';
        s.dispatchEvent(new Event('change', { bubbles: true })); }""")
    page.wait_for_timeout(500)
    fp = page.evaluate("""() => { const tr = document.querySelector('#ioSheetBody tr[data-r="0"]');
        return { originIn: !!tr.querySelector('[data-f="origin"]'), brandIn: !!tr.querySelector('[data-f="brand"]'),
                 c3: (tr.children[2] || {}).textContent || '', c4: (tr.children[3] || {}).textContent || '' }; }""")
    chk(not fp['originIn'] and not fp['brandIn'] and fp['c3'].strip() == '—', '① 완제품 줄에서는 입력칸이 사라진다(—)', fp)
    page.screenshot(path=os.path.join(OUT, 'P3-완제품-칸없음.png'))
    page.evaluate("""() => { const tr = document.querySelector('#ioSheetBody tr[data-r="0"]');
        const s = tr.querySelector('[data-f="kind"]'); s.value = 'meat';
        s.dispatchEvent(new Event('change', { bubbles: true })); }""")
    page.wait_for_timeout(400)

    # --- 저장 1: 새 로트에 원산지·브랜드
    n0 = len(T.MOCK.lots)
    page.fill('#ioSheetDate', '2026-11-26')
    page.fill('#ioSheetPartner', '검증육가공')
    page.fill('#ioSheetBody tr[data-r="0"] [data-f="name"]', 'v62테스트등갈비')
    page.fill('#ioSheetBody tr[data-r="0"] [data-f="origin"]', '호주')
    page.fill('#ioSheetBody tr[data-r="0"] [data-f="brand"]', '스위프트')
    page.fill('#ioSheetBody tr[data-r="0"] [data-f="expiry"]', '2027-12-31')
    page.fill('#ioSheetBody tr[data-r="0"] [data-f="qty"]', '12.5')
    page.fill('#ioSheetBody tr[data-r="0"] [data-f="price"]', '9500')
    page.wait_for_timeout(300)
    page.screenshot(path=os.path.join(OUT, 'P4-저장전.png'))
    page.click('#ioSheetSave')
    page.wait_for_timeout(3000)
    made = lot_by_name('v62테스트등갈비')
    print('   새 로트:', json.dumps(made, ensure_ascii=False)[:400])
    chk(len(T.MOCK.lots) > n0 and bool(made), '① 새 로트가 만들어졌다', len(T.MOCK.lots) - n0)
    chk(made and made[0].get('origin') == '호주' and made[0].get('brand') == '스위프트',
        '① 저장 → lots.origin·brand 에 그대로 들어감', made and [made[0].get('origin'), made[0].get('brand')])
    chk(made and abs(float(made[0]['frozen_qty']) - 12.5) < 0.001, '① 재고도 12.5kg', made and made[0]['frozen_qty'])

    # --- 저장 2: 이미 있는 로트(원산지 비어 있음)에 브랜드 채우기
    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"in\"]').click()")
    page.wait_for_timeout(900)
    page.fill('#ioSheetDate', '2026-10-02')          # 이 로트의 입고일과 같게 — 기존 로트로 묶인다
    page.fill('#ioSheetPartner', '위드미트')
    page.fill('#ioSheetBody tr[data-r="0"] [data-f="name"]', '닭가슴살SL')
    page.fill('#ioSheetBody tr[data-r="0"] [data-f="origin"]', '')
    page.fill('#ioSheetBody tr[data-r="0"] [data-f="brand"]', '검증브랜드')
    page.fill('#ioSheetBody tr[data-r="0"] [data-f="expiry"]', '2028-09-29')
    page.fill('#ioSheetBody tr[data-r="0"] [data-f="qty"]', '3')
    page.wait_for_timeout(300)
    page.click('#ioSheetSave')
    page.wait_for_timeout(2500)
    ex = [l for l in lot_by_name('닭가슴살SL') if l['id'] == 2]
    print('   기존 로트:', json.dumps(ex, ensure_ascii=False)[:400])
    chk(bool(ex) and ex[0].get('brand') == '검증브랜드', '① 기존 로트의 빈 브랜드가 채워진다', ex and ex[0].get('brand'))
    chk(bool(ex) and ex[0].get('origin') == '국내산', '① 적지 않은 원산지는 건드리지 않는다', ex and ex[0].get('origin'))

    # --- 출고 모드: 고른 로트의 원산지·브랜드를 읽기 전용으로
    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"out\"]').click()")
    page.wait_for_timeout(900)
    page.fill('#ioSheetBody tr[data-r="0"] [data-f="name"]', 'v62테스트등갈비')
    page.wait_for_timeout(800)
    outv = page.evaluate("""() => { const tr = document.querySelector('#ioSheetBody tr[data-r="0"]');
        const o = tr.children[2], b2 = tr.children[3];
        return { oIn: !!tr.querySelector('[data-f="origin"]'), o: o.textContent.trim(), b: b2.textContent.trim() }; }""")
    chk(not outv['oIn'] and outv['o'] == '호주' and outv['b'] == '스위프트',
        '① 출고에서는 고른 로트의 원산지·브랜드를 보여 준다', outv)
    page.screenshot(path=os.path.join(OUT, 'P5-출고-로트값.png'))
    page.evaluate("() => document.getElementById('ioSheetCancel').click()")
    page.wait_for_timeout(300)

    # --- 엑셀 일괄의 원산지·브랜드 열
    csv = os.path.join(OUT, 'v62_입고.csv')
    with open(csv, 'w', encoding='utf-8-sig') as f:
        f.write('구분,품목명,보관위치,원산지,브랜드,거래처,입고일,소비기한,수량,단가\n')
        f.write('원료육,v62엑셀목살,냉동고,미국,v62엑셀브랜드,검증육가공,2026-11-26,2027-08-31,7.5,8200\n')
    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"in\"]').click()")
    page.wait_for_timeout(900)
    page.set_input_files('#ioBulkFile', csv)
    page.wait_for_timeout(1800)
    xl = page.evaluate("""() => { const tr = document.querySelector('#ioSheetBody tr[data-r="0"]');
        return { n: document.querySelectorAll('#ioSheetBody tr[data-r]').length,
                 name: (tr.querySelector('[data-f=name]') || {}).value || '',
                 o: (tr.querySelector('[data-f=origin]') || {}).value || '',
                 b: (tr.querySelector('[data-f=brand]') || {}).value || '' }; }""")
    print('   엑셀:', json.dumps(xl, ensure_ascii=False))
    chk(xl['o'] == '미국' and xl['b'] == 'v62엑셀브랜드', '① 엑셀 원산지·브랜드 열이 줄에 그대로 채워진다', xl)
    page.screenshot(path=os.path.join(OUT, 'P6-엑셀-원산지브랜드.png'))
    page.click('#ioSheetSave')
    page.wait_for_timeout(2500)
    xlot = lot_by_name('v62엑셀목살')
    chk(bool(xlot) and xlot[0].get('origin') == '미국' and xlot[0].get('brand') == 'v62엑셀브랜드',
        '① 엑셀 줄도 저장되면 lots 에 원산지·브랜드가 남는다', xlot and [xlot[0].get('origin'), xlot[0].get('brand')])

    # --- 회귀: 매출 전표 팝업은 11칸 · 1080px 그대로
    page.evaluate("() => document.getElementById('btnAccSale').click()")
    page.wait_for_timeout(1200)
    pc = page.evaluate("""() => { const m = document.getElementById('accVoucherModal');
        const rows = m.querySelectorAll('#accVSheetBody tr');
        return { tds: rows.length ? rows[0].children.length : 0, card: Math.round(m.querySelector('.modal-card').getBoundingClientRect().width) }; }""")
    chk(pc['tds'] == 11 and pc['card'] == 1080, '① 전표 팝업은 그대로(11칸 · 1080px)', pc)
    page.evaluate("() => document.getElementById('accVoucherClose').click()")
    page.wait_for_timeout(300)
    page.screenshot(path=os.path.join(OUT, 'P7-전표-그대로.png'))
    page.close()

    # ============================================================ PC 1366
    print('== 2. PC 1366 ==')
    page = b.new_page(viewport={'width': 1366, 'height': 768})
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
    page.add_init_script(T.FAKE_WS)
    page.goto(T.BASE + '?v=20261126_71')
    page.wait_for_timeout(400)
    login(page)
    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"in\"]').click()")
    page.wait_for_timeout(1000)
    g2 = page.evaluate(PC_GEOM)
    print('   1366:', json.dumps({k: g2[k] for k in ('box', 'scroll', 'table', 'rowH')}, ensure_ascii=False))
    chk(g2['box'] == g2['scroll'] == g2['table'], '② 1366 에서도 표가 잘리지 않는다(가로 스크롤 0)', [g2['box'], g2['scroll'], g2['table']])
    page.screenshot(path=os.path.join(OUT, 'P8-1366-입고팝업.png'))
    page.close()

    # ============================================================ 폰 390
    print('== 3. 폰 입고 시트 ==')
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    page = ctx.new_page()
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.on('console', lambda m: errs.append('console:' + m.text) if m.type == 'error' else None)
    page.on('response', lambda r: bad.append((r.status, r.url.split('/')[-1])) if r.status >= 400 else None)
    page.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
    page.add_init_script(T.FAKE_WS)
    V36.seed_items()
    page.goto(T.BASE + '?v=20261126_71')
    page.wait_for_timeout(400)
    login(page, True)
    page.evaluate("() => document.querySelector('#mobTabs [data-mtab=\"in\"]').click()")
    page.wait_for_timeout(1200)
    mg = page.evaluate("""() => { const tr = document.querySelector('#ioSheetBody tr[data-mcard="1"]');
        const o = tr.querySelector('[data-f="origin"]'), br = tr.querySelector('[data-f="brand"]');
        const g = el => { if (!el) return null; const r = el.getBoundingClientRect(); const st = getComputedStyle(el);
          return { top: Math.round(r.top), left: Math.round(r.left), w: Math.round(r.width), h: Math.round(r.height),
                   fs: st.fontSize }; };
        const ex = tr.querySelector('[data-f="expiry"]');
        return { o: g(o), b: g(br), exp: g(ex), cardOver: document.documentElement.scrollWidth - window.innerWidth,
                 labels: [...tr.querySelectorAll('.mfields .mf > span')].map(s => s.textContent.trim()) }; }""")
    print('   폰:', json.dumps(mg, ensure_ascii=False))
    chk(mg['o'] and mg['b'], '③ 폰 입고 카드에 원산지·브랜드 칸', [mg['o'], mg['b']])
    chk(mg['o']['top'] == mg['b']['top'] and mg['o']['left'] < mg['b']['left'], '③ 두 칸이 2열로 나란히', [mg['o'], mg['b']])
    chk(mg['o']['h'] >= 44 and mg['o']['h'] <= 48 and mg['o']['fs'] == '16px', '③ 칸 44px · 글자 16px', [mg['o']['h'], mg['o']['fs']])
    chk(mg['exp'] and mg['o']['top'] >= mg['exp']['top'], '③ 소비기한 아래에 온다', [mg['exp'] and mg['exp']['top'], mg['o']['top']])
    chk(mg['cardOver'] == 0, '③ 화면 가로 넘침 0px', mg['cardOver'])
    ov = page.evaluate(OVER, '#ioSheetModal')
    chk(ov['over'] <= 1, '③ 카드 안 가로 넘침 0px', ov)
    page.screenshot(path=os.path.join(OUT, 'M1-폰-입고-원산지브랜드.png'))

    # 폰 저장
    page.fill('#ioSheetBody tr[data-mcard="1"] [data-f="name"]', 'v62폰등갈비')
    page.wait_for_timeout(300)
    page.fill('#ioSheetBody tr[data-mcard="1"] [data-f="origin"]', '국내산')
    page.fill('#ioSheetBody tr[data-mcard="1"] [data-f="brand"]', '폰브랜드')
    page.fill('#ioSheetBody tr[data-mcard="1"] [data-f="expiry"]', '2027-10-30')
    page.fill('#ioSheetBody tr[data-mcard="1"] [data-f="qty"]', '5')
    page.wait_for_timeout(400)
    page.screenshot(path=os.path.join(OUT, 'M2-폰-입고-작성.png'))
    page.evaluate("() => document.getElementById('ioSheetSave').click()")
    page.wait_for_timeout(3000)
    mlot = lot_by_name('v62폰등갈비')
    print('   폰 로트:', json.dumps(mlot, ensure_ascii=False)[:300])
    chk(bool(mlot) and mlot[0].get('origin') == '국내산' and mlot[0].get('brand') == '폰브랜드',
        '③ 폰에서 저장한 원산지·브랜드도 lots 에 들어간다', mlot and [mlot[0].get('origin'), mlot[0].get('brand')])
    page.wait_for_timeout(500)

    # 폰 — 완제품 줄은 칸이 없다
    page.evaluate("() => document.querySelector('#mobTabs [data-mtab=\"in\"]').click()")
    page.wait_for_timeout(1200)
    page.evaluate("""() => { const tr = document.querySelector('#ioSheetBody tr[data-mcard="1"]');
        const s = tr.querySelector('[data-f="kind"]'); s.value = 'fg';
        s.dispatchEvent(new Event('change', { bubbles: true })); }""")
    page.wait_for_timeout(700)
    pf = page.evaluate("""() => { const tr = document.querySelector('#ioSheetBody tr[data-mcard="1"]');
        return { originIn: !!tr.querySelector('[data-f="origin"]'), brandIn: !!tr.querySelector('[data-f="brand"]') }; }""")
    chk(not pf['originIn'] and not pf['brandIn'], '③ 폰 완제품 줄에는 원산지·브랜드 칸이 없다', pf)
    page.screenshot(path=os.path.join(OUT, 'M3-폰-완제품-칸없음.png'))
    page.evaluate("() => document.getElementById('ioSheetClose').click()")
    page.wait_for_timeout(300)

    # 폰 — 다른 화면 가로 넘침 0
    over2 = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    chk(over2 == 0, '③ 폰 화면 가로 넘침 0px', over2)

    real_errs = [e for e in errs if 'Failed to load resource' not in e]
    chk(not real_errs, '④ JS 오류 0', real_errs[:3])
    own = [x for x in bad if any(k in x[1] for k in ('app.js', 'mobile.css', 'style.css', 'index.html', 'partners_data.js'))]
    chk(not own, '④ 우리 자산 404 없음', own[:3])
    ctx.close()
    b.close()


with sync_playwright() as pw:
    run(pw)

print('RESULT', 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
