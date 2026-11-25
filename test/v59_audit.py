# -*- coding: utf-8 -*-
"""v59 검증 — 품목·거래처 실시간 검색 드롭다운 (폰 390×844 · PC 1920×1080)
   LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/v59_audit.py [tag]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_ui as T
import shot_v36 as V36
from playwright.sync_api import sync_playwright

TAG = sys.argv[1] if len(sys.argv) > 1 else 'run'
OUT = '/workspace/downloads/erp-v59-화면/' + TAG
os.makedirs(OUT, exist_ok=True)
ok = True


def chk(cond, label, extra=''):
    global ok
    print(('  [OK]   ' if cond else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not cond:
        ok = False


POP = """() => {
  const p = document.querySelector('.acpop');
  if (!p || p.classList.contains('hidden')) return { open: false };
  const r = p.getBoundingClientRect();
  const items = Array.from(p.querySelectorAll('.acitem'));
  const h = items.map(it => Math.round(it.getBoundingClientRect().height));
  const vv = window.visualViewport;
  const vh = vv ? vv.height : window.innerHeight;
  return { open: true, n: items.length, texts: items.map(it => (it.querySelector('.act') || {}).textContent),
           top: Math.round(r.top), bottom: Math.round(r.bottom), left: Math.round(r.left), w: Math.round(r.width),
           z: getComputedStyle(p).zIndex, bg: getComputedStyle(p).backgroundColor,
           rows: h, minRow: h.length ? Math.min.apply(null, h) : 0,
           vh: Math.round(vh), inView: r.top >= -1 && r.bottom <= vh + 1, over: document.documentElement.scrollWidth - window.innerWidth };
}"""


def seed_acc():
    w = {'worker_name': '김검증', 'worker_email': 'kim@meat.co.kr', 'created_at': '2026-11-18T00:00:00Z'}
    T.MOCK.vouchers += [
        dict(id=1, source='manual', source_kind='', source_id=None, v_date='2026-11-22', v_type='purchase',
             partner='하림', tax_type='tax', supply_amount=860000, vat_amount=86000, total_amount=946000,
             tax_status='none', note='닭고기 매입', **w),
    ]
    T.MOCK.seq_v = 1


def login(page):
    page.fill('#liEmail', 'kim@meat.co.kr')
    page.fill('#liPw', 'secret123')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=8000)
    page.wait_for_timeout(1800)
    page.add_style_tag(content='#toast{display:none !important}')


def run_mobile(pw):
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
    seed_acc()
    page.goto(T.BASE + '?v=20261126_68')
    page.wait_for_timeout(400)
    login(page)

    # ---------- 1. 출고 시트 · 현장(생산) 생산품목 ----------
    page.click('#mobTabs [data-mtab="out"]')
    page.wait_for_timeout(500)
    page.click('#mobSheet [data-nav="out"]')
    page.wait_for_timeout(900)
    chk(page.evaluate("() => !document.getElementById('ioSheetModal').classList.contains('hidden')"), '출고 시트 열림')
    chk(page.evaluate("() => (document.querySelector('#ioSheetDestSeg button.active')||{}).textContent.trim()") == '현장(생산)',
        '출고 구분 = 현장(생산)')
    page.click('#ioSheetPartner')
    page.type('#ioSheetPartner', '슈프', delay=90)
    page.wait_for_timeout(600)
    s = page.evaluate(POP)
    chk(s.get('open') and s['n'] >= 1, '① 생산품목 「슈프」 → 목록 뜸', s.get('texts'))
    chk(any('슈프' in (t or '') for t in (s.get('texts') or [])), '① 등록 품목이 부분일치로 잡힘', s.get('texts'))
    chk(s.get('minRow', 0) >= 40, '① 줄 높이 40 이상', s.get('rows'))
    chk(s.get('bg') == 'rgb(255, 255, 255)', '① 배경 순백', s.get('bg'))
    chk(int(s.get('z') or 0) >= 1000, '① z-index 최상단(바텀 시트 위)', s.get('z'))
    chk(s.get('inView'), '① 목록이 화면 안에 들어옴', [s.get('top'), s.get('bottom'), s.get('vh')])
    chk(s.get('over') == 0, '① 가로 넘침 0', s.get('over'))
    page.screenshot(path=os.path.join(OUT, 'F1-생산품목-슈프.png'))
    page.tap('.acpop .acitem >> nth=0')
    page.wait_for_timeout(500)
    v = page.eval_on_selector('#ioSheetPartner', 'e => e.value')
    chk(bool(v) and '슈프' in v, '① 터치로 품목이 입력됨', v)
    chk(page.evaluate("() => { const p = document.querySelector('.acpop'); return !p || p.classList.contains('hidden'); }"),
        '① 고른 뒤 목록 닫힘')
    # 고른 값이 그대로 저장 준비(줄 1개 채우고 출고 저장까지)
    page.fill('#ioSheetPartner', '')
    page.click('#ioSheetPartner')
    page.type('#ioSheetPartner', '슈프', delay=60)
    page.wait_for_timeout(400)
    page.tap('.acpop .acitem >> nth=0')
    page.wait_for_timeout(300)
    page.fill('#ioSheetBody tr[data-r="0"] input[data-f="qty"]', '2')
    page.screenshot(path=os.path.join(OUT, 'F2-생산품목-입력후.png'))

    # ---------- 2. 출고 시트 · 업체(판매) 거래처 ----------
    page.click('#ioSheetDestSeg button[data-dest="vendor"]')
    page.wait_for_timeout(300)
    chk(page.eval_on_selector('#ioSheetPartnerLabel', 'e => e.textContent.trim()') == '거래처', '출고 구분 → 거래처 칸')
    page.fill('#ioSheetPartner', '')
    page.click('#ioSheetPartner')
    page.type('#ioSheetPartner', '도드람', delay=80)
    page.wait_for_timeout(600)
    s = page.evaluate(POP)
    chk(s.get('open') and s['n'] >= 1, '② 거래처 「도드람」 → 목록 뜸', s.get('texts'))
    page.screenshot(path=os.path.join(OUT, 'F3-거래처-도드람.png'))
    page.tap('.acpop .acitem >> nth=0')
    page.wait_for_timeout(400)
    chk('도드람' in page.eval_on_selector('#ioSheetPartner', 'e => e.value'), '② 터치로 거래처 입력됨',
        page.eval_on_selector('#ioSheetPartner', 'e => e.value'))
    # 맞는 것이 없을 때
    page.fill('#ioSheetPartner', '')
    page.click('#ioSheetPartner')
    page.type('#ioSheetPartner', 'ㅁㄴㅇㄹ없는품목', delay=40)
    page.wait_for_timeout(500)
    nr = page.evaluate("() => { const p = document.querySelector('.acpop'); if (!p || p.classList.contains('hidden')) return null; const n = p.querySelector('.acnone'); return n ? n.textContent : ''; }")
    chk(bool(nr), '②b 맞는 항목이 없으면 «일치하는 항목이 없습니다» 한 줄', nr)
    page.screenshot(path=os.path.join(OUT, 'F3b-없음.png'))
    page.click('#ioSheetClose')
    page.wait_for_timeout(300)

    # ---------- 3. 입고 시트 · 업체·거래처 + 품목 줄 ----------
    page.click('#mobTabs [data-mtab="in"]')
    page.wait_for_timeout(900)
    chk(page.evaluate("() => !document.getElementById('ioSheetModal').classList.contains('hidden')"), '입고 시트 열림')
    page.click('#ioSheetPartner')
    page.type('#ioSheetPartner', '하림', delay=80)
    page.wait_for_timeout(600)
    s = page.evaluate(POP)
    chk(s.get('open') and s['n'] >= 1, '③ 입고 「업체·거래처」 목록', s.get('texts'))
    page.tap('.acpop .acitem >> nth=0')
    page.wait_for_timeout(300)
    chk('하림' in page.eval_on_selector('#ioSheetPartner', 'e => e.value'), '③ 입고 거래처 입력됨')
    ni = '#ioSheetBody tr[data-r="0"] input[data-f="name"]'
    page.click(ni)
    page.type(ni, '등갈', delay=90)
    page.wait_for_timeout(600)
    s = page.evaluate(POP)
    chk(s.get('open') and s['n'] >= 1, '③ 입고 품목 줄 「등갈」 목록', s.get('texts'))
    page.screenshot(path=os.path.join(OUT, 'F4-입고-품목줄.png'))
    page.tap('.acpop .acitem >> nth=0')
    page.wait_for_timeout(300)
    chk(page.eval_on_selector(ni, 'e => e.value') == '등갈비', '③ 품목 줄 터치 입력', page.eval_on_selector(ni, 'e => e.value'))
    # 완제품 줄
    page.select_option('#ioSheetBody tr[data-r="1"] select[data-f="kind"]', 'fg')
    page.wait_for_timeout(400)
    ni2 = '#ioSheetBody tr[data-r="1"] input[data-f="name"]'
    page.click(ni2)
    page.type(ni2, '슈프', delay=90)
    page.wait_for_timeout(600)
    s = page.evaluate(POP)
    chk(s.get('open') and any('슈프' in (t or '') for t in (s.get('texts') or [])), '③ 완제품 줄 「슈프」 목록', s.get('texts'))
    page.screenshot(path=os.path.join(OUT, 'F5-입고-완제품줄.png'))
    page.tap('.acpop .acitem >> nth=0')
    page.wait_for_timeout(600)
    code = page.eval_on_selector('#ioSheetBody tr[data-r="1"] [data-cell="code"]', 'e => e.textContent')
    chk(code.startswith('FP-') or code.startswith('W'), '③ 고른 품목의 코드가 채워짐', code)
    page.click('#ioSheetClose')
    page.wait_for_timeout(300)

    # ---------- 4. 해동/냉동 · 생산품명 (해동) ----------
    page.click('#mobTabs [data-mtab="out"]')
    page.wait_for_timeout(400)
    page.click('#mobSheet [data-nav="move"]')
    page.wait_for_timeout(800)
    chk(page.evaluate("() => !document.getElementById('uniMoveModal').classList.contains('hidden')"), '해동/냉동 시트 열림')
    page.click('#uniMoveProd')
    page.type('#uniMoveProd', '슈프', delay=90)
    page.wait_for_timeout(600)
    s = page.evaluate(POP)
    chk(s.get('open') and s['n'] >= 1, '④ 해동 「생산품명 (해동)」 목록', s.get('texts'))
    chk(s.get('inView'), '④ 목록이 화면 안', [s.get('top'), s.get('bottom'), s.get('vh')])
    page.screenshot(path=os.path.join(OUT, 'F6-해동-생산품명.png'))
    page.tap('.acpop .acitem >> nth=0')
    page.wait_for_timeout(300)
    chk('슈프' in page.eval_on_selector('#uniMoveProd', 'e => e.value'), '④ 해동 생산품명 입력됨',
        page.eval_on_selector('#uniMoveProd', 'e => e.value'))
    page.click('#uniMoveClose')
    page.wait_for_timeout(300)

    # ---------- 5. 원료육 출고 팝업(meatFormModal) 생산품목 ----------
    page.evaluate('() => document.querySelector(\'#ioHubModal [data-io="out"]\').click()')
    page.wait_for_timeout(900)
    chk(page.evaluate("() => !document.getElementById('meatFormModal').classList.contains('hidden')"), '원료육 출고 팝업 열림')
    page.click('#outDest')
    page.type('#outDest', '슈프', delay=90)
    page.wait_for_timeout(600)
    s = page.evaluate(POP)
    chk(s.get('open') and s['n'] >= 1, '⑤ 원료육 출고 「생산품목」 목록', s.get('texts'))
    page.screenshot(path=os.path.join(OUT, 'F7-원료육출고-생산품목.png'))
    page.tap('.acpop .acitem >> nth=0')
    page.wait_for_timeout(300)
    page.evaluate("() => document.getElementById('meatFormClose').click()")
    page.wait_for_timeout(300)

    # ---------- 6. 해동 팝업(thProd) ----------
    page.evaluate('() => document.querySelector(\'#ioHubModal [data-io="thaw"]\').click()')
    page.wait_for_timeout(900)
    page.click('#meatFormModal [data-mode="thaw"]')
    page.wait_for_timeout(300)
    page.click('#thProd')
    page.type('#thProd', '슈프', delay=90)
    page.wait_for_timeout(600)
    s = page.evaluate(POP)
    chk(s.get('open') and s['n'] >= 1, '⑥ 해동 팝업 「생산품명」 목록', s.get('texts'))
    page.screenshot(path=os.path.join(OUT, 'F8-해동팝업-생산품명.png'))
    page.evaluate("() => document.getElementById('meatFormClose').click()")
    page.wait_for_timeout(300)

    # ---------- 7. 전 화면 가로 넘침 ----------
    over = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    chk(over == 0, '⑦ 화면 가로 넘침 0', over)
    bad2 = [x for x in bad if x[1] not in ('favicon.ico',) and not x[1].startswith('audit_logs')]
    cerr = [e for e in errs if not (e.startswith('console:Failed to load resource') and not bad2)]
    chk(not cerr, '⑦ JS 오류 0 (모의 서버에 없는 audit_logs 404 는 제외)', cerr[:4])
    chk(not bad2, '⑦ 자산 404 없음(favicon·모의 audit_logs 제외)', bad2[:4])
    print('  URL', page.url)
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
    seed_acc()
    page.goto(T.BASE + '?v=20261126_68')
    page.wait_for_timeout(400)
    login(page)
    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"out\"]').click()")
    page.wait_for_timeout(900)
    page.click('#ioSheetPartner')
    page.type('#ioSheetPartner', '슈프', delay=60)
    page.wait_for_timeout(500)
    s = page.evaluate(POP)
    chk(s.get('open') and s['n'] >= 1, 'PC ① 생산품목 「슈프」 목록', s.get('texts'))
    page.screenshot(path=os.path.join(OUT, 'P1-생산품목-슈프.png'))
    page.keyboard.press('ArrowDown')
    page.keyboard.press('Enter')
    page.wait_for_timeout(300)
    v = page.eval_on_selector('#ioSheetPartner', 'e => e.value')
    chk(bool(v) and '슈프' in v, 'PC ① ↓·Enter 로 입력됨', v)
    page.click('#ioSheetDestSeg button[data-dest="vendor"]')
    page.wait_for_timeout(300)
    page.fill('#ioSheetPartner', '')
    page.click('#ioSheetPartner')
    page.type('#ioSheetPartner', '도드람', delay=60)
    page.wait_for_timeout(500)
    s = page.evaluate(POP)
    chk(s.get('open') and s['n'] >= 1, 'PC ② 거래처 목록', s.get('texts'))
    page.screenshot(path=os.path.join(OUT, 'P2-거래처-도드람.png'))
    page.click('.acpop .acitem >> nth=0')
    page.wait_for_timeout(300)
    chk('도드람' in page.eval_on_selector('#ioSheetPartner', 'e => e.value'), 'PC ② 클릭으로 거래처 입력',
        page.eval_on_selector('#ioSheetPartner', 'e => e.value'))
    # 전표 거래처 칸
    page.evaluate("() => document.getElementById('ioSheetClose').click()")
    page.wait_for_timeout(400)
    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"expense\"]').click()")
    page.wait_for_timeout(900)
    has = page.evaluate("() => !!document.getElementById('accVPartner')")
    chk(has, 'PC ③ 매입/매출 전표 팝업에 거래처 칸 있음')
    cerr2 = [e for e in errs if not e.startswith('console:Failed to load resource')]
    chk(not cerr2, 'PC JS 오류 0 (모의 audit_logs 404 제외)', cerr2[:4])
    b.close()


with sync_playwright() as pw:
    print('== 폰 390×844 ==')
    run_mobile(pw)
    print('== PC 1920×1080 ==')
    run_pc(pw)
print('RESULT', 'PASS' if ok else 'FAIL')
