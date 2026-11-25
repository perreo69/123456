# -*- coding: utf-8 -*-
"""v60 실서버(깃허브 페이지) 읽기 전용 확인 — 로그인하지 않고 자산·화면·서빙본만 본다.
   LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/v60_live.py
"""
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright

URL = 'https://perreo69.github.io/123456/?v=20261126_69'
OUT = '/workspace/downloads/erp-v60-화면/live'
ok = True


def chk(c, label, extra=''):
    global ok
    print(('  [OK]   ' if c else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not c:
        ok = False


def fetch(u):
    try:
        return urllib.request.urlopen(u, timeout=25).read().decode('utf-8', 'ignore')
    except Exception as ex:
        return 'ERR ' + str(ex)


env = dict(os.environ)
libs = '/workspace/tool-results/chromelibs'
if os.path.isdir(libs):
    env['LD_LIBRARY_PATH'] = libs + (':' + env.get('LD_LIBRARY_PATH', ''))
os.makedirs(OUT, exist_ok=True)
with sync_playwright() as pw:
    b = pw.chromium.launch(env=env)
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    p = ctx.new_page()
    errs, resp = [], []
    p.on('pageerror', lambda e: errs.append(str(e)))
    p.on('response', lambda r: resp.append((r.status, r.url)) if r.status >= 400 else None)
    p.goto(URL, wait_until='networkidle')
    p.wait_for_timeout(2500)
    info = p.evaluate("""() => {
      const sheets = Array.from(document.styleSheets).map(s => s.href || '').filter(Boolean);
      const tabs = document.getElementById('mobTabs');
      const photo = document.getElementById('btnPhotoInbox');
      const pst = photo ? getComputedStyle(photo).display : 'none';
      return { mobCss: sheets.filter(h => h.indexOf('mobile.css') >= 0).length,
               tabs: !!tabs, tabCount: tabs ? tabs.querySelectorAll('.mtab').length : 0,
               photo: pst,
               aiBtn: !!document.getElementById('ioAiPaste'),
               over: document.documentElement.scrollWidth - window.innerWidth,
               bodyBg: getComputedStyle(document.body).backgroundColor };
    }""")
    print(info)
    chk(info['mobCss'] == 1, '실서버 mobile.css 서빙', info['mobCss'])
    chk(info['tabs'] and info['tabCount'] == 5, '폰 하단 탭 5개', info['tabCount'])
    chk(info['photo'] == 'none', '상단 사진 대기함 버튼 숨김', info['photo'])
    chk(info['aiBtn'] is False, 'AI 자료 붙여넣기 버튼 없음', info['aiBtn'])
    chk(info['over'] == 0, '폰 가로 넘침 0', info['over'])
    chk(not errs, '폰 JS 오류 0', errs[:3])
    p.screenshot(path=os.path.join(OUT, 'L-폰-로그인.png'))
    ctx.close()

    ctx = b.new_context(viewport={'width': 1920, 'height': 1080})
    p = ctx.new_page()
    errs2 = []
    p.on('pageerror', lambda e: errs2.append(str(e)))
    p.goto(URL, wait_until='networkidle')
    p.wait_for_timeout(2000)
    pc = p.evaluate("""() => ({ tabs: !!document.getElementById('mobTabs'),
        mob: matchMedia('(max-width: 768px)').matches,
        photo: (() => { const e = document.getElementById('btnPhotoInbox'); return e ? getComputedStyle(e).display : 'none'; })(),
        over: document.documentElement.scrollWidth - window.innerWidth })""")
    print(pc)
    chk(not pc['tabs'], 'PC 에 폰 탭 바 없음', pc['tabs'])
    chk(pc['mob'] is False, 'PC 는 폰 조건 밖', pc['mob'])
    chk(pc['photo'] == 'none', 'PC 상단 사진 대기함 버튼 숨김', pc['photo'])
    chk(not errs2, 'PC JS 오류 0', errs2[:3])
    p.screenshot(path=os.path.join(OUT, 'L-PC-로그인.png'))
    ctx.close()
    b.close()

js = fetch('https://perreo69.github.io/123456/app.js?v=20261126_69')
css = fetch('https://perreo69.github.io/123456/mobile.css?v=20261126_69')
html = fetch('https://perreo69.github.io/123456/index.html')
local_js = open('/workspace/work/erp-web/app.js', encoding='utf-8').read()
local_css = open('/workspace/work/erp-web/mobile.css', encoding='utf-8').read()
chk('iosMobRowHtml' in js and 'data-lotpick' in js, '실서버 app.js 에 v60 카드 코드', len(js))
chk('mstk-list' in css and '.mlot' in css, '실서버 mobile.css 에 v60 스타일', len(css))
chk(js == local_js, '실서버 app.js = 로컬 바이트 동일', [len(js), len(local_js)])
chk(css == local_css, '실서버 mobile.css = 로컬 바이트 동일', [len(css), len(local_css)])
chk('20261126_69' in html and 'ioAiPaste' not in html, 'index.html 캐시 토큰 69 · AI 버튼 없음', '20261126_69' in html)

print('RESULT', 'PASS' if ok else 'FAIL')
