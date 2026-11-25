# -*- coding: utf-8 -*-
"""v55 실서버 확인 (읽기 전용 — 저장·수정 버튼은 누르지 않는다)

  LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/live_v55.py [URL] [OUT]
"""
import json
import os
import sys

os.environ.setdefault('LD_LIBRARY_PATH', '/workspace/tool-results/chromelibs')
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'https://perreo69.github.io/123456/?v=20261125_63'
OUT = sys.argv[2] if len(sys.argv) > 2 else '/workspace/downloads/erp-v55-live'
os.makedirs(OUT, exist_ok=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
AUDIT = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'v55_audit.py'), encoding='utf-8').read()
AUDIT = AUDIT[AUDIT.index('AUDIT = r"""') + len('AUDIT = r"""'):AUDIT.index('}"""\n\n\ndef run_audit') + 1]

errors, fails, bad_all = [], [], []


def chk(cond, label, extra=''):
    print(('  [OK]   ' if cond else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not cond:
        fails.append(label)


def audit(page, tag, root=None):
    data = page.evaluate(AUDIT, root)
    bad = [d for d in data if d['issues']]
    bad_all.extend([(tag, d) for d in bad])
    print('   audit %-22s 입력칸 %2d · 문제 %d' % (tag, len(data), len(bad)))
    for d in bad:
        print('      [X]', d['el'], d['id'], d['ph'], ';'.join(d['issues']))
    page.screenshot(path=os.path.join(OUT, tag + '.png'))
    return bad


def nav(page, key, wait=1600):
    page.evaluate("(k) => { const b = document.querySelector('#v8Side [data-nav=\"' + k + '\"]'); if (b) b.click(); }", key)
    page.wait_for_timeout(wait)


with sync_playwright() as pw:
    b = pw.chromium.launch(env=dict(os.environ))
    page = b.new_page(viewport={'width': 1920, 'height': 1080})
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('dialog', lambda d: d.dismiss())
    page.goto(BASE)
    page.wait_for_timeout(1200)
    page.fill('#liEmail', 'perreo@nate.com')
    page.fill('#liPw', '123456')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=45000)
    page.wait_for_timeout(6000)

    src = page.evaluate("() => (document.querySelector('script[src*=\"app.js\"]') || {}).src || ''")
    chk('20261125_63' in src, '실서버 app.js 토큰 _63', src)
    chk(page.evaluate("() => (document.querySelector('link[href*=\"design-system\"]') || {}).href || ''").find('20261125_138') > 0,
        'design-system.css 토큰 _138')

    # 검색창(통합 재고) 포커스
    nav(page, 'stock:all', 2200)
    page.focus('#uniSearch')
    page.wait_for_timeout(400)
    audit(page, '01-uni-search-focus')
    chk(page.evaluate("""() => { const i = document.getElementById('uniSearch'); const c = getComputedStyle(i);
        return c.boxShadow === 'none' && parseFloat(c.borderTopWidth) === 0; }"""), '검색창 안쪽 input 그림자·테두리 없음')
    chk(page.evaluate("""() => { const w = document.querySelector('.usearch'); const c = getComputedStyle(w);
        return c.boxShadow !== 'none'; }"""), '바깥 상자에만 포커스 링')
    page.screenshot(path=os.path.join(OUT, '01b-search-closeup.png'),
                    clip={'x': 282, 'y': 118, 'width': 320, 'height': 44})

    # 입출고 내역 · 변경이력 · 품목관리 검색칸
    for key, tag, sel in [('tx', '02-tx', '#utxSearch'), ('audit', '03-audit', '#auditSearch'), ('items', '04-items', '#itemsSearch')]:
        nav(page, key, 2000)
        page.focus(sel)
        page.wait_for_timeout(350)
        audit(page, tag + '-focus')
        chk(page.evaluate("(s) => getComputedStyle(document.querySelector(s)).boxShadow === 'none'", sel), tag + ' 안쪽 그림자 없음')

    # 입고 전표 팝업
    nav(page, 'in', 2200)
    audit(page, '05-pop-sheet-in')
    chk(page.evaluate("""() => { const tds = Array.from(document.querySelectorAll('#ioSheetBody tr')).map(tr =>
          Array.from(tr.children).map(td => Math.round(td.getBoundingClientRect().height)));
        return tds.every(r => Math.max(...r) - Math.min(...r) <= 1); }"""), '입고 표 — 한 줄 안 모든 칸 높이 같음')
    page.evaluate("() => document.querySelectorAll('#ioSheetModal .modal-x').forEach(b => b.click())")
    page.wait_for_timeout(500)

    # 출고 전표
    nav(page, 'out', 2000)
    audit(page, '06-pop-sheet-out')
    page.evaluate("() => document.querySelectorAll('#ioSheetModal .modal-x').forEach(b => b.click())")
    page.wait_for_timeout(500)

    # 로트 수정 팝업
    nav(page, 'stock:all', 2000)
    page.evaluate("() => { const t = document.querySelector('#uniTableWrap tbody tr.ulot .actmenu'); if (t) t.click(); }")
    page.wait_for_timeout(500)
    page.evaluate("() => { const b = Array.from(document.querySelectorAll('#rowMenu button')).find(x => x.textContent.trim() === '수정'); if (b) b.click(); }")
    page.wait_for_timeout(1000)
    if page.evaluate("() => !document.getElementById('lotModal').classList.contains('hidden')"):
        audit(page, '07-pop-lot')
        page.keyboard.press('Escape')
        page.wait_for_timeout(400)
    else:
        chk(False, '로트 수정 팝업이 열리지 않음')

    # 회계(거래처 원장) · 일반 경비 팝업
    nav(page, 'ledger', 2200)
    audit(page, '08-ledger')
    page.evaluate("() => { const b = document.getElementById('btnAccExpense'); if (b) b.click(); }")
    page.wait_for_timeout(900)
    if page.evaluate("() => !document.getElementById('accExpModal').classList.contains('hidden')"):
        audit(page, '09-pop-acc-exp')
        page.keyboard.press('Escape')
        page.wait_for_timeout(400)

    # 가로 넘침 (화면별)
    over = {}
    for key, tag in [('stock:all', 'uni'), ('tx', 'tx'), ('audit', 'audit'), ('items', 'items'),
                     ('stock:meat', 'meat'), ('stock:fg', 'fg'), ('buy-list', 'buy'), ('sale-list', 'sale'),
                     ('ledger', 'ledger'), ('expense', 'expense')]:
        nav(page, key, 1500)
        over[tag] = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    chk(all(v == 0 for v in over.values()), '가로 넘침 0px (10개 화면)', over)

    print('\nJS 오류 %d건 · 입력칸 문제 %d건 · 실패 %d건' % (len(errors), len(bad_all), len(fails)))
    for e in errors[:5]:
        print('  JS', e)
    with open(os.path.join(OUT, 'result.json'), 'w', encoding='utf-8') as f:
        json.dump({'errors': errors, 'fails': fails, 'bad': [(t, d['id'], d['issues']) for t, d in bad_all],
                   'overflow': over}, f, ensure_ascii=False, indent=1)
    b.close()
