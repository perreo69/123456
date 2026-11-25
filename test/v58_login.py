# -*- coding: utf-8 -*-
"""v58 폰 로그인 화면 확인"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_ui as T
from playwright.sync_api import sync_playwright
OUT = '/workspace/downloads/erp-v58-화면/final'
env = dict(os.environ); env['LD_LIBRARY_PATH'] = '/workspace/tool-results/chromelibs'
with sync_playwright() as pw:
    b = pw.chromium.launch(env=env)
    ctx = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    p = ctx.new_page()
    p.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
    p.goto(T.BASE + '?v=20261125_67')
    p.wait_for_timeout(1200)
    p.screenshot(path=os.path.join(OUT, 'M-로그인화면.png'))
    print('overflow', p.evaluate("() => document.documentElement.scrollWidth - window.innerWidth"))
    b.close()
