# -*- coding: utf-8 -*-
"""v63 검증 — PC 상단 브랜드 개편(파란 M 제거 · Built by LCP 두 줄을 제목 밑으로 · 하단 서명 제거)

  LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/v63_test.py [tag]

· PC 1920×1080 / 1440×900 : 왼쪽 위 파란 M 없음 · «미르스타푸드 ERP» 아래 두 줄(11px #8E8E93)
· 사이드바 맨 아래 서명·구분선 없음 · 첫 메뉴(입출고 관리)가 머리 밑에서 자연스럽게 시작
· 머리 64px · sticky 사이드바가 머리에 가리지 않음 · 가로 넘침 0
· 폰 390×844 : 상단 머리는 그대로(파란 M · 두 줄 없음) · 넘침 0 · 메뉴 시트 정상
· JS 오류 0
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_ui as T
from playwright.sync_api import sync_playwright

TAG = sys.argv[1] if len(sys.argv) > 1 else 'run'
OUT = '/workspace/downloads/erp-v63-화면/' + TAG
os.makedirs(OUT, exist_ok=True)
ok = True


def chk(cond, label, extra=''):
    global ok
    print(('  [OK]   ' if cond else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not cond:
        ok = False


INFO = """() => {
  const el = s => document.querySelector(s);
  const vis = s => { const e = el(s); if (!e) return false; const r = e.getBoundingClientRect();
    const cs = getComputedStyle(e); return cs.display !== 'none' && cs.visibility !== 'hidden' && r.width > 0 && r.height > 0; };
  const box = s => { const e = el(s); if (!e) return null; const r = e.getBoundingClientRect();
    return {x: Math.round(r.left), y: Math.round(r.top), w: Math.round(r.width), h: Math.round(r.height),
            t: (e.innerText || '').replace(/\\s+/g,' ').trim()}; };
  const sig = el('.brandsig');
  const sigB = sig && sig.querySelector('b');
  const sigS = sig && sig.querySelector('span');
  const csB = sigB ? getComputedStyle(sigB) : null;
  const csS = sigS ? getComputedStyle(sigS) : null;
  return {
    top: box('.top'), brand: box('.brand'), h1: box('.brand h1'),
    logoVis: vis('.brand .logo'), logoBox: box('.brand .logo'),
    sigVis: vis('.brandsig'), sig: box('.brandsig'),
    sigB: sigB ? sigB.innerText.trim() : null, sigS: sigS ? sigS.innerText.trim() : null,
    sigBfs: csB ? csB.fontSize : null, sigSfs: csS ? csS.fontSize : null,
    sigBcolor: csB ? csB.color : null, sigScolor: csS ? csS.color : null,
    sigBtop: sigB ? Math.round(sigB.getBoundingClientRect().top) : null,
    sigStop: sigS ? Math.round(sigS.getBoundingClientRect().top) : null,
    h1bottom: el('.brand h1') ? Math.round(el('.brand h1').getBoundingClientRect().bottom) : null,
    side: box('#v8Side'), glabel: box('#v8Nav .glabel'), nav: box('#v8Nav'),
    foot: box('.sidefoot'), footText: (el('.sidefoot') ? el('.sidefoot').innerText.replace(/\\s+/g,' ').trim() : ''),
    footBorder: el('.sidefoot') ? getComputedStyle(el('.sidefoot')).borderTopWidth : null,
    sideBorder: el('#v8Side') ? getComputedStyle(el('#v8Side')).borderTopWidth : null,
    topBorder: el('.top') ? getComputedStyle(el('.top')).borderBottomWidth : null,
    docOver: document.documentElement.scrollWidth - window.innerWidth,
    sigOccurrences: [...document.querySelectorAll('body *')].filter(e => e.children.length === 0 &&
        /Built by LCP|AI-assisted development/.test(e.textContent)).length,
    loginLogo: null,
  };
}"""


def login(page):
    page.goto(T.BASE + '?v=v63')
    page.wait_for_timeout(400)
    page.fill('#liEmail', 'kim@meat.co.kr')
    page.fill('#liPw', 'secret123')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=10000)
    page.wait_for_timeout(1600)
    page.add_style_tag(content='#toast{display:none !important}')


def main():
    errors = []
    with sync_playwright() as pw:
        env = dict(os.environ)
        libs = '/workspace/tool-results/chromelibs'
        if os.path.isdir(libs):
            env['LD_LIBRARY_PATH'] = libs + (':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
        b = pw.chromium.launch(env=env)

        # ---------- PC ----------
        for w, h in ((1920, 1080), (1440, 900)):
            print('--- PC %dx%d' % (w, h))
            ctx = b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=1)
            page = ctx.new_page()
            page.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
            page.add_init_script(T.FAKE_WS)
            page.on('pageerror', lambda e: errors.append('pc%d:%s' % (w, e)))
            login(page)
            d = page.evaluate(INFO)
            chk(not d['logoVis'], '왼쪽 위 파란 M 박스 없음', d['logoBox'])
            chk(d['sigVis'], '제목 아래 서명 두 줄 보임')
            chk(d['sigB'] == 'Built by LCP' and d['sigS'] == 'AI-assisted development', '두 줄 문구',
                [d['sigB'], d['sigS']])
            chk(d['sigBfs'] == '11px' and d['sigSfs'] == '11px', '두 줄 11px', [d['sigBfs'], d['sigSfs']])
            chk(d['sigBcolor'] == 'rgb(134, 134, 139)' and d['sigScolor'] == 'rgb(142, 142, 147)',
                '연회색(#8E8E93 계열)', [d['sigBcolor'], d['sigScolor']])
            chk(d['sig'] and d['h1'] and abs(d['sig']['x'] - d['h1']['x']) <= 1 and d['sig']['y'] - d['h1bottom'] <= 4,
                '제목 바로 아래 왼쪽 정렬', {'sig': d['sig'], 'h1': d['h1']})
            chk(d['sigStop'] - d['sigBtop'] >= 12, '두 줄이 한 줄씩(세로로)', [d['sigBtop'], d['sigStop']])
            chk(d['foot']['h'] == 0 and 'Built by LCP' not in d['footText'], '사이드바 아래 서명 없음',
                {'h': d['foot']['h'], 't': d['footText']})
            chk(d['footBorder'] in ('0px', None), '하단 빈 블록 구분선 없음', d['footBorder'])
            chk(d['sigOccurrences'] == 2, '서명은 화면에 한 벌만', d['sigOccurrences'])
            chk(d['top']['h'] == 64, '머리 64px', d['top']['h'])
            chk(d['side']['y'] == 78, '사이드바가 머리 바로 아래(78px)', d['side']['y'])
            chk(d['glabel']['y'] - d['side']['y'] == 11, '첫 메뉴 그룹 여백 11px',
                {'side': d['side']['y'], 'glabel': d['glabel']['y']})
            chk(d['docOver'] <= 0, '가로 넘침 0', d['docOver'])
            page.screenshot(path=os.path.join(OUT, 'pc-%d.png' % w))
            page.screenshot(path=os.path.join(OUT, 'pc-%d-brand.png' % w),
                            clip={'x': 0, 'y': 0, 'width': 400, 'height': 320})
            # 스크롤해도 사이드바가 머리에 가리지 않는지
            page.mouse.wheel(0, 600)
            page.wait_for_timeout(500)
            st = page.evaluate("""() => { const s = document.getElementById('v8Side').getBoundingClientRect();
                const t = document.querySelector('.top').getBoundingClientRect();
                return {sideTop: Math.round(s.top), topBottom: Math.round(t.bottom)}; }""")
            chk(st['sideTop'] >= st['topBottom'], '스크롤해도 사이드바가 머리 아래에 붙음', st)
            page.screenshot(path=os.path.join(OUT, 'pc-%d-scrolled.png' % w))
            page.mouse.wheel(0, -600)
            page.wait_for_timeout(300)
            ctx.close()

        # ---------- 로그인 화면(파란 M 은 그대로) ----------
        print('--- 로그인 화면 1920')
        ctx = b.new_context(viewport={'width': 1920, 'height': 1080}, device_scale_factor=1)
        page = ctx.new_page()
        page.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
        page.on('pageerror', lambda e: errors.append('login:%s' % e))
        page.goto(T.BASE + '?v=v63')
        page.wait_for_timeout(700)
        lg = page.evaluate("""() => { const l = document.querySelector('.login-brand .logo');
            if (!l) return {has:false}; const cs = getComputedStyle(l); const r = l.getBoundingClientRect();
            return {has:true, display: cs.display, w: Math.round(r.width), sig: !!document.querySelector('.login-brand .brandsig')}; }""")
        chk(lg['has'] and lg['display'] != 'none' and lg['w'] > 0, '로그인 화면 파란 M 그대로', lg)
        page.screenshot(path=os.path.join(OUT, 'login-1920.png'), clip={'x': 0, 'y': 0, 'width': 900, 'height': 500})
        ctx.close()

        # ---------- 폰 ----------
        print('--- 폰 390x844')
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2,
                            is_mobile=True, has_touch=True,
                            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 '
                                       '(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1')
        page = ctx.new_page()
        page.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
        page.add_init_script(T.FAKE_WS)
        page.on('pageerror', lambda e: errors.append('mob:%s' % e))
        login(page)
        m = page.evaluate(INFO)
        chk(m['logoVis'], '폰 상단 머리 파란 M 그대로', m['logoBox'])
        chk(not m['sigVis'], '폰에는 두 줄 없음(머리 52px 유지)')
        chk(m['top']['h'] in (50, 52), '폰 머리 높이 그대로(50px)', m['top']['h'])
        chk(m['docOver'] <= 0, '폰 가로 넘침 0', m['docOver'])
        page.screenshot(path=os.path.join(OUT, 'mob-390.png'))
        # 메뉴 시트 — 앱이 쓰는 것과 같은 body.sideopen 으로 연다
        page.evaluate("() => document.body.classList.add('sideopen')")
        page.wait_for_timeout(600)
        menu = page.evaluate("""() => { const s = document.getElementById('v8Side');
            const r = s.getBoundingClientRect(); const cs = getComputedStyle(s);
            const foot = document.querySelector('.sidefoot');
            return {open: cs.display !== 'none' && r.width > 0, w: Math.round(r.width), top: Math.round(r.top),
                    bottom: Math.round(r.bottom), vh: window.innerHeight,
                    footText: foot ? foot.innerText.replace(/\\s+/g,' ').trim() : '',
                    footH: foot ? Math.round(foot.getBoundingClientRect().height) : null,
                    over: Math.round(s.scrollWidth - s.clientWidth)}; }""")
        print('   menu:', menu)
        chk(menu['open'] and menu['w'] >= 280, '폰 메뉴 시트 열림', menu)
        chk('Built by LCP' not in menu['footText'] and (menu['footH'] or 0) == 0, '폰 메뉴 아래 서명 없음(빈 블록)',
            {'t': menu['footText'], 'h': menu['footH']})
        page.screenshot(path=os.path.join(OUT, 'mob-390-menu.png'))
        ctx.close()
        b.close()

    print('\nJS errors:', errors)
    chk(len(errors) == 0, 'JS 오류 0건', errors[:3])
    print('\n=== %s ===' % ('ALL OK' if ok else 'FAIL'))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
