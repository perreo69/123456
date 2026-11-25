# -*- coding: utf-8 -*-
"""v60 PC — 입고/출고 팝업에서 «사라진 AI 버튼» 말고 달라진 것이 있는지 요소 단위로 본다."""
import os
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_ui as T
import shot_v36 as V36
from playwright.sync_api import sync_playwright

OLD = '/workspace/work/_v60pc'
NEW = '/workspace/work/erp-web'
GEOM = """() => {
  const out = {};
  const g = (sel) => { const e = document.querySelector(sel); if (!e) return null;
    const r = e.getBoundingClientRect();
    return [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]; };
  ['#ioSheetModal .modal-card', '#ioSheetDestSeg', '.vhead', '#ioSheetDate', '#ioSheetPartner',
   '#ioSheetNote', '.iosdest', '#ioSheetWrap', '#ioSheetTable', '#ioSheetBody tr[data-r="0"]',
   '#ioSheetBody tr[data-r="0"] td[data-cell="lot"]', '#ioSheetBody tr[data-r="0"] td[data-f="qty"]',
   '.modal-actions', '#ioSheetSave', '#ioSheetCancel', '#ioSheetAdd', '#ioBulkUpload', '#ioBulkTemplate',
   '.minfo', '#ioSheetHint', '.vsheetbar'].forEach(s => { out[s] = g(s); });
  out._ths = Array.from(document.querySelectorAll('#ioSheetTable thead th')).map(th => Math.round(th.getBoundingClientRect().width));
  return out;
}"""


def serve(root):
    class H(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=root, **kw)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(('127.0.0.1', 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


def login(page):
    page.fill('#liEmail', 'kim@meat.co.kr')
    page.fill('#liPw', 'secret123')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=8000)
    page.wait_for_timeout(2200)
    page.add_style_tag(content='#toast{display:none!important}*{transition:none!important;animation:none!important}')


def shot(page, base, kind):
    page.goto(base + '?v=20261126_69')
    page.wait_for_timeout(400)
    login(page)
    page.evaluate("() => document.querySelector('#v8Side [data-nav=\"%s\"]').click()" % kind)
    page.wait_for_timeout(1200)
    return page.evaluate(GEOM)


env = dict(os.environ)
libs = '/workspace/tool-results/chromelibs'
if os.path.isdir(libs):
    env['LD_LIBRARY_PATH'] = libs + (':' + env.get('LD_LIBRARY_PATH', ''))
V36.seed_items()
po, pn = serve(OLD), serve(NEW)
ok = True
with sync_playwright() as pw:
    b = pw.chromium.launch(env=env)
    for w, h in [(1920, 1080), (1440, 900), (1366, 768)]:
        for kind in ('out', 'in'):
            res = {}
            for tag, port in (('old', po), ('new', pn)):
                ctx = b.new_context(viewport={'width': w, 'height': h})
                page = ctx.new_page()
                page.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
                page.add_init_script(T.FAKE_WS)
                res[tag] = shot(page, 'http://127.0.0.1:%d/index.html' % port, kind)
                if tag == 'new':
                    page.screenshot(path='/workspace/downloads/erp-v60-화면/pc/%dx%d-%s-팝업.png' % (w, h, kind))
                ctx.close()
            diffs = []
            for k in res['old']:
                if res['old'][k] != res['new'][k]:
                    diffs.append((k, res['old'][k], res['new'][k]))
            print('== %dx%d %s ==' % (w, h, kind))
            for d in diffs:
                print('   DIFF', d)
            # 표·칸·저장 버튼은 그대로여야 한다
            must = ['#ioSheetBody tr[data-r="0"]', '#ioSheetBody tr[data-r="0"] td[data-cell="lot"]',
                    '.modal-actions', '#ioSheetSave', '#ioSheetCancel', '.vhead', '#ioSheetDate']
            bad = [d for d in diffs if d[0] in must]
            if bad:
                ok = False
                print('   [FAIL] 핵심 요소 위치가 달라짐')
            else:
                print('   [OK] 표·칸·버튼·머리 3칸 위치 그대로')
            if res['old']['_ths'] != res['new']['_ths']:
                ok = False
                print('   [FAIL] 열 폭 달라짐', res['old']['_ths'], res['new']['_ths'])
    b.close()
print('RESULT', 'PASS' if ok else 'FAIL')
