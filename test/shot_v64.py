# -*- coding: utf-8 -*-
"""v64 빠른 스모크 — 모든 날짜 칸의 «/ · - · .» 구분자 입력 (PC 1920 · 폰 390)

  1) 날짜 칸 전부 type=text(data-sd) · 폰에서는 inputmode=text(/ 와 - 를 칠 수 있게)
  2) 형식 매트릭스 — 26/11/26 · 2026/11/26 · 26-11-26 · 2026-11-26 · 26/6/5 · 2026/6/5 ·
     26.11.26 · 2026.11.26 · 1112 · 281123 · 261125 · 20261126  →  YYYY-MM-DD
     · 달력에 없는 26/13/40 은 덮어쓰지 않고 원래 값으로 되돌린다
  3) 입고 팝업 입고일 26/11/26 → 2026-11-26 · 소비기한 26-6-5 → 2026-06-05 (타이핑 도중 값 보존)
  4) 1줄 저장 → DB(tx_date · exp_date)에 YYYY-MM-DD
  5) 기간 필터(#utxFrom · #buyFrom) · 전표일자(#accVDate) · 경비 기간(#accFrom)
  6) 폰 390 — 입고일 · 소비기한 · 기간 필터에 2026/11/26 · 26/6/5
  7) 레이아웃 넘침 0 · JS 오류 0

   LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/shot_v64.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_ui as T
from playwright.sync_api import sync_playwright

OUT = os.path.join('/workspace', 'downloads', 'erp-v64-화면')
ok = True


def chk(cond, label, extra=''):
    global ok
    print(('  [OK]   ' if cond else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not cond:
        ok = False


VAL = "() => { const el = document.activeElement; return { v: el ? el.value : null, s: el ? el.selectionStart : null, e: el ? el.selectionEnd : null }; }"

MATRIX = r"""async () => {
  const el = document.createElement('input');
  el.setAttribute('data-sd', '1');
  el.style.cssText = 'position:fixed;left:-9999px;top:0;width:120px';
  document.body.appendChild(el);
  await new Promise(r => setTimeout(r, 80));
  const cases = ['26/11/26', '2026/11/26', '26-11-26', '2026-11-26', '26/6/5', '26-6-5', '2026/6/5',
                 '2026-6-5', '26.11.26', '2026.11.26', '26/11/6', '1112', '281123', '261125',
                 '20261126', '2026/11/26 ', '2026／11／26', '26/13/40', '2026-02-30', '1332', '26/11'];
  const out = {};
  for (const c of cases) {
    el.value = c;
    el.setAttribute('data-sd-prev', '');
    el.dispatchEvent(new Event('blur'));
    out[c] = el.value;
  }
  const init = { sd: el.getAttribute('data-sd-init'), im: el.getAttribute('inputmode') };
  el.remove();
  return { out: out, init: init };
}"""

WANT = {
    '26/11/26': '2026-11-26', '2026/11/26': '2026-11-26', '26-11-26': '2026-11-26',
    '2026-11-26': '2026-11-26', '26/6/5': '2026-06-05', '26-6-5': '2026-06-05',
    '2026/6/5': '2026-06-05', '2026-6-5': '2026-06-05', '26.11.26': '2026-11-26',
    '2026.11.26': '2026-11-26', '26/11/6': '2026-11-06', '1112': '2026-11-12',
    '281123': '2028-11-23', '261125': '2026-11-25', '20261126': '2026-11-26',
    '2026/11/26 ': '2026-11-26', '2026／11／26': '2026-11-26', '26/11': '',
    '26/13/40': '', '2026-02-30': '', '1332': '',
}


def click_type(page, sel, text, expect_typed=None):
    """칸을 «클릭만» 한 뒤 지우지 않고 바로 타이핑한다(전체 선택이 돼 있어야 덮어쓴다)."""
    page.click(sel)
    page.wait_for_timeout(120)
    st = page.evaluate(VAL)
    if expect_typed is not None:
        chk(st['s'] == 0 and st['e'] == len(st['v'] or ''),
            '  클릭만 해도 들어 있던 날짜가 전체 선택된다', st)
    page.keyboard.type(text, delay=45)
    page.wait_for_timeout(120)
    return page.evaluate(VAL)


def layout_bad(page):
    return page.evaluate(r"""() => {
      const bad = [];
      document.querySelectorAll('input[data-sd="1"]').forEach(el => {
        if (!el.offsetParent) return;
        if (el.scrollWidth > el.clientWidth + 2) bad.push(['text-clip', el.id || el.className, el.scrollWidth, el.clientWidth]);
        const box = el.closest('.vhead, .field, .rng, .utool, td');
        if (box) { const r = el.getBoundingClientRect(), br = box.getBoundingClientRect();
          if (r.right > br.right + 1.5) bad.push(['out', el.id, Math.round(r.right), Math.round(br.right)]); }
      });
      return bad;
    }""")


def login(page):
    page.goto(T.BASE)
    page.wait_for_timeout(400)
    page.fill('#liEmail', 'kim@meat.co.kr')
    page.fill('#liPw', 'secret123')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=15000)
    page.wait_for_timeout(1800)
    page.add_style_tag(content='#toast{display:none !important}')


def open_in_sheet(page):
    mobile = page.evaluate("() => window.innerWidth <= 768")
    if mobile and not page.evaluate("() => document.body.classList.contains('sideopen')"):
        page.click('#qbList')
        page.wait_for_timeout(500)
    page.click('#v8Side [data-nav="stock:meat"]')
    page.wait_for_timeout(500)
    page.click('#v8Side [data-nav="stock:meat:F"]')
    page.wait_for_timeout(600)
    page.click('#v8Side [data-nav="in"]')
    page.wait_for_timeout(900)
    if mobile:
        page.click('#sideClose')
        page.wait_for_timeout(400)


def go_nav(page, nav):
    mobile = page.evaluate("() => window.innerWidth <= 768")
    if mobile and not page.evaluate("() => document.body.classList.contains('sideopen')"):
        page.click('#qbList')
        page.wait_for_timeout(500)
    page.click('#v8Side [data-nav="%s"]' % nav)
    page.wait_for_timeout(900)
    if mobile:
        page.click('#sideClose')
        page.wait_for_timeout(400)


def main():
    os.makedirs(OUT, exist_ok=True)
    errors = []
    libs = '/workspace/tool-results/chromelibs'
    env = dict(os.environ)
    if os.path.isdir(libs):
        env['LD_LIBRARY_PATH'] = libs + (':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    with sync_playwright() as pw:
        b = pw.chromium.launch(env=env)
        page = b.new_page(viewport={'width': 1920, 'height': 1080})
        bad_res = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: errors.append('console:' + m.text) if m.type == 'error' else None)
        page.on('response', lambda r: bad_res.append((r.status, r.url)) if r.status >= 400 else None)
        page.on('dialog', lambda d: d.accept())
        page.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
        page.add_init_script(T.FAKE_WS)
        login(page)

        print('== 1. 날짜 칸 상태 ============================================')
        stat = page.evaluate("""() => {
          const all = Array.from(document.querySelectorAll('input[data-sd="1"]'));
          return { n: all.length, dates: document.querySelectorAll('input[type="date"]').length,
                   texts: all.filter(e => e.type === 'text').length,
                   im: {} };
        }""")
        print('     ', stat)
        chk(stat['n'] >= 36 and stat['dates'] == 0 and stat['texts'] == stat['n'],
            '모든 날짜 칸이 type=text (브라우저 date 칸 0)', (stat['n'], stat['dates']))
        chk(page.evaluate("""() => Array.from(document.querySelectorAll('input[data-sd="1"]')).every(e => e.getAttribute('inputmode') === 'numeric')"""),
            'PC 는 숫자 자판 안내(inputmode=numeric)', '')

        print('== 2. 형식 매트릭스 ==========================================')
        m = page.evaluate(MATRIX)
        for k, want in WANT.items():
            chk(m['out'].get(k) == want, '%-14s → %-10s' % (k, want or '(되돌림)'), m['out'].get(k))

        print('== 3. 입고 팝업 — 입고일 · 소비기한 ===========================')
        open_in_sheet(page)
        d0 = page.input_value('#ioSheetDate')
        print('     입고일 기본값:', d0)
        st = click_type(page, '#ioSheetDate', '26/11/26', expect_typed=True)
        chk(st['v'] == '26/11/26', '치는 도중에는 글자를 건드리지 않는다', st['v'])
        page.keyboard.press('Tab')
        page.wait_for_timeout(250)
        v = page.input_value('#ioSheetDate')
        chk(v == '2026-11-26', '26/11/26 → blur 하면 2026-11-26', v)
        page.screenshot(path=os.path.join(OUT, '01-입고-슬래시날짜.png'))

        exp = '#ioSheetBody [data-r="0"] [data-f="expiry"]'
        st = click_type(page, exp, '26-6-5')
        chk(st['v'] == '26-6-5', '  하이픈 한 자리 월·일 그대로 들어간다', st['v'])
        page.keyboard.press('Enter')
        page.wait_for_timeout(250)
        v = page.input_value(exp)
        chk(v == '2026-06-05', '26-6-5 → Enter 하면 2026-06-05', v)

        # 완성된 YYYY-MM-DD 를 다시 쳐도 그대로
        st = click_type(page, exp, '2026/11/26')
        page.keyboard.press('Tab')
        page.wait_for_timeout(200)
        chk(page.input_value(exp) == '2026-11-26', '2026/11/26 → 2026-11-26', page.input_value(exp))

        # 알아볼 수 없는 값은 되돌림
        page.click(exp)
        page.wait_for_timeout(120)
        page.keyboard.type('26/13/40', delay=40)
        page.keyboard.press('Tab')
        page.wait_for_timeout(300)
        chk(page.input_value(exp) == '2026-11-26', '26/13/40 (13월 40일)은 덮어쓰지 않고 되돌린다', page.input_value(exp))

        print('== 4. 실제 1줄 저장 — DB 에 YYYY-MM-DD ========================')
        page.fill('#ioSheetBody [data-r="0"] [data-f="name"]', '테스트v64등갈비')
        page.wait_for_timeout(200)
        page.fill('#ioSheetBody [data-r="0"] [data-f="qty"]', '7.5')
        page.wait_for_timeout(200)
        click_type(page, '#ioSheetBody [data-r="0"] [data-f="expiry"]', '2028/11/23')
        page.keyboard.press('Tab')
        page.wait_for_timeout(200)
        click_type(page, '#ioSheetDate', '2026/11/12')
        page.keyboard.press('Tab')
        page.wait_for_timeout(200)
        nlog = len(T.MOCK.logs)
        page.click('#ioSheetSave')
        page.wait_for_timeout(3200)
        new = T.MOCK.logs[-1] if len(T.MOCK.logs) > nlog else {}
        print('     저장된 줄:', {k: new.get(k) for k in ('tx_date', 'tx_type', 'qty')})
        chk(new.get('tx_date') == '2026-11-12', '입고일이 2026-11-12 로 저장', new.get('tx_date'))
        lot = None
        for l in T.MOCK.lots:
            if l.get('id') == new.get('lot_id'):
                lot = l
        chk(lot is not None and lot.get('exp_date') == '2028-11-23', '소비기한이 2028-11-23 로 저장',
            (lot or {}).get('exp_date'))

        print('== 5. 기간 필터 · 전표일자 · 경비 =============================')
        page.click('#v8Side [data-nav="tx"]')
        page.wait_for_timeout(1000)
        st = click_type(page, '#utxFrom', '26/11/26')
        chk(st['v'] == '26/11/26', '  #utxFrom 치는 도중 그대로', st['v'])
        page.keyboard.press('Enter')
        page.wait_for_timeout(900)
        v = page.input_value('#utxFrom')
        disp = page.inner_text('#utxRangeDisplay')
        print('     기간 표시:', disp)
        chk(v == '2026-11-26', '입출고 기간 시작일 26/11/26 → 2026-11-26', v)
        chk('2026-11-26' in disp, '기간 필터(change)까지 그대로 돈다', disp)
        click_type(page, '#utxTo', '26-12-25')
        page.keyboard.press('Tab')
        page.wait_for_timeout(800)
        v2 = page.input_value('#utxTo')
        disp = page.inner_text('#utxRangeDisplay')
        chk(v2 == '2026-12-25' and '2026-12-25' in disp, '종료일 26-12-25 → 2026-12-25 · 표시 갱신', (v2, disp))
        page.screenshot(path=os.path.join(OUT, '02-기간필터-구분자.png'))

        page.click('#v8Side [data-nav="buy-list"]')
        page.wait_for_timeout(1000)
        click_type(page, '#buyFrom', '2026/6/5')
        page.keyboard.press('Tab')
        page.wait_for_timeout(700)
        chk(page.input_value('#buyFrom') == '2026-06-05', '매입 기간 시작일 2026/6/5 → 2026-06-05',
            page.input_value('#buyFrom'))
        page.click('#btnBuyNew')
        page.wait_for_timeout(900)
        click_type(page, '#accVDate', '26/11/12')
        page.keyboard.press('Tab')
        page.wait_for_timeout(400)
        chk(page.input_value('#accVDate') == '2026-11-12', '매입 전표일자 26/11/12 → 2026-11-12',
            page.input_value('#accVDate'))
        page.screenshot(path=os.path.join(OUT, '03-전표일자-구분자.png'))
        page.click('#accVoucherClose')
        page.wait_for_timeout(400)
        page.click('#v8Side [data-nav="sale-list"]')
        page.wait_for_timeout(1000)
        click_type(page, '#saleFrom', '2026.11.26')
        page.keyboard.press('Tab')
        page.wait_for_timeout(700)
        chk(page.input_value('#saleFrom') == '2026-11-26', '매출 기간 2026.11.26 → 2026-11-26',
            page.input_value('#saleFrom'))
        click_type(page, '#saleTo', '26.12.31')
        page.keyboard.press('Tab')
        page.wait_for_timeout(700)
        chk(page.input_value('#saleTo') == '2026-12-31', '매출 기간 26.12.31 → 2026-12-31',
            page.input_value('#saleTo'))

        print('== 6. 레이아웃 · 금지어 · JS 오류 =============================')
        bad = layout_bad(page)
        chk(not bad, '날짜 칸이 칸·줄 밖으로 넘치지 않는다', bad[:4])
        txt = page.evaluate("() => document.body.innerText")
        chk('줄돈' not in txt and '받을돈' not in txt, '금지어(줄돈 · 받을돈) 0건', '')
        real = [e for e in errors if 'favicon' not in e and 'Failed to load resource' not in e]
        res404 = [x for x in bad_res if 'favicon' not in x[1] and 'supabase.co' not in x[1]]
        print('     404:', res404[:5])
        chk(not res404, 'PC 404 응답 0건(favicon 제외)', res404[:3])
        chk(not real, 'PC 콘솔 JS 오류 0건', real[:3])
        page.close()

        print('== 7. 폰 390×844 ============================================')
        errors2 = []
        mp = b.new_page(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True,
                        device_scale_factor=3, user_agent=T.MOBILE_UA if hasattr(T, 'MOBILE_UA') else None)
        bad_res2 = []
        mp.on('pageerror', lambda e: errors2.append(str(e)))
        mp.on('response', lambda r: bad_res2.append((r.status, r.url)) if r.status >= 400 else None)
        mp.on('console', lambda m: errors2.append('console:' + m.text) if m.type == 'error' else None)
        mp.on('dialog', lambda d: d.accept())
        mp.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
        mp.add_init_script(T.FAKE_WS)
        login(mp)
        ims = mp.evaluate("""() => {
          const all = Array.from(document.querySelectorAll('input[data-sd="1"]'));
          return { coarse: matchMedia('(pointer: coarse)').matches, n: all.length,
                   text: all.filter(e => e.getAttribute('inputmode') === 'text').length };
        }""")
        print('     ', ims)
        chk(ims['coarse'] and ims['n'] > 0 and ims['text'] == ims['n'],
            '폰에서는 날짜 칸이 글자 자판(inputmode=text) — / 와 - 를 칠 수 있다', ims)

        mp.click('#mobTabs [data-mtab="in"]')
        mp.wait_for_timeout(1400)
        chk(mp.is_visible('#ioSheetDate'), '폰 «입고» 탭으로 입고 시트가 열린다', '')
        click_type(mp, '#ioSheetDate', '2026/11/26')
        mp.keyboard.press('Tab')
        mp.wait_for_timeout(250)
        chk(mp.input_value('#ioSheetDate') == '2026-11-26', '폰 입고일 2026/11/26 → 2026-11-26',
            mp.input_value('#ioSheetDate'))
        exp2 = '#ioSheetBody [data-r="0"] [data-f="expiry"]'
        click_type(mp, exp2, '26/6/5')
        mp.keyboard.press('Enter')
        mp.wait_for_timeout(250)
        chk(mp.input_value(exp2) == '2026-06-05', '폰 소비기한 26/6/5 → 2026-06-05', mp.input_value(exp2))
        mp.screenshot(path=os.path.join(OUT, '04-폰-입고-구분자.png'))
        mp.evaluate("() => { if (window.scrollTo) window.scrollTo(0,0); }")

        # 폰 기간 필터 — 하단 «내역» 탭
        mp.evaluate("() => { const x=document.getElementById('ioSheetClose'); if (x) x.click(); }")
        mp.wait_for_timeout(500)
        mp.click('#mobTabs [data-mtab="tx"]')
        mp.wait_for_timeout(1200)
        click_type(mp, '#utxFrom', '26/11/26')
        mp.keyboard.press('Tab')
        mp.wait_for_timeout(800)
        chk(mp.input_value('#utxFrom') == '2026-11-26', '폰 기간 필터 26/11/26 → 2026-11-26',
            mp.input_value('#utxFrom'))
        bad2 = layout_bad(mp)
        chk(not bad2, '폰에서 날짜 칸 넘침 없음', bad2[:4])

        print('== 8. 폰 목록 네 곳 기간 칸 — 잘림·가로 넘침 ==================')
        for nav, label in [('tx', '입출고내역'), ('buy-list', '매입'), ('sale-list', '매출'), ('audit', '변경이력')]:
            mp.evaluate("(n) => document.querySelector('#v8Side [data-nav=\"' + n + '\"]').click()", nav)
            mp.wait_for_timeout(1300)
            r = mp.evaluate("""() => {
              const bad = [];
              document.querySelectorAll('input[data-sd="1"]').forEach(el => {
                if (!el.offsetParent) return;
                if (!el.value) el.value = '2026-11-26';
                if (el.scrollWidth > el.clientWidth + 1) bad.push([el.id || el.className, el.clientWidth, el.scrollWidth]);
              });
              return { bad: bad, over: document.documentElement.scrollWidth - window.innerWidth, vw: window.innerWidth };
            }""")
            chk(not r['bad'] and r['over'] <= 0 and r['vw'] == 390,
                '폰 %s 기간 칸: 날짜 열 자가 잘리지 않고 가로 넘침도 없다' % label, r)
            mp.screenshot(path=os.path.join(OUT, '06-폰-%s-기간칸.png' % nav))
        real2 = [e for e in errors2 if 'favicon' not in e and 'Failed to load resource' not in e]
        res2 = [x for x in bad_res2 if 'favicon' not in x[1] and 'supabase.co' not in x[1]]
        print('     404:', res2[:5])
        chk(not res2, '폰 404 응답 0건(favicon 제외)', res2[:3])
        chk(not real2, '폰 콘솔 JS 오류 0건', real2[:3])
        mp.screenshot(path=os.path.join(OUT, '05-폰-기간필터-구분자.png'))
        b.close()
    print('\n결과:', '전체 통과' if ok else '실패 항목 있음')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
