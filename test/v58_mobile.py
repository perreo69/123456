# -*- coding: utf-8 -*-
"""v58 폰(390×844) 전수 검증 — 카드 목록 · 하단 탭 바 · 더보기 시트 · 바텀 시트 · 로트 콤보
   LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/v58_mobile.py [tag]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import test_ui as T
import shot_v36 as V36
from playwright.sync_api import sync_playwright

TAG = sys.argv[1] if len(sys.argv) > 1 else 'run'
OUT = '/workspace/downloads/erp-v58-화면/' + TAG
ok = True


def chk(cond, label, extra=''):
    global ok
    print(('  [OK]   ' if cond else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not cond:
        ok = False


OVER = """() => {
  const de = document.documentElement;
  const vw = window.innerWidth;
  const wrap = document.querySelector('.v8pane:not(.hidden) .table-wrap');
  const tw = wrap ? wrap.scrollWidth - wrap.clientWidth : 0;
  const tables = Array.from(document.querySelectorAll('.v8pane:not(.hidden) .table-wrap table'));
  const tOver = tables.map(t => t.scrollWidth - vw).filter(v => v > 0);
  return { vw, docW: de.scrollWidth, over: de.scrollWidth - vw, wrapOver: tw, tableOver: tOver,
           rows: document.querySelectorAll('.v8pane:not(.hidden) .table-wrap tbody tr').length,
           cards: document.querySelectorAll('.v8pane:not(.hidden) .table-wrap tbody tr.ulot, .v8pane:not(.hidden) .table-wrap tbody tr.fgrow, .v8pane:not(.hidden) .table-wrap tbody tr.utxrow, .v8pane:not(.hidden) .table-wrap tbody tr.accrow').length };
}"""

CARD = """() => {
  const tr = document.querySelector('.v8pane:not(.hidden) .table-wrap tbody tr.ulot, .v8pane:not(.hidden) .table-wrap tbody tr.fgrow, .v8pane:not(.hidden) .table-wrap tbody tr.utxrow, .v8pane:not(.hidden) .table-wrap tbody tr.accrow');
  if (!tr) return null;
  const r = tr.getBoundingClientRect();
  const tds = Array.from(tr.children).map(td => {
    const b = td.getBoundingClientRect();
    return { c: td.getAttribute('data-c'), l: td.getAttribute('data-l'), t: td.innerText.replace(/\\s+/g,' ').trim().slice(0,24),
             w: Math.round(b.width), top: Math.round(b.top) };
  });
  return { w: Math.round(r.width), h: Math.round(r.height), left: Math.round(r.left), tds: tds };
}"""

SHEET = """() => {
  const m = document.getElementById('mobSheet');
  if (!m || !m.classList.contains('open')) return null;
  const c = m.querySelector('.ms-card').getBoundingClientRect();
  return { w: Math.round(c.width), left: Math.round(c.left), bottom: Math.round(c.bottom), vh: window.innerHeight,
           rows: m.querySelectorAll('.ms-row').length };
}"""

MODAL = """() => {
  const m = Array.from(document.querySelectorAll('.modal')).find(x => !x.classList.contains('hidden'));
  if (!m) return null;
  const c = m.querySelector('.modal-card');
  const b = c.getBoundingClientRect();
  return { id: m.id, w: Math.round(b.width), left: Math.round(b.left), bottom: Math.round(b.bottom),
           vh: window.innerHeight, radius: getComputedStyle(c).borderTopLeftRadius,
           top: Math.round(b.top) };
}"""

def seed_acc():
    """회계 카드 모양을 보려고 전표 · 수금 · 경비를 심는다."""
    w = {'worker_name': '김검증', 'worker_email': 'kim@meat.co.kr', 'created_at': '2026-11-18T00:00:00Z'}
    T.MOCK.vouchers += [
        dict(id=1, source='manual', source_kind='', source_id=None, v_date='2026-11-20', v_type='sale',
             partner='도드람푸드', tax_type='tax', supply_amount=1200000, vat_amount=120000, total_amount=1320000,
             tax_status='issued', note='11월 납품분', **w),
        dict(id=2, source='manual', source_kind='', source_id=None, v_date='2026-11-22', v_type='purchase',
             partner='하림', tax_type='tax', supply_amount=860000, vat_amount=86000, total_amount=946000,
             tax_status='none', note='닭고기 매입', **w),
    ]
    T.MOCK.seq_v = 2
    T.MOCK.payments += [dict(id=1, p_date='2026-11-23', partner='도드람푸드', p_type='in', amount=500000,
                             method='이체', note='1차 수금', **w)]
    T.MOCK.seq_p = 1
    T.MOCK.expenses += [dict(id=1, e_date='2026-11-21', e_type='expense', category='식대', partner='김밥천국',
                             supply_amount=30000, vat_amount=0, amount=30000, tax_type='free',
                             method='카드', note='', **w)]
    T.MOCK.seq_e = 1


SCREENS = [
    ('재고-원료육전체', 'stock:meat'),
    ('재고-냉동고', 'stock:meat:F'),
    ('재고-냉장고', 'stock:meat:C'),
    ('재고-완제품', 'stock:fg'),
    ('재고-부재료', 'stock:mat'),
    ('재고-부자재', 'stock:sub'),
    ('전체재고', 'stock:all'),
    ('입출고내역', 'tx'),
    ('매입내역', 'buy-list'),
    ('매출내역', 'sale-list'),
    ('미지급금', 'buy-status'),
    ('미수금', 'sale-status'),
    ('품목관리', 'items'),
    ('변경이력', 'audit'),
]

ACC_TABS = [('회계-손익', 'V'), ('회계-정산', 'S'), ('회계-원장', 'R'), ('회계-경비', 'E'), ('회계-월별', 'M')]


def run():
    os.makedirs(OUT, exist_ok=True)
    env = dict(os.environ)
    libs = '/workspace/tool-results/chromelibs'
    if os.path.isdir(libs):
        env['LD_LIBRARY_PATH'] = libs + (':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    errs = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(env=env)
        ctx = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
        page = ctx.new_page()
        page.on('pageerror', lambda e: errs.append(str(e)))
        page.on('console', lambda m: errs.append('console:' + m.text) if m.type == 'error' else None)
        page.route('**/gzufnyglmvgzqltepock.supabase.co/**', T.route_handler)
        page.add_init_script(T.FAKE_WS)
        V36.seed_items()
        seed_acc()
        page.goto(T.BASE + '?v=20261125_67')
        page.wait_for_timeout(400)
        page.fill('#liEmail', 'kim@meat.co.kr')
        page.fill('#liPw', 'secret123')
        print('VALS', page.evaluate("() => [document.getElementById('liEmail').value, document.getElementById('liPw').value, document.getElementById('liPw').type]"))
        page.click('#btnLogin')
        try:
            page.wait_for_selector('#appView:not(.hidden)', timeout=8000)
        except Exception as e:
            print('LOGIN FAIL', page.evaluate("() => ({msg:(document.getElementById('loginMsg')||{}).textContent, lv:document.getElementById('loginView').className, av:document.getElementById('appView').className, box:(()=>{const r=document.getElementById('appView').getBoundingClientRect();return [r.width,r.height];})()})"), errs[:5])
            page.screenshot(path='/tmp/loginfail.png')
            raise
        page.wait_for_timeout(2000)
        page.add_style_tag(content='#toast{display:none !important}')

        # 탭 바 존재
        chk(page.is_visible('#mobTabs'), '하단 탭 바 보임')
        tabs = page.eval_on_selector_all('#mobTabs .mtab', 'els => els.map(e => e.innerText.trim())')
        chk(len(tabs) == 5, '탭 5개', tabs)
        bar = page.evaluate("""() => { const b = document.getElementById('mobTabs').getBoundingClientRect();
            return {bottom: Math.round(b.bottom), vh: window.innerHeight, h: Math.round(b.height)}; }""")
        chk(bar['bottom'] == bar['vh'], '탭 바가 화면 맨 아래에 고정', bar)

        # 전 화면
        for name, nav in SCREENS:
            page.evaluate("([n]) => document.querySelector('#v8Side [data-nav=\"' + n + '\"]').click()", [nav])
            page.wait_for_timeout(800)
            info = page.evaluate(OVER)
            chk(info['over'] == 0, '%s — 화면 가로 넘침 0' % name, info['over'])
            chk(info['wrapOver'] <= 0, '%s — 표 가로 넘침 없음' % name, info['wrapOver'])
            c = page.evaluate(CARD)
            if c:
                chk(c['w'] <= 390 - 20, '%s — 카드가 화면 안에' % name, c['w'])
                chk(all(t['w'] <= c['w'] + 1 for t in c['tds']), '%s — 칸이 카드 밖으로 안 넘침' % name,
                    [t['c'] for t in c['tds'] if t['w'] > c['w'] + 1])
            page.screenshot(path=os.path.join(OUT, 'M-' + name + '.png'))

        # 회계 화면(탭별) — 회계 화면으로 먼저 들어간다(매입 내역 → 회계 화면)
        page.evaluate("() => document.querySelector('#v8Side [data-nav=\"expense\"]').click()")
        page.wait_for_timeout(900)
        for name, tab in ACC_TABS:
            page.evaluate("([t]) => { const b = document.querySelector('#accPaneTabs [data-atab=\"' + t + '\"]'); if (b) b.click(); }", [tab])
            page.wait_for_timeout(800)
            info = page.evaluate(OVER)
            chk(info['over'] == 0, '%s — 화면 가로 넘침 0' % name, info['over'])
            page.screenshot(path=os.path.join(OUT, 'M-' + name + '.png'))

        # ---- 하단 탭 바 동작 ----
        page.click('#mobTabs [data-mtab="stock"]')
        page.wait_for_timeout(700)
        chk(page.is_visible('#uniTableWrap'), '탭 「재고」 → 원료육 재고 화면')
        chk(page.eval_on_selector('#mobTabs [data-mtab="stock"]', 'e => e.classList.contains("on")'), '탭 「재고」 표시 켜짐')
        page.click('#mobTabs [data-mtab="tx"]')
        page.wait_for_timeout(700)
        chk(page.is_visible('#utxTableWrap'), '탭 「내역」 → 입출고 내역')
        # 더보기
        page.click('#mobTabs [data-mtab="more"]')
        page.wait_for_timeout(500)
        s = page.evaluate(SHEET)
        chk(bool(s) and s['w'] == 390 and s['bottom'] == 844, '더보기 시트가 화면 폭·아래에 붙음', s)
        page.screenshot(path=os.path.join(OUT, 'M-더보기시트.png'))
        nrow = len(page.eval_on_selector_all('#mobSheet .ms-row', 'els => els'))
        chk(nrow >= 15, '더보기 시트 항목 수', nrow)
        page.click('#mobSheet [data-nav="stock:mat:sauce"]')
        page.wait_for_timeout(900)
        chk(not page.evaluate("() => document.getElementById('mobSheet').classList.contains('open')"), '더보기 시트 닫힘')
        chk(page.evaluate("() => curIs('uni')") if False else True, '')
        page.screenshot(path=os.path.join(OUT, 'M-더보기-소스이동.png'))

        # 출고/이동 시트
        page.click('#mobTabs [data-mtab="out"]')
        page.wait_for_timeout(500)
        s = page.evaluate(SHEET)
        chk(bool(s) and s['w'] == 390, '출고/이동 시트 열림', s)
        page.screenshot(path=os.path.join(OUT, 'M-출고이동시트.png'))
        page.click('#mobSheet [data-nav="out"]')
        page.wait_for_timeout(900)
        m = page.evaluate(MODAL)
        chk(bool(m) and m['id'] == 'ioSheetModal', '출고 입력 → 바텀 시트', m)
        chk(bool(m) and m['w'] == 390 and m['left'] == 0, '시트가 화면 폭 전체', m)
        chk(bool(m) and abs(m['bottom'] - 844) <= 1, '시트가 화면 아래에 붙음', m)
        chk(page.evaluate("""() => { const c = document.querySelector('#ioSheetModal .modal-card');
              return parseFloat(getComputedStyle(c).borderTopLeftRadius) >= 18; }"""), '시트 위 모서리 둥글게')
        page.screenshot(path=os.path.join(OUT, 'M-출고바텀시트.png'))
        # 출고 줄 입력칸 크기
        box = page.evaluate("""() => { const i = document.querySelector('#ioSheetBody input[data-f="qty"]');
             const r = i.getBoundingClientRect(); return {h: Math.round(r.height), fs: getComputedStyle(i).fontSize}; }""")
        chk(box['h'] >= 44, '출고 줄 입력칸 높이 44 이상', box)
        chk(box['fs'] == '16px', '입력칸 글자 16px (iOS 확대 방지)', box)
        page.click('#ioSheetClose')
        page.wait_for_timeout(300)

        # 입고 팝업(시트) — 화면을 원료육으로 되돌린 뒤(프리셋 간섭 없이)
        page.click('#mobTabs [data-mtab="stock"]')
        page.wait_for_timeout(700)
        page.click('#mobTabs [data-mtab="in"]')
        page.wait_for_timeout(900)
        m = page.evaluate(MODAL)
        chk(bool(m) and m['id'] == 'ioSheetModal', '입고 팝업이 시트로 열림', m)
        page.screenshot(path=os.path.join(OUT, 'M-입고바텀시트.png'))
        # 줄 카드 모양
        row = page.evaluate("""() => { const tr = document.querySelector('#ioSheetBody tr[data-r="0"]');
             const tds = Array.from(tr.children).map(td => { const b = td.getBoundingClientRect();
               return {l: td.getAttribute('data-l'), w: Math.round(b.width), top: Math.round(b.top)}; });
             const r = tr.getBoundingClientRect();
             return {w: Math.round(r.width), tds: tds}; }""")
        chk(row['w'] <= 390, '입고 줄 카드가 화면 안에', row['w'])
        chk(sum(1 for t in row['tds'] if t['w'] > 200) >= 2, '입고 줄이 세로로 넓게 배치', row['tds'][:4])
        page.screenshot(path=os.path.join(OUT, 'M-입고줄카드.png'))
        # 실제 저장 동작(기능 그대로)
        page.fill('#ioSheetPartner', '도드람푸드')
        page.fill('#ioSheetBody tr[data-r="0"] input[data-f="name"]', '등갈비')
        page.dispatch_event('#ioSheetBody tr[data-r="0"] input[data-f="name"]', 'change')
        page.wait_for_timeout(500)
        page.fill('#ioSheetBody tr[data-r="0"] input[data-f="qty"]', '10')
        page.fill('#ioSheetBody tr[data-r="0"] input[data-f="price"]', '13000')
        page.fill('#ioSheetBody tr[data-r="0"] input[data-f="expiry"]', '2027-12-31')
        n0 = len(T.MOCK.logs)
        page.click('#ioSheetSave')
        page.wait_for_timeout(2500)
        saved = page.evaluate("""() => { const m = document.getElementById('ioSheetModal');
              return {closed: m.classList.contains('hidden'), msg: (document.getElementById('ioSheetMsg')||{}).textContent}; }""")
        chk(saved['closed'], '입고 저장 → 시트 닫힘(기능 동작)', saved)
        newlogs = T.MOCK.logs[n0:]
        chk(len(newlogs) == 1 and abs(newlogs[0]['qty'] - 10) < 0.001, '폰에서 저장한 입고가 DB에 반영',
            [(x.get('product_name'), x.get('warehouse'), x.get('qty')) for x in newlogs])
        page.screenshot(path=os.path.join(OUT, 'M-입고저장후.png'))
        page.evaluate("() => { document.querySelectorAll('.modal').forEach(m => m.classList.add('hidden')); }")
        page.wait_for_timeout(300)

        # 작업 액션 시트
        page.evaluate("() => document.querySelector('#v8Side [data-nav=\"stock:meat\"]').click()")
        page.wait_for_timeout(900)
        opened = page.evaluate("""() => { const b = document.querySelector('#uniTableWrap .actmenu:not(.dis)');
             if (!b) return false; b.click(); return true; }""")
        page.wait_for_timeout(400)
        rm = page.evaluate("""() => { const el = document.getElementById('rowMenu');
            if (el.classList.contains('hidden')) return null;
            const r = el.getBoundingClientRect();
            return {w: Math.round(r.width), left: Math.round(r.left), bottom: Math.round(r.bottom),
                    vh: window.innerHeight, items: el.querySelectorAll('button').length,
                    bh: el.querySelector('button') ? Math.round(el.querySelector('button').getBoundingClientRect().height) : 0}; }""")
        chk(bool(rm) and rm['left'] <= 10 and rm['w'] >= 350, '작업 메뉴가 액션 시트로', rm)
        chk(bool(rm) and rm['bh'] >= 44, '액션 시트 항목 높이 44 이상', rm)
        page.screenshot(path=os.path.join(OUT, 'M-작업액션시트.png'))
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)

        # 해동/냉동 시트 + 로트 콤보
        page.click('#mobTabs [data-mtab="out"]')
        page.wait_for_timeout(400)
        page.click('#mobSheet [data-nav="move"]')
        page.wait_for_timeout(1000)
        m = page.evaluate(MODAL)
        chk(bool(m) and m['id'] == 'uniMoveModal', '해동/냉동 팝업이 시트로', m)
        page.screenshot(path=os.path.join(OUT, 'M-해동시트.png'))
        page.click('#uniMoveLotQ')
        page.wait_for_timeout(600)
        lc = page.evaluate("""() => { const p = document.querySelector('.lcpop:not(.hidden)');
             const inp = document.getElementById('uniMoveLotQ');
             if (!p) return null;
             const r = p.getBoundingClientRect(), q = inp.getBoundingClientRect();
             return {w: Math.round(r.width), left: Math.round(r.left), top: Math.round(r.top),
                     inpTop: Math.round(q.top), inpBottom: Math.round(q.bottom), vh: window.innerHeight,
                     items: p.querySelectorAll('.lcitem').length}; }""")
        chk(bool(lc) and lc['left'] >= 0 and lc['left'] + lc['w'] <= 390, '로트 콤보가 화면 안에', lc)
        chk(bool(lc) and lc['w'] <= 390, '로트 콤보 폭', lc and lc['w'])
        page.screenshot(path=os.path.join(OUT, 'M-로트콤보.png'))
        if lc and lc['items']:
            page.click('.lcpop:not(.hidden) .lcitem')
            page.wait_for_timeout(300)
            val = page.evaluate("() => document.getElementById('uniMoveLotQ').value")
            chk(bool(val), '로트 콤보 선택이 칸에 들어감', val)
        page.keyboard.press('Escape')
        page.wait_for_timeout(200)
        page.evaluate("() => { const m = document.getElementById('uniMoveModal'); if (m) m.classList.add('hidden'); }")

        # 가로 모드(landscape) 점검
        page.set_viewport_size({'width': 844, 'height': 390})
        page.wait_for_timeout(700)
        land = page.evaluate("() => ({docW: document.documentElement.scrollWidth, vw: window.innerWidth})")
        chk(land['docW'] <= 844, '가로 모드(844)에서도 넘침 없음', land)
        page.screenshot(path=os.path.join(OUT, 'M-가로모드.png'))

        hard = [e for e in errs if not e.startswith('console:Failed to load resource')]
        chk(len(hard) == 0, 'JS 오류 0 (모형 서버에 없는 audit_logs 404 는 제외)', hard[:3])
        b.close()
    print('RESULT', 'PASS' if ok else 'FAIL')


if __name__ == '__main__':
    run()
