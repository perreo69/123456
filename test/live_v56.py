# -*- coding: utf-8 -*-
"""v56 실서버 확인 (읽기 전용 — 저장·수정 버튼은 누르지 않는다)

  LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/live_v56.py [URL] [OUT]

· 해동/냉동 팝업의 탭 글자 잘림 0px · 로트 검색 콤보박스(클릭=전체, 검색=걸러짐, Enter=선택, 단가 자동)
· 가로 넘침 0px · JS 오류 0건. 저장(SB.db.apply)은 절대 호출하지 않는다.
"""
import json
import os
import sys

os.environ.setdefault('LD_LIBRARY_PATH', '/workspace/tool-results/chromelibs')
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'https://perreo69.github.io/123456/?v=20261125_64'
OUT = sys.argv[2] if len(sys.argv) > 2 else '/workspace/downloads/erp-v56-live'
os.makedirs(OUT, exist_ok=True)

errors, fails = [], []


def chk(cond, label, extra=''):
    print(('  [OK]   ' if cond else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not cond:
        fails.append(label)


TABS = r"""() => {
  const seg = document.getElementById('uniMoveSeg');
  if (!seg) return null;
  const out = {card: null, grid: getComputedStyle(seg).gridTemplateColumns, btns: []};
  const r0 = document.querySelector('#uniMoveModal .modal-card').getBoundingClientRect();
  out.card = Math.round(r0.width);
  seg.querySelectorAll('button').forEach(b => {
    const r = b.getBoundingClientRect();
    out.btns.push({text: b.textContent.trim(), w: Math.round(r.width), h: Math.round(r.height),
                   cut: b.scrollWidth - b.clientWidth});
  });
  return out;
}"""

POP = r"""() => {
  const p = document.getElementById('uniMoveLotPop');
  if (!p) return {missing: true};
  const rows = Array.from(p.querySelectorAll('.lcitem'));
  const pr = p.getBoundingClientRect();
  return {hidden: p.classList.contains('hidden'), n: rows.length,
          head: (p.querySelector('.lchead') || {}).textContent || '',
          first: rows[0] ? rows[0].textContent.slice(0, 60) : '',
          rect: [Math.round(pr.left), Math.round(pr.top), Math.round(pr.width), Math.round(pr.height)]};
}"""

STATE = r"""() => ({
  lot: document.getElementById('uniMoveLot').value,
  input: document.getElementById('uniMoveLotQ').value,
  price: document.getElementById('uniMovePrice').value,
  stat: document.getElementById('uniMoveStat').textContent.slice(0, 90)
})"""


def open_move(page):
    page.evaluate("() => { const b = document.querySelector('#v8Side [data-nav=\"move\"]'); if (b) b.click(); }")
    page.wait_for_timeout(1800)
    return page.evaluate("() => !document.getElementById('uniMoveModal').classList.contains('hidden')")


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
    chk('20261125_64' in src, '실서버 app.js 토큰 _64', src)
    chk('20261125_64' in page.evaluate("() => (document.querySelector('link[href*=\"style.css\"]') || {}).href || ''"),
        '실서버 style.css 토큰 _64')

    opened = open_move(page)
    chk(opened, '해동/냉동 팝업 열림')
    if opened:
        t = page.evaluate(TABS)
        print('   탭', json.dumps(t, ensure_ascii=False))
        chk(all(x['cut'] == 0 for x in t['btns']), 'PC 탭 글자 잘림 0px', [(x['text'], x['cut']) for x in t['btns']])
        chk(t['btns'][0]['w'] > 150, '탭이 반씩 폭을 나눔', t['grid'])

        page.click('#uniMoveLotQ')
        page.wait_for_timeout(500)
        p = page.evaluate(POP)
        print('   목록', json.dumps(p, ensure_ascii=False)[:260])
        chk(not p.get('hidden') and p.get('n', 0) > 10, '클릭만 해도 보관 로트 전체가 뜸', p.get('n'))
        chk('보관 중' in (p.get('head') or ''), '머리줄에 보관 개수', p.get('head'))
        page.screenshot(path=os.path.join(OUT, '01-pop-open.png'))
        page.screenshot(path=os.path.join(OUT, '01b-pop-modal.png'),
                        clip=page.evaluate("""() => { const r = document.querySelector('#uniMoveModal .modal-card').getBoundingClientRect();
                          return {x: Math.max(0, r.left - 10), y: Math.max(0, r.top - 10), width: Math.min(r.width + 20, innerWidth - 2), height: Math.min(r.height + 20, innerHeight - 2)}; }"""))

        page.fill('#uniMoveLotQ', '알전')
        page.wait_for_timeout(500)
        p = page.evaluate(POP)
        print('   알전', json.dumps(p, ensure_ascii=False)[:260])
        chk(0 < p.get('n', 0) <= 4, '‘알전’ 검색으로 걸러짐', p.get('n'))
        page.screenshot(path=os.path.join(OUT, '02-filter.png'))

        page.press('#uniMoveLotQ', 'Enter')
        page.wait_for_timeout(600)
        st = page.evaluate(STATE)
        print('   선택', json.dumps(st, ensure_ascii=False))
        chk(st['lot'] != '' and st['input'].startswith('알전'), 'Enter 로 로트 선택', st['input'])
        chk(st['price'] not in ('', '0'), '단가 자동 채움', st['price'])
        chk('현재고' in st['stat'], '현재고·이동 방향 안내', st['stat'])
        page.screenshot(path=os.path.join(OUT, '03-picked.png'))

        page.evaluate("() => document.querySelector('#uniMoveSeg [data-mv=\"re\"]').click()")
        page.wait_for_timeout(500)
        page.click('#uniMoveLotQ')
        page.wait_for_timeout(500)
        p = page.evaluate(POP)
        chk('냉장고' in (p.get('head') or ''), '재냉동 전환 시 냉장고 목록으로 갱신', p.get('head'))
        page.screenshot(path=os.path.join(OUT, '04-re.png'))
        page.keyboard.press('Escape')
        page.wait_for_timeout(200)
        page.evaluate("() => { const b = document.getElementById('uniMoveClose'); if (b) b.click(); }")
        page.wait_for_timeout(300)

    over = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    chk(over == 0, 'PC 가로 넘침 0px', over)

    # 폰 390
    page.set_viewport_size({'width': 390, 'height': 844})
    page.evaluate("() => window.dispatchEvent(new Event('resize'))")
    page.wait_for_timeout(600)
    if not open_move(page):
        chk(False, '폰에서 해동/냉동 팝업 열림')
    else:
        t = page.evaluate(TABS)
        print('   폰 탭', json.dumps(t, ensure_ascii=False))
        chk(all(x['cut'] == 0 for x in t['btns']), '폰(390) 탭 글자 잘림 0px', [(x['text'], x['cut']) for x in t['btns']])
        over = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
        chk(over == 0, '폰 가로 넘침 0px', over)
        page.click('#uniMoveLotQ')
        page.wait_for_timeout(500)
        p = page.evaluate(POP)
        print('   폰 목록', json.dumps(p, ensure_ascii=False)[:220])
        chk(not p.get('hidden') and p.get('n', 0) > 0, '폰에서도 전체 목록', p.get('n'))
        chk(p['rect'][0] >= 0 and p['rect'][0] + p['rect'][2] <= 391, '목록이 화면 안', p['rect'])
        page.screenshot(path=os.path.join(OUT, '05-phone.png'))

    print('\nJS 오류 %d건 · 실패 %d건' % (len(errors), len(fails)))
    for e in errors[:5]:
        print('  JS', e)
    with open(os.path.join(OUT, 'result.json'), 'w', encoding='utf-8') as f:
        json.dump({'errors': errors, 'fails': fails}, f, ensure_ascii=False, indent=1)
    b.close()
