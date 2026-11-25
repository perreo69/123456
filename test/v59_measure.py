# -*- coding: utf-8 -*-
"""v59 — 드롭다운 한 줄의 실제 높이·잘림을 잰다."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_ui as T
import shot_v36 as V36
from playwright.sync_api import sync_playwright

OUT = '/workspace/downloads/erp-v59-화면/measure'
os.makedirs(OUT, exist_ok=True)

with sync_playwright() as pw:
    env = dict(os.environ)
    libs = '/workspace/tool-results/chromelibs'
    if os.path.isdir(libs):
        env['LD_LIBRARY_PATH'] = libs + (':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    b = pw.chromium.launch(env=env)
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    page = ctx.new_page()
    page.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
    page.add_init_script(T.FAKE_WS)
    V36.seed_items()
    page.goto(T.BASE + '?v=20261125_67')
    page.wait_for_timeout(400)
    page.fill('#liEmail', 'kim@meat.co.kr')
    page.fill('#liPw', 'secret123')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=8000)
    page.wait_for_timeout(1600)
    page.add_style_tag(content='#toast{display:none !important}')
    page.click('#mobTabs [data-mtab="out"]')
    page.wait_for_timeout(400)
    page.click('#mobSheet [data-nav="out"]')
    page.wait_for_timeout(800)
    page.click('#ioSheetDestSeg button[data-dest="vendor"]')
    page.wait_for_timeout(200)
    page.click('#ioSheetPartner')
    page.type('#ioSheetPartner', '도드람', delay=80)
    page.wait_for_timeout(600)
    print(page.evaluate("""() => {
      const pop = document.querySelector('.acpop');
      const items = Array.from(pop.querySelectorAll('.acitem'));
      const info = items.map(it => {
        const a = it.querySelector('.act'), s = it.querySelector('.acs');
        const r = it.getBoundingClientRect(), ra = a ? a.getBoundingClientRect() : null, rs = s ? s.getBoundingClientRect() : null;
        return { h: Math.round(r.height), top: Math.round(r.top), bot: Math.round(r.bottom),
                 act: ra ? [Math.round(ra.height), Math.round(ra.top), Math.round(ra.bottom)] : null,
                 acs: rs ? [Math.round(rs.height), Math.round(rs.top), Math.round(rs.bottom)] : null,
                 acsLH: s ? getComputedStyle(s).lineHeight : '', acsFS: s ? getComputedStyle(s).fontSize : '',
                 acsOF: s ? getComputedStyle(s).overflow : '' };
      });
      const pr = pop.getBoundingClientRect();
      return { pop: [Math.round(pr.top), Math.round(pr.bottom), Math.round(pr.height)],
               clientH: pop.clientHeight, scrollH: pop.scrollHeight, maxH: getComputedStyle(pop).maxHeight,
               items: info };
    }"""))
    page.locator('.acpop').screenshot(path=os.path.join(OUT, 'pop.png'))
    b.close()
