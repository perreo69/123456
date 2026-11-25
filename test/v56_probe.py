# -*- coding: utf-8 -*-
"""v56 진단 — 해동/냉동 팝업 탭 글자 잘림 실측 (로컬 스텁)

  LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/v56_probe.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('LD_LIBRARY_PATH', '/workspace/tool-results/chromelibs')
import shot_v54 as V
from playwright.sync_api import sync_playwright

MEASURE = r"""() => {
  const seg = document.getElementById('uniMoveSeg');
  const card = document.querySelector('#uniMoveModal .modal-card');
  const out = {card: null, seg: null, btns: []};
  if (!seg) return out;
  const box = el => { const r = el.getBoundingClientRect();
    return {w: +r.width.toFixed(1), h: +r.height.toFixed(1), l: +r.left.toFixed(1), r: +r.right.toFixed(1)}; };
  const cs = el => getComputedStyle(el);
  out.card = box(card);
  out.cardPad = cs(card).padding;
  out.seg = box(seg);
  out.segGrid = cs(seg).gridTemplateColumns;
  seg.querySelectorAll('button').forEach(b => {
    const c = cs(b);
    out.btns.push({text: b.textContent.trim(), box: box(b), sw: b.scrollWidth, cw: b.clientWidth,
      clipped: b.scrollWidth - b.clientWidth, fs: c.fontSize, pad: c.padding, ls: c.letterSpacing,
      ws: c.whiteSpace, ov: c.overflow, ff: c.fontFamily});
  });
  const sel = document.getElementById('uniMoveLot');
  out.lot = sel ? {tag: sel.tagName, box: box(sel), opts: sel.options.length} : null;
  return out;
}"""

with sync_playwright() as pw:
    b = pw.chromium.launch(env=dict(os.environ))
    for vw, vh, tag in [(1920, 1080, 'pc'), (1280, 800, 'mid'), (390, 844, 'ph')]:
        page = b.new_page(viewport={'width': vw, 'height': vh})
        page.add_init_script(V.FAKE_WS)
        page.route('**/gzufnyglmvgzqltepock.supabase.co/**', V.route_handler)
        V.login(page)
        page.evaluate("() => { const b = document.querySelector('#v8Side [data-nav=\"stock:meat\"]'); if (b) b.click(); }")
        page.wait_for_timeout(1800)
        # 로트 행 [작업] → 해동
        opened = page.evaluate("""() => {
          const t = document.querySelector('#uniTableWrap tbody tr.ulot .actmenu') ||
                    document.querySelector('tr.ulot .actmenu');
          if (t) { t.click(); return true; } return false;
        }""")
        page.wait_for_timeout(400)
        clicked = page.evaluate("""() => {
          const b = Array.from(document.querySelectorAll('#rowMenu button')).find(x => /이동/.test(x.textContent));
          if (b) { b.click(); return true; } return false;
        }""")
        page.wait_for_timeout(900)
        m = page.evaluate(MEASURE)
        print('==', tag, vw, 'ulot:', opened, '해동클릭:', clicked)
        print(json.dumps(m, ensure_ascii=False, indent=1))
        page.screenshot(path='/workspace/downloads/v56-before-%s.png' % tag)
        try:
            page.screenshot(path='/workspace/downloads/v56-before-%s-modal.png' % tag,
                            clip=page.evaluate("""() => { const r = document.querySelector('#uniMoveModal .modal-card').getBoundingClientRect();
                              return {x: Math.max(0, r.left - 8), y: Math.max(0, r.top - 8), width: Math.min(r.width + 16, innerWidth), height: Math.min(r.height + 16, innerHeight)}; }"""))
        except Exception as e:
            print('  clip shot 실패', e)
        page.close()
    b.close()
