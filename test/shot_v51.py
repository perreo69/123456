# -*- coding: utf-8 -*-
"""v51 실서버/로컬 검증 — macOS·iOS HIG 스타일 캡처 + 기능·오류·넘침·금지어 확인

  LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/shot_v51.py [BASE_URL] [OUT_DIR]
"""
import os
import sys

os.environ['LD_LIBRARY_PATH'] = '/workspace/tool-results/chromelibs'
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'https://perreo69.github.io/123456/?v=20261125_58'
OUT = sys.argv[2] if len(sys.argv) > 2 else '/workspace/downloads/erp-v51-live'
errors = []
fails = []
os.makedirs(OUT, exist_ok=True)

FORBIDDEN = ['줄돈', '받을돈', '.traffic']


def chk(cond, label, extra=''):
    print(('  [OK]   ' if cond else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not cond:
        fails.append(label)


def shot(page, name):
    page.wait_for_timeout(450)
    page.screenshot(path=os.path.join(OUT, name + '.png'))
    print('  shot', name)


def nav(page, key, wait=1500):
    page.evaluate("(k) => { const b = document.querySelector('#v8Side [data-nav=\"' + k + '\"]'); if (b) b.click(); }", key)
    page.wait_for_timeout(wait)


def overflow(page):
    return page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")


def popup_open(page):
    return page.evaluate("""() => { const ids=['meatFormModal','ioSheetModal'];
        return ids.some(id => { const m=document.getElementById(id); return m && !m.classList.contains('hidden'); }); }""")


def login(page):
    page.goto(BASE)
    page.wait_for_timeout(900)
    page.fill('#liEmail', 'perreo@nate.com')
    page.fill('#liPw', '123456')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=45000)
    page.wait_for_timeout(6500)


def desktop(b):
    page = b.new_page(viewport={'width': 1920, 'height': 1080})
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('dialog', lambda d: d.dismiss())
    login(page)
    page.add_style_tag(content='#toast{display:none !important}')
    shot(page, 'pc-00-첫화면')

    # ---- 원료육
    nav(page, 'stock:meat')
    chk(overflow(page) <= 0, 'PC 원료육 가로 넘침 0', overflow(page))
    chk(page.evaluate("() => !document.getElementById('meatKpi').classList.contains('hidden')"), '원료육 KPI 표시')
    shot(page, 'pc-01-원료육-전체')
    nav(page, 'stock:meat:F')
    shot(page, 'pc-02-원료육-냉동고')

    # ---- 정렬 3단 + 호버 화살표 없음
    def arrow():
        return page.evaluate("""() => { const th = document.querySelector('#uniTableWrap thead th button[data-sort]'); if(!th) return 'NONE';
            const a = th.querySelector('.uarrow'); return a ? a.textContent.trim() : ''; }""")
    key = page.evaluate("() => { const th = document.querySelector('#uniTableWrap thead th button[data-sort]'); return th ? th.getAttribute('data-sort') : ''; }")
    page.evaluate("(k) => document.querySelector('#uniTableWrap thead th button[data-sort=\"'+k+'\"]').click()", key)
    page.wait_for_timeout(650)
    a1 = arrow()
    page.evaluate("(k) => document.querySelector('#uniTableWrap thead th button[data-sort=\"'+k+'\"]').click()", key)
    page.wait_for_timeout(650)
    a2 = arrow()
    page.evaluate("(k) => document.querySelector('#uniTableWrap thead th button[data-sort=\"'+k+'\"]').click()", key)
    page.wait_for_timeout(650)
    a3 = arrow()
    chk(a1 == '▲' and a2 == '▼' and a3 == '', 'PC 머리글 3단 정렬 ▲→▼→기본', (a1, a2, a3))
    chk(page.evaluate("() => document.querySelectorAll('#uniTableWrap thead th .car').length") == 0, 'PC 머리글 호버 화살표 0건')

    # ---- 표 안쪽 스크롤 없음 (max-height 금지)
    mh = page.evaluate("""() => { let bad=[];
        document.querySelectorAll('.table-wrap, .panel, table').forEach(e=>{ const s=getComputedStyle(e);
          const mx = s.maxHeight; if (mx && mx !== 'none' && parseFloat(mx) < 100000) bad.push((e.className||e.tagName)+':'+mx); });
        return bad; }""")
    chk(len(mh) == 0, 'PC 표 max-height 제한 0건', mh)

    # ---- 우클릭 값 필터
    bx = page.evaluate("""() => { const th = document.querySelectorAll('#uniTableWrap thead th')[3];
        const bt = th.querySelector('button'); const r = bt.getBoundingClientRect(); return {x: r.left + 16, y: r.top + r.height/2}; }""")
    page.mouse.click(bx['x'], bx['y'], button='right')
    page.wait_for_timeout(600)
    chk(page.evaluate("() => { const e=document.getElementById('fpop'); return e && !e.classList.contains('hidden'); }"), 'PC 우클릭 엑셀 값 필터')
    shot(page, 'pc-03-값필터')
    page.keyboard.press('Escape')
    page.mouse.click(900, 520)
    page.wait_for_timeout(300)

    # ---- 작업 메뉴 (원료육: 출고·이동·수정)
    bx = page.evaluate("""() => { const bt = document.querySelector('#uniTableWrap tbody tr.ulot .actmenu'); if(!bt) return null;
        const r = bt.getBoundingClientRect(); return {x: r.left + r.width/2, y: r.top + r.height/2}; }""")
    if bx:
        page.mouse.click(bx['x'], bx['y'])
        page.wait_for_timeout(600)
        items = page.evaluate("() => Array.from(document.querySelectorAll('#rowMenu button')).map(b => b.textContent.trim())")
        chk(set(items) == {'출고', '이동', '수정'}, '원료육 로트 [작업] = 출고·이동·수정', items)
        shot(page, 'pc-04-작업메뉴')
        page.keyboard.press('Escape')
        page.mouse.click(900, 520)
        page.wait_for_timeout(300)

    # ---- 완제품 (재고 0 포함)
    nav(page, 'stock:fg')
    page.evaluate("() => { const c = document.getElementById('uniShowZero'); if (c && !c.checked) c.click(); }")
    page.wait_for_timeout(1300)
    chk(overflow(page) <= 0, 'PC 완제품 가로 넘침 0', overflow(page))
    shot(page, 'pc-05-완제품-재고0포함')

    # ---- 전체 재고 / 품목관리
    nav(page, 'stock:all')
    shot(page, 'pc-06-전체재고')
    nav(page, 'items')
    chk(overflow(page) <= 0, 'PC 품목관리 가로 넘침 0', overflow(page))
    shot(page, 'pc-07-품목관리')
    page.evaluate("() => { const b=document.querySelector('#itemsTableWrap tbody tr td.actcell button'); if(b) b.click(); }")
    page.wait_for_timeout(600)
    items = page.evaluate("() => Array.from(document.querySelectorAll('#rowMenu button')).map(b=>b.textContent.trim())")
    chk(any('미사용' in i or '다시 사용' in i for i in items), '품목관리 [작업] 미사용/다시 사용', items)
    page.keyboard.press('Escape')
    page.wait_for_timeout(300)

    # ---- 입출고 내역
    nav(page, 'tx')
    chk(overflow(page) <= 0, 'PC 입출고 내역 가로 넘침 0', overflow(page))
    shot(page, 'pc-08-입출고내역')

    # ---- 회계 4화면
    for k, nm in [('buy-list', '매입'), ('sale-list', '매출'), ('buy-status', '미지급금'), ('sale-status', '미수금')]:
        nav(page, k, 1400)
        chk(overflow(page) <= 0, 'PC 회계·' + nm + ' 가로 넘침 0', overflow(page))
        shot(page, 'pc-09-회계-' + nm)

    # ---- 입고 팝업
    nav(page, 'stock:meat')
    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"in\"]').click()")
    page.wait_for_timeout(1800)
    opened = popup_open(page)
    chk(opened, 'PC 입고 팝업 열림')
    shot(page, 'pc-10-입고팝업')
    if opened:
        page.evaluate("() => { const b=document.getElementById('uniClose'); if(b) b.click(); }")
        page.wait_for_timeout(500)

    # ---- 사이드바 구성·감춘 메뉴 유지
    navcheck = page.evaluate("""() => {
      const labels = Array.from(document.querySelectorAll('#v8Side .glabel')).map(e => e.textContent.trim());
      const order = Array.from(document.querySelectorAll('#v8Nav .nitem[data-nav], #v8Nav .nitem.nflat, #v8Nav .nitem.npar'))
        .map(e => e.textContent.trim().split('\\n')[0]);
      const hidden = ['expense','ledger'].map(k => document.querySelector('#v8Side [data-nav="'+k+'"]'))
        .concat(Array.from(document.querySelectorAll('#v8Side [data-legacy]')));
      return { labels, first: order.slice(0,6), hiddenCount: hidden.filter(Boolean).length,
               hiddenVisible: hidden.filter(e => e && e.offsetParent !== null).length,
               foot: !!document.querySelector('#v8Side .sidefoot .sfbrand') }; }""")
    chk(navcheck['labels'] == ['입출고 관리', '재고 관리', '회계'], '사이드바 그룹 = 입출고 관리·재고 관리·회계', navcheck['labels'])
    chk(navcheck['hiddenCount'] == 4 and navcheck['hiddenVisible'] == 0, '감춘 메뉴 4개 유지(화면엔 0)', navcheck)
    chk(navcheck['foot'], 'Built by LCP 푸터 유지')
    order = page.evaluate("""() => Array.from(document.querySelectorAll('#v8Nav .nitem'))
        .filter(e => e.offsetParent !== null).map(e => e.textContent.trim().split('\\n')[0].replace(/[0-9]+$/,'').trim())""")
    chk(order[0] == '입고입력' and order[3] == '입출고 내역', '메뉴 순서: 입고입력 → … → 입출고 내역', order[:5])

    # ---- 제목 옆 + 품목 등록 위치 (h2 같은 줄 오른쪽)
    place = page.evaluate("""() => { const h = document.getElementById('v8Title');
        const btn = Array.from(document.querySelectorAll('.phtop button')).find(b => b.textContent.includes('품목 등록'));
        if (!btn) return 'NO';
        const r = h.getBoundingClientRect(), q = btn.getBoundingClientRect();
        return { right: q.left >= r.right - 2, sameRow: Math.abs((q.top + q.height/2) - (r.top + r.height/2)) < 26 };
      }""")
    chk(isinstance(place, dict) and place.get('right') and place.get('sameRow'), '제목 오른쪽 같은 줄에 + 품목 등록', place)

    # ---- 금지어·이모지
    txt = page.evaluate("() => document.body.innerText")
    bad = [w for w in FORBIDDEN if w in txt]
    chk(len(bad) == 0, '금지어 0건 (줄돈/받을돈/.traffic)', bad)
    emo = page.evaluate(r"""() => (document.body.innerText.match(/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}]/gu)||[]).slice(0,10)""")
    chk(len(emo) == 0, '이모지 0건', emo)
    # 폰트 스택 확인
    ff = page.evaluate("() => getComputedStyle(document.body).fontFamily")
    chk('Inter' in ff and 'Pretendard' in ff, '폰트 스택 Inter·Pretendard 포함', ff)
    page.close()


def mobile(b):
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    page = ctx.new_page()
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('dialog', lambda d: d.dismiss())
    login(page)
    shot(page, 'mo-00-첫화면')
    for k, nm in [('stock:meat', '원료육'), ('stock:fg', '완제품'), ('items', '품목관리'), ('tx', '입출고'), ('sale-list', '회계')]:
        page.evaluate("(k) => { const s=document.getElementById('v8Side'); document.querySelector('#v8Side [data-nav=\"'+k+'\"]')?.click(); }", k)
        page.wait_for_timeout(1500)
        chk(overflow(page) <= 0, '폰 ' + nm + ' 가로 넘침 0', overflow(page))
        shot(page, 'mo-01-' + nm)
    # 입고 팝업
    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"in\"]').click()")
    page.wait_for_timeout(1800)
    chk(popup_open(page), '폰 입고 팝업 열림')
    shot(page, 'mo-02-입고팝업')
    page.close()
    ctx.close()


with sync_playwright() as pw:
    b = pw.chromium.launch(env=dict(os.environ))
    desktop(b)
    mobile(b)
    b.close()

real = [e for e in errors if 'ResizeObserver' not in e]
print('JS 오류:', real if real else '0건')
print('실패:', fails if fails else '없음')
