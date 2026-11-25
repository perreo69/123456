# -*- coding: utf-8 -*-
"""v60 검증 — 폰(390×844) 출고·입고 시트: 실무 동선 · 기존재고 카드 · 검색 목록 통일
   LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/v60_mobile.py [tag]
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_ui as T
import shot_v36 as V36
from playwright.sync_api import sync_playwright

TAG = sys.argv[1] if len(sys.argv) > 1 else 'run'
OUT = '/workspace/downloads/erp-v60-화면/' + TAG
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
           display: st.display, vis: st.visibility, op: Number(st.opacity),
           inView: r.top >= -1 && r.bottom <= window.innerHeight + 1 && r.width > 0 };
}"""


def login(page):
    page.fill('#liEmail', 'kim@meat.co.kr')
    page.fill('#liPw', 'secret123')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=8000)
    page.wait_for_timeout(1800)
    page.add_style_tag(content='#toast{display:none !important}')


def open_out(page):
    page.click('#mobTabs [data-mtab="out"]')
    page.wait_for_timeout(450)
    page.click('#mobSheet [data-nav="out"]')
    page.wait_for_timeout(900)


def open_in(page):
    page.click('#mobTabs [data-mtab="in"]')
    page.wait_for_timeout(1000)


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
    page.goto(T.BASE + '?v=20261126_69')
    page.wait_for_timeout(400)
    login(page)

    # ---------------------------------------------------------------- 1. 출고 첫 화면
    open_out(page)
    chk(page.evaluate("() => !document.getElementById('ioSheetModal').classList.contains('hidden')"), '출고 시트 열림')
    ys = {}
    for key, sel in (('date', '#ioSheetDate'), ('partner', '#ioSheetPartner'), ('seg', '#ioSheetDestSeg'),
                     ('name', '#ioSheetBody [data-f="name"]')):
        v = page.evaluate(VIS, sel)
        ys[key] = v
        chk(bool(v) and v['inView'], '① 첫 화면에 %s 보임' % key, v)
    chk(ys['seg']['bottom'] <= ys['date']['top'] + 1, '① 출고 구분이 날짜보다 위', [ys['seg']['bottom'], ys['date']['top']])
    chk(ys['date']['bottom'] <= ys['partner']['top'] + 1, '① 날짜가 거래처보다 위')
    chk(ys['partner']['bottom'] <= ys['name']['top'] + 1, '① 거래처가 첫 품목칸보다 위')
    chk(page.evaluate("() => document.querySelectorAll('#ioSheetBody tr[data-mcard]').length") == 1,
        '① 기본 품목 줄 1장(폰)', page.evaluate("() => document.querySelectorAll('#ioSheetBody tr[data-mcard]').length"))
    # 안내문·엑셀·AI 버튼 정리
    for sel, lab in (('#ioAiPaste', 'AI 자료 붙여넣기'), ('#ioBulkUpload', '엑셀 일괄 업로드'), ('#ioBulkTemplate', '양식 받기')):
        v = page.evaluate(VIS, sel)
        chk(v is None or (v['display'] == 'none' or v['h'] == 0), '① 출고에서 %s 숨김' % lab, v)
    for sel, lab in (('.minfo', '회색 안내 상자'), ('#ioSheetHint', '아래 긴 안내'), ('#ioSheetModal .modal-sub', '제목 밑 설명')):
        v = page.evaluate(VIS, sel)
        chk(v is None or v['display'] == 'none' or v['h'] == 0, '① %s 안 보임' % lab, v)
    add = page.evaluate("""() => { const b = document.getElementById('ioSheetAdd');
        const bt = b.querySelector('.bt');
        return { h: Math.round(b.getBoundingClientRect().height),
                 after: bt ? getComputedStyle(bt, '::after').content : '' }; }""")
    chk('품목 추가' in (add.get('after') or ''), '① 버튼 = 「+ 품목 추가」', add)
    # 비고는 품목 카드 아래
    note = page.evaluate(VIS, '#ioSheetNote')
    card = page.evaluate(VIS, '#ioSheetBody tr[data-mcard]')
    chk(bool(note) and bool(card) and note['top'] > card['bottom'], '① 비고가 품목 카드 아래(저장 직전)',
        [card and card['bottom'], note and note['top']])
    # 카드 안 순서 — 구분 → 품명 → 재고 → 수량
    order = page.evaluate("""() => { const tr = document.querySelector('#ioSheetBody tr[data-mcard]');
        const y = s => { const e = tr.querySelector(s); return e ? Math.round(e.getBoundingClientRect().top) : -1; };
        return { kind: y('.mcr-top'), name: y('.mcr-name'), stock: y('.mcr-stock'), qty: y('.mcr-qty') }; }""")
    chk(order['kind'] < order['name'] < order['stock'] < order['qty'], '① 카드 안 순서: 구분 → 품명 → 재고 → 수량', order)
    page.screenshot(path=os.path.join(OUT, 'M1-출고-첫화면.png'))

    # ---------------------------------------------------------- 2. 품명 → 기존 재고 카드
    page.click('#ioSheetBody [data-f="name"]')
    page.type('#ioSheetBody [data-f="name"]', '우양지', delay=90)
    page.wait_for_timeout(600)
    pop = page.evaluate("""() => { const p = document.querySelector('.acpop');
        if (!p || p.classList.contains('hidden')) return { open: false };
        const r = p.getBoundingClientRect(), it = p.querySelector('.acitem');
        const st = getComputedStyle(p), si = it ? getComputedStyle(it) : null;
        return { open: true, n: p.querySelectorAll('.acitem').length, bg: st.backgroundColor,
                 radius: st.borderRadius, rowH: it ? Math.round(it.getBoundingClientRect().height) : 0,
                 rowBg: si ? si.backgroundColor : '', top: Math.round(r.top), bottom: Math.round(r.bottom) }; }""")
    chk(pop.get('open') and pop['n'] >= 1, '② 품명 「우양지」 → 등록 품목 목록', pop)
    chk(pop.get('bg') == 'rgb(255, 255, 255)', '② 목록 순백 #FFFFFF', pop.get('bg'))
    chk(str(pop.get('radius', '')).startswith('12px'), '② 모서리 12px', pop.get('radius'))
    chk(pop.get('rowH', 0) >= 48, '② 행 높이 48px 이상', pop.get('rowH'))
    page.screenshot(path=os.path.join(OUT, 'M2-품명-검색목록.png'))
    page.tap('.acpop .acitem >> nth=0')
    page.wait_for_timeout(700)
    chk(page.eval_on_selector('#ioSheetBody [data-f="name"]', 'e => e.value') == '우양지', '② 목록에서 품명 입력',
        page.eval_on_selector('#ioSheetBody [data-f="name"]', 'e => e.value'))
    stk = page.evaluate("""() => { const w = document.querySelector('#ioSheetBody [data-cell="stock"]');
        const cards = Array.from(w.querySelectorAll('.mlot'));
        return { head: (w.querySelector('.mstk-head') || {}).textContent || '',
                 n: cards.length,
                 texts: cards.map(c => c.innerText.replace(/\\s+/g, ' ').trim()),
                 h: cards.map(c => Math.round(c.getBoundingClientRect().height)),
                 wh: cards.map(c => (c.querySelector('.mwh') || {}).textContent || ''),
                 dd: cards.map(c => (c.querySelector('.mdd') || {}).textContent || ''),
                 q: cards.map(c => (c.querySelector('.mlq') || {}).textContent || '') }; }""")
    print('   재고 카드:', json.dumps(stk, ensure_ascii=False))
    chk(stk['n'] == 2, '② 기존 재고 로트 2장(냉장·냉동)', stk['n'])
    chk(min(stk['h']) >= 52, '② 카드 높이 52px 이상(터치)', stk['h'])
    chk('냉장고' in stk['wh'] and '냉동고' in stk['wh'], '② 창고 배지(냉동고·냉장고)', stk['wh'])
    chk(all(x.startswith('D') for x in stk['dd']), '② 소비기한 D-day 배지', stk['dd'])
    chk(all(x for x in stk['q']), '② 현재고 kg 표시', stk['q'])
    chk('기존 재고' in stk['head'] and '합' in stk['head'], '② 「기존 재고 · 합」 머리줄', stk['head'])
    page.screenshot(path=os.path.join(OUT, 'M3-기존재고-카드.png'))

    # 자동/터치 선택 → 수량 → 금액
    auto = page.evaluate("""() => Array.from(document.querySelectorAll('#ioSheetBody .mlot')).map(c => c.classList.contains('on'))""")
    chk(not any(auto), '② 로트가 둘이면 자동 선택하지 않음', auto)
    page.tap('#ioSheetBody .mlot >> nth=1')
    page.wait_for_timeout(500)
    sel = page.evaluate("""() => { const c = document.querySelector('#ioSheetBody .mlot.on');
        return c ? { i: Array.from(document.querySelectorAll('#ioSheetBody .mlot')).indexOf(c),
                     wh: (c.querySelector('.mwh') || {}).textContent } : null; }""")
    chk(sel and sel['i'] == 1, '② 터치한 로트가 선택됨', sel)
    onwh = page.evaluate("() => { const c = document.querySelector('#ioSheetBody .mlot.on'); return c ? c.getAttribute('data-lotwh') : null; }")
    chk(onwh == 'C', '② 고른 로트의 창고(냉장)로 함께 바뀜', onwh)
    page.fill('#ioSheetBody [data-f="qty"]', '10')
    page.wait_for_timeout(400)
    amt = page.eval_on_selector('#ioSheetBody [data-num="amt"]', 'e => e.textContent')
    page.screenshot(path=os.path.join(OUT, 'M4-로트선택-수량.png'))
    page.evaluate("() => { const c = document.querySelector('#ioSheetModal .modal-card'); c.scrollTop = c.scrollHeight; }")
    page.wait_for_timeout(400)
    page.screenshot(path=os.path.join(OUT, 'M4b-아래끝-비고-저장.png'))
    page.evaluate("() => { const c = document.querySelector('#ioSheetModal .modal-card'); c.scrollTop = 0; }")
    page.wait_for_timeout(200)
    chk(amt != '', '② 금액 자동 표시(단가 0이면 0)', amt)

    # ---------------------------------------------------------------- 3. 저장
    page.fill('#ioSheetBody [data-f="price"]', '12000')
    page.wait_for_timeout(300)
    n_after = page.evaluate("""() => { const c = document.querySelector('#ioSheetBody .mlot.on .mlq');
        return c ? c.textContent : ''; }""")
    before = T.MOCK.lots
    page.click('#ioSheetSave')
    page.wait_for_timeout(2200)
    toast = page.evaluate("""() => Array.from(document.querySelectorAll('#toast .tmsg')).map(e => e.textContent).join(' | ')""")
    chk('출고' in toast or '저장' in toast, '③ 저장 결과 알림', toast)
    mine = [l for l in T.MOCK.logs if l.get('tx_type') == 'out']
    chk(bool(mine), '③ 원료육 출고 1건 DB 반영', [(l.get('product_name'), l.get('qty'), l.get('warehouse')) for l in mine][-3:])
    if mine:
        last = mine[-1]
        chk(last.get('product_name') == '우양지' and abs(float(last.get('qty')) - 10) < 0.001,
            '③ 저장된 품목·수량 = 우양지 10kg', [last.get('product_name'), last.get('qty')])
        chk(last.get('warehouse') == onwh, '③ 고른 로트 창고 그대로 저장', [last.get('warehouse'), onwh])
    page.wait_for_timeout(400)

    # ------------------------------------------------------- 4. 단일 로트 자동 선택
    open_out(page)
    page.click('#ioSheetBody [data-f="name"]')
    page.type('#ioSheetBody [data-f="name"]', '꽃갈비', delay=90)
    page.wait_for_timeout(500)
    if page.evaluate("() => { const p = document.querySelector('.acpop'); return !!p && !p.classList.contains('hidden'); }"):
        page.tap('.acpop .acitem >> nth=0')
        page.wait_for_timeout(600)
    auto2 = page.evaluate("""() => { const c = document.querySelector('#ioSheetBody .mlot');
        return c ? { on: c.classList.contains('on'), q: (c.querySelector('.mlq') || {}).textContent } : null; }""")
    chk(auto2 and auto2['on'], '④ 보유 로트가 하나면 자동 선택', auto2)
    page.screenshot(path=os.path.join(OUT, 'M5-단일로트-자동선택.png'))
    page.click('#ioSheetClose')
    page.wait_for_timeout(300)

    # ---------------------------------------------------------------- 5. 입고 시트
    open_in(page)
    chk(page.evaluate("() => !document.getElementById('ioSheetModal').classList.contains('hidden')"), '⑤ 입고 시트 열림')
    chk(page.evaluate("() => document.getElementById('ioSheetDestWrap').classList.contains('hidden')"),
        '⑤ 입고에는 출고 구분 없음')
    v = page.evaluate(VIS, '#ioSheetBody [data-f="name"]')
    chk(v and v['inView'], '⑤ 첫 화면에 품목칸 보임', v)
    subv = page.evaluate(VIS, '#ioSheetModal .modal-sub')
    chk(subv and subv['display'] != 'none' and subv['h'] <= 40, '⑤ 입고 안내는 한 줄', subv)
    whv = page.evaluate(VIS, '#ioBulkUpload')
    chk(whv and whv['display'] != 'none' and whv['h'] <= 44, '⑤ 입고 엑셀 버튼은 작게 1줄', whv)
    inch = page.evaluate("""() => { const w = document.querySelector('#ioSheetBody [data-cell="stock"]');
        return { chips: Array.from(w.querySelectorAll('.mwhc')).map(b => b.textContent),
                 inputs: Array.from(w.querySelectorAll('input')).map(i => i.getAttribute('data-f')) }; }""")
    chk(inch['chips'] == ['냉동고', '냉장고'], '⑤ 입고 창고 칩 = 냉동고·냉장고', inch['chips'])
    chk('expiry' in inch['inputs'], '⑤ 입고 소비기한 칸', inch['inputs'])
    page.screenshot(path=os.path.join(OUT, 'M6-입고-첫화면.png'))
    page.click('#ioSheetBody [data-f="name"]')
    page.type('#ioSheetBody [data-f="name"]', '닭가슴살잔육', delay=70)
    page.wait_for_timeout(500)
    if page.evaluate("() => { const p = document.querySelector('.acpop'); return !!p && !p.classList.contains('hidden'); }"):
        page.tap('.acpop .acitem >> nth=0')
        page.wait_for_timeout(400)
    page.fill('#ioSheetBody [data-f="qty"]', '5')
    page.fill('#ioSheetBody [data-f="expiry"]', '20280630')
    page.wait_for_timeout(300)
    page.click('#ioSheetSave')
    page.wait_for_timeout(2200)
    ins = [l for l in T.MOCK.logs if l.get('tx_type') == 'in' and l.get('product_name') == '닭가슴살잔육' and abs(float(l.get('qty')) - 5) < 0.001]
    chk(bool(ins), '⑤ 입고 저장 → DB 반영', [(l.get('product_name'), l.get('qty'), l.get('exp_date')) for l in T.MOCK.logs[-2:]])
    page.wait_for_timeout(400)

    # ------------------------------------------- 5b. 로트가 많을 때 «더 보기»
    open_out(page)
    page.click('#ioSheetBody [data-f="name"]')
    page.type('#ioSheetBody [data-f="name"]', '로인립', delay=70)
    page.wait_for_timeout(500)
    if page.evaluate("() => { const p = document.querySelector('.acpop'); return !!p && !p.classList.contains('hidden'); }"):
        page.tap('.acpop .acitem >> nth=0')
        page.wait_for_timeout(600)
    many = page.evaluate("""() => { const w = document.querySelector('#ioSheetBody [data-cell=stock]');
        return { n: w.querySelectorAll('.mlot').length,
                 more: (w.querySelector('.mlmore') || {}).textContent || '',
                 head: (w.querySelector('.mstk-head') || {}).textContent || '' }; }""")
    chk(many['n'] == 5 and '더 보기' in many['more'], '⑤b 로트가 많으면 5장 + 더 보기', many)
    page.screenshot(path=os.path.join(OUT, 'M9-로트많음-더보기.png'))
    page.tap('#ioSheetBody .mlmore')
    page.wait_for_timeout(500)
    more = page.evaluate("() => document.querySelector('#ioSheetBody [data-cell=stock]').querySelectorAll('.mlot').length")
    chk(more > 5, '⑤b 더 보기로 전부 펼침', more)
    page.tap('#ioSheetBody .mlmore')
    page.wait_for_timeout(400)
    chk(page.evaluate("() => document.querySelector('#ioSheetBody [data-cell=stock]').querySelectorAll('.mlot').length") == 5,
        '⑤b 다시 접힘', '')
    page.click('#ioSheetClose')
    page.wait_for_timeout(300)

    # ---------------------------------------------------------- 6. 검색 목록 통일
    open_out(page)
    page.click('#ioSheetDestSeg button[data-dest="vendor"]')
    page.wait_for_timeout(300)
    page.click('#ioSheetPartner')
    page.type('#ioSheetPartner', '도드람', delay=80)
    page.wait_for_timeout(600)
    page.press('#ioSheetPartner', 'ArrowDown')
    page.wait_for_timeout(200)
    spec = page.evaluate("""() => { const p = document.querySelector('.acpop');
        if (!p || p.classList.contains('hidden')) return { open: false };
        const it = p.querySelector('.acitem'), on = p.querySelector('.acitem.on');
        const act = it.querySelector('.act'), acs = it.querySelector('.acs');
        return { open: true, bg: getComputedStyle(p).backgroundColor, radius: getComputedStyle(p).borderRadius,
                 rowH: Math.round(it.getBoundingClientRect().height),
                 onBg: on ? getComputedStyle(on).backgroundColor : '',
                 onColor: on ? getComputedStyle(on.querySelector('.act')).color : '',
                 tSize: act ? getComputedStyle(act).fontSize : '', tWeight: act ? getComputedStyle(act).fontWeight : '',
                 sSize: acs ? getComputedStyle(acs).fontSize : '', sColor: acs ? getComputedStyle(acs).color : '' }; }""")
    print('   목록 규격:', spec)
    chk(spec.get('bg') == 'rgb(255, 255, 255)', '⑥ 거래처 목록도 순백', spec.get('bg'))
    chk(str(spec.get('radius', '')).startswith('12px'), '⑥ 모서리 12px', spec.get('radius'))
    chk(spec.get('rowH', 0) >= 48, '⑥ 행 48px 이상', spec.get('rowH'))
    chk(spec.get('onBg') == 'rgb(239, 246, 255)', '⑥ 선택 하이라이트 #EFF6FF', spec.get('onBg'))
    chk(spec.get('onColor') == 'rgb(29, 78, 216)', '⑥ 선택 글자 #1D4ED8', spec.get('onColor'))
    chk(spec.get('tSize') == '15px' and str(spec.get('tWeight')) in ('600', '700'), '⑥ 제목 15px/600', [spec.get('tSize'), spec.get('tWeight')])
    chk(spec.get('sSize') == '12px' and spec.get('sColor') == 'rgb(107, 114, 128)', '⑥ 보조 12px #6B7280', [spec.get('sSize'), spec.get('sColor')])
    page.screenshot(path=os.path.join(OUT, 'M7-거래처-검색통일.png'))
    page.click('#ioSheetClose')
    page.wait_for_timeout(300)

    # ------------------------------------------------- 6b. 여러 줄 · 구분 바꾸기
    open_out(page)
    page.click('#ioSheetAdd')
    page.wait_for_timeout(500)
    chk(page.evaluate("() => document.querySelectorAll('#ioSheetBody tr[data-mcard]').length") == 2,
        '⑥b 「+ 품목 추가」로 카드가 한 장 더', page.evaluate("() => document.querySelectorAll('#ioSheetBody tr[data-mcard]').length"))
    page.select_option('#ioSheetBody tr[data-r="1"] [data-f="kind"]', 'fg')
    page.wait_for_timeout(400)
    fg = page.evaluate("""() => { const tr = document.querySelector('#ioSheetBody tr[data-r="1"]');
        return { flag: !!tr.querySelector('[data-f=\"flag\"]'),
                 chips: Array.from(tr.querySelectorAll('.mwhc')).map(b => b.textContent) }; }""")
    chk(fg['flag'], '⑥b 완제품으로 바꾸면 자체/매입 칩이 나옴', fg)
    page.fill('#ioSheetBody tr[data-r="1"] [data-f="name"]', '탐나는피자 슈프림불고기')
    page.dispatch_event('#ioSheetBody tr[data-r="1"] [data-f="name"]', 'change')
    page.wait_for_timeout(600)
    fp = page.evaluate("""() => { const tr = document.querySelector('#ioSheetBody tr[data-r="1"]');
        const c = tr.querySelector('.mlot');
        return { head: (tr.querySelector('.mstk-head') || {}).textContent || '',
                 n: tr.querySelectorAll('.mlot').length,
                 txt: c ? c.innerText.replace(/\\s+/g, ' ') : '' }; }""")
    chk(fp['n'] == 2, '⑥b 완제품도 있는 로트가 카드로', fp)
    page.screenshot(path=os.path.join(OUT, 'M8-완제품-로트카드.png'))
    page.click('#ioSheetBody tr[data-r="1"] .vdel')
    page.wait_for_timeout(400)
    chk(page.evaluate("() => document.querySelectorAll('#ioSheetBody tr[data-mcard]').length") == 1,
        '⑥b × 로 줄 삭제', page.evaluate("() => document.querySelectorAll('#ioSheetBody tr[data-mcard]').length"))
    page.click('#ioSheetClose')
    page.wait_for_timeout(300)

    # --------------------------------------------------------------- 7. 마무리
    over = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    chk(over == 0, '⑦ 가로 넘침 0px', over)
    real_errs = [e for e in errs if 'Failed to load resource' not in e]
    chk(not real_errs, '⑦ JS 오류 0', real_errs[:3])
    own = [x for x in bad if any(k in x[1] for k in ('app.js', 'mobile.css', 'style.css', 'index.html', 'partners_data.js'))]
    chk(not own, '⑦ 우리 자산 404 없음', own[:3])
    ctx.close()

    # ------------------------------------------------------------- PC 1920 확인
    ctx = b.new_context(viewport={'width': 1920, 'height': 1080})
    page = ctx.new_page()
    errs2 = []
    page.on('pageerror', lambda e: errs2.append(str(e)))
    page.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
    page.add_init_script(T.FAKE_WS)
    page.goto(T.BASE + '?v=20261126_69')
    page.wait_for_timeout(400)
    login(page)
    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"out\"]').click()")
    page.wait_for_timeout(1200)
    pc = page.evaluate("""() => { const m = document.getElementById('ioSheetModal');
        const rows = m.querySelectorAll('#ioSheetBody tr');
        const tds = rows.length ? rows[0].children.length : 0;
        return { open: !m.classList.contains('hidden'), rows: rows.length, tds: tds,
                 mcard: m.querySelectorAll('[data-mcard]').length,
                 sum: getComputedStyle(document.getElementById('ioSheetMSum')).display,
                 mob: matchMedia('(max-width: 768px)').matches }; }""")
    print('   PC:', pc)
    chk(pc['open'] and pc['tds'] == 10 and pc['mcard'] == 0, '⑧ PC 는 지금까지의 10칸 표 그대로', pc)
    chk(pc['sum'] == 'none', '⑧ PC 에서 폰 합계줄 숨김', pc['sum'])
    page.screenshot(path=os.path.join(OUT, 'P1-출고팝업.png'))
    chk(not errs2, '⑧ PC JS 오류 0', errs2[:3])
    ctx.close()
    b.close()


with sync_playwright() as pw:
    run(pw)

print('RESULT', 'PASS' if ok else 'FAIL')
sys.exit(0 if ok else 1)
