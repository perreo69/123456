# -*- coding: utf-8 -*-
"""v59 실서버(깃허브 페이지) 읽기 전용 확인 — 로그인하지 않고 자산·화면만 본다."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright

URL = 'https://perreo69.github.io/123456/?v=20261126_68'
OUT = '/workspace/downloads/erp-v59-화면/live'
ok = True


def chk(c, label, extra=''):
    global ok
    print(('  [OK]   ' if c else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not c:
        ok = False


env = dict(os.environ)
libs = '/workspace/tool-results/chromelibs'
if os.path.isdir(libs):
    env['LD_LIBRARY_PATH'] = libs + (':' + env.get('LD_LIBRARY_PATH', ''))
os.makedirs(OUT, exist_ok=True)
with sync_playwright() as pw:
    b = pw.chromium.launch(env=env)
    # 폰
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    p = ctx.new_page()
    errs, resp = [], []
    p.on('pageerror', lambda e: errs.append(str(e)))
    p.on('response', lambda r: resp.append((r.status, r.url)) if r.status >= 400 else None)
    p.goto(URL, wait_until='networkidle')
    p.wait_for_timeout(2500)
    info = p.evaluate("""() => {
      const sheets = Array.from(document.styleSheets).map(s => s.href || 'inline').filter(Boolean);
      const mob = sheets.filter(h => h.indexOf('mobile.css') >= 0);
      const tabs = document.getElementById('mobTabs');
      const st = tabs ? getComputedStyle(tabs) : null;
      return {mobCss: mob.length, tabs: !!tabs, tabsVisible: !!(st && st.display !== 'none'),
              tabCount: tabs ? tabs.querySelectorAll('.mtab').length : 0,
              over: document.documentElement.scrollWidth - window.innerWidth,
              bodyBg: getComputedStyle(document.body).backgroundColor};
    }""")
    print(info)
    chk(info['mobCss'] == 1, '실서버가 mobile.css 를 물려 줌', info['mobCss'])
    chk(info['tabs'] and info['tabCount'] == 5, '하단 탭 바 5개 생성', info['tabCount'])
    chk(info['bodyBg'] == 'rgb(242, 242, 247)', '폰 배경 = iOS 회색(#,F2F2F7)', info['bodyBg'])
    chk(info['over'] == 0, '폰 화면 가로 넘침 0', info['over'])
    chk(not errs, 'JS 오류 0', errs[:3])
    bad = [r for r in resp if 'mobile.css' in r[1] or 'app.js' in r[1]]
    chk(not bad, '핵심 자산 404 없음', bad[:3])
    p.screenshot(path=os.path.join(OUT, 'L-폰-로그인.png'))
    ctx.close()
    # PC
    ctx = b.new_context(viewport={'width': 1920, 'height': 1080})
    p = ctx.new_page()
    errs2 = []
    p.on('pageerror', lambda e: errs2.append(str(e)))
    p.goto(URL, wait_until='networkidle')
    p.wait_for_timeout(2000)
    pc = p.evaluate("""() => ({tabs: !!document.getElementById('mobTabs'),
        sheets: Array.from(document.styleSheets).map(s => s.href||'').filter(h => h.indexOf('mobile.css')>=0).length,
        mob: matchMedia('(max-width: 768px), (max-width: 900px) and (pointer: coarse)').matches,
        over: document.documentElement.scrollWidth - window.innerWidth})""")
    print(pc)
    chk(not pc['tabs'], 'PC 에는 폰 탭 바가 만들어지지 않음', pc['tabs'])
    chk(pc['mob'] is False, 'PC 는 폰 조건 밖(폰 CSS·탭 바 미적용)', pc['mob'])

    # v59 — 새 코드가 실제로 서빙되는지(파일 내용) 확인
    import urllib.request
    def fetch(u):
        try:
            return urllib.request.urlopen(u, timeout=20).read().decode('utf-8', 'ignore')
        except Exception as ex:
            return 'ERR ' + str(ex)
    js = fetch('https://perreo69.github.io/123456/app.js?v=20261126_68')
    css = fetch('https://perreo69.github.io/123456/mobile.css?v=20261126_68')
    chk('acIoPartnerCands' in js and 'setAcList' in js, '실서버 app.js 에 v59 검색 코드 있음', len(js))
    chk('z-index:1200' in css.replace(' ', ''), '실서버 mobile.css 에 v59 목록 스타일 있음', len(css))
    chk(not errs2, 'PC JS 오류 0', errs2[:3])
    p.screenshot(path=os.path.join(OUT, 'L-PC-로그인.png'))
    b.close()
print('RESULT', 'PASS' if ok else 'FAIL')
