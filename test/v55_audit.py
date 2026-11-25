# -*- coding: utf-8 -*-
"""v55 — 모든 화면·팝업 입력칸 전수 점검 (로컬 · 스텁 Supabase, 실제 DB 무접촉)

  LD_LIBRARY_PATH=/workspace/tool-results/chromelibs python3 work/erp-web/test/v55_audit.py [before|after]

각 상태에서 보이는 input/select/textarea 를 모두 모아
  ① 검색 상자(.usearch/.fsearch) 안쪽 input 의 테두리·그림자·배경(이중 테두리)
  ② 부모 상자(테두리/배경 있는 가장 가까운 조상) 밖으로 삐져나옴(경계 침범)
  ③ 바로 위 부모의 안쪽 여백 상자 침범
를 잰다. focus() 한 상태도 같은 검사.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('LD_LIBRARY_PATH', '/workspace/tool-results/chromelibs')
import shot_v54 as V
from playwright.sync_api import sync_playwright

TAG = sys.argv[1] if len(sys.argv) > 1 else 'before'
OUT = '/workspace/downloads/erp-v55-' + TAG
os.makedirs(OUT, exist_ok=True)

AUDIT = r"""(ROOT) => {
  const vis = el => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    const c = getComputedStyle(el);
    if (c.visibility === 'hidden' || c.display === 'none' || parseFloat(c.opacity) === 0) return false;
    /* 닫힌 <details> 안쪽은 레이아웃 상자가 남아 있어도 화면에 없다 */
    let a = el.parentElement, n = 0;
    while (a && n < 8) {
      if (a.tagName === 'DETAILS' && !a.open) return false;
      const acs = getComputedStyle(a);
      if (acs.contentVisibility === 'hidden') return false;
      a = a.parentElement; n++;
    }
    return true;
  };
  const Q = 'input:not([type=checkbox]):not([type=radio]):not([type=hidden]):not([type=file]):not([type=button]):not([type=submit]):not([type=reset]):not([type=color]):not([type=range]),select,textarea';
  const R = el => { const r = el.getBoundingClientRect(); return {t:r.top,l:r.left,r:r.right,b:r.bottom,w:r.width,h:r.height}; };
  const out = [];
  const root = ROOT ? document.querySelector(ROOT) : document;
  if (!root) return [{el:'root-missing', issues:['no ' + ROOT]}];
  const transparentBg = v => !v || v === 'transparent' || /rgba\(0, 0, 0, 0\)/.test(v);
  root.querySelectorAll(Q).forEach(el => {
    if (!vis(el)) return;
    const cs = getComputedStyle(el), r = R(el);
    const rec = {
      el: el.tagName.toLowerCase(), type: el.type || '', id: el.id || '',
      ph: el.getAttribute('placeholder') || '', cls: String(el.className || '').slice(0, 60),
      w: Math.round(r.w*10)/10, h: Math.round(r.h*10)/10,
      border: cs.borderTopWidth, shadow: cs.boxShadow, bg: cs.backgroundColor,
      outline: cs.outlineStyle + ' ' + cs.outlineWidth,
      parent: '', issues: []
    };
    const comp = el.closest('.usearch,.fsearch,.v133-search-wrap');
    if (comp) {
      rec.comp = comp.className;
      if (parseFloat(cs.borderTopWidth) > 0) rec.issues.push('search-inner-border:' + cs.borderTopWidth);
      if (cs.boxShadow && cs.boxShadow !== 'none') rec.issues.push('search-inner-shadow:' + cs.boxShadow);
      if (!transparentBg(cs.backgroundColor)) rec.issues.push('search-inner-bg:' + cs.backgroundColor);
      if (cs.outlineStyle !== 'none') rec.issues.push('search-inner-outline');
    }
    /* ① 바로 위 부모의 안쪽 여백 상자 침범 */
    const p = el.parentElement;
    if (p) {
      const pr = R(p), pcs = getComputedStyle(p);
      const pt = parseFloat(pcs.paddingTop)||0, pb = parseFloat(pcs.paddingBottom)||0,
            pl = parseFloat(pcs.paddingLeft)||0, prr = parseFloat(pcs.paddingRight)||0,
            btw = parseFloat(pcs.borderTopWidth)||0, bbw = parseFloat(pcs.borderBottomWidth)||0,
            blw = parseFloat(pcs.borderLeftWidth)||0, brw = parseFloat(pcs.borderRightWidth)||0;
      const inner = {t: pr.t + btw + pt, b: pr.b - bbw - pb, l: pr.l + blw + pl, r: pr.r - brw - prr};
      rec.parent = String(p.className || p.tagName).slice(0, 60);
      const o = {top: +(inner.t - r.t).toFixed(1), bottom: +(r.b - inner.b).toFixed(1),
                 left: +(inner.l - r.l).toFixed(1), right: +(r.r - inner.r).toFixed(1)};
      if (o.top > 1.2 || o.bottom > 1.2 || o.left > 1.2 || o.right > 1.2)
        rec.issues.push('parent-box:' + JSON.stringify(o) + '@' + rec.parent);
    }
    /* ② 테두리/배경 있는 가장 가까운 조상 상자 밖으로 삐져나옴 */
    let a = el.parentElement, hops = 0;
    while (a && hops < 5) {
      const acs = getComputedStyle(a);
      if (parseFloat(acs.borderTopWidth) > 0 || (!transparentBg(acs.backgroundColor)) || (acs.boxShadow && acs.boxShadow !== 'none')) break;
      a = a.parentElement; hops++;
    }
    if (a && a !== p) {
      const ar = R(a), acs = getComputedStyle(a);
      const bt = parseFloat(acs.borderTopWidth)||0, bb = parseFloat(acs.borderBottomWidth)||0,
            bl = parseFloat(acs.borderLeftWidth)||0, br = parseFloat(acs.borderRightWidth)||0;
      const o = {top: +(ar.t + bt - r.t).toFixed(1), bottom: +(r.b - (ar.b - bb)).toFixed(1),
                 left: +(ar.l + bl - r.l).toFixed(1), right: +(r.r - (ar.r - br)).toFixed(1)};
      if (o.top > 1.2 || o.bottom > 1.2 || o.left > 1.2 || o.right > 1.2)
        rec.issues.push('box:' + JSON.stringify(o) + '@' + String(a.className || a.tagName).slice(0, 50));
      /* 상자 테두리와 입력칸 테두리가 2.5px 안에서 맞닿으면 «이중 테두리»로 본다 */
      if (parseFloat(cs.borderTopWidth) > 0) {
        const near = [];
        if (o.top >= -1.2 && o.top < 2.5) near.push('top');
        if (o.bottom >= -1.2 && o.bottom < 2.5) near.push('bottom');
        if (o.left >= -1.2 && o.left < 2.5) near.push('left');
        if (o.right >= -1.2 && o.right < 2.5) near.push('right');
        if (near.length) rec.issues.push('double-border:' + near.join(',') + '@' + String(a.className || a.tagName).slice(0, 40));
      }
    }
    /* ③ 표 칸(td)과 줄(tr) 경계 — 칸이 줄 높이만큼 늘어나지 않으면 열마다 선이 어긋난다 */
    const td = el.closest('td');
    if (td && td.parentElement) {
      const T = R(td), TRr = R(td.parentElement);
      const tcs = getComputedStyle(td);
      const bBot = parseFloat(tcs.borderBottomWidth)||0;
      if (Math.abs(T.h - TRr.h) > 1.5) rec.issues.push('cell-not-stretched:' + (T.h - TRr.h).toFixed(1) + 'px');
      const gap = +(T.b - bBot - r.b).toFixed(1);
      if (gap < 2) rec.issues.push('flush-bottom:' + gap + 'px');
    }
    out.push(rec);
  });
  return out;
}"""


def run_audit(page, tag, root=None):
    data = page.evaluate(AUDIT, root)
    bad = [d for d in data if d['issues']]
    print('\n== %s — 입력칸 %d개, 문제 %d개' % (tag, len(data), len(bad)))
    for d in bad:
        print('   [X]', d['el'], d['type'], ('#' + d['id'] if d['id'] else ''), '|', d['ph'] or d['cls'], '|', '; '.join(d['issues']))
    with open(os.path.join(OUT, 'audit.jsonl'), 'a', encoding='utf-8') as f:
        f.write(json.dumps({'tag': tag, 'n': len(data), 'bad': bad, 'all': data}, ensure_ascii=False) + '\n')
    page.screenshot(path=os.path.join(OUT, tag.replace('/', '_') + '.png'))
    return bad


def focus_audit(page, sel, tag, root=None):
    if page.evaluate("(s) => !!document.querySelector(s)", sel):
        page.evaluate("(s) => document.querySelector(s).focus()", sel)
        page.wait_for_timeout(250)
        return run_audit(page, tag + ' [focus]', root)
    return []


def nav(page, key, wait=1200):
    page.evaluate("(k) => { const b = document.querySelector('#v8Side [data-nav=\"' + k + '\"]'); if (b) b.click(); }", key)
    page.wait_for_timeout(wait)


total_bad = []
with sync_playwright() as pw:
    b = pw.chromium.launch(env=dict(os.environ))
    page = b.new_page(viewport={'width': 1920, 'height': 1080})
    errs = []
    page.on('pageerror', lambda e: errs.append(str(e)))

    def rh(route, request):
        if '/rest/v1/' in request.url or '/auth/v1/' in request.url:
            return V.route_handler(route, request)
        return route.continue_()

    page.route('**/*', rh)
    page.add_init_script(V.FAKE_WS)
    V.login(page)
    page.wait_for_timeout(1600)
    page.add_style_tag(content='#toast{display:none !important}')

    def open_check(mid):
        return page.evaluate("(m) => { const e = document.getElementById(m); return !!e && !e.classList.contains('hidden'); }", mid)

    def close_all():
        page.keyboard.press('Escape')
        page.wait_for_timeout(300)
        page.evaluate("""() => {
          document.querySelectorAll('.modal').forEach(m => m.classList.add('hidden'));
          const fp = document.getElementById('fpop'); if (fp) fp.classList.add('hidden');
        }""")
        page.wait_for_timeout(200)

    # --- 화면들
    for key, tag, sel in [
        ('stock:all', 'uni', '#uniSearch'),
        ('tx', 'tx', '#utxSearch'),
        ('audit', 'audit', '#auditSearch'),
        ('items', 'items', '#itemsSearch'),
        ('stock:meat', 'meat', '#meatSearch'),
        ('stock:fg', 'fg', None),
        ('stock:mat', 'mat', None),
        ('stock:sub', 'sub', None),
        ('buy-list', 'buy-list', None),
        ('buy-status', 'buy-status', None),
        ('sale-list', 'sale-list', None),
        ('sale-status', 'sale-status', None),
        ('ledger', 'ledger', None),
        ('expense', 'expense', None),
    ]:
        nav(page, key, 1400)
        total_bad += run_audit(page, tag)
        if sel:
            total_bad += focus_audit(page, sel, tag)

    # --- 기간 달력
    nav(page, 'audit', 1200)
    page.click('#auditBtnPeriod')
    page.wait_for_timeout(700)
    total_bad += run_audit(page, 'range-modal', '#rangeModal')
    total_bad += focus_audit(page, '#rangeModal input', 'range-modal', '#rangeModal')
    close_all()

    # --- 열 필터 팝업 (검색칸 포함)
    nav(page, 'stock:all', 1300)
    page.evaluate("() => { const b = document.querySelector('#uniTableWrap button[data-filter]'); if (b) b.click(); }")
    page.wait_for_timeout(500)
    page.evaluate("() => { const e = document.getElementById('fpop'); if (e) e.classList.remove('hidden'); }")
    page.wait_for_timeout(300)
    total_bad += run_audit(page, 'filter-pop', '#fpop')
    total_bad += focus_audit(page, '#fpopSearch', 'filter-pop', '#fpop')
    close_all()

    # --- 전표형 입고/출고 (ioSheetModal — 표 안 입력칸, 왼쪽 메뉴 입고·출고)
    for navkey, tag in [('in', 'pop-sheet-in'), ('out', 'pop-sheet-out')]:
        nav(page, navkey, 1400)
        if open_check('ioSheetModal'):
            total_bad += run_audit(page, tag, '#ioSheetModal')
            total_bad += focus_audit(page, '#ioSheetModal tbody input', tag, '#ioSheetModal')
            total_bad += focus_audit(page, '#ioSheetModal tbody select', tag, '#ioSheetModal')
        close_all()

    # --- 원료육 입고/출고 팝업 (meatFormModal — 입출고 허브에서)
    for io, tag in [('in', 'pop-meat-in'), ('out', 'pop-meat-out')]:
        nav(page, 'stock:all', 1200)
        page.evaluate("() => { const h = document.getElementById('ioHubModal'); if (h) h.classList.remove('hidden'); }")
        page.wait_for_timeout(250)
        page.evaluate("(a) => { const b = document.querySelector('#ioHubModal [data-io=\"' + a + '\"]'); if (b) b.click(); }", io)
        page.wait_for_timeout(1200)
        if open_check('meatFormModal'):
            total_bad += run_audit(page, tag, '#meatFormModal')
            total_bad += focus_audit(page, '#meatFormModal input[type=text]', tag, '#meatFormModal')
        close_all()

    # --- 완제품 입고/출고 팝업 (fgFormModal)
    nav(page, 'stock:fg', 1200)
    page.evaluate("() => { const h = document.getElementById('ioHubModal'); if (h) h.classList.remove('hidden'); }")
    page.wait_for_timeout(250)
    page.evaluate("() => { const b = document.querySelector('#ioHubModal [data-io=\"fp-in\"]'); if (b) b.click(); }")
    page.wait_for_timeout(1200)
    if open_check('fgFormModal'):
        total_bad += run_audit(page, 'pop-fg-in', '#fgFormModal')
        total_bad += focus_audit(page, '#fgFormModal input[type=text]', 'pop-fg-in', '#fgFormModal')
    close_all()

    # --- 품목 등록 (fgNewModal)
    nav(page, 'items', 1300)
    page.click('#itemsBtnNew')
    page.wait_for_timeout(900)
    if open_check('fgNewModal'):
        total_bad += run_audit(page, 'pop-item-new', '#fgNewModal')
        total_bad += focus_audit(page, '#fgNewModal input[type=text]', 'pop-item-new', '#fgNewModal')
    close_all()

    # --- 재고 이동(해동) 팝업
    nav(page, 'move', 1300)
    if open_check('uniMoveModal'):
        total_bad += run_audit(page, 'pop-move', '#uniMoveModal')
        total_bad += focus_audit(page, '#uniMoveModal input[type=text]', 'pop-move', '#uniMoveModal')
    close_all()

    # --- 로트 수정 팝업 (원료육)
    nav(page, 'stock:all', 1300)
    page.evaluate("() => { const t = document.querySelector('#uniTableWrap tbody tr.ulot .actmenu'); if (t) t.click(); }")
    page.wait_for_timeout(400)
    page.evaluate("() => { const b = Array.from(document.querySelectorAll('#rowMenu button')).find(x => x.textContent.trim() === '수정'); if (b) b.click(); }")
    page.wait_for_timeout(900)
    if open_check('lotModal'):
        total_bad += run_audit(page, 'pop-lot', '#lotModal')
        total_bad += focus_audit(page, '#lotModal input[type=text]', 'pop-lot', '#lotModal')
    close_all()

    # --- 완제품 로트 수정
    nav(page, 'stock:fg', 1300)
    page.evaluate("() => { const t = document.querySelector('#fgTableWrap tbody .actmenu'); if (t) t.click(); }")
    page.wait_for_timeout(400)
    page.evaluate("() => { const b = Array.from(document.querySelectorAll('#rowMenu button')).find(x => x.textContent.indexOf('정보 수정') >= 0); if (b) b.click(); }")
    page.wait_for_timeout(900)
    if open_check('fpLotModal'):
        total_bad += run_audit(page, 'pop-fplot', '#fpLotModal')
        total_bad += focus_audit(page, '#fpLotModal input[type=text]', 'pop-fplot', '#fpLotModal')
    close_all()

    # --- 입출고 내역 수정 (editModal)
    nav(page, 'tx', 1300)
    if page.evaluate("() => !!document.querySelector('#utxTableWrap tbody .actmenu')"):
        page.evaluate("() => document.querySelector('#utxTableWrap tbody .actmenu').click()")
        page.wait_for_timeout(400)
        page.evaluate("() => { const b = Array.from(document.querySelectorAll('#rowMenu button')).find(x => x.textContent.indexOf('수정') >= 0); if (b) b.click(); }")
        page.wait_for_timeout(900)
        if open_check('editModal'):
            total_bad += run_audit(page, 'pop-tx-edit', '#editModal')
            total_bad += focus_audit(page, '#editModal input[type=text]', 'pop-tx-edit', '#editModal')
    close_all()

    # --- 매입/매출 전표 팝업
    for pane, btn, tag in [('buy-list', 'btnBuyNew', 'pop-voucher-buy'), ('sale-list', 'btnSaleNew', 'pop-voucher-sale')]:
        nav(page, pane, 1300)
        if page.evaluate("(b) => !!document.getElementById(b)", btn):
            page.click('#' + btn)
            page.wait_for_timeout(900)
            if open_check('accVoucherModal'):
                total_bad += run_audit(page, tag, '#accVoucherModal')
                total_bad += focus_audit(page, '#accVoucherModal input[type=text]', tag, '#accVoucherModal')
        close_all()

    # --- 회계 수금/지급 · 경비 팝업
    for pane in ('sale-status', 'buy-status'):
        nav(page, pane, 1300)
        page.evaluate("""() => { const b = Array.from(document.querySelectorAll('.v8pane:not(.hidden) button')).find(x => /수금|지급/.test(x.textContent)); if (b) b.click(); }""")
        page.wait_for_timeout(800)
        if open_check('accPayModal'):
            total_bad += run_audit(page, 'pop-acc-pay-' + pane, '#accPayModal')
            total_bad += focus_audit(page, '#accPayModal input[type=text]', 'pop-acc-pay-' + pane, '#accPayModal')
        close_all()
    nav(page, 'expense', 1300)
    page.evaluate("""() => { const b = Array.from(document.querySelectorAll('.v8pane:not(.hidden) button')).find(x => /경비/.test(x.textContent)); if (b) b.click(); }""")
    page.wait_for_timeout(800)
    if open_check('accExpModal'):
        total_bad += run_audit(page, 'pop-acc-exp', '#accExpModal')
    close_all()

    # --- 완제품 단가 수정 팝업
    nav(page, 'stock:fg', 1300)
    page.evaluate("() => { const t = document.querySelector('#fgTableWrap tbody .actmenu'); if (t) t.click(); }")
    page.wait_for_timeout(400)
    page.evaluate("() => { const b = Array.from(document.querySelectorAll('#rowMenu button')).find(x => x.textContent.indexOf('단가 수정') >= 0); if (b) b.click(); }")
    page.wait_for_timeout(900)
    if open_check('fgPriceModal'):
        total_bad += run_audit(page, 'pop-fg-price', '#fgPriceModal')
        total_bad += focus_audit(page, '#fgPriceModal input[type=text]', 'pop-fg-price', '#fgPriceModal')
    close_all()

    # --- 회계 일반 출금(경비) 팝업
    nav(page, 'ledger', 1300)
    page.evaluate("() => { const b = document.getElementById('btnAccExpense'); if (b) b.click(); }")
    page.wait_for_timeout(800)
    if open_check('accExpModal'):
        total_bad += run_audit(page, 'pop-acc-exp', '#accExpModal')
        total_bad += focus_audit(page, '#accExpModal input[type=text]', 'pop-acc-exp', '#accExpModal')
    close_all()

    # --- 기타 팝업 (미반영·명세표·공급자·엑셀·업로드·회계도움·사진함)
    nav(page, 'buy-list', 1300)
    if page.evaluate("() => !!document.getElementById('btnBuyReflect')"):
        page.click('#btnBuyReflect')
        page.wait_for_timeout(800)
        if open_check('reflectModal'):
            total_bad += run_audit(page, 'pop-reflect', '#reflectModal')
        close_all()
    nav(page, 'sale-list', 1300)
    if page.evaluate("() => !!document.getElementById('btnSaleStmt')"):
        page.click('#btnSaleStmt')
        page.wait_for_timeout(900)
        if open_check('stmtModal'):
            page.evaluate("() => { const d = document.getElementById('stmtBuyerBox'); if (d) d.open = true; }")
            page.wait_for_timeout(400)
            total_bad += run_audit(page, 'pop-stmt', '#stmtModal')
            total_bad += focus_audit(page, '#stmtBuyerName', 'pop-stmt', '#stmtModal')
            if page.evaluate("() => !!document.getElementById('stmtSupBtn')"):
                page.click('#stmtSupBtn')
                page.wait_for_timeout(700)
                if open_check('supplierModal'):
                    total_bad += run_audit(page, 'pop-supplier', '#supplierModal')
        close_all()
    nav(page, 'stock:all', 1200)
    page.evaluate("() => { const b = document.getElementById('xlUniBtn'); if (b) b.click(); }")
    page.wait_for_timeout(400)
    page.evaluate("() => { const b = document.getElementById('btnUniSabang'); if (b) b.click(); }")
    page.wait_for_timeout(900)
    if open_check('xlsModal'):
        total_bad += run_audit(page, 'pop-xls', '#xlsModal')
    close_all()
    nav(page, 'ledger', 1300)
    page.evaluate("() => { const b = document.getElementById('btnAccHelp'); if (b) b.click(); }")
    page.wait_for_timeout(700)
    if open_check('accHelpModal'):
        total_bad += run_audit(page, 'pop-acchelp', '#accHelpModal')
    close_all()
    nav(page, 'stock:fg', 1300)
    page.evaluate("() => { const b = document.getElementById('btnFgUpload'); if (b) b.click(); }")
    page.wait_for_timeout(800)
    if open_check('uploadModal'):
        total_bad += run_audit(page, 'pop-upload', '#uploadModal')
    close_all()
    page.evaluate("() => { const h = document.getElementById('ioHubModal'); if (h) h.classList.remove('hidden'); }")
    page.wait_for_timeout(250)
    page.evaluate("() => { const b = document.querySelector('#ioHubModal [data-io=\"photo\"]'); if (b) b.click(); }")
    page.wait_for_timeout(900)
    if open_check('photoInboxModal'):
        total_bad += run_audit(page, 'pop-photo', '#photoInboxModal')
    close_all()

    print('\n===== TOTAL 문제 %d개 · JS 오류 %d개 =====' % (len(total_bad), len(errs)))
    if errs:
        for e in errs[:5]:
            print('  JS', e)
    b.close()
