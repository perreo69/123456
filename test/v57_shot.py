# -*- coding: utf-8 -*-
"""v57 — 로트 드롭다운 순백·모달 폭·한 줄 표 정렬 (스텁 Supabase, 실제 DB 무접촉)

  LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/v57_shot.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('LD_LIBRARY_PATH', '/workspace/tool-results/chromelibs')
import shot_v54 as V
from playwright.sync_api import sync_playwright

OUT = '/workspace/downloads/erp-v57'
os.makedirs(OUT, exist_ok=True)
errors, fails = [], []


def chk(cond, label, extra=''):
    print(('  [OK]   ' if cond else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not cond:
        fails.append(label)


# 사람이 실제로 보는 이름·업체로 목록을 채운다(길어서 잘리는 이름 포함)
EXTRA = [
    ('돈잡육', '에스디푸드/SD', 'SD', '2028-09-20', 20.0, 8900),
    ('돈잡육', '침선우', '', '2028-11-05', 300.0, 9100),
    ('돈전지', '침선우', '', '2027-12-30', 28.4, 9400),
    ('돈지방', '에스디푸드/SD', 'SD', '2028-06-28', 29.99, 5200),
    ('돈지방', '케드인터내셔널', 'KED', '2028-08-22', 40.0, 5400),
    ('돈지방', '미트중전소스', 'PILGRIMS', '2027-10-11', 180.0, 5300),
    ('닭가슴살찜육', '청수푸드', '계육', '2028-10-23', 200.0, 7600),
    ('닭다리(미팅)', '대명', '미트', '2027-03-16', 15.0, 6900),
    ('닭발채', '미트중전소스', 'PILGRIMS', '2028-02-09', 12.5, 4300),
    ('닭장각', '미트중전소스', 'PILGRIMS', '2027-12-01', 544.4, 4100),
    ('닭안심', '대명', '', '2028-01-19', 6.0, 8200),
    ('목전지', '테드스토리', 'TEYS', '2027-08-01', 120.0, 8700),
    ('앞다리살', '한돈', '한돈', '2027-07-01', 88.25, 11200),
    ('우삼겹', '알전푸드', 'AURORA', '2028-04-18', 42.6, 15800),
    ('부채살', '알전푸드', 'AURORA', '2028-05-02', 31.2, 16400),
]
base = len(V.MOCK.lots)
for i, (nm, vd, br, ex, q, pr) in enumerate(EXTRA):
    V.MOCK.lots.append({
        'id': 100 + i, 'product_name': nm, 'meat_type': '돈육', 'origin': '국내',
        'vendor': vd, 'brand': br, 'in_date': '2026-11-0%d' % (i % 9 + 1),
        'exp_date': ex, 'frozen_qty': q, 'chilled_qty': 0.0, 'unit_price': pr,
        'major_category': '원료육', 'created_at': '2026-11-01T00:00:00Z',
        'updated_at': '2026-11-01T00:00:00Z'})
print('스텁 로트 %d개(기본 %d + %d)' % (len(V.MOCK.lots), base, len(EXTRA)))

POP = r"""(pid) => {
  const p = document.getElementById(pid || 'uniMoveLotPop');
  if (!p) return {missing: true};
  const card = document.querySelector(p.id === 'uniMoveLotPop'
    ? '#uniMoveModal .modal-card' : '#meatFormModal .modal-card');
  const rows = Array.from(p.querySelectorAll('.lcitem'));
  const cs = getComputedStyle(p);
  const rr = rows.map(r => r.getBoundingClientRect());
  const col = (r, cls) => { const e = r.querySelector(cls); return e ? Math.round(e.getBoundingClientRect().left) : null; };
  const head = p.querySelector('.lccols');
  const hl = head ? Array.from(head.children).map(e => Math.round(e.getBoundingClientRect().left)) : [];
  const one = rows[0];
  const cs1 = one ? getComputedStyle(one) : null;
  const span = (r, c) => { const e = r.querySelector(c); return e ? Math.round(e.getBoundingClientRect().width) : null; };
  return {
    hidden: p.classList.contains('hidden'), n: rows.length,
    bg: cs.backgroundColor, border: cs.borderColor, shadow: cs.boxShadow, radius: cs.borderRadius,
    rect: (r => [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)])(p.getBoundingClientRect()),
    card: card ? (r => [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)])(card.getBoundingClientRect()) : null,
    headText: head ? head.textContent : '', sum: (p.querySelector('.lchsum') || {}).textContent || '',
    heads: hl,
    cols: rows.map(r => [col(r, '.lcn'), col(r, '.lcv'), col(r, '.lce'), col(r, '.lcw')]),
    rowH: rr.map(r => Math.round(r.height)),
    rowBorder: cs1 ? cs1.borderBottomColor + ' ' + cs1.borderBottomWidth : '',
    rowBg: cs1 ? cs1.backgroundColor : '',
    nameColor: one ? getComputedStyle(one.querySelector('.lcn')).color : '',
    nameWeight: one ? getComputedStyle(one.querySelector('.lcn')).fontWeight : '',
    vColor: one ? getComputedStyle(one.querySelector('.lcv')).color : '',
    eColor: one ? getComputedStyle(one.querySelector('.lce')).color : '',
    eNum: one ? getComputedStyle(one.querySelector('.lce')).fontVariantNumeric : '',
    wColor: one ? getComputedStyle(one.querySelector('.lcw')).color : '',
    wAlign: one ? getComputedStyle(one.querySelector('.lcw')).textAlign : '',
    first: one ? one.textContent : '',
    clipped: p.scrollWidth - p.clientWidth,
    vw: innerWidth, vh: innerHeight
  };
}"""

HOVER = r"""() => {
  const p = document.getElementById('uniMoveLotPop');
  const r = p.querySelector('.lcitem:hover') || p.querySelectorAll('.lcitem')[1];
  const s = getComputedStyle(r);
  return {bg: s.backgroundColor, name: getComputedStyle(r.querySelector('.lcn')).color,
          w: getComputedStyle(r.querySelector('.lcw')).color};
}"""


def align_ok(pop):
    """세로 열이 모든 행에서 같은 x 에서 시작하는지"""
    cols = pop['cols']
    if len(cols) < 2:
        return True, cols
    bad = 0
    for c in range(4):
        xs = [row[c] for row in cols if row[c] is not None]
        if len(xs) > 1 and (max(xs) - min(xs)) > 1:
            bad += 1
    return bad == 0, cols[:4]


def run_pc(b):
    page = b.new_page(viewport={'width': 1920, 'height': 1080})
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('dialog', lambda d: d.dismiss())
    page.add_init_script(V.FAKE_WS)
    page.route('**/gzufnyglmzyqltepock.supabase.co/**', V.route_handler)
    page.route('**/gzufnyglmvgzqltepock.supabase.co/**', V.route_handler)
    V.login(page)

    page.evaluate("() => { const b = document.querySelector('#v8Side [data-nav=\"move\"]'); if (b) b.click(); }")
    page.wait_for_timeout(1600)
    chk(page.evaluate("() => !document.getElementById('uniMoveModal').classList.contains('hidden')"), '해동/냉동 팝업 열림')
    page.click('#uniMoveLotQ')
    page.wait_for_timeout(500)
    pop = page.evaluate(POP)
    print('   PC 목록', json.dumps({k: pop[k] for k in ('n', 'bg', 'border', 'rect', 'card', 'rowH', 'rowBorder', 'clipped')}, ensure_ascii=False))
    chk(not pop.get('hidden') and pop['n'] > 10, '클릭만 해도 전체 로트', pop.get('n'))
    chk(pop['bg'] == 'rgb(255, 255, 255)', '드롭다운 순백 #FFFFFF', pop['bg'])
    chk('209, 213, 219' in pop['border'], '테두리 #D1D5DB', pop['border'])
    chk('0.16' in pop['shadow'], '깊은 그림자 rgba(0,0,0,.16)', pop['shadow'])
    cw = pop['card'][2]
    chk(pop['rect'][2] >= cw - 46 and pop['rect'][2] <= cw + 2, '드롭다운 폭 ≈ 모달 폭', (pop['rect'][2], cw))
    chk(pop['rect'][0] >= pop['card'][0], '왼쪽이 모달 안', (pop['rect'][0], pop['card'][0]))
    chk(pop['rect'][0] + pop['rect'][2] <= pop['card'][0] + pop['card'][2] + 1, '오른쪽이 모달 밖으로 안 나감',
        (pop['rect'][0] + pop['rect'][2], pop['card'][0] + pop['card'][2]))
    chk(pop['rect'][1] + pop['rect'][3] <= pop['card'][1] + pop['card'][3] + 1, '아래가 모달 밖으로 안 나감',
        (pop['rect'][1] + pop['rect'][3], pop['card'][1] + pop['card'][3]))
    chk(pop['rect'][1] + pop['rect'][3] <= pop['vh'], '아래가 화면 안', pop['vh'])
    chk('품명' in pop['headText'] and '업체' in pop['headText'] and '소비기한' in pop['headText'] and '중량' in pop['headText'],
        '머리글 품명·업체·소비기한·중량', pop['headText'])
    ok, cols = align_ok(pop)
    chk(ok, '모든 행의 세로 열이 딱 맞음', cols)
    chk(pop['heads'] and all(abs(pop['heads'][i] - cols[0][i]) <= 1 for i in range(4)), '머리글과 행 열 위치 일치',
        (pop['heads'], cols[0]))
    chk(all(34 <= h <= 41 for h in pop['rowH']), '행 높이 34~41px', pop['rowH'][:6])
    chk('238, 242, 246' in pop['rowBorder'], '줄 구분선 #EEF2F6', pop['rowBorder'])
    chk(pop['nameColor'] == 'rgb(17, 24, 39)' and pop['nameWeight'] in ('600', '700'), '품명 진하게 #111827', pop['nameColor'] + ' ' + pop['nameWeight'])
    chk(pop['vColor'] == 'rgb(75, 85, 99)', '업체·브랜드 #4B5563', pop['vColor'])
    chk(pop['eColor'] == 'rgb(55, 65, 81)' and 'tabular' in pop['eNum'], '소비기한 #374151 tabular', pop['eColor'] + ' ' + pop['eNum'])
    chk(pop['wColor'] == 'rgb(15, 23, 42)' and pop['wAlign'] == 'right', '중량 우측 정렬·진하게', pop['wColor'] + ' ' + pop['wAlign'])
    chk('돈육' not in pop['first'] and '소비기한 ' not in pop['first'], '한 줄에 육류·"소비기한" 꼬리표 없음', pop['first'])
    chk(pop['clipped'] <= 0, '가로 넘침 0', pop['clipped'])
    page.screenshot(path=os.path.join(OUT, '01-pc-open.png'))
    page.screenshot(path=os.path.join(OUT, '01b-pc-pop.png'),
                    clip=page.evaluate("""() => { const r = document.getElementById('uniMoveLotPop').getBoundingClientRect();
                      return {x: Math.max(0, r.left - 6), y: Math.max(0, r.top - 40), width: Math.min(r.width + 12, innerWidth - 2),
                              height: Math.min(r.height + 46, innerHeight - 2)}; }"""))

    # 마우스 오버 · 키보드 선택 하이라이트
    page.hover('#uniMoveLotPop .lcitem[data-lci="1"]')
    page.wait_for_timeout(250)
    hv = page.evaluate(HOVER)
    chk(hv['bg'] == 'rgb(239, 246, 255)', '마우스 오버 #EFF6FF', hv['bg'])
    chk(hv['name'] == 'rgb(29, 78, 216)' and hv['w'] == 'rgb(29, 78, 216)', '오버 글자 #1D4ED8', hv['name'])
    page.screenshot(path=os.path.join(OUT, '02-pc-hover.png'),
                    clip=page.evaluate("""() => { const r = document.getElementById('uniMoveLotPop').getBoundingClientRect();
                      return {x: Math.max(0, r.left - 6), y: Math.max(0, r.top - 40), width: Math.min(r.width + 12, innerWidth - 2),
                              height: Math.min(r.height + 46, innerHeight - 2)}; }"""))
    page.click('#uniMoveLotQ')
    page.press('#uniMoveLotQ', 'ArrowDown')
    page.press('#uniMoveLotQ', 'ArrowDown')
    page.wait_for_timeout(250)
    kb = page.evaluate("""() => { const r = document.querySelector('#uniMoveLotPop .lcitem.on');
      if (!r) return null; const s = getComputedStyle(r);
      return {bg: s.backgroundColor, name: getComputedStyle(r.querySelector('.lcn')).color, txt: r.textContent.slice(0, 20)}; }""")
    chk(kb and kb['bg'] == 'rgb(239, 246, 255)' and kb['name'] == 'rgb(29, 78, 216)', '↑↓ 선택 #EFF6FF·#1D4ED8', kb)
    page.screenshot(path=os.path.join(OUT, '03-pc-key.png'))

    # 검색 — 품명·업체·브랜드·원산지·입고일·소비기한 모두 걸러지는지
    for q, lo, hi, label in [('목전', 1, 3, '품명'), ('침선우', 1, 4, '업체'), ('AURORA', 1, 3, '브랜드'),
                             ('국내', 1, 99, '원산지'), ('2028-09-20', 1, 2, '소비기한'), ('돈지방 SD', 1, 2, '낱말 두 개')]:
        page.fill('#uniMoveLotQ', q)
        page.wait_for_timeout(350)
        p2 = page.evaluate(POP)
        chk(lo <= p2['n'] <= hi, "‘%s’ 검색(%s) → %d개" % (q, label, p2['n']), p2['n'])
    page.screenshot(path=os.path.join(OUT, '04-pc-search.png'))
    page.fill('#uniMoveLotQ', '목전')
    page.wait_for_timeout(300)
    page.press('#uniMoveLotQ', 'Enter')
    page.wait_for_timeout(500)
    st = page.evaluate("""() => ({lot: document.getElementById('uniMoveLot').value,
      input: document.getElementById('uniMoveLotQ').value, price: document.getElementById('uniMovePrice').value})""")
    chk(st['lot'] != '' and '목전' in st['input'] and st['price'] not in ('', '0'), '검색 후 Enter 선택·단가 채움', st)
    chk(page.evaluate("() => document.getElementById('uniMoveLotPop').classList.contains('hidden')"), '고르면 목록 닫힘')

    # 입력칸 스타일 — 단일 테두리 + 포커스 링 하나
    page.evaluate("() => { if (document.activeElement && document.activeElement.blur) document.activeElement.blur(); }")
    page.wait_for_timeout(200)
    inp = page.evaluate("""() => { const e = document.getElementById('uniMoveLotQ'); const s = getComputedStyle(e);
      return {bg: s.backgroundColor, border: s.borderColor, shadow: s.boxShadow, outline: s.outlineStyle}; }""")
    chk(inp['bg'] == 'rgb(255, 255, 255)' and '209, 213, 219' in inp['border'], '로트 입력칸 흰 바탕·#D1D5DB 단일 테두리', inp)
    page.focus('#uniMoveLotQ')
    page.wait_for_timeout(200)
    inf = page.evaluate("""() => { const s = getComputedStyle(document.getElementById('uniMoveLotQ'));
      return {border: s.borderColor, shadow: s.boxShadow, outline: s.outlineStyle}; }""")
    chk('0, 122, 255' in inf['border'] and inf['shadow'].count('rgb') <= 1 and inf['outline'] == 'none',
        '포커스 = 파란 테두리 + 링 하나', inf)
    page.screenshot(path=os.path.join(OUT, '05-pc-input.png'),
                    clip=page.evaluate("""() => { const r = document.querySelector('#uniMoveModal .modal-card').getBoundingClientRect();
                      return {x: Math.max(0, r.left - 8), y: Math.max(0, r.top - 8), width: Math.min(r.width + 16, innerWidth - 2),
                              height: Math.min(r.height + 16, innerHeight - 2)}; }"""))
    page.keyboard.press('Escape')
    page.evaluate("() => { const b = document.getElementById('uniMoveClose'); if (b) b.click(); }")
    page.wait_for_timeout(300)

    # 원료육 입력 팝업(출고) 로트 칸 — 같은 모양인지
    page.evaluate("() => { const h = document.getElementById('ioHubModal'); if (h) h.classList.remove('hidden'); }")
    page.wait_for_timeout(300)
    page.evaluate("() => { const b = document.querySelector('#ioHubModal [data-io=\"out\"]'); if (b) b.click(); }")
    page.wait_for_timeout(1400)
    chk(page.evaluate("() => !document.getElementById('meatFormModal').classList.contains('hidden')"), '출고 팝업 열림')
    page.click('#outLotQ')
    page.wait_for_timeout(450)
    p3 = page.evaluate(POP, 'outLotPop' if False else 'outLotPop')
    print('   출고 목록', json.dumps({k: p3[k] for k in ('n', 'bg', 'rect', 'card')}, ensure_ascii=False))
    chk(not p3.get('hidden') and p3['n'] > 0, '출고 팝업 목록 뜸', p3.get('n'))
    ok3, cols3 = align_ok(p3)
    chk(ok3 and '품명' in p3['headText'], '출고 팝업도 한 줄 표·열 정렬', (p3['headText'], cols3[:2]))
    chk(p3['rect'][0] + p3['rect'][2] <= p3['card'][0] + p3['card'][2] + 1, '출고 팝업 목록도 카드 안',
        (p3['rect'][0] + p3['rect'][2], p3['card'][0] + p3['card'][2]))
    page.screenshot(path=os.path.join(OUT, '06-pc-out.png'))
    # 같은 팝업의 해동·재냉동 로트 칸도 같은 모양인지 (4곳 전부)
    for mode, pid, qid in [('thaw', 'thLotPop', 'thLotQ'), ('re', 'reLotPop', 'reLotQ')]:
        page.evaluate("(m) => document.querySelector('#meatFormModal .formmodes [data-mode=\"' + m + '\"]').click()", mode)
        page.wait_for_timeout(700)
        page.click('#' + qid)
        page.wait_for_timeout(400)
        px = page.evaluate(POP, pid)
        print('   %s 목록' % mode, json.dumps({k: px[k] for k in ('n', 'bg', 'rect', 'card', 'headText')}, ensure_ascii=False))
        okx, colsx = align_ok(px)
        chk(not px.get('hidden') and px['bg'] == 'rgb(255, 255, 255)' and '품명' in px['headText'] and okx,
            '%s 로트 칸도 순백 한 줄 표' % mode, (px.get('n'), px['headText']))
        chk(px['card'] and px['rect'][0] >= px['card'][0] and px['rect'][0] + px['rect'][2] <= px['card'][0] + px['card'][2] + 1
            and px['rect'][1] + px['rect'][3] <= px['card'][1] + px['card'][3] + 1,
            '%s 목록이 카드 안' % mode, (px['rect'], px['card']))
        page.screenshot(path=os.path.join(OUT, '08-pc-%s.png' % mode))
        page.press('#' + qid, 'Tab')
        page.wait_for_timeout(250)
    page.evaluate("() => document.querySelectorAll('.modal').forEach(m => m.classList.add('hidden'))")
    page.wait_for_timeout(300)

    # 해동/냉동 팝업 재냉동 탭 → 냉장고 목록·같은 표
    page.evaluate("() => { const b = document.querySelector('#v8Side [data-nav=\"move\"]'); if (b) b.click(); }")
    page.wait_for_timeout(1200)
    page.evaluate("() => document.querySelector('#uniMoveSeg [data-mv=\"re\"]').click()")
    page.wait_for_timeout(500)
    page.click('#uniMoveLotQ')
    page.wait_for_timeout(400)
    pr = page.evaluate(POP)
    chk('냉장고' in pr['sum'], '재냉동 탭 → 냉장고 목록', pr['sum'])
    page.screenshot(path=os.path.join(OUT, '09-pc-re.png'))
    page.keyboard.press('Escape')
    page.evaluate("() => { const b = document.getElementById('uniMoveClose'); if (b) b.click(); }")
    page.wait_for_timeout(300)

    over = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    chk(over == 0, 'PC 가로 넘침 0px', over)

    # 폰 390
    page.set_viewport_size({'width': 390, 'height': 844})
    page.evaluate("() => window.dispatchEvent(new Event('resize'))")
    page.wait_for_timeout(500)
    page.evaluate("() => { const b = document.querySelector('#v8Side [data-nav=\"move\"]'); if (b) b.click(); }")
    page.wait_for_timeout(1500)
    if page.evaluate("() => !document.getElementById('uniMoveModal').classList.contains('hidden')"):
        page.click('#uniMoveLotQ')
        page.wait_for_timeout(450)
        pm = page.evaluate(POP)
        print('   폰 목록', json.dumps({k: pm[k] for k in ('n', 'rect', 'card', 'rowH', 'clipped')}, ensure_ascii=False))
        chk(pm['rect'][0] >= 0 and pm['rect'][0] + pm['rect'][2] <= 391, '폰 목록이 화면 안', pm['rect'])
        chk(pm['rect'][2] >= 300, '폰 목록 폭 300+ (입력칸보다 넓게)', pm['rect'][2])
        chk(pm['rect'][1] + pm['rect'][3] <= 845, '폰 목록이 아래로 안 잘림', pm['rect'])
        okm, colsm = align_ok(pm)
        chk(okm, '폰에서도 열 정렬', colsm[:2])
        chk(pm['clipped'] <= 0, '폰 가로 넘침 0', pm['clipped'])
        over = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
        chk(over == 0, '폰 가로 넘침 0px', over)
        page.screenshot(path=os.path.join(OUT, '07-phone.png'))
        page.screenshot(path=os.path.join(OUT, '07b-phone-pop.png'),
                        clip=page.evaluate("""() => { const r = document.getElementById('uniMoveLotPop').getBoundingClientRect();
                          return {x: Math.max(0, r.left - 4), y: Math.max(0, r.top - 60), width: Math.min(r.width + 8, innerWidth - 2),
                                  height: Math.min(r.height + 70, innerHeight - 2)}; }"""))
    else:
        chk(False, '폰에서 해동/냉동 팝업 열림')
    page.close()


with sync_playwright() as pw:
    b = pw.chromium.launch(env=dict(os.environ))
    run_pc(b)
    print('\nJS 오류 %d건 · 실패 %d건' % (len(errors), len(fails)))
    for e in errors[:6]:
        print('  JS', e)
    for f in fails:
        print('  FAIL', f)
    with open(os.path.join(OUT, 'result.json'), 'w', encoding='utf-8') as fh:
        json.dump({'errors': errors, 'fails': fails}, fh, ensure_ascii=False, indent=1)
    b.close()
