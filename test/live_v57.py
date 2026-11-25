# -*- coding: utf-8 -*-
"""v57 실서버 확인 (읽기 전용 — 저장·수정 버튼은 누르지 않는다)

  LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/live_v57.py [URL] [OUT]

· 로트 드롭다운: 순백 배경·#D1D5DB 테두리·깊은 그림자, 폭이 팝업 카드 안쪽 폭과 같고 카드·화면 밖으로 안 나감
· 한 줄 네 열(품명·업체·소비기한·중량)의 x 좌표가 모든 행에서 같은지, 머리글과도 같은지
· 마우스 오버/↑↓ 하이라이트, 검색(품명·업체·소비기한), Enter 선택·단가 자동
· 4곳(해동/냉동 팝업 + 원료육 해동·재냉동·출고), PC 1920 · 폰 390, 가로 넘침 0 · JS 오류 0
· SB.db.apply 같은 저장 호출은 절대 하지 않는다.
"""
import json
import os
import sys

os.environ.setdefault('LD_LIBRARY_PATH', '/workspace/tool-results/chromelibs')
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'https://perreo69.github.io/123456/?v=20261125_66'
TOKEN = BASE.split('v=')[1].split('&')[0] if 'v=' in BASE else ''
OUT = sys.argv[2] if len(sys.argv) > 2 else '/workspace/downloads/erp-v57-live'
os.makedirs(OUT, exist_ok=True)

errors, fails = [], []


def chk(cond, label, extra=''):
    print(('  [OK]   ' if cond else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not cond:
        fails.append(label)


POP = r"""(pid) => {
  pid = pid || 'uniMoveLotPop';
  const p = document.getElementById(pid);
  if (!p) return {missing: true};
  const card = document.querySelector(pid === 'uniMoveLotPop' ? '#uniMoveModal .modal-card' : '#meatFormModal .modal-card');
  const rows = Array.from(p.querySelectorAll('.lcitem'));
  const cs = getComputedStyle(p);
  const col = (r, c) => { const e = r.querySelector(c); return e ? Math.round(e.getBoundingClientRect().left) : null; };
  const head = p.querySelector('.lccols');
  const one = rows[0];
  return {
    hidden: p.classList.contains('hidden'), n: rows.length,
    bg: cs.backgroundColor, border: cs.borderColor, shadow: cs.boxShadow,
    rect: (r => [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)])(p.getBoundingClientRect()),
    card: card ? (r => [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)])(card.getBoundingClientRect()) : null,
    headText: head ? head.textContent : '',
    heads: head ? Array.from(head.children).map(e => Math.round(e.getBoundingClientRect().left)) : [],
    cols: rows.map(r => [col(r, '.lcn'), col(r, '.lcv'), col(r, '.lce'), col(r, '.lcw')]),
    rowH: rows.map(r => Math.round(r.getBoundingClientRect().height)),
    first: one ? one.textContent : '',
    clipped: p.scrollWidth - p.clientWidth,
    vw: innerWidth, vh: innerHeight
  };
}"""


def align_bad(pop):
    bad = 0
    for c in range(4):
        xs = [row[c] for row in pop['cols'] if row[c] is not None]
        if len(xs) > 1 and (max(xs) - min(xs)) > 1:
            bad += 1
    return bad


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
    # 스텁이 아닌 실서버라 로트 목록이 늦게 올 수 있다 — 목록이 찰 때까지 기다린다
    for _ in range(20):
        n = page.evaluate("() => (window.st && st.lots) ? st.lots.length : 0")
        if n > 0:
            break
        page.wait_for_timeout(1000)
    print('   로트 %d건 로드' % page.evaluate("() => (window.st && st.lots) ? st.lots.length : 0"))

    src = page.evaluate("() => (document.querySelector('script[src*=\"app.js\"]') || {}).src || ''")
    chk(TOKEN and TOKEN in src, '실서버 app.js 토큰 ' + TOKEN, src)
    chk(TOKEN and TOKEN in page.evaluate("() => (document.querySelector('link[href*=\"style.css\"]') || {}).href || ''"),
        '실서버 style.css 토큰 ' + TOKEN)

    opened = open_move(page)
    chk(opened, '해동/냉동 팝업 열림')
    if opened:
        page.click('#uniMoveLotQ')
        page.wait_for_timeout(600)
        for _ in range(10):
            if page.evaluate("() => document.querySelectorAll('#uniMoveLotPop .lcitem').length") > 0:
                break
            page.wait_for_timeout(700)
            page.click('#uniMoveLotQ')
            page.wait_for_timeout(300)
        pop = page.evaluate(POP)
        print('   PC 목록', json.dumps({k: pop[k] for k in ('n', 'bg', 'border', 'rect', 'card', 'rowH', 'clipped')}, ensure_ascii=False))
        chk(not pop.get('hidden') and pop['n'] > 10, '클릭만 해도 보관 로트 전체', pop.get('n'))
        chk(pop['bg'] == 'rgb(255, 255, 255)', '순백 #FFFFFF', pop['bg'])
        chk('209, 213, 219' in pop['border'], '테두리 #D1D5DB', pop['border'])
        chk('0.16' in pop['shadow'], '그림자 rgba(0,0,0,.16)', pop['shadow'])
        cw = pop['card'][2]
        chk(pop['rect'][2] >= cw - 46 and pop['rect'][2] <= cw + 2, '폭 ≈ 모달 폭', (pop['rect'][2], cw))
        chk(pop['rect'][0] >= pop['card'][0] and pop['rect'][0] + pop['rect'][2] <= pop['card'][0] + pop['card'][2] + 1,
            '카드 좌우 안', (pop['rect'], pop['card']))
        chk(pop['rect'][1] + pop['rect'][3] <= pop['card'][1] + pop['card'][3] + 1, '카드 아래 안',
            (pop['rect'][1] + pop['rect'][3], pop['card'][1] + pop['card'][3]))
        chk(pop['rect'][1] + pop['rect'][3] <= pop['vh'], '화면 아래 안', pop['vh'])
        chk(all(w in pop['headText'] for w in ('품명', '업체', '소비기한', '중량')), '머리글 네 열', pop['headText'])
        chk(align_bad(pop) == 0, '모든 행 열 x 일치', pop['cols'][:3])
        chk(pop['heads'] and all(abs(pop['heads'][i] - pop['cols'][0][i]) <= 1 for i in range(4)), '머리글-행 열 일치',
            (pop['heads'], pop['cols'][0]))
        chk(all(34 <= h <= 41 for h in pop['rowH']), '행 높이 34~41px', pop['rowH'][:5])
        chk('돈육' not in pop['first'] and '소비기한 ' not in pop['first'], '한 줄에 육류·꼬리표 없음', pop['first'])
        chk(pop['clipped'] <= 0, '가로 넘침 0', pop['clipped'])
        page.screenshot(path=os.path.join(OUT, '01-pc-open.png'))
        page.screenshot(path=os.path.join(OUT, '01b-pc-pop.png'),
                        clip=page.evaluate("""() => { const r = document.getElementById('uniMoveLotPop').getBoundingClientRect();
                          return {x: Math.max(0, r.left - 6), y: Math.max(0, r.top - 40), width: Math.min(r.width + 12, innerWidth - 2),
                                  height: Math.min(r.height + 46, innerHeight - 2)}; }"""))

        page.hover('#uniMoveLotPop .lcitem[data-lci="1"]')
        page.wait_for_timeout(250)
        hv = page.evaluate("""() => { const r = document.querySelector('#uniMoveLotPop .lcitem:hover');
          if (!r) return null; const s = getComputedStyle(r);
          return {bg: s.backgroundColor, name: getComputedStyle(r.querySelector('.lcn')).color}; }""")
        chk(hv and hv['bg'] == 'rgb(239, 246, 255)' and hv['name'] == 'rgb(29, 78, 216)', '오버 #EFF6FF·#1D4ED8', hv)
        page.screenshot(path=os.path.join(OUT, '02-pc-hover.png'),
                        clip=page.evaluate("""() => { const r = document.getElementById('uniMoveLotPop').getBoundingClientRect();
                          return {x: Math.max(0, r.left - 6), y: Math.max(0, r.top - 40), width: Math.min(r.width + 12, innerWidth - 2),
                                  height: Math.min(r.height + 46, innerHeight - 2)}; }"""))

        page.click('#uniMoveLotQ')
        page.press('#uniMoveLotQ', 'ArrowDown')
        page.press('#uniMoveLotQ', 'ArrowDown')
        page.wait_for_timeout(250)
        kb = page.evaluate("""() => { const r = document.querySelector('#uniMoveLotPop .lcitem.on');
          if (!r) return null; return {bg: getComputedStyle(r).backgroundColor, name: getComputedStyle(r.querySelector('.lcn')).color}; }""")
        chk(kb and kb['bg'] == 'rgb(239, 246, 255)' and kb['name'] == 'rgb(29, 78, 216)', '↑↓ 하이라이트', kb)

        page.fill('#uniMoveLotQ', '목전')
        page.wait_for_timeout(450)
        p2 = page.evaluate(POP)
        print('   목전', p2['n'], p2['cols'][:2])
        chk(0 < p2['n'] <= 6, "‘목전’ 검색", p2['n'])
        page.screenshot(path=os.path.join(OUT, '03-pc-search.png'))
        page.press('#uniMoveLotQ', 'Enter')
        page.wait_for_timeout(600)
        st = page.evaluate("""() => ({lot: document.getElementById('uniMoveLot').value,
          input: document.getElementById('uniMoveLotQ').value, price: document.getElementById('uniMovePrice').value})""")
        chk(st['lot'] != '' and '목전' in st['input'] and st['price'] not in ('', '0'), 'Enter 선택·단가 채움', st)

        page.fill('#uniMoveLotQ', '에스디')
        page.wait_for_timeout(400)
        p3 = page.evaluate(POP)
        chk(0 < p3['n'] < p2['n'] + 40, "‘에스디’(업체) 검색", p3['n'])
        page.fill('#uniMoveLotQ', '2028-09')
        page.wait_for_timeout(400)
        c1, c2 = p3['n'], page.evaluate(POP)['n']
        chk(c2 <= c1, "‘2028-09’(소비기한) 검색", (c1, c2))
        page.press('#uniMoveLotQ', 'Escape')
        page.wait_for_timeout(200)

        page.evaluate("() => document.querySelector('#uniMoveSeg [data-mv=\"re\"]').click()")
        page.wait_for_timeout(500)
        page.click('#uniMoveLotQ')
        page.wait_for_timeout(450)
        pr = page.evaluate(POP)
        chk('냉장고' in page.evaluate("() => document.querySelector('#uniMoveLotPop .lchsum').textContent"),
            '재냉동 전환 시 냉장고 목록', page.evaluate("() => document.querySelector('#uniMoveLotPop .lchsum').textContent"))
        page.screenshot(path=os.path.join(OUT, '04-pc-re.png'))
        page.keyboard.press('Escape')
        page.wait_for_timeout(200)
        page.evaluate("() => { const b = document.getElementById('uniMoveClose'); if (b) b.click(); }")
        page.wait_for_timeout(300)

    # 원료육 입력 팝업 — 출고/해동/재냉동 로트 칸
    page.evaluate("() => { const h = document.getElementById('ioHubModal'); if (h) h.classList.remove('hidden'); }")
    page.wait_for_timeout(300)
    page.evaluate("() => { const b = document.querySelector('#ioHubModal [data-io=\"out\"]'); if (b) b.click(); }")
    page.wait_for_timeout(1500)
    if page.evaluate("() => !document.getElementById('meatFormModal').classList.contains('hidden')"):
        for mode, pid, qid in [('out', 'outLotPop', 'outLotQ'), ('thaw', 'thLotPop', 'thLotQ'), ('re', 'reLotPop', 'reLotQ')]:
            page.evaluate("(m) => document.querySelector('#meatFormModal .formmodes [data-mode=\"' + m + '\"]').click()", mode)
            page.wait_for_timeout(600)
            page.click('#' + qid)
            page.wait_for_timeout(450)
            px = page.evaluate(POP, pid)
            print('   %s' % mode, json.dumps({k: px[k] for k in ('n', 'bg', 'rect', 'card', 'headText')}, ensure_ascii=False)[:180])
            chk(not px.get('hidden') and px['bg'] == 'rgb(255, 255, 255)' and '품명' in px['headText'] and align_bad(px) == 0,
                '%s 로트 칸도 순백 한 줄 표' % mode, (px.get('n'), px['headText']))
            chk(px['card'] and px['rect'][0] >= px['card'][0]
                and px['rect'][0] + px['rect'][2] <= px['card'][0] + px['card'][2] + 1
                and px['rect'][1] + px['rect'][3] <= px['card'][1] + px['card'][3] + 1,
                '%s 목록이 카드 안' % mode, (px['rect'], px['card']))
            page.screenshot(path=os.path.join(OUT, '05-pc-%s.png' % mode))
            page.press('#' + qid, 'Tab')
            page.wait_for_timeout(250)
        page.evaluate("() => document.querySelectorAll('.modal').forEach(m => m.classList.add('hidden'))")
        page.wait_for_timeout(300)
    else:
        chk(False, '원료육 입력 팝업 열림')

    over = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    chk(over == 0, 'PC 가로 넘침 0px', over)

    page.set_viewport_size({'width': 390, 'height': 844})
    page.evaluate("() => window.dispatchEvent(new Event('resize'))")
    page.wait_for_timeout(600)
    if not open_move(page):
        chk(False, '폰에서 해동/냉동 팝업 열림')
    else:
        page.click('#uniMoveLotQ')
        page.wait_for_timeout(500)
        pm = page.evaluate(POP)
        print('   폰 목록', json.dumps({k: pm[k] for k in ('n', 'rect', 'card', 'rowH', 'clipped')}, ensure_ascii=False))
        chk(pm['rect'][0] >= 0 and pm['rect'][0] + pm['rect'][2] <= 391, '폰 목록이 화면 안', pm['rect'])
        chk(pm['rect'][2] >= 300, '폰 목록 폭 300+', pm['rect'][2])
        chk(pm['rect'][1] + pm['rect'][3] <= 845, '폰 목록 아래 안 잘림', pm['rect'])
        chk(align_bad(pm) == 0, '폰에서도 열 정렬', pm['cols'][:2])
        chk(pm['clipped'] <= 0, '폰 가로 넘침 0', pm['clipped'])
        over = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
        chk(over == 0, '폰 화면 가로 넘침 0px', over)
        page.screenshot(path=os.path.join(OUT, '06-phone.png'))
        page.screenshot(path=os.path.join(OUT, '06b-phone-pop.png'),
                        clip=page.evaluate("""() => { const r = document.getElementById('uniMoveLotPop').getBoundingClientRect();
                          return {x: Math.max(0, r.left - 4), y: Math.max(0, r.top - 60), width: Math.min(r.width + 8, innerWidth - 2),
                                  height: Math.min(r.height + 70, innerHeight - 2)}; }"""))

    print('\nJS 오류 %d건 · 실패 %d건' % (len(errors), len(fails)))
    for e in errors[:5]:
        print('  JS', e)
    for f in fails:
        print('  FAIL', f)
    with open(os.path.join(OUT, 'result.json'), 'w', encoding='utf-8') as fh:
        json.dump({'errors': errors, 'fails': fails}, fh, ensure_ascii=False, indent=1)
    b.close()
