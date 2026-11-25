# -*- coding: utf-8 -*-
"""v56 — 해동/냉동 로트 검색·선택 콤보박스 + 탭 글자 잘림 (로컬 스텁 Supabase)

  LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/v56_shot.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('LD_LIBRARY_PATH', '/workspace/tool-results/chromelibs')
import shot_v54 as V
from playwright.sync_api import sync_playwright

OUT = '/workspace/downloads/erp-v56'
os.makedirs(OUT, exist_ok=True)
errors, fails = [], []


def chk(cond, label, extra=''):
    print(('  [OK]   ' if cond else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not cond:
        fails.append(label)


TABS = r"""() => {
  const seg = document.getElementById('uniMoveSeg');
  const out = {card: null, seg: null, btns: []};
  const box = el => { const r = el.getBoundingClientRect(); return {w: +r.width.toFixed(1), h: +r.height.toFixed(1)}; };
  out.card = box(document.querySelector('#uniMoveModal .modal-card'));
  out.seg = box(seg);
  out.grid = getComputedStyle(seg).gridTemplateColumns;
  seg.querySelectorAll('button').forEach(b => {
    const c = getComputedStyle(b);
    out.btns.push({text: b.textContent.trim(), w: box(b).w, sw: b.scrollWidth, cw: b.clientWidth,
                   cut: b.scrollWidth - b.clientWidth, h: box(b).h, lines: Math.round(b.getBoundingClientRect().height / parseFloat(c.lineHeight || 16))});
  });
  return out;
}"""

POP = r"""() => {
  const p = document.getElementById('uniMoveLotPop');
  if (!p) return {missing: true};
  const rows = Array.from(p.querySelectorAll('.lcitem'));
  return {hidden: p.classList.contains('hidden'), n: rows.length,
          head: (p.querySelector('.lchead') || {}).textContent || '',
          first: rows[0] ? rows[0].textContent : '',
          sel: (p.querySelector('.lcitem.sel') || {}).textContent || '',
          rect: (r => ({w: Math.round(r.width), h: Math.round(r.height), t: Math.round(r.top), l: Math.round(r.left)}))(p.getBoundingClientRect())};
}"""

STATE = r"""() => ({
  lot: document.getElementById('uniMoveLot').value,
  input: document.getElementById('uniMoveLotQ').value,
  price: document.getElementById('uniMovePrice').value,
  stat: document.getElementById('uniMoveStat').textContent,
  kgmax: document.getElementById('uniMoveKg').getAttribute('max')
})"""

with sync_playwright() as pw:
    b = pw.chromium.launch(env=dict(os.environ))

    # ---------- 1) PC 1920 ----------
    page = b.new_page(viewport={'width': 1920, 'height': 1080})
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('dialog', lambda d: d.dismiss())
    page.add_init_script(V.FAKE_WS)
    page.route('**/gzufnyglmvgzqltepock.supabase.co/**', V.route_handler)
    V.login(page)

    # 재고표 [작업] → 이동 (로트가 미리 채워져 열린다)
    page.evaluate("() => { const b = document.querySelector('#v8Side [data-nav=\"stock:meat\"]'); if (b) b.click(); }")
    page.wait_for_timeout(1800)
    pre = page.evaluate("""() => { const t = document.querySelector('#uniTableWrap tbody tr.ulot'); 
      return t ? {lot: t.getAttribute('data-lot'), txt: t.textContent.slice(0, 40)} : null; }""")
    page.evaluate("() => { const t = document.querySelector('#uniTableWrap tbody tr.ulot .actmenu'); if (t) t.click(); }")
    page.wait_for_timeout(400)
    page.evaluate("""() => { const b = Array.from(document.querySelectorAll('#rowMenu button')).find(x => x.textContent.trim() === '이동'); if (b) b.click(); }""")
    page.wait_for_timeout(900)
    chk(page.evaluate("() => !document.getElementById('uniMoveModal').classList.contains('hidden')"), '해동/냉동 팝업 열림')
    st = page.evaluate(STATE)
    print('   사전 선택', pre, '→', json.dumps(st, ensure_ascii=False))
    chk(st['lot'] != '', '[작업] → 이동 으로 연 로트가 그대로 선택됨', st['lot'])
    chk(st['input'].strip() != '' and '로트 선택' not in st['input'], '입력칸에 선택 로트 이름 표시', st['input'])
    chk(st['price'] not in ('', '0'), '단가 자동 채움', st['price'])
    chk('현재고' in st['stat'], '보관 중량 안내 문구', st['stat'][:80])

    t = page.evaluate(TABS)
    print('   탭', json.dumps(t, ensure_ascii=False))
    chk(all(x['cut'] == 0 for x in t['btns']), '탭 글자 잘림 0px', [(x['text'], x['cut']) for x in t['btns']])
    chk(t['btns'][0]['w'] > 150, '탭 두 개가 반씩 폭을 나눔', t['grid'])

    # 클릭만으로 전체 목록
    page.click('#uniMoveLotQ')
    page.wait_for_timeout(400)
    p = page.evaluate(POP)
    print('   목록', json.dumps(p, ensure_ascii=False)[:300])
    chk(not p['hidden'] and p['n'] >= 2, '클릭만 해도 보관 로트 전체가 열림', p['n'])
    page.screenshot(path=os.path.join(OUT, '01-pop-open.png'))
    page.screenshot(path=os.path.join(OUT, '01b-pop-modal.png'),
                    clip=page.evaluate("""() => { const r = document.querySelector('#uniMoveModal .modal-card').getBoundingClientRect();
                      return {x: Math.max(0, r.left - 10), y: Math.max(0, r.top - 10), width: Math.min(r.width + 20, innerWidth - 2), height: Math.min(r.height + 20, innerHeight - 2)}; }"""))

    # 타이핑 필터
    page.fill('#uniMoveLotQ', '알전')
    page.wait_for_timeout(350)
    p = page.evaluate(POP)
    print('   알전 검색', json.dumps(p, ensure_ascii=False)[:300])
    chk(not p['hidden'] and 0 < p['n'] <= 3, '‘알전’ 검색으로 걸러짐', p['n'])
    chk('알전' in p['first'], '검색 결과 첫 줄이 알전', p['first'])
    page.screenshot(path=os.path.join(OUT, '02-filter.png'))

    # 엔터로 선택
    page.press('#uniMoveLotQ', 'Enter')
    page.wait_for_timeout(500)
    st = page.evaluate(STATE)
    print('   선택 후', json.dumps(st, ensure_ascii=False))
    chk(st['lot'] != '', '엔터로 로트 선택됨', st['lot'])
    chk(st['input'].startswith('알전'), '입력칸에 고른 로트 이름', st['input'])
    chk('현재고' in st['stat'], '고른 뒤 중량 안내 갱신', st['stat'][:80])
    chk(page.evaluate("() => document.getElementById('uniMoveLotPop').classList.contains('hidden')"), '고르면 목록 닫힘')

    # 재냉동 전환 → 목록 자동 갱신
    page.evaluate("() => document.querySelector('#uniMoveSeg [data-mv=\"re\"]').click()")
    page.wait_for_timeout(400)
    page.click('#uniMoveLotQ')
    page.wait_for_timeout(400)
    p = page.evaluate(POP)
    hdr = p['head']
    chk('냉장고' in hdr, '재냉동으로 바꾸면 냉장고 로트만 뜸', hdr)
    page.screenshot(path=os.path.join(OUT, '03-re-pop.png'))
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)
    page.evaluate("() => document.getElementById('uniMoveClose').click()")
    page.wait_for_timeout(300)

    # ---------- 3) 원료육 입력 팝업의 로트 칸(출고) ----------
    page.evaluate("() => { const h = document.getElementById('ioHubModal'); if (h) h.classList.remove('hidden'); }")
    page.wait_for_timeout(250)
    page.evaluate("() => { const b = document.querySelector('#ioHubModal [data-io=\"out\"]'); if (b) b.click(); }")
    page.wait_for_timeout(1400)
    isopen = page.evaluate("() => !document.getElementById('meatFormModal').classList.contains('hidden')")
    chk(isopen, '원료육 입력 팝업(출고) 열림')
    if isopen:
        # 출고 칸을 냉동고로 (스텁 냉장고 재고는 1건뿐)
        page.evaluate("() => { const b = document.querySelector('#whSegOut [data-wh=\"F\"]'); if (b) b.click(); }")
        page.wait_for_timeout(500)
        page.click('#outLotQ')
        page.wait_for_timeout(400)
        p2 = page.evaluate("""() => { const p = document.getElementById('outLotPop');
          return {hidden: p.classList.contains('hidden'), n: p.querySelectorAll('.lcitem').length}; }""")
        chk(not p2['hidden'] and p2['n'] >= 2, '출고 팝업 로트 칸도 클릭하면 전체 목록', p2['n'])
        page.fill('#outLotQ', '목전')
        page.wait_for_timeout(300)
        page.press('#outLotQ', 'Enter')
        page.wait_for_timeout(400)
        s2 = page.evaluate("""() => ({lot: document.getElementById('outLot').value,
          input: document.getElementById('outLotQ').value, price: document.getElementById('outPrice').value,
          info: document.getElementById('outInfo').textContent.slice(0, 60)})""")
        print('   출고 선택', json.dumps(s2, ensure_ascii=False))
        chk(s2['lot'] != '' and '목전' in s2['input'], '출고 팝업에서도 검색·선택 동작', s2)
        chk('목전' in s2['info'], '고른 로트 정보표 갱신', s2['info'])
        page.screenshot(path=os.path.join(OUT, '04-out-modal.png'))
        page.keyboard.press('Escape')
    print('   JS 오류', errors)
    page.close()

    # ---------- 2) 폰 390 ----------
    page = b.new_page(viewport={'width': 390, 'height': 844})
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.add_init_script(V.FAKE_WS)
    page.route('**/gzufnyglmvgzqltepock.supabase.co/**', V.route_handler)
    V.login(page)
    page.evaluate("() => { const b = document.querySelector('#v8Side [data-nav=\"move\"]'); if (b) b.click(); }")
    page.wait_for_timeout(1600)
    if not page.evaluate("() => !document.getElementById('uniMoveModal').classList.contains('hidden')"):
        page.evaluate("() => { const b = document.querySelector('#v8Side [data-nav=\"stock:meat\"]'); if (b) b.click(); }")
        page.wait_for_timeout(1400)
        page.evaluate("() => { const t = document.querySelector('#uniTableWrap tbody tr.ulot .actmenu'); if (t) t.click(); }")
        page.wait_for_timeout(400)
        page.evaluate("""() => { const b = Array.from(document.querySelectorAll('#rowMenu button')).find(x => x.textContent.trim() === '이동'); if (b) b.click(); }""")
        page.wait_for_timeout(800)
    t = page.evaluate(TABS)
    print('   폰 탭', json.dumps(t, ensure_ascii=False))
    chk(all(x['cut'] == 0 for x in t['btns']), '폰(390) 탭 글자 잘림 0px', [(x['text'], x['cut']) for x in t['btns']])
    chk(page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth") == 0, '폰 가로 넘침 0px')
    page.click('#uniMoveLotQ')
    page.wait_for_timeout(400)
    p = page.evaluate(POP)
    print('   폰 목록', json.dumps(p, ensure_ascii=False)[:240])
    chk(not p['hidden'] and p['n'] >= 2, '폰에서도 목록 열림', p['n'])
    chk(p['rect']['l'] >= 0 and p['rect']['l'] + p['rect']['w'] <= 391, '목록이 화면 안에 들어옴', p['rect'])
    page.screenshot(path=os.path.join(OUT, '05-phone-pop.png'))
    page.screenshot(path=os.path.join(OUT, '05b-phone-modal.png'),
                    clip=page.evaluate("""() => { const r = document.querySelector('#uniMoveModal .modal-card').getBoundingClientRect();
                      return {x: Math.max(0, r.left - 4), y: Math.max(0, r.top - 4), width: Math.min(r.width + 8, innerWidth), height: Math.min(r.height + 8, innerHeight)}; }"""))
    page.close()
    b.close()

print('\n실패 %d건 · JS 오류 %d건' % (len(fails), len(errors)))
for f in fails:
    print('  -', f)
