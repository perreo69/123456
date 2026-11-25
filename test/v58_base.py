# -*- coding: utf-8 -*-
"""v58 기준선 — 지금(v57) 폰 390×844 화면이 어떻게 보이는지 재고, 넘침을 잰다.
   LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/v58_base.py before
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_ui as T
import shot_v36 as V36
from playwright.sync_api import sync_playwright

TAG = sys.argv[1] if len(sys.argv) > 1 else 'before'
OUT = '/workspace/downloads/erp-v58-화면/' + TAG
MOBILE = {'width': 390, 'height': 844}

OVER = """() => {
  const de = document.documentElement, b = document.body;
  const vw = window.innerWidth;
  const wide = [];
  document.querySelectorAll('body *').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) return;
    if (r.right > vw + 1.5) wide.push({ tag: el.tagName, cls: (el.className||'').toString().slice(0,60),
      id: el.id, right: Math.round(r.right), w: Math.round(r.width) });
  });
  const tw = document.getElementById('tableWrap');
  const wrapScroll = tw ? tw.scrollWidth - tw.clientWidth : null;
  const seen = new Set();
  const uniq = wide.filter(x => { const k = x.tag + '#' + x.id + '.' + x.cls;
    if (seen.has(k)) return false; seen.add(k); return true; });
  return { vw, docW: de.scrollWidth, bodyW: b.scrollWidth, overflowX: de.scrollWidth - vw,
    wrapScroll: wrapScroll, wide: uniq.slice(0, 12) };
}"""

SCREENS = [
    ('재고-원료육전체', 'stock:meat'),
    ('재고-냉동고', 'stock:meat:F'),
    ('재고-냉장고', 'stock:meat:C'),
    ('재고-완제품', 'stock:fg'),
    ('재고-부자재', 'stock:sub'),
    ('입출고내역', 'tx'),
    ('변경이력', 'audit'),
    ('품목관리', 'items'),
    ('전체재고', 'stock:all'),
]


def run(pw, mobile):
    env = dict(os.environ)
    libs = '/workspace/tool-results/chromelibs'
    if os.path.isdir(libs):
        env['LD_LIBRARY_PATH'] = libs + (':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    b = pw.chromium.launch(env=env)
    ctx = b.new_context(viewport=MOBILE if mobile else {'width': 1920, 'height': 1080},
                        is_mobile=mobile, has_touch=mobile, device_scale_factor=2 if mobile else 1) \
        if mobile else b.new_context(viewport={'width': 1920, 'height': 1080})
    page = ctx.new_page()
    errs = []
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
    page.add_init_script(T.FAKE_WS)
    V36.seed_items()
    page.goto(T.BASE + '?v=20261125_66')
    page.wait_for_timeout(400)
    page.fill('#liEmail', 'kim@meat.co.kr')
    page.fill('#liPw', 'secret123')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=8000)
    page.wait_for_timeout(2000)
    page.add_style_tag(content='#toast{display:none !important}')
    prefix = '폰-' if mobile else 'PC-'
    for name, nav in SCREENS:
        if mobile:
            page.evaluate("([n]) => document.querySelector('#v8Side [data-nav=\"' + n + '\"]').click()", [nav])
            page.wait_for_timeout(900)
        else:
            V36.open_view(page, nav, wait=900)
        info = page.evaluate(OVER)
        print(('  %-16s' % name), info)
        page.screenshot(path=os.path.join(OUT, prefix + name + '.png'))
    # 입고 팝업
    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"in\"]').click()")
    page.wait_for_timeout(1200)
    page.screenshot(path=os.path.join(OUT, prefix + '입고팝업.png'))
    print('  popup overflow', page.evaluate(OVER))
    print('  JS errors:', errs[:5])
    b.close()


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as pw:
        print('--- mobile 390x844 ---')
        run(pw, True)
    print('done', OUT)
