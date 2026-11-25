# -*- coding: utf-8 -*-
"""v54 검증 — 변경이력 화면 + 모든 수정·삭제 기록 (스텁 Supabase · 실제 DB 무접촉)

  LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/shot_v54.py [OUT_DIR]

· 로컬 work/erp-web 을 그대로 띄우고 supabase 요청만 파이썬 더미로 받는다.
· 실제 Supabase(알전각 등)는 읽지도 쓰지도 않는다.
· audit_logs 표가 있을 때 / 없을 때(SQL 미실행) 두 경우를 모두 확인한다.
"""
import json
import os
import sys
import threading
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

os.environ.setdefault('LD_LIBRARY_PATH', '/workspace/tool-results/chromelibs')
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else '/workspace/downloads/erp-v54-stub'
os.makedirs(OUT, exist_ok=True)

errors, fails = [], []


def chk(cond, label, extra=''):
    print(('  [OK]   ' if cond else '  [FAIL] ') + label + (('  ' + str(extra)) if extra != '' else ''))
    if not cond:
        fails.append(label)


# ---------------------------------------------------------------------------
# 가짜 Supabase (메모리 표)
# ---------------------------------------------------------------------------
class Mock:
    def __init__(self):
        self.lock = threading.Lock()
        self.audit_on = True          # False 로 두면 audit_logs 표가 없는 DB(SQL 미실행)를 흉내낸다
        self.seq = {'lots': 3, 'tx_logs': 2, 'fp_lots': 1, 'fp_logs': 0, 'audit_logs': 0}
        self.lots = [
            {'id': 1, 'product_name': '알전각', 'meat_type': '돈육', 'origin': '국내',
             'vendor': '테드스토리', 'brand': 'TEYS', 'in_date': '2026-11-10',
             'exp_date': '2027-09-09', 'frozen_qty': 699.84, 'chilled_qty': 0.0,
             'unit_price': 9500.0, 'major_category': '원료육',
             'created_at': '2026-11-10T00:00:00Z', 'updated_at': '2026-11-10T00:00:00Z'},
            {'id': 2, 'product_name': '목전지', 'meat_type': '돈육', 'origin': '국내',
             'vendor': '테드스토리', 'brand': 'TEYS', 'in_date': '2026-11-12',
             'exp_date': '2027-08-01', 'frozen_qty': 120.0, 'chilled_qty': 0.0,
             'unit_price': 8700.0, 'major_category': '원료육',
             'created_at': '2026-11-12T00:00:00Z', 'updated_at': '2026-11-12T00:00:00Z'},
            {'id': 3, 'product_name': '삼겹살', 'meat_type': '돈육', 'origin': '국내',
             'vendor': '한돈', 'brand': '', 'in_date': '2026-11-14',
             'exp_date': '2027-07-01', 'frozen_qty': 0.0, 'chilled_qty': 45.0,
             'unit_price': 13200.0, 'major_category': '원료육',
             'created_at': '2026-11-14T00:00:00Z', 'updated_at': '2026-11-14T00:00:00Z'},
        ]
        self.logs = [
            {'id': 1, 'tx_date': '2026-11-10', 'tx_type': 'in', 'warehouse': 'F', 'lot_id': 1,
             'product_name': '알전각', 'major_category': '원료육', 'meat_type': '돈육',
             'vendor': '테드스토리', 'in_date': '2026-11-10', 'exp_date': '2027-09-09',
             'qty': 699.84, 'dest_type': '', 'dest_detail': '', 'note': '',
             'unit_price': 9500.0, 'total_amount': 6648480.0, 'trade_type': 'purchase',
             'settle_status': 'unsettled', 'tax_invoice_status': 'none',
             'worker_email': 'perreo@nate.com', 'worker_name': '박한솔', 'is_manual': True,
             'created_at': '2026-11-10T00:00:00Z'},
            {'id': 2, 'tx_date': '2026-11-12', 'tx_type': 'in', 'warehouse': 'F', 'lot_id': 2,
             'product_name': '목전지', 'major_category': '원료육', 'meat_type': '돈육',
             'vendor': '테드스토리', 'in_date': '2026-11-12', 'exp_date': '2027-08-01',
             'qty': 120.0, 'dest_type': '', 'dest_detail': '', 'note': '',
             'unit_price': 8700.0, 'total_amount': 1044000.0, 'trade_type': 'purchase',
             'settle_status': 'unsettled', 'tax_invoice_status': 'none',
             'worker_email': 'perreo@nate.com', 'worker_name': '박한솔', 'is_manual': True,
             'created_at': '2026-11-12T00:00:00Z'},
        ]
        self.fp_products = [
            {'code': '0000000896', 'category': '완제품', 'name': '일식커리소스-Y 1kg',
             'spec': '1kg*8팩', 'unit': '팩', 'stock': 0.0, 'in_price': 5630.0,
             'out_price': 7000.0, 'expiry': '2027-10-14', 'supplier': '', 'barcode': '',
             'active': True, 'updated_at': '2026-11-18T00:00:00Z'},
            {'code': '0000001884', 'category': '완제품', 'name': '찢은닭가슴살 5kg',
             'spec': '5kg*2팩', 'unit': '팩', 'stock': 64.0, 'in_price': 12000.0,
             'out_price': 15000.0, 'expiry': '2027-11-14', 'supplier': '자체생산', 'barcode': '',
             'active': True, 'updated_at': '2026-11-18T00:00:00Z'},
        ]
        self.fp_lots = [
            {'id': 1, 'code': '0000001884', 'lot_no': '이월-0000001884', 'category': '완제품',
             'name': '찢은닭가슴살 5kg', 'spec': '5kg*2팩', 'unit': '팩',
             'in_date': '2026-11-01', 'exp_date': '2027-11-14', 'qty': 64.0,
             'in_price': 12000.0, 'out_price': 0.0, 'supplier': '자체생산', 'memo': 'wh:F',
             'created_at': '2026-11-18T00:00:00Z', 'updated_at': '2026-11-18T00:00:00Z'},
        ]
        self.fp_logs = []
        self.audit = []
        self.acc = {'acc_vouchers': [], 'acc_payments': [], 'acc_expenses': []}
        self.photos = []
        self.tokens = {}

    def table(self, name):
        if name == 'audit_logs':
            return self.audit if self.audit_on else None
        return {
            'lots': self.lots, 'tx_logs': self.logs, 'fp_products': self.fp_products,
            'fp_lots': self.fp_lots, 'fp_logs': self.fp_logs,
            'acc_vouchers': self.acc['acc_vouchers'], 'acc_payments': self.acc['acc_payments'],
            'acc_expenses': self.acc['acc_expenses'], 'inbound_photos': self.photos,
        }.get(name)

    def next_id(self, name):
        self.seq[name] = self.seq.get(name, 0) + 1
        return self.seq[name]

    # ---- 호출 ----
    def handle(self, request):
        u = urllib.parse.urlparse(request.url)
        path, method = u.path, request.method
        qs = urllib.parse.parse_qs(u.query)
        body = {}
        if request.post_data:
            try:
                body = json.loads(request.post_data)
            except Exception:
                body = {}

        if method == 'OPTIONS':
            return 204, '', {}
        if path == '/auth/v1/token':
            tok = 'tok_%d' % (len(self.tokens) + 1)
            email = body.get('email', 'test@example.com')
            self.tokens[tok] = {'email': email, 'name': '박한솔', 'id': 'u-1'}
            return 200, {'access_token': tok, 'token_type': 'bearer', 'expires_in': 3600,
                         'refresh_token': 'ref_' + tok,
                         'user': {'id': 'u-1', 'email': email, 'user_metadata': {'name': '박한솔'}}}, {}
        if path == '/auth/v1/user':
            return 200, {'id': 'u-1', 'email': 'perreo@nate.com',
                         'user_metadata': {'name': '박한솔'}}, {}
        if path == '/auth/v1/logout':
            return 204, '', {}

        if path.startswith('/rest/v1/rpc/'):
            fn = path.rsplit('/', 1)[-1]
            with self.lock:
                if fn == 'lot_update':
                    lot = next((x for x in self.lots if x['id'] == body.get('p_lot_id')), None)
                    if lot is None:
                        return 400, {'message': '해당 로트를 찾을 수 없습니다.'}, {}
                    for key, col in (('p_meat', 'meat_type'), ('p_name', 'product_name'),
                                     ('p_brand', 'brand'), ('p_origin', 'origin'),
                                     ('p_vendor', 'vendor'), ('p_unit_price', 'unit_price'),
                                     ('p_in_date', 'in_date'), ('p_exp_date', 'exp_date')):
                        if body.get(key) is not None:
                            lot[col] = body[key]
                    lot['updated_at'] = '2026-11-25T01:00:00Z'
                    return 200, lot, {}
                if fn == 'tx_undo':
                    lg = next((x for x in self.logs if x['id'] == body.get('p_log_id')), None)
                    if lg is None:
                        return 400, {'message': '해당 이력을 찾을 수 없습니다.'}, {}
                    lot = next((x for x in self.lots if x['id'] == lg['lot_id']), None)
                    if lot is not None and lg['tx_type'] == 'in':
                        if lg['warehouse'] == 'C':
                            lot['chilled_qty'] = round(lot['chilled_qty'] - lg['qty'], 3)
                        else:
                            lot['frozen_qty'] = round(lot['frozen_qty'] - lg['qty'], 3)
                    self.logs.remove(lg)
                    return 200, lg, {}
                if fn == 'fp_product_save':
                    code = body.get('p_code') or ''
                    p = next((x for x in self.fp_products if x['code'] == code), None)
                    if p is None:
                        p = {'code': code, 'stock': 0.0, 'barcode': '', 'updated_at': ''}
                        self.fp_products.append(p)
                    p.update({'category': body.get('p_category') or '완제품',
                              'name': body.get('p_name') or '', 'spec': body.get('p_spec') or '',
                              'unit': body.get('p_unit') or '개',
                              'in_price': float(body.get('p_in_price') or 0),
                              'out_price': float(body.get('p_out_price') or 0),
                              'expiry': body.get('p_expiry'), 'supplier': body.get('p_supplier') or '',
                              'active': bool(body.get('p_active'))})
                    return 200, p, {}
                return 404, {'message': 'no function'}, {}

        if path.startswith('/rest/v1/'):
            table = path[len('/rest/v1/'):]
            rows = self.table(table)
            if rows is None:
                return 404, {'code': 'PGRST205',
                             'message': "Could not find the table 'public.%s' in the schema cache" % table}, {}
            with self.lock:
                if method == 'GET':
                    out = list(rows)
                    if 'id' in qs and qs['id'][0].startswith('eq.'):
                        want = qs['id'][0][3:]
                        out = [x for x in out if str(x.get('id')) == want]
                    if 'code' in qs and qs['code'][0].startswith('eq.'):
                        want = qs['code'][0][3:]
                        out = [x for x in out if str(x.get('code')) == want]
                    if 'status' in qs and qs['status'][0].startswith('eq.'):
                        want = qs['status'][0][3:]
                        out = [x for x in out if str(x.get('status')) == want]
                    # limit
                    if 'limit' in qs:
                        try:
                            out = out[:int(qs['limit'][0])]
                        except Exception:
                            pass
                    return 200, out, {}
                if method == 'POST':
                    items = body if isinstance(body, list) else [body]
                    made = []
                    for it in items:
                        row = dict(it)
                        row['id'] = self.next_id(table)
                        if table == 'audit_logs':
                            row.setdefault('created_at', '2026-11-25T0%d:30:00Z' % min(9, row['id']))
                        rows.append(row)
                        made.append(row)
                    print('    [mock] POST %s -> %s' % (table, json.dumps(made, ensure_ascii=False)[:240]))
                    return 201, made, {}
                if method in ('PATCH', 'DELETE'):
                    target = list(rows)
                    if 'id' in qs and qs['id'][0].startswith('eq.'):
                        want = qs['id'][0][3:]
                        target = [x for x in target if str(x.get('id')) == want]
                    if 'code' in qs and qs['code'][0].startswith('eq.'):
                        want = qs['code'][0][3:]
                        target = [x for x in target if str(x.get('code')) == want]
                    if method == 'PATCH':
                        for x in target:
                            x.update(body)
                        return 204, '', {}
                    for x in target:
                        rows.remove(x)
                    return 204, '', {}
        return 404, {'message': 'not found'}, {}


MOCK = Mock()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, *a):
        pass


srv = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = 'http://127.0.0.1:%d/index.html' % PORT

FAKE_WS = r"""
window.__WS = {urls:[], sent:[], inst:null};
window.WebSocket = function(url){
  var self = this;
  this.url = url; this.readyState = 0; this.onopen = null; this.onmessage = null; this.onclose = null; this.onerror = null;
  window.__WS.inst = this; window.__WS.urls.push(url);
  setTimeout(function(){ self.readyState = 1; if (self.onopen) self.onopen(); }, 20);
  this.send = function(text){
    var m = JSON.parse(text); window.__WS.sent.push(m);
    if (m.event === 'phx_join') {
      setTimeout(function(){
        if (self.onmessage) self.onmessage({data: JSON.stringify({topic: m.topic, event: 'phx_reply', ref: m.ref,
          payload: {status: 'ok', response: {postgres_changes: []}}})});
      }, 20);
    }
  };
  this.close = function(){ self.readyState = 3; if (self.onclose) self.onclose(); };
};
"""


def route_handler(route, request):
    status, body, extra = MOCK.handle(request)
    headers = {'content-type': 'application/json', 'access-control-allow-origin': '*',
               'access-control-allow-headers': '*',
               'access-control-allow-methods': 'GET,POST,PATCH,DELETE,OPTIONS'}
    headers.update(extra or {})
    if isinstance(body, (dict, list)):
        body = json.dumps(body, ensure_ascii=False)
    route.fulfill(status=status, body=body, headers=headers)


def shot(page, name):
    page.wait_for_timeout(350)
    page.screenshot(path=os.path.join(OUT, name + '.png'), full_page=False)
    print('  shot', name)


def nav(page, key, wait=1200):
    page.evaluate("(k) => { const b = document.querySelector('#v8Side [data-nav=\"' + k + '\"]'); if (b) b.click(); }", key)
    page.wait_for_timeout(wait)


def rowmenu(page, which_name, must=''):
    page.evaluate("""(need) => {
        const trs = Array.from(document.querySelectorAll('#uniTableWrap tbody tr.ulot'));
        const tr = need ? trs.find(t => t.innerText.indexOf(need) >= 0) : trs[0];
        const bt = tr ? tr.querySelector('.actmenu') : null;
        if (bt) bt.click();
    }""", must)
    page.wait_for_timeout(450)
    items = page.evaluate("() => Array.from(document.querySelectorAll('#rowMenu button')).map(b => b.textContent.trim())")
    page.evaluate("""(n) => { const b = Array.from(document.querySelectorAll('#rowMenu button')).find(x => x.textContent.trim() === n); if (b) b.click(); }""", which_name)
    page.wait_for_timeout(700)
    return items


def arows(page):
    return page.evaluate("""() => Array.from(document.querySelectorAll('#auditTableWrap tbody tr')).map(tr => ({
        ts: (tr.children[0] || {}).innerText || '',
        type: (tr.children[1] || {}).innerText || '',
        target: (tr.children[2] || {}).innerText || '',
        summary: (tr.children[3] || {}).innerText || '',
        reason: (tr.children[4] || {}).innerText || '',
        actor: (tr.children[5] || {}).innerText || '' }))""")


def overflow(page):
    return page.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")


def login(page):
    page.goto(BASE)
    page.wait_for_timeout(800)
    page.fill('#liEmail', 'perreo@nate.com')
    page.fill('#liPw', '123456')
    page.click('#btnLogin')
    page.wait_for_selector('#appView:not(.hidden)', timeout=30000)
    page.wait_for_timeout(2500)
    page.add_style_tag(content='#toast{display:none !important}')


def main():
    with sync_playwright() as pw:
        b = pw.chromium.launch(env=dict(os.environ))
        page = b.new_page(viewport={'width': 1920, 'height': 1080})
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('dialog', lambda d: d.accept())
        page.add_init_script(FAKE_WS)
        page.route('**/gzufnyglmvgzqltepock.supabase.co/**', route_handler)
        login(page)
        shot(page, 'pc-00-첫화면')

        # ---------- 1) 원료육 로트 — 단가만 수정 → 정보수정 ----------
        nav(page, 'stock:meat')
        items = rowmenu(page, '수정', '699.84')
        chk('수정' in items, '원료육 [작업] 메뉴에 수정 있음', items)
        chk(page.evaluate("() => !document.getElementById('lotModal').classList.contains('hidden')"), '로트 수정 팝업 열림')
        page.fill('#ltPrice', '10200')
        page.fill('#ltWhy', '단가 인상')
        shot(page, 'pc-01-단가만수정')
        page.click('#lotSave')
        page.wait_for_timeout(2200)
        chk(page.evaluate("() => document.getElementById('lotModal').classList.contains('hidden')"), '저장 후 팝업 닫힘')
        lot1 = next(x for x in MOCK.lots if x['id'] == 1)
        chk(abs(lot1['unit_price'] - 10200) < 0.001, 'lots.unit_price 10,200 반영', lot1['unit_price'])
        adjlogs = [x for x in MOCK.logs if str(x.get('note', '')).startswith('[재고조정]')]
        chk(len(adjlogs) == 0, '재고가 그대로면 재고조정 이력은 안 생긴다', len(adjlogs))
        chk(len(MOCK.audit) == 1, 'audit_logs 에 1줄', len(MOCK.audit))
        if MOCK.audit:
            A = MOCK.audit[0]
            chk(A['action_type'] == '정보수정', '구분 = 정보수정', A['action_type'])
            chk(A['product_name'] == '알전각' and A['target_type'] == '원료육', '대상 = 원료육 · 알전각', (A['target_type'], A['product_name']))
            chk('단가' in A['summary'] and '9,500' in A['summary'] and '10,200' in A['summary'],
                '변경 내용에 단가 전 → 후', A['summary'])
            chk(A['reason'] == '단가 인상', '사유 저장', A['reason'])
            chk(A['actor_name'] == '박한솔' and A['actor_email'] == 'perreo@nate.com', '수정자 이름·이메일', (A['actor_name'], A['actor_email']))

        # ---------- 2) 변경이력 화면 ----------
        nav(page, 'audit', 1500)
        chk(page.evaluate("() => !document.getElementById('auditMode').classList.contains('hidden')"), '변경이력 화면 열림')
        chk(page.evaluate("() => document.getElementById('v8Title').textContent") == '변경이력', '제목 변경이력',
            page.evaluate("() => document.getElementById('v8Title').textContent"))
        chk(page.evaluate("() => !!document.querySelector('#v8Side [data-nav=\"audit\"].on')"), '왼쪽 메뉴 표시')
        chk(page.evaluate("() => document.getElementById('auditSqlNotice').classList.contains('hidden')"),
            'audit_logs 표가 있으면 SQL 안내 배너는 숨김')
        r0 = arows(page)
        chk(len(r0) == 1, '표 1줄', len(r0))
        if r0:
            chk(r0[0]['type'] == '정보수정' and '단가' in r0[0]['summary'], '줄: 정보수정 · 단가', r0[0])
            chk('알전각' in r0[0]['target'] and '원료육' in r0[0]['target'], '대상 칸 = 원료육 · 알전각', r0[0]['target'])
            chk('박한솔' in r0[0]['actor'] and 'perreo@nate.com' in r0[0]['actor'], '수정자 칸', r0[0]['actor'])
            chk(r0[0]['ts'].startswith('2026-11-25'), '일시 칸', r0[0]['ts'])
        shot(page, 'pc-02-변경이력-정보수정')

        # 필터 · 검색 · 정렬
        page.click('#auditTypeChips [data-atype="재고조정"]')
        page.wait_for_timeout(400)
        chk(len(arows(page)) == 0, '구분=재고조정 이면 0줄')
        page.click('#auditTypeChips [data-atype="정보수정"]')
        page.wait_for_timeout(400)
        chk(len(arows(page)) == 1, '구분=정보수정 이면 1줄')
        page.click('#auditTypeChips [data-atype="all"]')
        page.fill('#auditSearch', '없는말')
        page.wait_for_timeout(500)
        chk(page.evaluate("() => (document.querySelector('#auditTableWrap .uempty') || {}).innerText || ''").find('조건에 맞는') >= 0,
            '검색 결과 없음 안내')
        page.fill('#auditSearch', '단가')
        page.wait_for_timeout(500)
        chk(len(arows(page)) == 1, '검색 "단가" → 1줄')
        page.fill('#auditSearch', '')
        page.wait_for_timeout(400)
        chk(page.evaluate("() => document.querySelector('#auditTableWrap th button').classList.contains('uhd')"), '머리글 단추 클래스')
        page.click('#auditTableWrap th[data-col="ts"] button')
        page.wait_for_timeout(300)
        chk('▲' in page.inner_text('#auditTableWrap th[data-col="ts"]'), '머리글 클릭 1회 = 오름차순 ▲')
        page.click('#auditTableWrap th[data-col="ts"] button')
        page.wait_for_timeout(300)
        chk('▼' in page.inner_text('#auditTableWrap th[data-col="ts"]'), '머리글 클릭 2회 = 내림차순 ▼')
        page.click('#auditTableWrap th[data-col="ts"] button')
        page.wait_for_timeout(300)
        chk(page.inner_text('#auditTableWrap th[data-col="ts"]').strip() == '일시', '머리글 클릭 3회 = 기본(화살표 없음)',
            page.inner_text('#auditTableWrap th[data-col="ts"]'))
        chk(page.evaluate("""() => { const t = document.querySelector('#auditTableWrap thead'); return t ? getComputedStyle(t.querySelector('th')).cursor : ''; }""") is not None, '머리글 존재')

        # ---------- 3) 재고 수정 → 재고조정 기록(전 → 후 · 사유) ----------
        nav(page, 'stock:meat')
        rowmenu(page, '수정', '699.84')
        page.fill('#ltFrozen', '726.84')
        page.fill('#ltWhy', '실사 조정')
        page.click('#lotSave')
        page.wait_for_timeout(2400)
        lot1 = next(x for x in MOCK.lots if x['id'] == 1)
        chk(abs(lot1['frozen_qty'] - 726.84) < 0.001, 'lots.frozen_qty 726.84 반영', lot1['frozen_qty'])
        adjlogs = [x for x in MOCK.logs if str(x.get('note', '')).startswith('[재고조정]')]
        chk(len(adjlogs) == 1, 'tx_logs 재고조정 이력 1줄', len(adjlogs))
        adj = [a for a in MOCK.audit if a['action_type'] == '재고조정']
        chk(len(adj) == 1, 'audit_logs 에 재고조정 1줄', len(adj))
        if adj:
            A = adj[0]
            chk('699.84' in A['summary'] and '726.84' in A['summary'] and '+27.00' in A['summary'],
                '변경 내용 699.84 → 726.84 kg (+27.00)', A['summary'])
            chk(A['reason'] == '실사 조정', '사유 실사 조정', A['reason'])
            chk('txlog:' in A['target_id'], '이력 id 와 연결(txlog:) — 예전 기록과 중복 제거용', A['target_id'])

        nav(page, 'audit', 1500)
        all_rows = arows(page)
        chk(len(all_rows) == 2, '병합 표 2줄(정보수정 + 재고조정, 중복 없음)', [x['type'] for x in all_rows])
        chk(all_rows[0]['type'] == '재고조정', '기본 정렬 = 최신 먼저', all_rows[0]['type'])
        page.click('#auditTypeChips [data-atype="재고조정"]')
        page.wait_for_timeout(400)
        r1 = arows(page)
        chk(len(r1) == 1 and '699.84' in r1[0]['summary'] and '실사 조정' in r1[0]['reason'],
            '구분=재고조정 → 1줄, 전 → 후 · 사유 표시', r1)
        page.click('#auditTypeChips [data-atype="all"]')
        page.wait_for_timeout(300)
        shot(page, 'pc-03-변경이력-재고조정')

        # ---------- 4) 완제품 사용/미사용 전환 → 정보수정 ----------
        nav(page, 'stock:fg', 1500)
        page.evaluate("""() => {
            const trs = Array.from(document.querySelectorAll('#uniTableWrap tbody tr.ulot'));
            const tr = trs.find(t => t.innerText.indexOf('찢은닭가슴살') >= 0);
            const bt = tr ? tr.querySelector('.actmenu') : null;
            if (bt) bt.click();
        }""")
        page.wait_for_timeout(500)
        mitems = page.evaluate("() => Array.from(document.querySelectorAll('#rowMenu button')).map(b => b.textContent.trim())")
        chk(any('미사용' in x for x in mitems), '완제품 [작업] 메뉴에 미사용 전환 있음', mitems)
        page.evaluate("""() => {
            const b = Array.from(document.querySelectorAll('#rowMenu button')).find(x => x.textContent.indexOf('미사용으로 전환') >= 0);
            if (b) b.click();
        }""")
        page.wait_for_timeout(1800)
        usd = [a for a in MOCK.audit if '사용여부' in str(a.get('summary', ''))]
        chk(len(usd) == 1, 'audit_logs 에 사용/미사용 기록 1줄', len(usd))
        if usd:
            chk(usd[0]['action_type'] == '정보수정' and '사용 → 미사용' in usd[0]['summary'],
                '사용여부 사용 → 미사용', usd[0]['summary'])
            chk(usd[0]['product_name'] == '찢은닭가슴살 5kg' and usd[0]['target_type'] == '완제품',
                '대상 = 완제품 · 찢은닭가슴살', (usd[0]['target_type'], usd[0]['product_name']))
        nav(page, 'audit', 1500)
        chk(len(arows(page)) == 3, '변경이력 3줄(정보수정 2 + 재고조정 1)', len(arows(page)))
        page.fill('#auditSearch', '찢은닭')
        page.wait_for_timeout(500)
        chk(len(arows(page)) == 1, '품목명 검색 → 1줄')
        page.fill('#auditSearch', '')
        page.wait_for_timeout(300)
        shot(page, 'pc-04-변경이력-3줄')

        # ---------- 5) 입출고 내역 정리 — 재고조정은 남고 길이 보인다 ----------
        nav(page, 'tx', 1600)
        chk(page.evaluate("() => !!document.getElementById('utxToAudit')"), '입출고 내역에 「변경이력」 가는 링크 있음')
        page.click('#utxToAudit')
        page.wait_for_timeout(1200)
        chk(page.evaluate("() => !document.getElementById('auditMode').classList.contains('hidden')"), '링크로 변경이력 이동')
        chk(page.evaluate("() => (document.querySelector('#auditTypeChips [data-atype=\"재고조정\"]') || {}).className || ''").find('on') >= 0,
            '링크로 오면 구분=재고조정 으로 걸러 줌')

        # ---------- 6) 입출고 취소 → 삭제 기록 ----------
        nav(page, 'tx', 1800)
        page.evaluate("""() => {
            const trs = Array.from(document.querySelectorAll('#utxTableWrap tbody tr.utxrow'));
            const tr = trs.find(t => t.innerText.indexOf('목전지') >= 0);
            const bt = tr ? tr.querySelector('.actmenu') : null;
            if (bt) bt.click();
        }""")
        page.wait_for_timeout(500)
        citems = page.evaluate("() => Array.from(document.querySelectorAll('#rowMenu button')).map(b => b.textContent.trim())")
        chk('취소' in citems, '입출고 내역 [작업] 에 취소 있음', citems)
        page.evaluate("""() => {
            const b = Array.from(document.querySelectorAll('#rowMenu button')).find(x => x.textContent.trim() === '취소');
            if (b) b.click();
        }""")
        page.wait_for_timeout(2000)
        dele = [a for a in MOCK.audit if a['action_type'] == '삭제']
        chk(len(dele) == 1, 'audit_logs 에 삭제 1줄', len(dele))
        if dele:
            chk('목전지' == dele[0]['product_name'] and '120' in dele[0]['summary'] and '취소' in dele[0]['summary'],
                '삭제 줄: 목전지 · 120kg · 취소', dele[0]['summary'])
            chk(dele[0]['reason'] == '입출고 내역 취소', '삭제 사유', dele[0]['reason'])
        nav(page, 'audit', 1600)
        page.click('#auditTypeChips [data-atype="삭제"]')
        page.wait_for_timeout(500)
        dr = arows(page)
        chk(len(dr) == 1 and dr[0]['type'] == '삭제' and '목전지' in dr[0]['target'], '구분=삭제 → 1줄', dr)
        shot(page, 'pc-05-변경이력-삭제')
        page.click('#auditTypeChips [data-atype="all"]')
        page.wait_for_timeout(300)

        # ---------- 7) 모바일 390×844 ----------
        m = b.new_page(viewport={'width': 390, 'height': 844})
        m.on('pageerror', lambda e: errors.append(str(e)))
        m.on('dialog', lambda d: d.accept())
        m.add_init_script(FAKE_WS)
        m.route('**/gzufnyglmvgzqltepock.supabase.co/**', route_handler)
        login(m)
        m.evaluate("() => { const b = document.querySelector('#qbList'); if (b) b.click(); }")
        m.wait_for_timeout(500)
        nav(m, 'audit', 1400)
        chk(m.evaluate("() => !document.getElementById('auditMode').classList.contains('hidden')"), '폰: 변경이력 화면 열림')
        chk(overflow(m) <= 0, '폰 390px 가로 넘침 0', overflow(m))
        mr = arows(m)
        chk(len(mr) == 4, '폰에서도 4줄', len(mr))
        shot(m, 'mobile-390-변경이력')

        # ---------- 7) audit_logs 표가 없을 때 (SQL 미실행) ----------
        MOCK.audit_on = False
        MOCK.audit = []
        p2 = b.new_page(viewport={'width': 1600, 'height': 1000})
        p2.on('pageerror', lambda e: errors.append(str(e)))
        p2.on('dialog', lambda d: d.accept())
        p2.add_init_script(FAKE_WS)
        p2.route('**/gzufnyglmvgzqltepock.supabase.co/**', route_handler)
        login(p2)
        nav(p2, 'audit', 1600)
        chk(p2.evaluate("() => !document.getElementById('auditSqlNotice').classList.contains('hidden')"),
            'SQL 미실행이면 안내 배너 보임')
        notice = p2.inner_text('#auditSqlNotice')
        chk('SQL' in notice and '실행' in notice, '배너 문구에 SQL 실행 안내', notice.replace('\n', ' ')[:80])
        rows2 = arows(p2)
        chk(len(rows2) >= 1, '표가 없어도 예전 [재고조정] 이력은 보인다', len(rows2))
        chk(any('재고조정' in x['type'] for x in rows2), '예전 재고조정이 병합돼 보임', [x['type'] for x in rows2])
        chk(p2.evaluate("() => document.querySelectorAll('#toast .tmsg').length") == 0, '오류 토스트 없음(조용한 fallback)',
            p2.evaluate("() => document.querySelectorAll('#toast .tmsg').length"))
        shot(p2, 'pc-05-SQL미실행-배너')
        # 표가 없을 때 수정해도 앱이 멀쩡한지
        nav(p2, 'stock:meat')
        rowmenu(p2, '수정', '726.84')
        p2.fill('#ltPrice', '9800')
        p2.click('#lotSave')
        p2.wait_for_timeout(2000)
        chk(p2.evaluate("() => document.getElementById('lotModal').classList.contains('hidden')"),
            'SQL 없이도 로트 수정은 그대로 저장된다')
        lot1 = next(x for x in MOCK.lots if x['id'] == 1)
        chk(abs(lot1['unit_price'] - 9800) < 0.001, 'lots.unit_price 9,800 반영', lot1['unit_price'])
        chk(len(MOCK.audit) == 0, 'SQL 전에는 audit_logs 에 아무 것도 안 쓴다', len(MOCK.audit))

        b.close()

    print()
    if errors:
        print('  JS 오류 %d건:' % len(errors))
        for e in errors[:10]:
            print('   -', e)
    else:
        print('  JS 오류 0건')
    chk(len(errors) == 0, 'JS 오류 0건', errors[:3])
    print()
    if fails:
        print('실패 %d건:' % len(fails))
        for f in fails:
            print('  -', f)
        sys.exit(1)
    print('전부 통과 (%d개 확인)' % 0 if False else '전부 통과')


if __name__ == '__main__':
    main()
