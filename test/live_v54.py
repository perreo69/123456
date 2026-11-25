# -*- coding: utf-8 -*-
"""v54 실서버 확인 (읽기 전용 — 저장·수정 버튼은 누르지 않는다)

  LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/live_v54.py [URL] [OUT_DIR]
"""
import os
import sys

os.environ.setdefault('LD_LIBRARY_PATH', '/workspace/tool-results/chromelibs')
from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else 'https://perreo69.github.io/123456/?v=20261125_62'
OUT = sys.argv[2] if len(sys.argv) > 2 else '/workspace/downloads/erp-v54-live'
os.makedirs(OUT, exist_ok=True)
errors, fails = [], []


def chk(cond, label, extra=''):
    print(('  [OK]   ' if cond else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not cond:
        fails.append(label)


def shot(page, name):
    page.wait_for_timeout(350)
    page.screenshot(path=os.path.join(OUT, name + '.png'))
    print('  shot', name)


def nav(page, key, wait=1500):
    page.evaluate("(k) => { const b = document.querySelector('#v8Side [data-nav=\"' + k + '\"]'); if (b) b.click(); }", key)
    page.wait_for_timeout(wait)


with sync_playwright() as pw:
    b = pw.chromium.launch(env=dict(os.environ))
    page = b.new_page(viewport={'width': 1920, 'height': 1080})
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('dialog', lambda d: d.dismiss())
    page.goto(BASE)
    page.wait_for_timeout(900)
    page.fill('#liEmail', 'perreo@nate.com')
    page.fill('#liPw', '123456')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=45000)
    page.wait_for_timeout(6000)

    src = page.evaluate("() => (document.querySelector('script[src*=\"app.js\"]') || {}).src || ''")
    chk('20261125_62' in src, '실서버 app.js 토큰 _62', src)
    chk(page.evaluate("() => !!document.querySelector('#v8Side [data-nav=\"audit\"]')"), '왼쪽 메뉴에 변경이력 있음')

    nav(page, 'audit', 2000)
    chk(page.evaluate("() => !document.getElementById('auditMode').classList.contains('hidden')"), '변경이력 화면 열림')
    chk(page.evaluate("() => document.getElementById('v8Title').textContent") == '변경이력', '제목 변경이력',
        page.evaluate("() => document.getElementById('v8Title').textContent"))
    chk(page.evaluate("() => document.getElementById('auditSqlNotice').classList.contains('hidden')") is False,
        'SQL 실행 전 — 안내 배너가 보인다')
    rows = page.evaluate("""() => Array.from(document.querySelectorAll('#auditTableWrap tbody tr')).map(tr => ({
        ts: (tr.children[0] || {}).innerText || '', type: (tr.children[1] || {}).innerText || '',
        target: (tr.children[2] || {}).innerText || '', summary: (tr.children[3] || {}).innerText || '',
        reason: (tr.children[4] || {}).innerText || '', actor: (tr.children[5] || {}).innerText || '' }))""")
    print('    실제 줄 %d개' % len(rows), [r['type'] for r in rows[:6]])
    chk(all(r['type'] in ('재고조정', '정보수정', '삭제') for r in rows), '구분 값이 셋 중 하나', set(r['type'] for r in rows))
    chk(any(r['type'] == '재고조정' for r in rows), '기존 [재고조정] 이력이 병합돼 보인다', len(rows))
    if rows:
        chk(any('→' in r['summary'] for r in rows), '전 → 후 표시', rows[0]['summary'][:60])
    chk(page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth") <= 0, '가로 넘침 0건',
        page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth"))
    chk(page.evaluate("() => document.querySelectorAll('#toast .tmsg').length") == 0, '오류 토스트 없음',
        page.evaluate("() => Array.from(document.querySelectorAll('#toast .tmsg')).map(x => x.textContent)"))
    shot(page, 'live-01-변경이력')

    # 필터 · 정렬 (읽기만)
    page.click('#auditTypeChips [data-atype="재고조정"]')
    page.wait_for_timeout(500)
    n1 = page.evaluate("() => document.querySelectorAll('#auditTableWrap tbody tr').length")
    page.click('#auditTypeChips [data-atype="all"]')
    page.wait_for_timeout(400)
    n2 = page.evaluate("() => document.querySelectorAll('#auditTableWrap tbody tr').length")
    chk(n1 <= n2, '구분 필터 동작', (n1, n2))
    page.click('#auditTableWrap th[data-col="ts"] button')
    page.wait_for_timeout(400)
    chk('▲' in page.inner_text('#auditTableWrap th[data-col="ts"]'), '머리글 클릭 정렬(▲)')
    page.click('#auditTableWrap th[data-col="ts"] button')
    page.click('#auditTableWrap th[data-col="ts"] button')
    page.wait_for_timeout(300)

    body = page.inner_text('body')
    chk('줄돈' not in body and '받을돈' not in body, '금지 용어(줄돈·받을돈) 0건')
    emo = page.evaluate("""() => {
        const re = /[\\u{1F300}-\\u{1FAFF}\\u{2600}-\\u{27BF}]/u;
        const out = [];
        document.querySelectorAll('#auditMode *, #v8Side [data-nav="audit"]').forEach(e => {
            if (e.children.length === 0 && re.test(e.textContent || '')) out.push(e.textContent.slice(0, 20));
        });
        return out; }""")
    chk(len(emo) == 0, '변경이력 화면 이모지 0건', emo)

    # 입출고 내역 → 변경이력 링크 (읽기만)
    nav(page, 'tx', 2000)
    chk(page.evaluate("() => !!document.getElementById('utxToAudit')"), '입출고 내역에 변경이력 링크 있음')
    chk(page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth") <= 0, '입출고 내역 가로 넘침 0건',
        page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth"))
    shot(page, 'live-02-입출고내역')

    # 폰 390
    m = b.new_page(viewport={'width': 390, 'height': 844})
    m.on('pageerror', lambda e: errors.append(str(e)))
    m.on('dialog', lambda d: d.dismiss())
    m.goto(BASE.replace('?v=', '?m=v') if False else BASE)
    m.wait_for_timeout(900)
    m.fill('#liEmail', 'perreo@nate.com')
    m.fill('#liPw', '123456')
    m.click('#btnLogin')
    m.wait_for_selector('#appView:not(.hidden)', timeout=45000)
    m.wait_for_timeout(5000)
    m.evaluate("() => { const b = document.querySelector('#qbList'); if (b) b.click(); }")
    m.wait_for_timeout(500)
    nav(m, 'audit', 1800)
    chk(m.evaluate("() => !document.getElementById('auditMode').classList.contains('hidden')"), '폰: 변경이력 화면 열림')
    chk(m.evaluate("() => document.documentElement.scrollWidth - window.innerWidth") <= 0, '폰 390 가로 넘침 0',
        m.evaluate("() => document.documentElement.scrollWidth - window.innerWidth"))
    shot(m, 'live-03-폰-변경이력')

    b.close()

print()
print('  JS 오류 %d건' % len(errors))
for e in errors[:8]:
    print('   -', e)
chk(len(errors) == 0, 'JS 오류 0건')
print()
if fails:
    print('실패 %d건:' % len(fails))
    for f in fails:
        print('  -', f)
    sys.exit(1)
print('전부 통과')
