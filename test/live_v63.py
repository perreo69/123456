# -*- coding: utf-8 -*-
"""v63 실서버 확인 (읽기 전용 — 저장·수정·삭제 버튼은 절대 누르지 않는다)

  LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/live_v63.py [URL] [OUT]

· 새 토큰 ?v=20261126_73 이 style.css 에 실제로 걸렸는지
· PC 1920 · 1440 : 왼쪽 위 파란 M 없음 · «미르스타푸드 ERP» 아래 두 줄 · 사이드바 아래 서명 0 · 넘침 0
· 폰 390 : 파란 M 유지 · 두 줄 없음 · 넘침 0 · JS 오류 0
"""
import json
import os
import sys

os.environ.setdefault('LD_LIBRARY_PATH', '/workspace/tool-results/chromelibs')
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'https://perreo69.github.io/123456/?v=20261126_73'
TOKEN = BASE.split('v=')[1].split('&')[0] if 'v=' in BASE else ''
OUT = sys.argv[2] if len(sys.argv) > 2 else '/workspace/downloads/erp-v63-실서버'
os.makedirs(OUT, exist_ok=True)
errors, fails = [], []


def chk(cond, label, extra=''):
    print(('  [OK]   ' if cond else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not cond:
        fails.append(label)


SHAPE = """() => {
  const el = s => document.querySelector(s);
  const vis = s => { const e = el(s); if (!e) return false; const r = e.getBoundingClientRect();
    const cs = getComputedStyle(e); return cs.display !== 'none' && cs.visibility !== 'hidden' && r.width > 0; };
  const sig = el('.brandsig');
  return {
    logoVis: vis('.brand .logo'),
    sigVis: vis('.brandsig'),
    sigText: sig ? sig.innerText.replace(/\\s+/g, ' ').trim() : '',
    sigFs: sig ? [...sig.querySelectorAll('b,span')].map(x => getComputedStyle(x).fontSize) : [],
    sigColors: sig ? [...sig.querySelectorAll('b,span')].map(x => getComputedStyle(x).color) : [],
    topH: el('.top') ? Math.round(el('.top').getBoundingClientRect().height) : null,
    sideTop: el('#v8Side') ? Math.round(el('#v8Side').getBoundingClientRect().top) : null,
    footH: el('.sidefoot') ? Math.round(el('.sidefoot').getBoundingClientRect().height) : null,
    footBorder: el('.sidefoot') ? getComputedStyle(el('.sidefoot')).borderTopWidth : null,
    docOver: document.documentElement.scrollWidth - window.innerWidth,
    h1: el('.brand h1') ? el('.brand h1').innerText.replace(/\\s+/g, ' ').trim() : null,
  };
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

    # ---------------------------------------------------------------- PC
    for w, h in ((1920, 1080), (1440, 900)):
        print('--- 실서버 PC %dx%d' % (w, h))
        page = b.new_page(viewport={'width': w, 'height': h})
        page.on('pageerror', lambda e: errors.append('pc%d:%s' % (w, e)))
        page.on('dialog', lambda d: d.dismiss())
        page.goto(BASE)
        page.wait_for_timeout(1200)
        login(page)
        css = page.evaluate("() => (document.querySelector('link[href*=\"style.css\"]') || {}).href || ''")
        chk(TOKEN and TOKEN in css, '실서버 style.css 토큰 ' + TOKEN, css)
        d = page.evaluate(SHAPE)
        print('   ', json.dumps(d, ensure_ascii=False))
        chk(not d['logoVis'], '실서버 PC 파란 M 없음')
        chk(d['sigVis'] and d['sigText'] == 'Built by LCP AI-assisted development', '서명 두 줄이 제목 밑에', d['sigText'])
        chk(d['sigFs'] == ['11px', '11px'], '두 줄 11px', d['sigFs'])
        chk(d['footH'] == 0 and d['footBorder'] in ('0px', None), '사이드바 아래 서명·구분선 0', [d['footH'], d['footBorder']])
        chk(d['docOver'] <= 0, '가로 넘침 0', d['docOver'])
        page.screenshot(path=os.path.join(OUT, 'L-PC-%d.png' % w))
        page.screenshot(path=os.path.join(OUT, 'L-PC-%d-brand.png' % w),
                        clip={'x': 0, 'y': 0, 'width': 420, 'height': 300})
        page.close()

    # ---------------------------------------------------------------- 폰
    print('--- 실서버 폰 390x844')
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    page = ctx.new_page()
    page.on('pageerror', lambda e: errors.append('mob:%s' % e))
    page.on('dialog', lambda d: d.dismiss())
    page.goto(BASE)
    page.wait_for_timeout(1000)
    login(page)
    page.add_style_tag(content='#toast{display:none !important}')
    m = page.evaluate(SHAPE)
    print('   ', json.dumps(m, ensure_ascii=False))
    chk(m['logoVis'], '폰 파란 M 그대로')
    chk(not m['sigVis'], '폰에는 두 줄 없음')
    chk(m['docOver'] <= 0, '폰 가로 넘침 0', m['docOver'])
    page.screenshot(path=os.path.join(OUT, 'L-폰-390.png'))
    ctx.close()
    b.close()

print('\nJS errors:', errors)
chk(len(errors) == 0, 'JS 오류 0건', errors[:3])
print('\n=== %s ===' % ('ALL OK' if not fails else 'FAIL: ' + str(fails)))
sys.exit(0 if not fails else 1)
