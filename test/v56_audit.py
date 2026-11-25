# -*- coding: utf-8 -*-
"""v56 — 새 로트 입력칸·탭이 기존 입력칸 규칙(이중 테두리·상자 침범)을 깨지 않는지 점검 (로컬 스텁)

  LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/v56_audit.py

v55 의 입력칸 전수 점검(AUDIT)을 그대로 가져와, 바뀐 팝업(해동/냉동 · 원료육 입출고 · 보관 위치)만 다시 잰다.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault('LD_LIBRARY_PATH', '/workspace/tool-results/chromelibs')
import shot_v54 as V
from playwright.sync_api import sync_playwright

SRC = open(os.path.join(HERE, 'v55_audit.py'), encoding='utf-8').read()
AUDIT = SRC[SRC.index('AUDIT = r"""') + len('AUDIT = r"""'):SRC.index('}\"\"\"\n\n\ndef run_audit') + 1]

OUT = '/workspace/downloads/erp-v56'
os.makedirs(OUT, exist_ok=True)
fails, errors = [], []


def chk(cond, label, extra=''):
    print(('  [OK]   ' if cond else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not cond:
        fails.append(label)


def run(page, tag, root):
    data = page.evaluate(AUDIT, root)
    bad = [d for d in data if d['issues']]
    print('   %-12s 입력칸 %2d · 문제 %d' % (tag, len(data), len(bad)))
    for d in bad:
        print('      [X]', d['el'], d['id'], ';'.join(d['issues']))
    if bad:
        fails.append(tag + ' 입력칸')
    page.screenshot(path=os.path.join(OUT, 'a-' + tag + '.png'))
    return data


with sync_playwright() as pw:
    b = pw.chromium.launch(env=dict(os.environ))
    page = b.new_page(viewport={'width': 1920, 'height': 1080})
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.add_init_script(V.FAKE_WS)
    page.route('**/gzufnyglmvgzqltepock.supabase.co/**', V.route_handler)
    V.login(page)

    def nav(key, wait=1400):
        page.evaluate("(k) => { const b = document.querySelector('#v8Side [data-nav=\"' + k + '\"]'); if (b) b.click(); }", key)
        page.wait_for_timeout(wait)

    def closeall():
        page.keyboard.press('Escape')
        page.wait_for_timeout(200)
        page.evaluate("() => document.querySelectorAll('.modal').forEach(m => m.classList.add('hidden'))")
        page.wait_for_timeout(200)

    def combo_geom(cid, wrap_sel):
        return page.evaluate("""([cid, ws]) => {
          const i = document.getElementById(cid), w = i.closest(ws), c = getComputedStyle(i), wr = w.getBoundingClientRect(), r = i.getBoundingClientRect();
          return {fill: [+(r.left - wr.left).toFixed(1), +(wr.right - r.right).toFixed(1), +(r.top - wr.top).toFixed(1), +(wr.bottom - r.bottom).toFixed(1)],
                  border: c.borderTopWidth, shadow: c.boxShadow, h: Math.round(r.height), w: Math.round(r.width)};
        }""", [cid, wrap_sel])

    # 1) 해동/냉동 팝업
    nav('move')
    if page.evaluate("() => !document.getElementById('uniMoveModal').classList.contains('hidden')"):
        run(page, 'uni-move', '#uniMoveModal')
        g = combo_geom('uniMoveLotQ', '.lotcombo')
        print('   로트칸', g)
        chk(all(abs(v) <= 1.2 for v in g['fill']), '로트 입력칸이 자기 상자를 꽉 채움', g['fill'])
        chk(g['w'] > 200 and g['h'] >= 30, '로트 입력칸 크기', (g['w'], g['h']))
        page.click('#uniMoveLotQ')
        page.wait_for_timeout(300)
        page.screenshot(path=os.path.join(OUT, 'a-uni-move-open.png'))
    else:
        fails.append('해동 팝업 안 열림')
    closeall()

    # 2) 원료육 입력 팝업 (입고 / 출고)
    for io in ('in', 'out'):
        nav('stock:all', 1200)
        page.evaluate("() => { const h = document.getElementById('ioHubModal'); if (h) h.classList.remove('hidden'); }")
        page.wait_for_timeout(250)
        page.evaluate("(a) => { const b = document.querySelector('#ioHubModal [data-io=\"' + a + '\"]'); if (b) b.click(); }", io)
        page.wait_for_timeout(1300)
        if page.evaluate("() => !document.getElementById('meatFormModal').classList.contains('hidden')"):
            run(page, 'meat-' + io, '#meatFormModal')
            if io == 'out':
                g = combo_geom('outLotQ', '.lotcombo')
                print('   로트칸', g)
                chk(all(abs(v) <= 1.2 for v in g['fill']), '출고 로트 입력칸이 자기 상자를 꽉 채움', g['fill'])
                page.click('#outLotQ')
                page.wait_for_timeout(300)
                page.screenshot(path=os.path.join(OUT, 'a-meat-out-open.png'))
        else:
            fails.append('원료육 ' + io + ' 팝업 안 열림')
        closeall()

    # 3) 보관 위치 변경 (3개 탭)
    nav('stock:fg', 1500)
    page.evaluate("() => { const t = document.querySelector('#fgTableWrap tbody .actmenu'); if (t) t.click(); }")
    page.wait_for_timeout(400)
    got = page.evaluate("""() => { const b = Array.from(document.querySelectorAll('#rowMenu button')).find(x => x.textContent.indexOf('보관') >= 0);
      if (b) { b.click(); return true; } return false; }""")
    page.wait_for_timeout(800)
    if got and page.evaluate("() => !document.getElementById('fpWhModal').classList.contains('hidden')"):
        t = page.evaluate("""() => { const seg = document.getElementById('fpWhSeg');
          return {grid: getComputedStyle(seg).gridTemplateColumns,
            btns: Array.from(seg.querySelectorAll('button')).map(x => ({t: x.textContent, w: Math.round(x.getBoundingClientRect().width), cut: x.scrollWidth - x.clientWidth}))}; }""")
        print('   fpWh', json.dumps(t, ensure_ascii=False))
        chk(all(x['cut'] == 0 for x in t['btns']), '보관 위치 탭 3개 — 잘림 없음')
        chk(len(t['grid'].split(' ')) == 3, '보관 위치 탭이 3등분', t['grid'])
        run(page, 'fp-wh', '#fpWhModal')
    else:
        print('   (보관 위치 팝업 없음 — 건너뜀)')
    closeall()

    # 4) 원료육 작업 탭 4개(입고·해동·재냉동·출고)가 그대로인지
    page.evaluate("() => { const h = document.getElementById('ioHubModal'); if (h) h.classList.remove('hidden'); }")
    page.wait_for_timeout(250)
    page.evaluate("() => { const b = document.querySelector('#ioHubModal [data-io=\"in\"]'); if (b) b.click(); }")
    page.wait_for_timeout(1200)
    t4 = page.evaluate("""() => { const seg = document.querySelector('#meatFormModal .formmodes');
      return {grid: getComputedStyle(seg).gridTemplateColumns,
        btns: Array.from(seg.querySelectorAll('button')).map(x => ({t: x.textContent.trim(), cut: x.scrollWidth - x.clientWidth}))}; }""")
    print('   formmodes', json.dumps(t4, ensure_ascii=False))
    chk(len(t4['grid'].split(' ')) == 4, '입고·해동·재냉동·출고 탭 4등분 유지', t4['grid'])
    chk(all(x['cut'] == 0 for x in t4['btns']), '작업 탭 글자 잘림 없음')
    closeall()

    print('\nJS 오류', errors)
    b.close()

print('실패 %d건' % len(fails))
for f in fails:
    print('  -', f)
