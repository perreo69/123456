# -*- coding: utf-8 -*-
"""v62 사전 측정 — PC 입고 팝업 표의 지금(원산지·브랜드 칸 없음) 기하를 잰다(로컬 스텁).
   LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/v62_probe.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_ui as T
import shot_v36 as V36
from playwright.sync_api import sync_playwright

GEOM = """() => {
  const w = document.querySelector('#ioSheetWrap .vsheet-scroll');
  const tb = document.getElementById('ioSheetTable');
  const ths = [...tb.querySelectorAll('thead th')].map(th => Math.round(th.getBoundingClientRect().width));
  const card = document.querySelector('#ioSheetModal .modal-card');
  const tr = document.querySelector('#ioSheetBody tr');
  return { card: Math.round(card.getBoundingClientRect().width),
           table: Math.round(tb.getBoundingClientRect().width),
           box: w ? Math.round(w.clientWidth) : -1,
           scroll: w ? Math.round(w.scrollWidth) : -1,
           ths: ths, rowH: tr ? Math.round(tr.getBoundingClientRect().height) : 0,
           inputs: tr ? tr.querySelectorAll('input,select').length : 0 };
}"""


def main():
    env = dict(os.environ)
    libs = '/workspace/tool-results/chromelibs'
    if os.path.isdir(libs):
        env['LD_LIBRARY_PATH'] = libs
    with sync_playwright() as pw:
        b = pw.chromium.launch(env=env)
        for vw in (1920, 1440, 1366):
            page = b.new_page(viewport={'width': vw, 'height': 900})
            page.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
            page.add_init_script(T.FAKE_WS)
            V36.seed_items()
            page.goto(T.BASE + '?v=20261126_70')
            page.fill('#liEmail', 'kim@meat.co.kr')
            page.fill('#liPw', 'secret123')
            page.click('#btnLogin')
            page.wait_for_selector('#appView:not(.hidden)', timeout=8000)
            page.wait_for_timeout(1800)
            page.evaluate("() => document.querySelector('#v8Side [data-nav=\"in\"]').click()")
            page.wait_for_timeout(900)
            print(vw, json.dumps(page.evaluate(GEOM), ensure_ascii=False))
            page.close()
        b.close()


main()
