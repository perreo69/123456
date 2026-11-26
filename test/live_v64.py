# -*- coding: utf-8 -*-
"""v64 실서버 확인 (읽기 전용 — 저장·수정·삭제 버튼은 절대 누르지 않는다)

  LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/live_v64.py [URL] [OUT]

· 새 토큰 ?v=20261126_74 이 style.css · mobile.css · app.js 에 실제로 걸렸는지
· PC 1920: 형식 매트릭스(26/11/26 · 2026/11/26 · 26-6-5 …) · 입고일/소비기한 칸에 직접 타이핑 ·
  기간 칸(입출고내역) 26/11/26 → 2026-11-26 · 가로 넘침 0 · JS 오류 0
· 폰 390: inputmode=text · 입고일 2026/11/26 · 소비기한 26/6/5 · 날짜 잘림 0 · JS 오류 0
· 저장은 하지 않는다 (입고 팝업은 열었다가 «취소»로 닫기만 한다)
"""
import json
import os
import sys

os.environ.setdefault('LD_LIBRARY_PATH', '/workspace/tool-results/chromelibs')
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'https://perreo69.github.io/123456/?v=20261126_74'
TOKEN = BASE.split('v=')[1].split('&')[0] if 'v=' in BASE else ''
OUT = sys.argv[2] if len(sys.argv) > 2 else '/workspace/downloads/erp-v64-실서버'
os.makedirs(OUT, exist_ok=True)
fails, errors = [], []


def chk(cond, label, extra=''):
    print(('  [OK]   ' if cond else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not cond:
        fails.append(label)


MATRIX = r"""async () => {
  const el = document.createElement('input');
  el.setAttribute('data-sd', '1');
  el.style.cssText = 'position:fixed;left:-9999px;top:0;width:120px';
  document.body.appendChild(el);
  await new Promise(r => setTimeout(r, 90));
  const cases = ['26/11/26', '2026/11/26', '26-11-26', '2026-11-26', '26/6/5', '2026/6/5',
                 '26.11.26', '2026.11.26', '1112', '281123', '261125', '26/13/40'];
  const out = {};
  for (const c of cases) {
    el.value = c; el.setAttribute('data-sd-prev', '');
    el.dispatchEvent(new Event('blur'));
    out[c] = el.value;
  }
  el.remove();
  return out;
}"""

WANT = {'26/11/26': '2026-11-26', '2026/11/26': '2026-11-26', '26-11-26': '2026-11-26',
        '2026-11-26': '2026-11-26', '26/6/5': '2026-06-05', '2026/6/5': '2026-06-05',
        '26.11.26': '2026-11-26', '2026.11.26': '2026-11-26', '1112': '2026-11-12',
        '281123': '2028-11-23', '261125': '2026-11-25', '26/13/40': ''}

OVER = "() => document.documentElement.scrollWidth - window.innerWidth"


def login(page):
    page.fill('#liEmail', 'perreo@nate.com')
    page.fill('#liPw', '123456')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=45000)
    page.wait_for_timeout(6000)
    for _ in range(20):
        if page.evaluate("() => (window.st && st.lots) ? st.lots.length : 0") > 0:
            break
        page.wait_for_timeout(500)


def type_into(page, sel, text):
    page.click(sel)
    page.wait_for_timeout(150)
    page.keyboard.type(text, delay=45)
    page.wait_for_timeout(150)
    st = page.evaluate("() => { const e = document.activeElement; return e ? e.value : null; }")
    return st


def main():
    libs = '/workspace/tool-results/chromelibs'
    env = dict(os.environ)
    with sync_playwright() as pw:
        b = pw.chromium.launch(env=env)
        # ---------------- PC ----------------
        page = b.new_page(viewport={'width': 1920, 'height': 1080})
        bad = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: errors.append('console:' + m.text) if m.type == 'error' else None)
        page.on('response', lambda r: bad.append((r.status, r.url)) if r.status >= 400 else None)
        page.goto(BASE)
        page.wait_for_timeout(600)
        login(page)
        page.add_style_tag(content='#toast{display:none !important}')

        print('== 1. 배포본 · 토큰 =========================================')
        src = page.evaluate("() => Array.from(document.querySelectorAll('script')).map(s => s.src).join(' ') + ' ' + Array.from(document.querySelectorAll('link')).map(l => l.href).join(' ')")
        chk(TOKEN in src and src.count(TOKEN) >= 4, '캐시 토큰 %s 가 css·app.js 모두에 걸렸다' % TOKEN, src.count(TOKEN))

        print('== 2. 날짜 칸 · 형식 매트릭스 ================================')
        stat = page.evaluate("""() => {
          const all = Array.from(document.querySelectorAll('input[data-sd="1"]'));
          return { n: all.length, dates: document.querySelectorAll('input[type="date"]').length };
        }""")
        chk(stat['n'] >= 36 and stat['dates'] == 0, '날짜 칸 %d개 모두 type=text' % stat['n'], stat)
        m = page.evaluate(MATRIX)
        for k, want in WANT.items():
            chk(m.get(k) == want, '%-12s → %-10s' % (k, want or '(되돌림)'), m.get(k))

        print('== 3. 입고 팝업 — 입고일 · 소비기한 (저장 안 함) ===============')
        page.click('#v8Side [data-nav="in"]')
        page.wait_for_timeout(1400)
        chk(page.is_visible('#ioSheetDate'), '입고 팝업이 열린다', '')
        v = type_into(page, '#ioSheetDate', '26/11/26')
        chk(v == '26/11/26', '입고일 칸에 26/11/26 이 그대로 쳐진다', v)
        page.keyboard.press('Tab')
        page.wait_for_timeout(300)
        chk(page.input_value('#ioSheetDate') == '2026-11-26', '입고일 26/11/26 → 2026-11-26', page.input_value('#ioSheetDate'))
        exp = '#ioSheetBody [data-r="0"] [data-f="expiry"]'
        v = type_into(page, exp, '26-6-5')
        page.keyboard.press('Enter')
        page.wait_for_timeout(300)
        chk(page.input_value(exp) == '2026-06-05', '소비기한 26-6-5 → 2026-06-05', page.input_value(exp))
        page.screenshot(path=os.path.join(OUT, '01-실서버-입고-구분자.png'))
        page.click('#ioSheetClose')
        page.wait_for_timeout(500)

        print('== 4. 기간 칸 (보기만 바뀜 — 저장 없음) ======================')
        page.click('#v8Side [data-nav="tx"]')
        page.wait_for_timeout(1400)
        type_into(page, '#utxFrom', '2026/11/26')
        page.keyboard.press('Enter')
        page.wait_for_timeout(900)
        chk(page.input_value('#utxFrom') == '2026-11-26', '입출고내역 시작일 2026/11/26 → 2026-11-26', page.input_value('#utxFrom'))
        type_into(page, '#utxTo', '26.12.25')
        page.keyboard.press('Tab')
        page.wait_for_timeout(900)
        chk(page.input_value('#utxTo') == '2026-12-25', '입출고내역 종료일 26.12.25 → 2026-12-25', page.input_value('#utxTo'))
        page.screenshot(path=os.path.join(OUT, '02-실서버-기간-구분자.png'))
        chk(page.evaluate(OVER) <= 0, 'PC 가로 넘침 0', page.evaluate(OVER))
        real = [e for e in errors if 'favicon' not in e and 'Failed to load resource' not in e]
        chk(not real, 'PC JS 오류 0건', real[:3])
        page.close()

        # ---------------- 폰 ----------------
        err2 = []
        mp = b.new_page(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=3)
        mp.on('pageerror', lambda e: err2.append(str(e)))
        mp.on('console', lambda m: err2.append('console:' + m.text) if m.type == 'error' else None)
        mp.goto(BASE)
        mp.wait_for_timeout(600)
        login(mp)
        mp.add_style_tag(content='#toast{display:none !important}')
        print('== 5. 폰 390 ================================================')
        ims = mp.evaluate("""() => {
          const all = Array.from(document.querySelectorAll('input[data-sd="1"]'));
          return { coarse: matchMedia('(pointer: coarse)').matches, n: all.length,
                   text: all.filter(e => e.getAttribute('inputmode') === 'text').length };
        }""")
        chk(ims['coarse'] and ims['n'] > 0 and ims['text'] == ims['n'], '폰 날짜 칸 전부 글자 자판(inputmode=text)', ims)
        mp.click('#mobTabs [data-mtab="in"]')
        mp.wait_for_timeout(1600)
        type_into(mp, '#ioSheetDate', '2026/11/26')
        mp.keyboard.press('Tab')
        mp.wait_for_timeout(300)
        chk(mp.input_value('#ioSheetDate') == '2026-11-26', '폰 입고일 2026/11/26 → 2026-11-26', mp.input_value('#ioSheetDate'))
        exp2 = '#ioSheetBody [data-r="0"] [data-f="expiry"]'
        type_into(mp, exp2, '26/6/5')
        mp.keyboard.press('Enter')
        mp.wait_for_timeout(300)
        chk(mp.input_value(exp2) == '2026-06-05', '폰 소비기한 26/6/5 → 2026-06-05', mp.input_value(exp2))
        mp.screenshot(path=os.path.join(OUT, '03-실서버-폰-입고.png'))
        mp.evaluate("() => { const x = document.getElementById('ioSheetClose'); if (x) x.click(); }")
        mp.wait_for_timeout(500)
        mp.click('#mobTabs [data-mtab="tx"]')
        mp.wait_for_timeout(1500)
        r = mp.evaluate("""() => {
          const bad = [];
          document.querySelectorAll('input[data-sd="1"]').forEach(el => {
            if (!el.offsetParent) return;
            if (!el.value) el.value = '2026-11-26';
            if (el.scrollWidth > el.clientWidth + 1) bad.push([el.id || el.className, el.clientWidth, el.scrollWidth]);
          });
          return { bad: bad, over: document.documentElement.scrollWidth - window.innerWidth, vw: window.innerWidth };
        }""")
        chk(not r['bad'] and r['over'] <= 0 and r['vw'] == 390, '폰 기간 칸 날짜 잘림 0 · 가로 넘침 0', r)
        mp.screenshot(path=os.path.join(OUT, '04-실서버-폰-기간.png'))
        real2 = [e for e in err2 if 'favicon' not in e and 'Failed to load resource' not in e]
        chk(not real2, '폰 JS 오류 0건', real2[:3])
        b.close()

    print('\n결과:', '전체 통과' if not fails else ('실패 %d건: %s' % (len(fails), fails[:5])))
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
