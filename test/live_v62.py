# -*- coding: utf-8 -*-
"""v62 실서버 확인 (읽기 전용 — 저장·수정·삭제 버튼은 절대 누르지 않는다)

  LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/live_v62.py [URL] [OUT]

· 새 토큰 ?v=20261126_71 이 app.js · style.css · mobile.css 에 실제로 걸렸는지
· PC 1920: 입고 팝업 표에 원산지·브랜드 두 칸, 표가 옆으로 밀리지 않는지, 다른 화면 회귀 0
· 폰 390: 입고 카드에 원산지 | 브랜드 2열(44px · 16px), 가로 넘침 0, JS 오류 0
"""
import json
import os
import sys

os.environ.setdefault('LD_LIBRARY_PATH', '/workspace/tool-results/chromelibs')
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'https://perreo69.github.io/123456/?v=20261126_71'
TOKEN = BASE.split('v=')[1].split('&')[0] if 'v=' in BASE else ''
OUT = sys.argv[2] if len(sys.argv) > 2 else '/workspace/downloads/erp-v62-실서버'
os.makedirs(OUT, exist_ok=True)
errors, fails = [], []


def chk(cond, label, extra=''):
    print(('  [OK]   ' if cond else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not cond:
        fails.append(label)


OVER = """(sel) => {
  const m = document.querySelector(sel);
  if (!m) return { open: false };
  const card = m.querySelector('.modal-card');
  const cr = card.getBoundingClientRect();
  let worst = 0, who = '';
  card.querySelectorAll('*').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width <= 0) return;
    const over = Math.max(r.right - cr.right, cr.left - r.left);
    if (over > worst) { worst = over; who = el.tagName + '.' + ((el.className || '').toString().slice(0, 24)); }
  });
  return { open: !m.classList.contains('hidden'), over: Math.round(worst), who: who,
           docOver: document.documentElement.scrollWidth - window.innerWidth };
}"""


def login(page):
    page.fill('#liEmail', 'perreo@nate.com')
    page.fill('#liPw', '123456')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=45000)
    page.wait_for_timeout(6000)
    for _ in range(20):
        n = page.evaluate("() => (window.st && st.lots) ? st.lots.length : 0")
        if n > 0:
            break
        page.wait_for_timeout(1000)


with sync_playwright() as pw:
    b = pw.chromium.launch(env=dict(os.environ))

    # ---------------------------------------------------------------- PC 1920
    page = b.new_page(viewport={'width': 1920, 'height': 1080})
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('dialog', lambda d: d.dismiss())
    page.goto(BASE)
    page.wait_for_timeout(1200)
    login(page)
    src = page.evaluate("() => (document.querySelector('script[src*=\"app.js\"]') || {}).src || ''")
    chk(TOKEN and TOKEN in src, '실서버 app.js 토큰 ' + TOKEN, src)
    chk(TOKEN and TOKEN in page.evaluate("() => (document.querySelector('link[href*=\"style.css\"]') || {}).href || ''"),
        '실서버 style.css 토큰 ' + TOKEN)
    chk(TOKEN and TOKEN in page.evaluate("() => (document.querySelector('link[href*=\"mobile.css\"]') || {}).href || ''"),
        '실서버 mobile.css 토큰 ' + TOKEN)

    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"in\"]').click()")
    page.wait_for_timeout(1400)
    g = page.evaluate("""() => { const box = document.querySelector('#ioSheetWrap .vsheet-scroll');
        const tb = document.getElementById('ioSheetTable');
        const ths = [...tb.querySelectorAll('thead th')].map(t => t.textContent.trim());
        const tr = document.querySelector('#ioSheetBody tr[data-r="0"]');
        const q = s => tr && tr.querySelector(s);
        const w = el => el ? Math.round(el.getBoundingClientRect().width) : 0;
        const h = el => el ? Math.round(el.getBoundingClientRect().height) : 0;
        return { ths: ths, box: Math.round(box.clientWidth), scroll: Math.round(box.scrollWidth),
                 table: Math.round(tb.getBoundingClientRect().width),
                 o: q('[data-f="origin"]') ? { w: w(q('[data-f="origin"]')), h: h(q('[data-f="origin"]')) } : null,
                 b: q('[data-f="brand"]') ? { w: w(q('[data-f="brand"]')), h: h(q('[data-f="brand"]')) } : null }; }""")
    print('   PC:', json.dumps(g, ensure_ascii=False))
    chk(g['ths'][2:4] == ['원산지', '브랜드'], 'PC 입고 표에 원산지 · 브랜드 칸', g['ths'][:5])
    chk(bool(g['o']) and bool(g['b']), 'PC 원료육 줄에 두 입력칸', [g['o'], g['b']])
    chk(g['box'] == g['scroll'] == g['table'], 'PC 표가 옆으로 밀리지 않는다', [g['box'], g['scroll'], g['table']])
    ov = page.evaluate(OVER, '#ioSheetModal')
    chk(ov['over'] <= 1, 'PC 팝업 가로 넘침 0px', ov)
    page.screenshot(path=os.path.join(OUT, 'L1-PC-입고-원산지브랜드.png'))
    # 자동완성(읽기 전용 — 값을 넣고 목록만 본다)
    page.click('#ioSheetBody tr[data-r="0"] [data-f="origin"]')
    page.type('#ioSheetBody tr[data-r="0"] [data-f="origin"]', '호', delay=90)
    page.wait_for_timeout(700)
    ac = page.evaluate("""() => { const p = document.querySelector('.acpop');
        if (!p || p.classList.contains('hidden')) return { open: false };
        return { open: true, n: p.querySelectorAll('.acitem').length,
                 items: [...p.querySelectorAll('.acitem .act')].slice(0, 4).map(x => x.textContent.trim()) }; }""")
    print('   원산지 후보:', json.dumps(ac, ensure_ascii=False))
    chk(ac.get('open') and ac.get('n', 0) >= 1, 'PC 원산지 실시간 후보(지금까지 쓴 값)', ac.get('items'))
    page.screenshot(path=os.path.join(OUT, 'L2-PC-원산지-후보.png'))
    page.keyboard.press('Escape')
    page.evaluate("() => document.getElementById('ioSheetCancel').click()")
    page.wait_for_timeout(400)
    # 다른 화면 회귀
    okview = page.evaluate("""() => { document.querySelector('#v8Side [data-nav="stock:meat"]').click(); return 1; }""")
    page.wait_for_timeout(1500)
    reg = page.evaluate("""() => { const t = document.querySelector('#tableWrap table, #uniTableWrap table');
        return { rows: t ? t.querySelectorAll('tbody tr').length : 0,
                 over: document.documentElement.scrollWidth - window.innerWidth }; }""")
    print('   원료육 재고:', json.dumps(reg, ensure_ascii=False))
    chk(reg['rows'] > 0 and reg['over'] == 0, 'PC 원료육 재고 화면 그대로(줄 N · 가로 넘침 0)', reg)
    page.screenshot(path=os.path.join(OUT, 'L3-PC-원료육재고.png'))
    page.close()

    # ---------------------------------------------------------------- 폰 390
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    page = ctx.new_page()
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('dialog', lambda d: d.dismiss())
    page.goto(BASE)
    page.wait_for_timeout(1000)
    login(page)
    page.add_style_tag(content='#toast{display:none !important}')
    page.evaluate("() => document.querySelector('#mobTabs [data-mtab=\"in\"]').click()")
    page.wait_for_timeout(1600)
    m = page.evaluate("""() => { const tr = document.querySelector('#ioSheetBody tr[data-mcard="1"]');
        if (!tr) return { none: true };
        const o = tr.querySelector('[data-f="origin"]'), br = tr.querySelector('[data-f="brand"]');
        const g = el => { if (!el) return null; const r = el.getBoundingClientRect(); const st = getComputedStyle(el);
          return { top: Math.round(r.top), left: Math.round(r.left), w: Math.round(r.width), h: Math.round(r.height), fs: st.fontSize }; };
        const ex = tr.querySelector('[data-f="expiry"]');
        return { o: g(o), b: g(br), exp: g(ex), docOver: document.documentElement.scrollWidth - window.innerWidth,
                 labels: [...tr.querySelectorAll('.mfields .mf > span')].map(s => s.textContent.trim()) }; }""")
    print('   폰:', json.dumps(m, ensure_ascii=False))
    chk(not m.get('none') and m.get('o') and m.get('b'), '폰 입고 카드에 원산지·브랜드 칸', [m.get('o'), m.get('b')])
    chk(m.get('o') and m['b'] and m['o']['top'] == m['b']['top'] and m['o']['left'] < m['b']['left'], '폰 2열 나란히', [m.get('o'), m.get('b')])
    chk(m.get('o') and m['o']['h'] >= 44 and m['o']['h'] <= 48 and m['o']['fs'] == '16px', '폰 칸 44px · 글자 16px', m.get('o'))
    chk(m.get('exp') and m['o'] and m['o']['top'] >= m['exp']['top'], '폰 소비기한 아래에 온다', [m.get('exp') and m['exp']['top'], m.get('o') and m['o']['top']])
    chk(m.get('docOver') == 0, '폰 화면 가로 넘침 0px', m.get('docOver'))
    ov2 = page.evaluate(OVER, '#ioSheetModal')
    chk(ov2['over'] <= 1, '폰 카드 안 가로 넘침 0px', ov2)
    page.screenshot(path=os.path.join(OUT, 'L4-폰-입고-원산지브랜드.png'))
    page.evaluate("() => { const c = document.querySelector('#ioSheetModal .modal-card'); c.scrollTop = 260; }")
    page.wait_for_timeout(500)
    page.screenshot(path=os.path.join(OUT, 'L5-폰-입고-아래.png'))
    page.evaluate("() => document.getElementById('ioSheetClose').click()")
    page.wait_for_timeout(400)
    over3 = page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    chk(over3 == 0, '폰 화면 전체 가로 넘침 0px', over3)

    real = [e for e in errors if 'Failed to load resource' not in e]
    chk(not real, 'JS 오류 0', real[:3])
    ctx.close()
    b.close()

print('\n결과:', 'PASS' if not fails else ('FAIL ' + str(fails)))
sys.exit(0 if not fails else 1)
