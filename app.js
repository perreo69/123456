/* ============================================================================
   원료육 입출고 ERP · Supabase 연동 웹앱
   ----------------------------------------------------------------------------
   이 파일은 세 부분으로 나뉩니다.
     CORE : 순수 계산(재고 합계·정렬·CSV). 화면/DOM/네트워크를 건드리지 않는다.
     API  : Supabase Auth(로그인) + PostgREST(조회) + RPC(저장/취소) + 실시간
     UI   : 화면 그리기와 입력 처리
   재고 계산과 검증은 Supabase의 tx_apply / tx_undo 함수가 한 트랜잭션에서
   처리합니다(POST /rest/v1/rpc/tx_apply). 그래서 PC와 폰에서 동시에 눌러도
   재고가 어긋나지 않습니다.
   ============================================================================ */

/* ============================== CONFIG ============================== */
var CONFIG = {
  SUPABASE_URL: 'https://gzufnyglmvgzqltepock.supabase.co',
  SUPABASE_ANON_KEY: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imd6dWZueWdsbXZnenFsdGVwb2NrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTQ4NDg3NDAsImV4cCI6MjExMDQyNDc0MH0.xFxZA9BjTCLJMmhMUbm93CrSqfqtcAz_GCrkf4t4vCc',
  /* 실시간(웹소켓)이 막히면 이 주기로 다시 불러옵니다 */
  POLL_MS: 60000
};

/* ============================== CORE:START ============================== */
var ERP = (function () {
  'use strict';
  var EPS = 0.004;

  function r2(x) {
    var v = Math.round(Number(x) * 100) / 100;
    return v === 0 ? 0 : v;
  }
  function r0(x) { return Math.round(Number(x) || 0); }
  function nz(x) { return x === undefined || x === null ? '' : String(x); }
  function s(x) { return nz(x).replace(/^\s+|\s+$/g, ''); }
  function pad2(n) { return (n < 10 ? '0' : '') + n; }

  /* ---------- 대분류 / 소분류 ---------- */
  var MAJORS = ['원료육', '완제품', '부자재', '소스'];
  var MAJOR_DEFAULT = '원료육';
  function majorName(v) { var t = s(v); return t || MAJOR_DEFAULT; }

  /* 옛 표기(돈/우/계/양)는 새 표기로 읽는다 (DB 마이그레이션 전 데이터도 안전하게) */
  var MEAT_OLD = { '돈': '돈육', '우': '우육', '계': '계육', '양': '양육' };
  var MEATS = ['돈육', '우육', '계육', '양육'];
  function meatName(v) {
    var t = s(v);
    return MEAT_OLD[t] || t;
  }

  /* 출고처 구분: 현장 / 업체 / 택배 / 기타 */
  var DEST_KEYS = ['site', 'vendor', 'courier', 'other'];
  var DEST_NAME = { site: '현장', vendor: '업체', courier: '택배', other: '기타' };
  var DEST_LABEL = { site: '생산품목', vendor: '출고 업체명', courier: '택배 수령처·내역', other: '출고처·사유' };
  var DEST_HINT = {
    site: '현장(생산품목)으로 나간 물량입니다. 생산품목을 적으면 생산 기록과 맞춰볼 수 있습니다.',
    vendor: '업체로 판매하거나 옮긴 경우입니다. 업체명을 적으면 거래처별로 모아볼 수 있습니다.',
    courier: '택배로 보낸 경우입니다. 받는 곳과 운송장·메모를 함께 적으면 나중에 찾기 쉽습니다.',
    other: '현장·업체·택배 밖의 출고입니다. 사유까지 적어두세요.'
  };
  function destKey(v) {
    v = s(v);
    return Object.prototype.hasOwnProperty.call(DEST_NAME, v) ? v : 'site';
  }
  function destName(v) { return DEST_NAME[destKey(v)]; }
  function typeName(t) {
    return t === 'in' ? '입고' : (t === 'thaw' ? '해동' : (t === 're' ? '재냉동' : (t === 'base' ? '기초재고' : '출고')));
  }
  function whName(w) { return w === 'C' ? '냉장고' : '냉동고'; }
  /* 창고 열: 이동은 어디서 → 어디로, 그 밖엔 재고가 있는 창고 */
  function moveName(e) {
    if (e.t === 'thaw') return '냉동고→냉장고';
    if (e.t === 're') return '냉장고→냉동고';
    return whName(e.w);
  }

  /* ---------- DB 행 → 화면용 상태 ---------- */
  function stateFrom(lotsRows, logRows) {
    var lots = [], logs = [], i, r;
    lotsRows = lotsRows || [];
    logRows = logRows || [];
    for (i = 0; i < lotsRows.length; i++) {
      r = lotsRows[i];
      lots.push({
        id: 'L' + r.id, dbid: Number(r.id), n: nz(r.product_name),
        major: majorName(r.major_category), mt: meatName(r.meat_type),
        o: nz(r.origin), v: nz(r.vendor), b: nz(r.brand),
        i: nz(r.in_date), e: nz(r.exp_date),
        fq: r2(r.frozen_qty), cq: r2(r.chilled_qty),
        price: r2(r.unit_price), up: nz(r.updated_at)
      });
    }
    for (i = 0; i < logRows.length; i++) {
      r = logRows[i];
      var pr = r2(r.unit_price);
      logs.push({
        id: 'H' + r.id, dbid: Number(r.id), d: nz(r.tx_date), w: nz(r.warehouse) || 'F',
        t: nz(r.tx_type) || 'out', n: nz(r.product_name),
        major: majorName(r.major_category), mt: meatName(r.meat_type),
        v: nz(r.vendor), i: nz(r.in_date), e: nz(r.exp_date), k: r2(r.qty),
        price: pr, amt: r2(r.total_amount),
        p: nz(r.dest_detail), dt: nz(r.dest_type), note: nz(r.note),
        lid: r.lot_id === null || r.lot_id === undefined ? '' : String(r.lot_id),
        worker: nz(r.worker_name), email: nz(r.worker_email),
        act: r.is_manual !== false, at: nz(r.created_at)
      });
    }
    return { lots: lots, logs: logs, loadedAt: Date.now() };
  }

  function lotValue(l) { return r0((l.fq + l.cq) * l.price); }

  function totals(st) {
    var f = 0, c = 0, lf = 0, lc = 0, live = 0, mine = 0, value = 0, i;
    for (i = 0; i < st.lots.length; i++) {
      var l = st.lots[i];
      f += l.fq; c += l.cq;
      value += (l.fq + l.cq) * l.price;
      if (l.fq > EPS) lf++;
      if (l.cq > EPS) lc++;
      if (l.fq > EPS || l.cq > EPS) live++;
    }
    for (i = 0; i < st.logs.length; i++) if (st.logs[i].act) mine++;
    return { frozen: r2(f), chilled: r2(c), liveFrozen: lf, liveChilled: lc, live: live, manual: mine, value: r0(value) };
  }

  function getLot(st, id) {
    for (var i = 0; i < st.lots.length; i++) if (st.lots[i].id === id) return st.lots[i];
    return null;
  }
  function getLog(st, id) {
    for (var i = 0; i < st.logs.length; i++) if (st.logs[i].dbid === Number(id)) return st.logs[i];
    return null;
  }
  function qtyOf(lot, wh) { return wh === 'F' ? lot.fq : lot.cq; }

  function sortLots(a, b) {
    var an = a.e || '9999-99-99', bn = b.e || '9999-99-99';
    if (an !== bn) return an < bn ? -1 : 1;
    var ai = a.i || '9999-99-99', bi = b.i || '9999-99-99';
    if (ai !== bi) return ai < bi ? -1 : 1;
    return a.v < b.v ? -1 : (a.v > b.v ? 1 : 0);
  }

  /* ---------- 표 컬럼 정의 (머리글 · 정렬 · 필터가 모두 여기서 나온다) ---------- */
  var LOT_COLS = [
    { k: 'major', t: '대분류', w: 78 },
    { k: 'mt', t: '소분류', w: 72 },
    { k: 'n', t: '제품명', w: 152 },
    { k: 'o', t: '원산지', w: 76 },
    { k: 'v', t: '업체명', w: 96 },
    { k: 'b', t: '브랜드', w: 76 },
    { k: 'i', t: '입고일', w: 90 },
    { k: 'e', t: '소비기한', w: 104 },
    { k: 'qty', t: '재고(kg)', w: 88, num: true },
    { k: 'price', t: '단가(원/kg)', w: 84, num: true },
    { k: 'amt', t: '재고금액(원)', w: 112, num: true }
  ];
  var LOG_COLS = [
    { k: 'd', t: '날짜', w: 88 },
    { k: 't', t: '구분', w: 66 },
    { k: 'major', t: '대분류', w: 78 },
    { k: 'mv', t: '창고', w: 84 },
    { k: 'n', t: '제품명', w: 132 },
    { k: 'v', t: '업체명', w: 92 },
    { k: 'i', t: '입고일', w: 88 },
    { k: 'e', t: '소비기한', w: 96 },
    { k: 'k', t: '중량(kg)', w: 76, num: true },
    { k: 'price', t: '단가(원/kg)', w: 82, num: true },
    { k: 'amt', t: '금액(원)', w: 106, num: true },
    { k: 'p', t: '출고처 · 비고', w: 0 },
    { k: 'worker', t: '작업자', w: 72 }
  ];
  function lotCols(wh) {
    var out = [], i, c;
    for (i = 0; i < LOT_COLS.length; i++) {
      c = LOT_COLS[i];
      out.push({ k: c.k, t: c.k === 'qty' ? (wh === 'F' ? '냉동고 재고(kg)' : '냉장고 재고(kg)') : c.t,
        w: c.w, num: !!c.num });
    }
    return out;
  }
  function colDef(list, k) {
    for (var i = 0; i < list.length; i++) if (list[i].k === k) return list[i];
    return null;
  }

  /* 셀에 들어가는 값 (정렬·필터·표시가 같은 값을 쓴다) */
  function lotCell(l, k, wh) {
    if (k === 'major') return l.major;
    if (k === 'mt') return l.mt;
    if (k === 'n') return l.n;
    if (k === 'o') return l.o;
    if (k === 'v') return l.v;
    if (k === 'b') return l.b;
    if (k === 'i') return l.i;
    if (k === 'e') return l.e;
    if (k === 'qty') return qtyOf(l, wh);
    if (k === 'price') return l.price;
    if (k === 'amt') return r0(qtyOf(l, wh) * l.price);
    return '';
  }
  function logCell(e, k) {
    if (k === 'd') return e.d;
    if (k === 't') return typeName(e.t);
    if (k === 'major') return e.major;
    if (k === 'mv') return moveName(e);
    if (k === 'n') return e.n;
    if (k === 'v') return e.v;
    if (k === 'i') return e.i;
    if (k === 'e') return e.e;
    if (k === 'k') return e.k;
    if (k === 'price') return e.price;
    if (k === 'amt') return e.amt;
    if (k === 'p') {
      var parts = [];
      if (e.t === 'out') parts.push(destName(e.dt) + ' ' + (e.p || ''));
      else if (e.p) parts.push(e.p);
      if (e.note) parts.push(e.note);
      return parts.join(' ').replace(/\s+/g, ' ');
    }
    if (k === 'worker') return e.worker;
    return '';
  }
  /* 필터에 쓰는 값 키 (빈 값은 '-') */
  function cellKey(v) {
    var t = s(v);
    return t === '' ? '-' : t;
  }

  function cmpVal(a, b, numeric) {
    if (numeric) return (Number(a) || 0) - (Number(b) || 0);
    return String(a).localeCompare(String(b), 'ko');
  }

  /* 컬럼 필터: cols = { 컬럼키: [허용값...] }, 비었으면 통과 */
  function passCols(cols, getter) {
    if (!cols) return true;
    for (var k in cols) {
      if (!Object.prototype.hasOwnProperty.call(cols, k)) continue;
      var allow = cols[k];
      if (!allow || !allow.length) continue;
      var v = cellKey(getter(k));
      var hit = false;
      for (var i = 0; i < allow.length; i++) if (String(allow[i]) === v) { hit = true; break; }
      if (!hit) return false;
    }
    return true;
  }

  /* 컬럼에 실제로 나오는 값 목록 (필터 체크박스) */
  function uniqValues(rows, k, cell) {
    var out = [], seen = {}, i, v;
    for (i = 0; i < rows.length; i++) {
      v = cellKey(cell(rows[i], k));
      if (seen[v]) continue;
      seen[v] = 1;
      out.push(v);
    }
    out.sort(function (a, b) {
      var na = /^-?[\d.]+$/.test(a), nb = /^-?[\d.]+$/.test(b);
      if (na && nb) return Number(a) - Number(b);
      return a.localeCompare(b, 'ko');
    });
    return out;
  }

  /* ---------- 기간 ---------- */
  function dateAdd(dstr, days) {
    var m = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(s(dstr));
    if (!m) return '';
    var t = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])));
    t.setUTCDate(t.getUTCDate() + Number(days || 0));
    return t.getUTCFullYear() + '-' + pad2(t.getUTCMonth() + 1) + '-' + pad2(t.getUTCDate());
  }
  function inRange(d, from, to) {
    var v = s(d);
    if (!s(from) && !s(to)) return true;
    if (!v) return false;
    if (s(from) && v < s(from)) return false;
    if (s(to) && v > s(to)) return false;
    return true;
  }
  /* 오늘 / 이번주(월~일) / 이번달 / 유통임박(30일) */
  function presetRange(key, todayStr) {
    var t = s(todayStr);
    if (key === 'today') return { from: t, to: t };
    if (key === 'week') {
      var m = /^(\d{4})-(\d{1,2})-(\d{1,2})$/.exec(t);
      if (!m) return { from: '', to: '' };
      var dow = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]))).getUTCDay();
      var back = (dow + 6) % 7;
      return { from: dateAdd(t, -back), to: dateAdd(t, 6 - back) };
    }
    if (key === 'month') return monthRange(t);
    if (key === 'soon') return { from: t, to: dateAdd(t, 30) };
    return { from: '', to: '' };
  }
  function monthRange(todayStr) {
    var t = s(todayStr);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(t)) return { from: '', to: '' };
    var first = t.slice(0, 8) + '01';
    var next = dateAdd(first, 32).slice(0, 8) + '01';
    return { from: first, to: dateAdd(next, -1) };
  }
  function rangeOf(key, todayStr) {
    if (key === 'month') return monthRange(todayStr);
    return presetRange(key, todayStr);
  }

  /* ---------- 재고 묶음 ---------- */
  /* opt: { major, dateField:'in'|'exp', from, to, cols, sortKey, sortDir } */
  function filterLots(st, wh, q, showZero, opt) {
    opt = opt || {};
    var rows = [], i, l, qq = s(q).toLowerCase();
    for (i = 0; i < st.lots.length; i++) {
      l = st.lots[i];
      if (!showZero && qtyOf(l, wh) <= EPS) continue;
      if (opt.major && opt.major !== 'all' && l.major !== opt.major) continue;
      var base = opt.dateField === 'exp' ? l.e : l.i;
      if (!inRange(base, opt.from, opt.to)) continue;
      if (qq) {
        var hay = [l.n, l.v, l.o, l.i, l.b, l.e, l.mt, l.major].join(' ').toLowerCase();
        if (hay.indexOf(qq) < 0) continue;
      }
      if (!passCols(opt.cols, function (k) { return lotCell(l, k, wh); })) continue;
      rows.push(l);
    }
    return rows;
  }

  /* 제품명 묶음 + 정렬. wh 재고가 0인 로트는 showZero 일 때만. */
  function grouped(st, wh, q, showZero, opt) {
    opt = opt || {};
    var rows = filterLots(st, wh, q, showZero, opt);
    var i, j, groups = {}, order = [], out = [];
    for (i = 0; i < rows.length; i++) {
      var k = rows[i].n;
      if (!groups[k]) { groups[k] = []; order.push(k); }
      groups[k].push(rows[i]);
    }
    order.sort(function (a, b) { return a.localeCompare(b, 'ko'); });
    if (opt.sortKey === 'n' && opt.sortDir === -1) order.reverse();

    var sk = opt.sortKey, sd = opt.sortDir === -1 ? -1 : 1;
    var def = sk && colDef(LOT_COLS, sk);
    for (i = 0; i < order.length; i++) {
      var list = groups[order[i]];
      if (sk && sk !== 'n') {
        list.sort(function (a, b) {
          var c = cmpVal(lotCell(a, sk, wh), lotCell(b, sk, wh), def && def.num);
          if (c !== 0) return sd * c;
          return sortLots(a, b);
        });
      } else {
        list.sort(sortLots);
      }
      var sum = 0, live = 0, amt = 0;
      for (j = 0; j < list.length; j++) {
        sum += qtyOf(list[j], wh);
        amt += qtyOf(list[j], wh) * list[j].price;
        if (qtyOf(list[j], wh) > EPS) live++;
      }
      out.push({ name: order[i], lots: list, sum: r2(sum), live: live, amt: r0(amt) });
    }
    return out;
  }

  function countLive(st, wh) {
    var n = 0;
    for (var i = 0; i < st.lots.length; i++) if (qtyOf(st.lots[i], wh) > EPS) n++;
    return n;
  }

  /* ---------- 입출고 내역 필터/정렬 ---------- */
  function sortLogsDesc(logs) {
    var out = logs.slice();
    out.sort(function (a, b) {
      if (a.d !== b.d) return a.d < b.d ? 1 : -1;
      return (b.dbid || 0) - (a.dbid || 0);
    });
    return out;
  }
  function sortLogsAsc(logs) {
    var out = logs.slice();
    out.sort(function (a, b) {
      if (a.d !== b.d) return a.d < b.d ? -1 : 1;
      return (a.dbid || 0) - (b.dbid || 0);
    });
    return out;
  }

  /* opt: { q, type, major, from, to, cols, sortKey, sortDir } */
  function filterLogs(st, opt) {
    opt = opt || {};
    var out = [], i, e, qq = s(opt.q).toLowerCase();
    for (i = 0; i < st.logs.length; i++) {
      e = st.logs[i];
      if (opt.type && opt.type !== 'all' && e.t !== opt.type) continue;
      if (opt.major && opt.major !== 'all' && e.major !== opt.major) continue;
      if (!inRange(e.d, opt.from, opt.to)) continue;
      if (qq) {
        var hay = [e.n, e.v, e.p, e.note, e.i, e.d, e.worker, typeName(e.t),
          e.t === 'out' ? destName(e.dt) : '', moveName(e), e.major, e.mt].join(' ').toLowerCase();
        if (hay.indexOf(qq) < 0) continue;
      }
      if (!passCols(opt.cols, function (k) { return logCell(e, k); })) continue;
      out.push(e);
    }
    if (opt.sortKey) {
      var def = colDef(LOG_COLS, opt.sortKey), sd = opt.sortDir === -1 ? -1 : 1;
      out.sort(function (a, b) {
        var c = cmpVal(logCell(a, opt.sortKey), logCell(b, opt.sortKey), def && def.num);
        if (c !== 0) return sd * c;
        return (b.dbid || 0) - (a.dbid || 0);
      });
    } else {
      out = sortLogsDesc(out);
    }
    return out;
  }

  /* ---------- CSV ---------- */
  function csvQuote(rows) {
    var out = [], r, c, cells, v;
    for (r = 0; r < rows.length; r++) {
      cells = [];
      for (c = 0; c < rows[r].length; c++) {
        v = rows[r][c] === null || rows[r][c] === undefined ? '' : String(rows[r][c]);
        cells.push('"' + v.replace(/"/g, '""') + '"');
      }
      out.push(cells.join(','));
    }
    return out.join('\r\n');
  }

  /* 입출고 내역 CSV — 날짜, 구분, 대분류, 창고, …, 단가 · 금액, 출고처 · 비고, 작업자 */
  function csv(st) {
    var head = ['날짜', '구분', '대분류', '창고', '제품명', '업체명', '입고일', '소비기한', '중량(kg)',
      '단가(원/kg)', '금액(원)', '출고처 구분', '출고처 / 생산품목', '비고', '작업자'];
    var rows = [head];
    var list = sortLogsDesc(st.logs);
    for (var i = 0; i < list.length; i++) {
      var e = list[i];
      rows.push([
        e.d, typeName(e.t), e.major, moveName(e), e.n, e.v, e.i, e.e, Number(e.k).toFixed(2),
        Number(e.price || 0).toFixed(2), r0(e.amt),
        e.t === 'out' ? destName(e.dt) : '', e.p || '', e.note || '', e.worker || ''
      ]);
    }
    return csvQuote(rows);
  }

  /* 재고 CSV — 대분류, 제품명, 소분류, 원산지, 업체명, 브랜드, 입고일, 소비기한, 재고(kg), 단가, 금액 */
  function stockCsv(st, wh) {
    var head = ['대분류', '제품명', '소분류', '원산지', '업체명', '브랜드', '입고일', '소비기한',
      wh === 'F' ? '냉동고 재고(kg)' : '냉장고 재고(kg)', '단가(원/kg)', '재고금액(원)'];
    var rows = [head];
    var groups = grouped(st, wh, '', false);
    for (var i = 0; i < groups.length; i++) {
      for (var j = 0; j < groups[i].lots.length; j++) {
        var l = groups[i].lots[j];
        var q = qtyOf(l, wh);
        if (q <= EPS) continue;
        rows.push([l.major, l.n, l.mt, l.o, l.v, l.b, l.i, l.e, Number(q).toFixed(2),
          Number(l.price || 0).toFixed(2), r0(q * l.price)]);
      }
    }
    return csvQuote(rows);
  }

  /* ==========================================================================
     실무 양식 내보내기
       · 사방넷 풀필먼트 엑셀입고   : 시트 '엑셀입고',   1행 헤더 8열
       · 경리나라 매출거래명세표     : 시트 '일괄등록',   1행 헤더 20열
     헤더 이름과 순서는 사용자가 준 원본 양식과 똑같이 맞춘다. 바꾸지 말 것.
     ========================================================================== */

  /* 'YYYY-MM-DD' → 'YYYYMMDD' (사방넷 유통기한·제조일자 형식) */
  function ymd8(v) {
    var m = /^(\d{4})-(\d{1,2})-(\d{1,2})/.exec(s(v));
    if (!m) return '';
    return m[1] + pad2(Number(m[2])) + pad2(Number(m[3]));
  }
  /* 'YYYY-MM-DD' → 'MMDD' (경리나라 품목월일 형식) */
  function mmdd(v) {
    var m = /^(\d{4})-(\d{1,2})-(\d{1,2})/.exec(s(v));
    if (!m) return '';
    return pad2(Number(m[2])) + pad2(Number(m[3]));
  }
  /* 값이 있는 것만 '/'로 잇는다 */
  function joinSlash(parts) {
    var out = [];
    for (var i = 0; i < parts.length; i++) {
      var v = s(parts[i]);
      if (v) out.push(v);
    }
    return out.join('/');
  }

  /* 이력 한 건이 가리키는 로트 (원산지·브랜드는 로트에만 있다) */
  function lotOf(st, e) {
    var i, l;
    if (e.lid) {
      for (i = 0; i < st.lots.length; i++) if (st.lots[i].id === 'L' + e.lid) return st.lots[i];
    }
    for (i = 0; i < st.lots.length; i++) {
      l = st.lots[i];
      if (l.n === e.n && l.v === e.v && l.i === e.i && l.e === e.e) return l;
    }
    return null;
  }

  /* 날짜 범위 조건 — opt.range: 'today' | 'range' | 'all' */
  function inDateRange(d, opt) {
    opt = opt || {};
    d = s(d);
    if (opt.range === 'all') return true;
    if (opt.range === 'range') {
      if (!s(opt.from) && !s(opt.to)) return true;
      if (s(opt.from) && d < s(opt.from)) return false;
      if (s(opt.to) && d > s(opt.to)) return false;
      return true;
    }
    return d === s(opt.today);
  }

  /* 사방넷 풀필먼트 '엑셀입고' 양식 — 헤더 8열 */
  var SABANG_HEAD = ['매입처', '출고상품코드', '출고상품명', '수량', '제조일자', '유통기한', '로케이션', '입고메모'];
  function sabangnetRows(st, opt) {
    opt = opt || {};
    var rows = [SABANG_HEAD.slice()];
    var list = sortLogsAsc(st.logs);
    for (var i = 0; i < list.length; i++) {
      var e = list[i];
      var isIn = e.t === 'in';
      var isThaw = e.t === 'thaw';
      if (!isIn && !(opt.thaw && isThaw)) continue;
      if (!inDateRange(e.d, opt)) continue;
      var lot = lotOf(st, e);
      var qty = Math.abs(Number(e.k) || 0);
      if (!(qty > 0)) continue;
      /* 해동은 냉장고로 들어오는 입고라 로케이션을 냉장고로 적는다 */
      var wh = isThaw ? 'C' : e.w;
      rows.push([
        s(e.v),                                        /* 매입처 (업체명) */
        '',                                            /* 출고상품코드 */
        s(e.n),                                        /* 출고상품명 */
        qty,                                           /* 수량 (양수 kg) */
        '',                                            /* 제조일자 */
        ymd8(e.e),                                     /* 유통기한 YYYYMMDD */
        whName(wh),                                    /* 로케이션 냉동고 / 냉장고 */
        joinSlash([lot ? lot.o : '', lot ? lot.b : '', e.note]) /* 입고메모 원산지/브랜드/비고 */
      ]);
    }
    return rows;
  }

  /* 경리나라 '매출거래명세표 일괄등록' 양식 — 헤더 20열
     단가가 있으면 단가·공급가액·세액을 채운다 (부가세 별도면 10%) */
  var SALES_HEAD = ['거래일자', '구분', '거래처명', '사업자번호', '부가세구분', '프로젝트/현장', '창고',
    '품목월일', '품목코드', '품목명', '규격', '수량', '단위', '단가', '공급가액', '세액', '품목비고',
    '입금액', '인수자', '공통메모'];
  function salesRows(st, opt) {
    opt = opt || {};
    var vat = s(opt.vat) || '면세';
    var rows = [SALES_HEAD.slice()];
    var list = sortLogsAsc(st.logs);
    for (var i = 0; i < list.length; i++) {
      var e = list[i];
      if (e.t !== 'out') continue;
      if (!opt.allOut && e.dt !== 'vendor') continue;
      if (!inDateRange(e.d, opt)) continue;
      var qty = Math.abs(Number(e.k) || 0);
      if (!(qty > 0)) continue;
      var lot = lotOf(st, e);
      var price = Number(e.price || 0) > 0 ? Number(e.price) : (lot ? Number(lot.price || 0) : 0);
      var supply = r0(qty * price);
      var tax = vat === '별도' ? r0(supply * 0.1) : 0;
      rows.push([
        s(e.d),                                        /* 거래일자 YYYY-MM-DD */
        '사업자',                                      /* 구분 */
        s(e.p) || destName(e.dt),                      /* 거래처명 */
        '',                                            /* 사업자번호 */
        vat,                                           /* 부가세구분 면세/별도/없음 */
        e.dt === 'site' ? '현장' : '',                 /* 프로젝트/현장 */
        whName(e.w),                                   /* 창고 */
        mmdd(e.d),                                     /* 품목월일 MMDD */
        '',                                            /* 품목코드 */
        s(e.n),                                        /* 품목명 */
        joinSlash([lot ? lot.o : '', lot ? lot.b : '']), /* 규격 원산지/브랜드 */
        qty,                                           /* 수량 (양수) */
        'kg',                                          /* 단위 */
        price,                                         /* 단가 */
        supply,                                        /* 공급가액 */
        tax,                                           /* 세액 */
        s(e.note),                                     /* 품목비고 */
        '', '', ''                                     /* 입금액·인수자·공통메모 */
      ]);
    }
    return rows;
  }

  /* ---------- 입고 단가 이력 (가격 변동·오타 확인) ---------- */
  /* 같은 품목(대분류 포함)의 과거 입고 단가를 날짜·번호 순으로 모은다. 단가 0(미입력)은 뺀다. */
  function priceStats(st, name, major) {
    var key = s(name).toLowerCase();
    var res = { count: 0, last: 0, lastDate: '', prev: 0, prevDate: '', min: 0, max: 0, avg: 0,
      firstDate: '', first: 0 };
    if (!key) return res;
    var rows = [], i, e;
    for (i = 0; i < st.logs.length; i++) {
      e = st.logs[i];
      if (e.t !== 'in') continue;
      if (!(Number(e.price) > 0)) continue;
      if (s(e.n).toLowerCase() !== key) continue;
      if (major && major !== 'all' && e.major !== major) continue;
      rows.push(e);
    }
    rows.sort(function (a, b) {
      if (a.d !== b.d) return a.d < b.d ? -1 : 1;
      return (a.dbid || 0) - (b.dbid || 0);
    });
    if (!rows.length) return res;
    var sum = 0, min = Infinity, max = -Infinity;
    for (i = 0; i < rows.length; i++) {
      var p = Number(rows[i].price);
      sum += p;
      if (p < min) min = p;
      if (p > max) max = p;
    }
    var lastRow = rows[rows.length - 1];
    res.count = rows.length;
    res.min = r0(min);
    res.max = r0(max);
    res.avg = r0(sum / rows.length);
    res.last = r0(lastRow.price);
    res.lastDate = lastRow.d;
    res.first = r0(rows[0].price);
    res.firstDate = rows[0].d;
    if (rows.length > 1) {
      res.prev = r0(rows[rows.length - 2].price);
      res.prevDate = rows[rows.length - 2].d;
    }
    return res;
  }
  /* 새로 입력한 단가를 직전가와 비교 */
  function priceCompare(stat, price) {
    var p = Number(price) || 0;
    var res = { has: !!(stat && stat.count > 0), base: 0, delta: 0, pct: 0, dir: 'none', warn: false, warnAvg: false };
    if (!res.has || !(p > 0)) return res;
    var base = Number(stat.last) || 0;
    res.base = base;
    res.delta = r0(p - base);
    res.pct = base > 0 ? Math.round((p - base) / base * 1000) / 10 : 0;
    res.dir = p > base + 0.004 ? 'up' : (p < base - 0.004 ? 'down' : 'same');
    res.warn = base > 0 && Math.abs(res.pct) >= 30;
    res.warnAvg = Number(stat.avg) > 0 && Math.abs(Math.round((p - stat.avg) / stat.avg * 1000) / 10) >= 30;
    res.warn = res.warn || res.warnAvg;
    return res;
  }

  /* ---------- xlsx 만들기 (외부 라이브러리·CDN 없이 ZIP store + OOXML) ---------- */
  var CRC_TABLE = null;
  function crc32(bytes) {
    if (!CRC_TABLE) {
      CRC_TABLE = [];
      for (var n = 0; n < 256; n++) {
        var c = n;
        for (var k = 0; k < 8; k++) c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
        CRC_TABLE[n] = c >>> 0;
      }
    }
    var v = -1;
    for (var i = 0; i < bytes.length; i++) v = (v >>> 8) ^ CRC_TABLE[(v ^ bytes[i]) & 0xFF];
    return (v ^ -1) >>> 0;
  }
  function utf8(sv) {
    var out = [], i, c, c2, cp;
    for (i = 0; i < sv.length; i++) {
      c = sv.charCodeAt(i);
      if (c < 0x80) out.push(c);
      else if (c < 0x800) out.push(0xC0 | (c >> 6), 0x80 | (c & 0x3F));
      else if (c >= 0xD800 && c <= 0xDBFF && i + 1 < sv.length) {
        c2 = sv.charCodeAt(i + 1);
        if (c2 >= 0xDC00 && c2 <= 0xDFFF) {
          cp = 0x10000 + ((c - 0xD800) << 10) + (c2 - 0xDC00);
          out.push(0xF0 | (cp >> 18), 0x80 | ((cp >> 12) & 0x3F), 0x80 | ((cp >> 6) & 0x3F), 0x80 | (cp & 0x3F));
          i++;
        } else out.push(0xE0 | (c >> 12), 0x80 | ((c >> 6) & 0x3F), 0x80 | (c & 0x3F));
      } else out.push(0xE0 | (c >> 12), 0x80 | ((c >> 6) & 0x3F), 0x80 | (c & 0x3F));
    }
    return out;
  }
  function push16(a, v) { a.push(v & 0xFF, (v >>> 8) & 0xFF); }
  function push32(a, v) { a.push(v & 0xFF, (v >>> 8) & 0xFF, (v >>> 16) & 0xFF, (v >>> 24) & 0xFF); }
  /* 파일 목록 → ZIP(무압축 store) 바이트 배열. [ {name:'a.xml', data:'<xml/>'} ] */
  function zipStore(files) {
    var out = [], central = [], i, f, nameB, dataB, crc, off = 0;
    var DOS_TIME = 0, DOS_DATE = 0x21; /* 1980-01-01 00:00 */
    for (i = 0; i < files.length; i++) {
      f = files[i];
      nameB = utf8(f.name);
      dataB = utf8(f.data);
      crc = crc32(dataB);
      f._off = off;
      push32(out, 0x04034b50);
      push16(out, 20); push16(out, 0x0800); push16(out, 0);
      push16(out, DOS_TIME); push16(out, DOS_DATE);
      push32(out, crc); push32(out, dataB.length); push32(out, dataB.length);
      push16(out, nameB.length); push16(out, 0);
      for (var k = 0; k < nameB.length; k++) out.push(nameB[k]);
      for (var d = 0; d < dataB.length; d++) out.push(dataB[d]);
      off += 30 + nameB.length + dataB.length;
    }
    var cdStart = off, cdSize = 0;
    for (i = 0; i < files.length; i++) {
      f = files[i];
      nameB = utf8(f.name);
      dataB = utf8(f.data);
      crc = crc32(dataB);
      push32(central, 0x02014b50);
      push16(central, 20); push16(central, 20); push16(central, 0x0800); push16(central, 0);
      push16(central, DOS_TIME); push16(central, DOS_DATE);
      push32(central, crc); push32(central, dataB.length); push32(central, dataB.length);
      push16(central, nameB.length); push16(central, 0); push16(central, 0);
      push16(central, 0); push16(central, 0); push32(central, 0);
      push32(central, f._off);
      for (var j = 0; j < nameB.length; j++) central.push(nameB[j]);
      cdSize += 46 + nameB.length;
    }
    for (var m = 0; m < central.length; m++) out.push(central[m]);
    push32(out, 0x06054b50);
    push16(out, 0); push16(out, 0);
    push16(out, files.length); push16(out, files.length);
    push32(out, cdSize); push32(out, cdStart); push16(out, 0);
    return out;
  }

  function xmlEsc(v) {
    return String(v === null || v === undefined ? '' : v)
      .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '')
      .replace(/[&<>"']/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' }[c];
      });
  }
  function colName(n) {
    var out = '';
    while (n > 0) { var m = (n - 1) % 26; out = String.fromCharCode(65 + m) + out; n = Math.floor((n - 1) / 26); }
    return out;
  }
  function numStr(v) {
    var n = Number(v);
    if (!isFinite(n)) return '0';
    return String(n);
  }
  function cellXml(ref, v, style) {
    var st2 = style ? ' s="' + style + '"' : '';
    if (v === null || v === undefined || v === '') return '<c r="' + ref + '"' + st2 + '/>';
    if (typeof v === 'number' && isFinite(v)) return '<c r="' + ref + '"' + st2 + '><v>' + numStr(v) + '</v></c>';
    return '<c r="' + ref + '"' + st2 + ' t="inlineStr"><is><t xml:space="preserve">' + xmlEsc(v) + '</t></is></c>';
  }
  function sheetXml(sheet) {
    var rows = sheet.rows || [], widths = sheet.widths || [], out = [], i, j, r;
    var maxCol = 1;
    for (i = 0; i < rows.length; i++) if (rows[i] && rows[i].length > maxCol) maxCol = rows[i].length;
    out.push('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>');
    out.push('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">');
    out.push('<dimension ref="A1:' + colName(maxCol) + Math.max(1, rows.length) + '"/>');
    out.push('<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>');
    out.push('<sheetFormatPr defaultRowHeight="15"/>');
    if (widths.length) {
      out.push('<cols>');
      for (i = 0; i < widths.length; i++) {
        out.push('<col min="' + (i + 1) + '" max="' + (i + 1) + '" width="' + widths[i] + '" customWidth="1"/>');
      }
      out.push('</cols>');
    }
    out.push('<sheetData>');
    for (i = 0; i < rows.length; i++) {
      r = rows[i] || [];
      out.push('<row r="' + (i + 1) + '">');
      for (j = 0; j < r.length; j++) out.push(cellXml(colName(j + 1) + (i + 1), r[j], i === 0 ? 1 : 0));
      out.push('</row>');
    }
    out.push('</sheetData></worksheet>');
    return out.join('');
  }
  var XML_HEAD = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>';
  function stylesXml() {
    return XML_HEAD +
      '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' +
      '<fonts count="2"><font><sz val="11"/><name val="맑은 고딕"/></font>' +
      '<font><b/><sz val="11"/><name val="맑은 고딕"/></font></fonts>' +
      '<fills count="2"><fill><patternFill patternType="none"/></fill>' +
      '<fill><patternFill patternType="gray125"/></fill></fills>' +
      '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>' +
      '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>' +
      '<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>' +
      '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>' +
      '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>' +
      '</styleSheet>';
  }
  /* sheets: [ {name:'엑셀입고', rows:[[...],...], widths:[14,12,...]} ] → xlsx 바이트(숫자 배열) */
  function xlsxBytes(sheets) {
    var files = [], i, n = sheets.length;
    var ct = [XML_HEAD, '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
      '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
      '<Default Extension="xml" ContentType="application/xml"/>',
      '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
      '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'];
    for (i = 0; i < n; i++) {
      ct.push('<Override PartName="/xl/worksheets/sheet' + (i + 1) + '.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>');
    }
    ct.push('</Types>');
    files.push({ name: '[Content_Types].xml', data: ct.join('') });
    files.push({ name: '_rels/.rels', data: XML_HEAD +
      '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
      '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>' +
      '</Relationships>' });
    var wb = [XML_HEAD, '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" ',
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'];
    for (i = 0; i < n; i++) wb.push('<sheet name="' + xmlEsc(sheets[i].name) + '" sheetId="' + (i + 1) + '" r:id="rId' + (i + 1) + '"/>');
    wb.push('</sheets></workbook>');
    files.push({ name: 'xl/workbook.xml', data: wb.join('') });
    var rels = [XML_HEAD, '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'];
    for (i = 0; i < n; i++) {
      rels.push('<Relationship Id="rId' + (i + 1) + '" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet' + (i + 1) + '.xml"/>');
    }
    rels.push('<Relationship Id="rId' + (n + 1) + '" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>');
    rels.push('</Relationships>');
    files.push({ name: 'xl/_rels/workbook.xml.rels', data: rels.join('') });
    files.push({ name: 'xl/styles.xml', data: stylesXml() });
    for (i = 0; i < n; i++) files.push({ name: 'xl/worksheets/sheet' + (i + 1) + '.xml', data: sheetXml(sheets[i]) });
    return zipStore(files);
  }

  /* 자동완성·필터 목록 (지금 데이터에서 뽑는다) */
  function dict(st) {
    var names = [], vendors = [], origins = [], brands = [], products = [], majors = [], meats = [];
    var seen = { n: {}, v: {}, o: {}, b: {}, p: {}, m: {}, t: {} };
    function add(arr, seenMap, v) {
      v = s(v);
      if (!v || seenMap[v]) return;
      seenMap[v] = 1;
      arr.push(v);
    }
    var i, l, e;
    for (i = 0; i < MAJORS.length; i++) add(majors, seen.m, MAJORS[i]);
    for (i = 0; i < MEATS.length; i++) add(meats, seen.t, MEATS[i]);
    for (i = 0; i < st.lots.length; i++) {
      l = st.lots[i];
      add(names, seen.n, l.n);
      add(vendors, seen.v, l.v);
      add(origins, seen.o, l.o);
      add(brands, seen.b, l.b);
      add(majors, seen.m, l.major);
      add(meats, seen.t, l.mt);
    }
    for (i = 0; i < st.logs.length; i++) {
      e = st.logs[i];
      add(names, seen.n, e.n);
      add(vendors, seen.v, e.v);
      add(majors, seen.m, e.major);
      add(meats, seen.t, e.mt);
      if (e.t === 'out' && e.p) add(products, seen.p, e.p);
    }
    return { names: names, vendors: vendors, origins: origins, brands: brands,
      products: products, majors: majors, meats: meats };
  }

  /* 택배·기타 출고처는 그동안 쓴 이름을 자동완성으로 재사용한다. */
  function destHistory(st) {
    var courier = [], other = [], seenC = {}, seenO = {}, i, e, v;
    for (i = 0; i < st.logs.length; i++) {
      e = st.logs[i];
      if (e.t !== 'out' || !e.p) continue;
      v = s(e.p);
      if (e.dt === 'courier' && !seenC[v]) { seenC[v] = 1; courier.push(v); }
      if (e.dt === 'other' && !seenO[v]) { seenO[v] = 1; other.push(v); }
    }
    return { courier: courier, other: other };
  }

  /* 서버에 보내기 전에 비어 있는 필수칸만 먼저 걸러 준다 (최종 검증은 서버 함수) */
  function precheck(p) {
    if (p.type === 'in') {
      if (!s(p.name)) return { msg: '제품명을 입력하세요.', field: 'name' };
      if (p.wh !== 'F' && p.wh !== 'C') return { msg: '받는 창고를 선택하세요.', field: 'wh' };
      if (!s(p.in_date)) return { msg: '입고일을 입력하세요.', field: 'inDate' };
      if (!s(p.exp_date)) return { msg: '소비기한을 입력하세요.', field: 'expiry' };
    } else if (p.type === 'out') {
      if (!s(p.lot_id)) return { msg: '먼저 재고표에서 출고할 로트를 선택하세요.', field: 'lot' };
      if (p.wh !== 'F' && p.wh !== 'C') return { msg: '출발 창고를 선택하세요.', field: 'wh' };
      if (!s(p.dest)) {
        return { msg: '출고처를 입력하세요. (' + destName(p.dest_type) + ' · ' + DEST_LABEL[destKey(p.dest_type)] + ')', field: 'dest' };
      }
    } else {
      if (!s(p.lot_id)) return { msg: '먼저 재고표에서 ' + (p.type === 'thaw' ? '해동' : '재냉동') + '할 로트를 선택하세요.', field: 'lot' };
    }
    if (!(Number(p.kg) > 0)) return { msg: '중량(kg)은 0보다 커야 합니다.', field: 'kg' };
    if (p.price !== undefined && p.price !== '' && Number(p.price) < 0) {
      return { msg: '단가(원/kg)는 0보다 작을 수 없습니다.', field: 'price' };
    }
    if (p.amount !== undefined && p.amount !== '' && Number(p.amount) < 0) {
      return { msg: '금액(원)은 0보다 작을 수 없습니다.', field: 'amount' };
    }
    return null;
  }

  /* 수정 모달에서 저장하기 전 확인 */
  function precheckUpdate(p) {
    if (!s(p.date)) return { msg: '거래일을 입력하세요.', field: 'date' };
    if (!(Number(p.kg) > 0)) return { msg: '중량(kg)은 0보다 커야 합니다.', field: 'kg' };
    if (Number(p.price) < 0) return { msg: '단가(원/kg)는 0보다 작을 수 없습니다.', field: 'price' };
    if (Number(p.amount) < 0) return { msg: '금액(원)은 0보다 작을 수 없습니다.', field: 'amount' };
    if (p.type === 'out' && !s(p.dest)) return { msg: '출고처를 입력하세요.', field: 'dest' };
    return null;
  }

  return {
    EPS: EPS, r2: r2, r0: r0, MAJORS: MAJORS, MAJOR_DEFAULT: MAJOR_DEFAULT, majorName: majorName,
    MEATS: MEATS, meatName: meatName,
    DESTS: DEST_KEYS, DEST_NAME: DEST_NAME, DEST_LABEL: DEST_LABEL, DEST_HINT: DEST_HINT,
    destKey: destKey, destName: destName, typeName: typeName, whName: whName, moveName: moveName,
    stateFrom: stateFrom, totals: totals, getLot: getLot, getLog: getLog, qtyOf: qtyOf, lotValue: lotValue,
    sortLots: sortLots, LOT_COLS: LOT_COLS, LOG_COLS: LOG_COLS, lotCols: lotCols,
    lotCell: lotCell, logCell: logCell, cellKey: cellKey, passCols: passCols, uniqValues: uniqValues,
    dateAdd: dateAdd, inRange: inRange, presetRange: presetRange, rangeOf: rangeOf, monthRange: monthRange,
    grouped: grouped, filterLots: filterLots, countLive: countLive,
    sortLogsDesc: sortLogsDesc, sortLogsAsc: sortLogsAsc, filterLogs: filterLogs,
    priceStats: priceStats, priceCompare: priceCompare,
    csv: csv, stockCsv: stockCsv, csvQuote: csvQuote, dict: dict, destHistory: destHistory,
    precheck: precheck, precheckUpdate: precheckUpdate,
    SABANG_HEAD: SABANG_HEAD, SALES_HEAD: SALES_HEAD, sabangnetRows: sabangnetRows, salesRows: salesRows,
    lotOf: lotOf, ymd8: ymd8, mmdd: mmdd, inDateRange: inDateRange,
    xlsxBytes: xlsxBytes, zipStore: zipStore, crc32: crc32, colName: colName
  };
})();
/* ============================== CORE:END ============================== */

/* ============================== API:START ============================== */
var SB = (function () {
  'use strict';
  var URL_ = String(CONFIG.SUPABASE_URL).replace(/\/+$/, '');
  var KEY = CONFIG.SUPABASE_ANON_KEY;
  var SESKEY = 'meatERP.session.v1';
  var ses = null;

  /* ---------- 도우미 ---------- */
  function errOf(msg, kind, status) {
    var e = new Error(msg);
    e.kind = kind || 'app';
    e.status = status || 0;
    return e;
  }
  function readBody(res) {
    var ct = res.headers && res.headers.get('content-type') || '';
    if (ct.indexOf('json') >= 0) return res.json().catch(function () { return null; });
    return res.text().then(function (t) { return t; });
  }
  function errMessage(body, status) {
    var m = body && (body.msg || body.message || body.error_description || body.error);
    if (typeof m !== 'string') m = '';
    if (/Invalid login credentials/i.test(m)) return '이메일 또는 비밀번호가 맞지 않습니다.';
    if (/Email not confirmed/i.test(m)) return '이메일 확인이 아직 안 됐습니다. 받은 메일의 확인 링크를 누르거나, 관리자에게 계정 확인을 요청하세요.';
    if (/User already registered|already been registered/i.test(m)) return '이미 가입된 이메일입니다. 위의 로그인 탭에서 로그인해 주세요.';
    if (/Password should be at least|password.*too short/i.test(m)) return '비밀번호가 너무 짧습니다. 6자 이상으로 만들어 주세요.';
    if (/Unable to validate email|invalid.*email/i.test(m)) return '이메일 형식이 올바르지 않습니다.';
    if (/For security purposes|only request this after/i.test(m)) return '잠시 뒤 다시 시도해 주세요. (연속 요청 제한)';
    if (status === 429) return '시도가 너무 잦습니다. 1분 뒤 다시 시도해 주세요.';
    if (status === 401) return '로그인이 만료되었습니다. 다시 로그인해 주세요.';
    if (/Could not find the table|relation .* does not exist|PGRST205|schema cache/i.test(m)) {
      return 'DB 표를 찾을 수 없습니다. supabase_setup.sql을 먼저 실행해 주세요.';
    }
    if (/permission denied/i.test(m)) return '이 작업을 할 권한이 없습니다. 로그인 상태를 확인해 주세요.';
    if (/JWT expired|invalid JWT|token is expired/i.test(m)) return '로그인이 만료되었습니다. 다시 로그인해 주세요.';
    if (/duplicate key value/i.test(m)) return '같은 내용이 이미 있습니다. 새로고침 후 다시 시도해 주세요.';
    if (m) return m;
    return '요청을 처리하지 못했습니다. (' + status + ')';
  }
  function request(url, opts) {
    return fetch(url, opts).then(function (res) {
      return readBody(res).then(function (body) {
        if (res.ok) return body;
        throw errOf(errMessage(body, res.status), 'http', res.status);
      });
    }, function () {
      throw errOf('인터넷 연결을 확인해 주세요. (서버에 닿지 않습니다)', 'network', 0);
    });
  }
  function authUrl(path) { return URL_ + '/auth/v1/' + path; }
  function authReq(path, body, token) {
    var h = { apikey: KEY, 'Content-Type': 'application/json' };
    if (token) h.Authorization = 'Bearer ' + token;
    var opts = { method: body ? 'POST' : 'GET', headers: h };
    if (body) opts.body = JSON.stringify(body);
    return request(authUrl(path), opts);
  }

  /* ---------- 세션 ---------- */
  function sesFrom(tok) {
    var u = (tok && tok.user) || {};
    var meta = u.user_metadata || {};
    var email = u.email || '';
    return {
      access: tok.access_token, refresh: tok.refresh_token,
      exp: Date.now() + Number(tok.expires_in || 3600) * 1000,
      email: email, name: meta.name || meta.full_name || email.split('@')[0], uid: u.id || ''
    };
  }
  function persist() {
    try {
      if (ses) localStorage.setItem(SESKEY, JSON.stringify(ses));
      else localStorage.removeItem(SESKEY);
    } catch (e) { /* 저장 못 하는 환경 무시 */ }
  }
  function readStored() {
    try {
      var raw = localStorage.getItem(SESKEY);
      if (!raw) return null;
      var s = JSON.parse(raw);
      if (s && s.access && s.refresh) return s;
    } catch (e) { /* 무시 */ }
    return null;
  }
  function signIn(email, pw) {
    return authReq('token?grant_type=password', { email: email, password: pw }).then(function (r) {
      if (!r || !r.access_token) throw errOf('로그인하지 못했습니다. 계정 확인 상태를 확인해 주세요.', 'auth');
      ses = sesFrom(r); persist(); return ses;
    });
  }
  function signUp(email, pw, name) {
    return authReq('signup', { email: email, password: pw, data: { name: name || '' } }).then(function (r) {
      if (r && r.access_token) { ses = sesFrom(r); persist(); return { session: ses }; }
      return { confirm: true, email: (r && r.email) || email };
    });
  }
  function refresh() {
    if (!ses || !ses.refresh) return Promise.reject(errOf('다시 로그인해 주세요.', 'auth', 401));
    return authReq('token?grant_type=refresh_token', { refresh_token: ses.refresh }).then(function (r) {
      ses = sesFrom(r); persist(); return ses;
    }, function (e) {
      ses = null; persist();
      throw errOf('로그인이 만료되었습니다. 다시 로그인해 주세요.', 'auth', 401);
    });
  }
  function signOut() {
    var t = ses && ses.access;
    ses = null; persist();
    if (!t) return Promise.resolve();
    return request(authUrl('logout'), { method: 'POST', headers: { apikey: KEY, Authorization: 'Bearer ' + t } })
      .catch(function () { /* 서버 로그아웃 실패해도 기기에서는 지운다 */ });
  }
  function ensure() {
    if (!ses) return Promise.reject(errOf('로그인이 필요합니다.', 'auth', 401));
    if (ses.exp - Date.now() > 60000) return Promise.resolve(ses);
    return refresh();
  }

  /* ---------- 데이터 ---------- */
  function rest(path, opts, retried) {
    opts = opts || {};
    return ensure().then(function (s) {
      var h = { apikey: KEY, Authorization: 'Bearer ' + s.access };
      if (opts.body) h['Content-Type'] = 'application/json';
      if (opts.headers) for (var k in opts.headers) if (opts.headers.hasOwnProperty(k)) h[k] = opts.headers[k];
      var o = { method: opts.method || 'GET', headers: h };
      if (opts.body) o.body = JSON.stringify(opts.body);
      return fetch(URL_ + '/rest/v1/' + path, o).then(function (res) {
        if (res.status === 401 && !retried) {
          return refresh().then(function () { return rest(path, opts, true); });
        }
        return readBody(res).then(function (body) {
          if (res.ok) return body;
          throw errOf(errMessage(body, res.status), 'http', res.status);
        });
      }, function () {
        throw errOf('인터넷 연결을 확인해 주세요.', 'network', 0);
      });
    });
  }
  var PAGE = 1000;
  function selectAll(table, order) {
    var out = [];
    var seen = {};
    function step(from, pageNo) {
      if (pageNo > 40) return out;
      var headers = { Range: from + '-' + (from + PAGE - 1), 'Range-Unit': 'items' };
      return rest(table + '?select=*&order=' + order, { headers: headers }).then(function (rows) {
        rows = rows || [];
        for (var i = 0; i < rows.length; i++) {
          var key = String(rows[i].id);
          if (seen[key]) continue;
          seen[key] = 1;
          out.push(rows[i]);
        }
        if (rows.length < PAGE) return out;
        return step(from + PAGE, pageNo + 1);
      });
    }
    return step(0, 0);
  }
  function loadAll() {
    return Promise.all([selectAll('lots', 'id.asc'), selectAll('tx_logs', 'id.asc')])
      .then(function (r) { return { lots: r[0] || [], logs: r[1] || [] }; });
  }
  /* 저장: 화면 파라미터 → DB 함수 파라미터 */
  function apply(p) {
    return rest('rpc/tx_apply', {
      method: 'POST', body: {
        p_date: p.date || null,
        p_type: p.type,
        p_wh: p.wh || null,
        p_lot_id: p.lot_id === null || p.lot_id === undefined || p.lot_id === '' ? null : Number(p.lot_id),
        p_kg: Number(p.kg || 0),
        p_dest_type: p.dest_type || '',
        p_dest: p.dest || '',
        p_note: p.note || '',
        p_name: p.name || '',
        p_vendor: p.vendor || '',
        p_in_date: p.in_date || null,
        p_exp_date: p.exp_date || null,
        p_meat: p.meat || '',
        p_origin: p.origin || '',
        p_brand: p.brand || '',
        p_major: p.major || '원료육',
        p_unit_price: Number(p.price || 0),
        p_amount: p.amount === undefined || p.amount === null || p.amount === '' ? null : Number(p.amount)
      }
    });
  }
  /* 입력한 이력 수정 (서버가 예전 영향을 되돌리고 새 값으로 다시 계산) */
  function update(p) {
    return rest('rpc/tx_update', {
      method: 'POST', body: {
        p_log_id: Number(p.logId),
        p_date: p.date || null,
        p_kg: Number(p.kg || 0),
        p_unit_price: Number(p.price || 0),
        p_amount: p.amount === undefined || p.amount === null || p.amount === '' ? null : Number(p.amount),
        p_dest_type: p.dest_type || '',
        p_dest: p.dest || '',
        p_note: p.note || '',
        p_wh: p.wh || null
      }
    });
  }
  /* 로트 정보(대분류·소분류·품목명·브랜드·원산지·업체·기준단가·날짜) 수정 */
  function lotUpdate(p) {
    return rest('rpc/lot_update', {
      method: 'POST', body: {
        p_lot_id: Number(p.lotId),
        p_major: p.major || null,
        p_meat: p.meat === undefined ? null : String(p.meat || ''),
        p_name: p.name || null,
        p_brand: p.brand === undefined ? null : String(p.brand || ''),
        p_origin: p.origin === undefined ? null : String(p.origin || ''),
        p_vendor: p.vendor === undefined ? null : String(p.vendor || ''),
        p_unit_price: p.price === undefined || p.price === null || p.price === '' ? null : Number(p.price),
        p_in_date: p.in_date || null,
        p_exp_date: p.exp_date || null
      }
    });
  }
  function undo(logId) { return rest('rpc/tx_undo', { method: 'POST', body: { p_log_id: Number(logId) } }); }

  function restore() {
    ses = readStored();
    return ses;
  }

  return {
    auth: { signIn: signIn, signUp: signUp, signOut: signOut, refresh: refresh, ensure: ensure, restore: restore, session: function () { return ses; } },
    db: { loadAll: loadAll, apply: apply, update: update, lotUpdate: lotUpdate, undo: undo, rest: rest },
    errOf: errOf
  };
})();

/* ---------- 실시간(웹소켓) + 주기 재조회 ---------- */
var LIVE = (function () {
  'use strict';
  var ws = null, ref = 0, joined = false, topic = 'realtime:erp', hb = null, retry = 0;
  var onChange = null, onState = null, stopped = true, stateText = 'off';

  function wsUrl() {
    var base = String(CONFIG.SUPABASE_URL).replace(/^http/, 'ws').replace(/\/+$/, '');
    return base + '/realtime/v1/websocket?apikey=' + encodeURIComponent(CONFIG.SUPABASE_ANON_KEY) + '&vsn=1.0.0';
  }
  function send(obj) { try { if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj)); } catch (e) { } }
  function join() {
    var s = SB.auth.session();
    if (!s) return;
    ref += 1;
    send({
      topic: topic, event: 'phx_join', ref: String(ref), join_ref: String(ref),
      payload: {
        config: {
          broadcast: { ack: false, self: false },
          presence: { key: '' },
          postgres_changes: [
            { event: '*', schema: 'public', table: 'lots' },
            { event: '*', schema: 'public', table: 'tx_logs' }
          ]
        },
        access_token: s.access
      }
    });
  }
  function setState(t) {
    stateText = t;
    if (typeof onState === 'function') onState(t);
  }
  function connect() {
    if (stopped) return;
    if (typeof WebSocket === 'undefined') { setState('poll'); return; }
    try { ws = new WebSocket(wsUrl()); } catch (e) { setState('poll'); return; }
    ws.onopen = function () {
      joined = false; retry = 0; join(); setState('connecting');
      hb = setInterval(function () { ref += 1; send({ topic: 'phoenix', event: 'heartbeat', payload: {}, ref: String(ref) }); }, 25000);
    };
    ws.onmessage = function (ev) {
      var msg;
      try { msg = JSON.parse(ev.data); } catch (e) { return; }
      if (!msg || !msg.event) return;
      if (msg.event === 'phx_reply' && msg.payload && msg.payload.status === 'ok') {
        if (msg.topic === topic) { joined = true; setState('live'); }
      } else if (msg.event === 'phx_error' || msg.event === 'phx_close') {
        setState('poll');
      } else if (msg.event === 'postgres_changes') {
        if (typeof onChange === 'function') onChange();
      }
    };
    ws.onclose = function () {
      if (hb) { clearInterval(hb); hb = null; }
      joined = false;
      setState('poll');
      if (stopped) return;
      retry += 1;
      var wait = Math.min(30000, 1500 * retry);
      setTimeout(connect, wait);
    };
    ws.onerror = function () { /* onclose가 이어서 처리 */ };
  }
  function start(cb, stCb) {
    onChange = cb; onState = stCb || null; stopped = false; retry = 0;
    connect();
  }
  function stop() {
    stopped = true; onChange = null;
    if (hb) { clearInterval(hb); hb = null; }
    try { if (ws) ws.close(); } catch (e) { }
    ws = null; joined = false; stateText = 'off';
  }
  function state() { return stateText; }
  return { start: start, stop: stop, state: state };
})();
/* ============================== API:END ============================== */

/* ============================== UI:START ============================== */
(function () {
  'use strict';
  var st = { lots: [], logs: [], loadedAt: 0 };
  var cur = {
    mode: 'in', tab: 'F', whIn: 'F', whOut: 'C', dest: 'site',
    search: '', showZero: false, hFilter: 'all', hLimit: 250, lotId: null,
    major: 'all',
    stock: { preset: 'all', field: 'in', from: '', to: '' },
    hist: { preset: 'all', from: '', to: '' },
    sortLot: { k: '', dir: 1 },
    sortLog: { k: '', dir: -1 },
    fLot: {}, fLog: {}
  };
  var prev = {};
  var loading = false, again = false;
  var pollTimer = null;
  var editing = null, lotEditing = null;
  var fpop = { open: false, tbl: '', key: '', rect: null, all: [], sel: {}, q: '' };

  function $(id) { return document.getElementById(id); }
  function esc(v) {
    return String(v === null || v === undefined ? '' : v).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function fmtInt(x) {
    var n = Math.round(Number(x || 0));
    var neg = n < 0;
    return (neg ? '-' : '') + String(Math.abs(n)).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  }
  function fmt(x) {
    var n = Number(x || 0);
    var neg = n < 0;
    var s = Math.abs(n).toFixed(2).split('.');
    return (neg ? '-' : '') + s[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',') + '.' + s[1];
  }
  function pad2(n) { return (n < 10 ? '0' : '') + n; }
  function today() {
    var d = new Date();
    return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate());
  }
  function clock() {
    var d = new Date();
    return pad2(d.getHours()) + ':' + pad2(d.getMinutes()) + ':' + pad2(d.getSeconds());
  }
  function daysLeft(exp) {
    if (!exp) return null;
    var parts = String(exp).split('-');
    if (parts.length < 3) return null;
    var t = new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2]));
    var n = new Date();
    n.setHours(0, 0, 0, 0);
    return Math.round((t.getTime() - n.getTime()) / 86400000);
  }
  function ddayHtml(exp) {
    var d = daysLeft(exp);
    if (d === null) return '';
    if (d < 0) return '<span class="dday danger">만료 ' + Math.abs(d) + '일</span>';
    if (d <= 30) return '<span class="dday warn">D-' + d + '</span>';
    if (d <= 90) return '<span class="dday ok">D-' + d + '</span>';
    return '';
  }

  /* ---------- 토스트 ---------- */
  function toast(msg, kind) {
    var box = $('toast');
    if (!box) return;
    var el = document.createElement('div');
    el.className = 'tmsg ' + (kind || '');
    el.textContent = msg;
    box.appendChild(el);
    requestAnimationFrame(function () { el.classList.add('show'); });
    setTimeout(function () {
      el.classList.remove('show');
      setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 260);
    }, 3600);
  }

  /* ---------- 동기화 상태 ---------- */
  function setSync(kind, text) {
    var el = $('syncState');
    if (!el) return;
    el.className = 'sync ' + kind;
    $('syncText').textContent = text;
  }
  function liveLabel(kind) {
    if (kind === 'live') setSync('ok', '실시간 연결됨 · ' + clock());
    else if (kind === 'connecting') setSync('wait', '실시간 연결 중…');
    else if (kind === 'poll') setSync('poll', '자동 새로고침(1분) · ' + clock());
  }
  function showBanner(html) {
    var b = $('banner');
    b.innerHTML = html;
    b.classList.remove('hidden');
  }
  function hideBanner() { $('banner').classList.add('hidden'); }
  function isSetupError(e) {
    return e && (/supabase_setup\.sql|만들 수 없습니다|DB 표를 찾을 수 없습니다/.test(e.message || ''));
  }

  /* ---------- KPI ---------- */
  function kpi(id, val, dp) {
    var el = $(id);
    var txt = dp === 0 ? fmtInt(val) : fmt(val);
    if (prev[id] !== undefined && prev[id] !== txt) {
      el.classList.remove('flash');
      void el.offsetWidth;
      el.classList.add('flash');
    }
    el.textContent = txt;
    prev[id] = txt;
  }
  function renderKPI() {
    var t = ERP.totals(st);
    kpi('kFree', t.frozen);
    kpi('kChill', t.chilled);
    kpi('kValue', t.value, 0);
    kpi('kLive', t.live, 0);
    var tp = 0, d0 = today(), priced = 0, i;
    for (i = 0; i < st.logs.length; i++) if (st.logs[i].d === d0) tp++;
    for (i = 0; i < st.lots.length; i++) if (st.lots[i].price > 0 && (st.lots[i].fq + st.lots[i].cq) > ERP.EPS) priced++;
    kpi('kToday', tp, 0);
    $('kFreeSub').textContent = '보관 로트 ' + t.liveFrozen + '개';
    $('kChillSub').textContent = '보관 로트 ' + t.liveChilled + '개';
    $('kValueSub').textContent = '단가 있는 로트 ' + priced + '개 기준';
    $('kLiveSub').textContent = '전체 ' + st.lots.length + '개 로트 중';
    $('kTodaySub').textContent = d0 + ' 입력 기준';
    $('cntF').textContent = ERP.countLive(st, 'F');
    $('cntC').textContent = ERP.countLive(st, 'C');
    $('cntH').textContent = st.logs.length;
  }

  /* ---------- 표 머리글 (정렬 + 필터) ---------- */
  function thHtml(c, sort, filt) {
    var on = !!(sort && sort.k === c.k);
    var arrow = on ? (sort.dir === -1 ? '▼' : '▲') : '';
    var onF = !!(filt && filt[c.k] && filt[c.k].length);
    return '<th class="' + (c.num ? 'num' : '') + '" data-col="' + c.k + '">' +
      '<div class="hdbox">' +
      '<button type="button" class="hdsort' + (on ? ' on' : '') + '" data-sort="' + c.k + '" title="' + esc(c.t) + ' 정렬">' +
      '<span class="ht">' + esc(c.t) + '</span><span class="harrow">' + arrow + '</span></button>' +
      '<button type="button" class="hdfilt' + (onF ? ' on' : '') + '" data-filter="' + c.k + '" title="' + esc(c.t) + ' 값 필터" aria-label="' + esc(c.t) + ' 필터">▾</button>' +
      '</div></th>';
  }
  function colGroup(cols, extra) {
    var out = ['<colgroup>'], i;
    for (i = 0; i < cols.length; i++) {
      out.push(cols[i].w ? '<col style="width:' + cols[i].w + 'px">' : '<col>');
    }
    if (extra) out.push('<col style="width:' + extra + 'px">');
    out.push('</colgroup>');
    return out.join('');
  }

  /* ---------- 재고표 ---------- */
  function lotOpts() {
    return {
      major: cur.major, dateField: cur.stock.field, from: cur.stock.from, to: cur.stock.to,
      cols: cur.fLot, sortKey: cur.sortLot.k, sortDir: cur.sortLot.dir
    };
  }
  function renderStock(wh) {
    var wrap = $('tableWrap');
    var keep = wrap.scrollTop, keepL = wrap.scrollLeft;
    var cols = ERP.lotCols(wh);
    var groups = ERP.grouped(st, wh, cur.search, cur.showZero, lotOpts());

    var nRow = 0, kg = 0, amt = 0, i, j;
    for (i = 0; i < groups.length; i++) { nRow += groups[i].lots.length; kg += groups[i].sum; amt += groups[i].amt; }
    setRangeSum(nRow + '개 로트', kg, amt);

    if (!groups.length) {
      wrap.innerHTML = '<table><tbody><tr class="empty-row"><td>조건에 맞는 로트가 없습니다. 기간·대분류·필터를 넓혀 보세요.</td></tr></tbody></table>';
      wrap.scrollTop = 0;
      return;
    }
    var html = ['<table class="fixed t-lot">', colGroup(cols, 126),
      '<thead><tr>'];
    for (i = 0; i < cols.length; i++) html.push(thHtml(cols[i], cur.sortLot, cur.fLot));
    html.push('<th class="num"><span class="th-plain">작업</span></th></tr></thead><tbody>');

    for (i = 0; i < groups.length; i++) {
      var g = groups[i];
      html.push('<tr class="group"><td colspan="' + (cols.length + 1) + '"><span class="g-name">' + esc(g.name) + '</span>' +
        '<span class="g-meta">' + g.lots.length + '개 로트 · 보관 ' + g.live + '개 · <b>' + fmt(g.sum) + '</b> kg' +
        (g.amt ? ' · <b>' + fmtInt(g.amt) + '</b>원' : '') + '</span></td></tr>');
      for (j = 0; j < g.lots.length; j++) {
        var lot = g.lots[j];
        var qv = ERP.qtyOf(lot, wh);
        var sel = cur.lotId === lot.id ? ' sel' : '';
        html.push('<tr class="lot' + sel + '" data-lot="' + lot.id + '">');
        for (var c = 0; c < cols.length; c++) {
          html.push(lotCellHtml(lot, cols[c].k, wh, qv));
        }
        html.push('<td><div class="acts">' +
          (wh === 'F'
            ? '<button class="act thaw" data-act="thaw" data-lot="' + lot.id + '"' + (qv <= ERP.EPS ? ' disabled' : '') + '>해동</button>'
            : '<button class="act re" data-act="re" data-lot="' + lot.id + '"' + (qv <= ERP.EPS ? ' disabled' : '') + '>재냉동</button>') +
          '<button class="act out" data-act="out" data-lot="' + lot.id + '"' + (qv <= ERP.EPS ? ' disabled' : '') + '>출고</button>' +
          '<button class="act edit" data-lot-edit="' + lot.id + '">수정</button>' +
          '</div></td>');
        html.push('</tr>');
      }
    }
    html.push('</tbody></table>');
    wrap.innerHTML = html.join('');
    wrap.scrollTop = keep;
    wrap.scrollLeft = keepL;
  }

  function lotCellHtml(lot, k, wh, qv) {
    if (k === 'major') return '<td><span class="mj">' + esc(lot.major || ERP.MAJOR_DEFAULT) + '</span></td>';
    if (k === 'mt') return '<td><span class="mtag mt-' + esc(lot.mt || '기타') + '">' + esc(lot.mt || '-') + '</span></td>';
    if (k === 'n') return '<td class="ellip"><b>' + esc(lot.n) + '</b></td>';
    if (k === 'qty') return '<td class="num' + (qv <= ERP.EPS ? ' zero' : '') + '">' + fmt(qv) + '</td>';
    if (k === 'price') return '<td class="num">' + (lot.price > 0 ? fmtInt(lot.price) : '<span class="ttag">-</span>') + '</td>';
    if (k === 'amt') return '<td class="num" title="' + (lot.price > 0 ? fmtInt(Math.round(qv * lot.price)) + '원' : '단가 미입력') + '">' +
      (lot.price > 0 ? fmtInt(Math.round(qv * lot.price)) : '<span class="ttag">-</span>') + '</td>';
    if (k === 'e') return '<td>' + esc(lot.e || '-') + ddayHtml(lot.e) + '</td>';
    if (k === 'i') return '<td>' + esc(lot.i || '-') + '</td>';
    return '<td class="ellip">' + esc(ERP.lotCell(lot, k, wh) || '-') + '</td>';
  }

  /* ---------- 입출고 내역 ---------- */
  function setRangeSum(n, kg, amt) {
    var el = $('rangeSum');
    if (!el) return;
    el.textContent = n + ' · ' + fmt(kg) + ' kg' + (amt ? ' · ' + fmtInt(amt) + '원' : '');
  }
  function renderHistNote() {
    var orig = 0, mine = 0, i;
    for (i = 0; i < st.logs.length; i++) {
      if (st.logs[i].act) mine++; else orig++;
    }
    $('histNote').textContent = '처음 엑셀에서 옮긴 이력 ' + orig + '건 + 화면에서 입력한 이력 ' + mine + '건. ' +
      '화면에서 입력한 건은 [수정]으로 고치거나 [취소]로 되돌릴 수 있고, 취소하면 재고도 함께 원복됩니다. ' +
      '원본 엑셀 이력은 보존을 위해 수정·취소할 수 없습니다.';
  }
  function destCell(e) {
    var extra = [];
    if (e.t === 'out') {
      extra.push('<span class="dtype ' + ERP.destKey(e.dt) + '">' + ERP.destName(e.dt) + '</span>' +
        (e.p ? ' ' + esc(e.p) : ''));
    } else if (e.p) {
      extra.push(esc(e.p));
    }
    if (e.t === 'thaw' || e.t === 're') {
      extra.push('<span class="ttag">' + (e.t === 'thaw' ? '냉동 −' : '냉장 −') + fmt(e.k) +
        ' / ' + (e.t === 'thaw' ? '냉장 +' : '냉동 +') + fmt(e.k) + '</span>');
    }
    if (e.note) extra.push('<span class="ttag">' + esc(e.note) + '</span>');
    return extra.join(' ') || '<span class="ttag">-</span>';
  }
  function destTitle(e) {
    var parts = [];
    if (e.t === 'out') parts.push(ERP.destName(e.dt) + ' ' + (e.p || ''));
    else if (e.p) parts.push(e.p);
    if (e.note) parts.push(e.note);
    return parts.join(' · ');
  }
  function logCellHtml(e, k) {
    if (k === 'd') return '<td>' + esc(e.d || '-') + '</td>';
    if (k === 't') return '<td><span class="badge ' + esc(e.t) + '">' + ERP.typeName(e.t) + '</span></td>';
    if (k === 'major') return '<td><span class="mj">' + esc(e.major || ERP.MAJOR_DEFAULT) + '</span></td>';
    if (k === 'mv') return '<td><span class="move">' + ERP.moveName(e) + '</span></td>';
    if (k === 'n') return '<td class="ellip"><b>' + esc(e.n) + '</b></td>';
    if (k === 'k') return '<td class="num">' + fmt(e.k) + '</td>';
    if (k === 'price') return '<td class="num">' + (e.price > 0 ? fmtInt(e.price) : '<span class="ttag">-</span>') + '</td>';
    if (k === 'amt') return '<td class="num" title="' + (e.amt > 0 ? fmtInt(e.amt) + '원' : '금액 미입력') + '">' +
      (e.amt > 0 ? fmtInt(e.amt) : '<span class="ttag">-</span>') + '</td>';
    if (k === 'p') return '<td class="ellip" title="' + esc(destTitle(e)) + '">' + destCell(e) + '</td>';
    if (k === 'worker') return '<td class="ellip">' + (e.worker ? '<span class="worker" title="' + esc(e.email) + '">' + esc(e.worker) + '</span>' : '<span class="ttag">-</span>') + '</td>';
    return '<td class="ellip">' + esc(ERP.logCell(e, k) || '-') + '</td>';
  }
  function renderHistory() {
    var wrap = $('tableWrap');
    renderHistNote();
    var list = ERP.filterLogs(st, {
      q: cur.search, type: cur.hFilter, major: cur.major, from: cur.hist.from, to: cur.hist.to,
      cols: cur.fLog, sortKey: cur.sortLog.k, sortDir: cur.sortLog.dir
    });
    var kg = 0, amt = 0, i;
    for (i = 0; i < list.length; i++) { kg += Number(list[i].k) || 0; amt += Number(list[i].amt) || 0; }
    setRangeSum(list.length + '건', kg, amt);

    if (!list.length) {
      wrap.innerHTML = '<table><tbody><tr class="empty-row"><td>조건에 맞는 내역이 없습니다. 기간·대분류·필터를 넓혀 보세요.</td></tr></tbody></table>';
      return;
    }
    var cols = ERP.LOG_COLS;
    var page = list.slice(0, cur.hLimit);
    var html = ['<table class="fixed t-log">', colGroup(cols, 92), '<thead><tr>'];
    for (i = 0; i < cols.length; i++) html.push(thHtml(cols[i], cur.sortLog, cur.fLog));
    html.push('<th class="num"><span class="th-plain">작업</span></th></tr></thead><tbody>');
    for (i = 0; i < page.length; i++) {
      var e = page[i];
      html.push('<tr>');
      for (var c = 0; c < cols.length; c++) html.push(logCellHtml(e, cols[c].k));
      html.push('<td><div class="acts">' +
        (e.act
          ? '<button class="act edit" data-edit="' + e.dbid + '">수정</button>' +
            '<button class="cancel" data-undo="' + e.dbid + '">취소</button>'
          : '<span class="ttag">원본</span>') +
        '</div></td>');
      html.push('</tr>');
    }
    html.push('</tbody></table>');
    if (list.length > cur.hLimit) {
      html.push('<button class="more" id="btnMore">더 보기 (' + (list.length - cur.hLimit) + '건 남음)</button>');
    }
    wrap.innerHTML = html.join('');
    var more = $('btnMore');
    if (more) more.addEventListener('click', function () { cur.hLimit += 250; renderHistory(); });
  }

  function renderTable() {
    var anyF = hasCols(cur.fLot) || hasCols(cur.fLog);
    var btn = $('btnResetFilters');
    if (btn) btn.classList.toggle('hidden', !anyF);
    if (cur.tab === 'H') { renderHistory(); return; }
    renderStock(cur.tab);
  }

  function hasCols(o) {
    for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k) && o[k] && o[k].length) return true;
    return false;
  }

  /* ---------- 기간 바 ---------- */
  function rangeTarget() { return cur.tab === 'H' ? cur.hist : cur.stock; }
  function renderRangeBar() {
    var isH = cur.tab === 'H';
    $('dateFieldWrap').classList.toggle('hidden', isH);
    var soon = document.querySelector('#rangePresets [data-preset="soon"]');
    if (soon) soon.classList.toggle('hidden', isH);
    var r = rangeTarget();
    var btns = document.querySelectorAll('#rangePresets .pr');
    for (var i = 0; i < btns.length; i++) {
      btns[i].classList.toggle('active', btns[i].getAttribute('data-preset') === r.preset);
    }
    $('rangeFrom').value = r.from || '';
    $('rangeTo').value = r.to || '';
    if (!isH) $('dateField').value = cur.stock.field || 'in';
  }
  function setPreset(key) {
    var r = rangeTarget();
    r.preset = key;
    if (key === 'soon') cur.stock.field = 'exp';
    var rg = ERP.rangeOf(key, today());
    r.from = rg.from;
    r.to = rg.to;
    cur.hLimit = 250;
    renderRangeBar();
    renderTable();
  }
  function setCustomRange() {
    var r = rangeTarget();
    r.preset = 'custom';
    r.from = $('rangeFrom').value || '';
    r.to = $('rangeTo').value || '';
    cur.hLimit = 250;
    var btns = document.querySelectorAll('#rangePresets .pr');
    for (var i = 0; i < btns.length; i++) btns[i].classList.remove('active');
    renderTable();
  }

  /* ---------- 컬럼 필터 팝오버 ---------- */
  function rowsForFilter(tbl, key) {
    var base = tbl === 'lot' ? cur.fLot : cur.fLog;
    var cols = {}, k;
    for (k in base) if (Object.prototype.hasOwnProperty.call(base, k) && k !== key) cols[k] = base[k];
    if (tbl === 'lot') {
      return ERP.filterLots(st, cur.tab, cur.search, cur.showZero, {
        major: cur.major, dateField: cur.stock.field, from: cur.stock.from, to: cur.stock.to, cols: cols
      });
    }
    return ERP.filterLogs(st, {
      q: cur.search, type: cur.hFilter, major: cur.major, from: cur.hist.from, to: cur.hist.to, cols: cols
    });
  }
  function filterStore(tbl) { return tbl === 'lot' ? cur.fLot : cur.fLog; }
  function cellOf(tbl) {
    return tbl === 'lot'
      ? function (l, k) { return ERP.lotCell(l, k, cur.tab); }
      : function (e, k) { return ERP.logCell(e, k); };
  }
  function colLabel(tbl, key) {
    var list = tbl === 'lot' ? ERP.LOT_COLS : ERP.LOG_COLS;
    for (var i = 0; i < list.length; i++) if (list[i].k === key) return list[i].t;
    return key;
  }
  function openFilter(tbl, key, btn) {
    var rect = btn.getBoundingClientRect();
    var vals = ERP.uniqValues(rowsForFilter(tbl, key), key, cellOf(tbl));
    var allow = filterStore(tbl)[key];
    var sel = {};
    for (var i = 0; i < vals.length; i++) sel[vals[i]] = !allow || allow.length === 0 || allow.indexOf(vals[i]) >= 0;
    fpop = { open: true, tbl: tbl, key: key, rect: rect, all: vals, sel: sel, q: '' };
    $('fpopTitle').textContent = colLabel(tbl, key) + ' 값 선택';
    $('fpopSearch').value = '';
    renderFpop();
    $('fpop').classList.remove('hidden');
    placeFpop();
    setTimeout(function () { try { $('fpopSearch').focus(); } catch (e) { } }, 40);
  }
  function renderFpop() {
    var list = $('fpopList');
    var q = fpop.q.toLowerCase();
    var shown = 0, html = [], i;
    for (i = 0; i < fpop.all.length; i++) {
      var v = fpop.all[i];
      if (q && v.toLowerCase().indexOf(q) < 0) continue;
      shown++;
      html.push('<label class="fitem"><input type="checkbox" data-val="' + esc(v) + '"' +
        (fpop.sel[v] ? ' checked' : '') + '><span>' + esc(v) + '</span></label>');
    }
    if (!shown) html.push('<div class="fempty">해당하는 값이 없습니다.</div>');
    list.innerHTML = html.join('');
    var on = 0;
    for (i = 0; i < fpop.all.length; i++) if (fpop.sel[fpop.all[i]]) on++;
    $('fpopTitle').textContent = colLabel(fpop.tbl, fpop.key) + ' · ' + on + '/' + fpop.all.length + ' 선택';
  }
  function placeFpop() {
    var el = $('fpop');
    if (!el || !fpop.open || !fpop.rect) return;
    if (window.innerWidth <= 640) {
      el.classList.add('sheet');
      el.style.left = '';
      el.style.top = '';
      return;
    }
    el.classList.remove('sheet');
    var r = fpop.rect;
    var w = el.offsetWidth || 268, h = el.offsetHeight || 340;
    var left = Math.min(Math.max(8, r.left - 40), window.innerWidth - w - 10);
    var top = r.bottom + 6;
    if (top + h > window.innerHeight - 8) top = Math.max(8, r.top - h - 6);
    el.style.left = left + 'px';
    el.style.top = top + 'px';
  }
  function closeFilter() {
    fpop.open = false;
    $('fpop').classList.add('hidden');
  }
  function applyFilter() {
    var store = filterStore(fpop.tbl);
    var on = [], off = 0, i;
    for (i = 0; i < fpop.all.length; i++) {
      if (fpop.sel[fpop.all[i]]) on.push(fpop.all[i]); else off++;
    }
    if (!off) delete store[fpop.key];
    else store[fpop.key] = on;
    renderTable();
    if (fpop.open) $('fpop').classList.remove('hidden');
  }

  /* ---------- 로트 선택 ---------- */
  function fillLotSelect(sel, wh) {
    var prevVal = sel.value;
    var list = [], i, l;
    for (i = 0; i < st.lots.length; i++) {
      l = st.lots[i];
      if (ERP.qtyOf(l, wh) <= ERP.EPS) continue;
      list.push(l);
    }
    list.sort(function (a, b) {
      var c = a.n.localeCompare(b.n, 'ko');
      if (c !== 0) return c;
      return ERP.sortLots(a, b);
    });
    var html = ['<option value="">— 로트 선택 (' + list.length + '개 보관중) —</option>'];
    var curName = null;
    for (i = 0; i < list.length; i++) {
      l = list[i];
      if (l.n !== curName) { html.push('<option disabled>■ ' + esc(l.n) + '</option>'); curName = l.n; }
      html.push('<option value="' + l.id + '">' + esc(l.n) + ' · ' + esc(l.v || '업체없음') +
        ' · ' + esc(l.i || '?') + ' · ' + fmt(ERP.qtyOf(l, wh)) + 'kg</option>');
    }
    sel.innerHTML = html.join('');
    if (prevVal && ERP.getLot(st, prevVal)) sel.value = prevVal;
    else sel.value = '';
  }

  function lotInfoHtml(lot, wh, id) {
    var att = id ? ' id="' + id + '"' : '';
    if (!lot) return '<div' + att + ' class="lotinfo empty">' + (wh === 'C' ? '냉장고' : '냉동고') + ' 재고표에서 로트 행을 클릭하거나 위에서 선택하세요.</div>';
    var q = ERP.qtyOf(lot, wh);
    return '<div' + att + ' class="lotinfo"><b>' + esc(lot.n) + '</b> · ' + esc(lot.v || '업체없음') +
      ' · ' + esc(lot.major || '원료육') + '/' + esc(lot.mt || '-') + '/' + esc(lot.o || '-') + '<br>' +
      '입고 ' + esc(lot.i || '-') + ' · 소비기한 ' + esc(lot.e || '-') + ddayHtml(lot.e) +
      ' · 단가 ' + (lot.price > 0 ? fmtInt(lot.price) + '원/kg' : '미입력') + '<br>' +
      (wh === 'F' ? '냉동고' : '냉장고') + ' 현재고 <b>' + fmt(q) + ' kg</b>' +
      (wh === 'C' && lot.fq > ERP.EPS ? ' <span class="ttag">(냉동고 ' + fmt(lot.fq) + 'kg 보유)</span>' : '') +
      (wh === 'F' && lot.cq > ERP.EPS ? ' <span class="ttag">(냉장고 ' + fmt(lot.cq) + 'kg 보유)</span>' : '') +
      '</div>';
  }

  function syncLotViews() {
    var thSel = $('thLot'), reSel = $('reLot'), outSel = $('outLot');
    fillLotSelect(thSel, 'F');
    fillLotSelect(reSel, 'C');
    fillLotSelect(outSel, cur.whOut);
    if (cur.lotId) {
      if (thSel.querySelector('option[value="' + cur.lotId + '"]')) thSel.value = cur.lotId;
      if (reSel.querySelector('option[value="' + cur.lotId + '"]')) reSel.value = cur.lotId;
      if (outSel.querySelector('option[value="' + cur.lotId + '"]')) outSel.value = cur.lotId;
    }
    $('thInfo').outerHTML = lotInfoHtml(ERP.getLot(st, thSel.value), 'F', 'thInfo');
    $('reInfo').outerHTML = lotInfoHtml(ERP.getLot(st, reSel.value), 'C', 'reInfo');
    $('outInfo').outerHTML = lotInfoHtml(ERP.getLot(st, outSel.value), cur.whOut, 'outInfo');
  }

  /* ---------- 단가 ↔ 금액 양방향 ---------- */
  var PRICE_IDS = {
    in: { kg: 'inKg', price: 'inPrice', amount: 'inAmount' },
    thaw: { kg: 'thKg', price: 'thPrice', amount: 'thAmount' },
    re: { kg: 'reKg', price: 'rePrice', amount: 'reAmount' },
    out: { kg: 'outKg', price: 'outPrice', amount: 'outAmount' }
  };
  function priceSync(mode, src) {
    var ids = PRICE_IDS[mode || cur.mode];
    if (!ids) return;
    var kg = Number($(ids.kg).value || 0);
    var pr = Number($(ids.price).value || 0);
    var am = Number($(ids.amount).value || 0);
    if (src === 'amount') {
      if (kg > 0) {
        var p2 = Math.round(am / kg);
        $(ids.price).value = am > 0 ? String(p2) : '';
      }
    } else {
      var v = Math.round(kg * pr);
      $(ids.amount).value = (kg > 0 && pr > 0) ? String(v) : '';
    }
    if ((mode || cur.mode) === 'in') updatePriceHint();
  }
  function fillLotPrice(mode, lot) {
    var ids = PRICE_IDS[mode];
    if (!ids) return;
    $(ids.price).value = lot && lot.price > 0 ? String(lot.price) : '';
    priceSync(mode, 'price');
  }

  /* ---------- 입고 단가 비교 (요구 8) ---------- */
  function updatePriceHint() {
    var box = $('priceHint');
    if (!box) return;
    if (cur.mode !== 'in') { box.className = 'pricebox hidden'; box.innerHTML = ''; return; }
    var name = ($('inName').value || '').replace(/^\s+|\s+$/g, '');
    var major = ($('inMajor').value || '').replace(/^\s+|\s+$/g, '') || ERP.MAJOR_DEFAULT;
    var price = Number($('inPrice').value || 0);
    box.className = 'pricebox';
    if (!name) {
      box.innerHTML = '<span class="pb-empty">품목명을 입력하면 지난 입고 단가와 비교해 드립니다.</span>';
      return;
    }
    var stat = ERP.priceStats(st, name, major);
    if (!stat.count) {
      box.innerHTML = '<div class="pb-line"><b>' + esc(name) + '</b> <span class="pb-new">첫 단가 입력(비교 이력 없음)</span></div>' +
        '<div class="pb-range">지난 입고 단가 기록이 없어 오타 여부를 비교할 수 없습니다.</div>';
      return;
    }
    var html = ['<div class="pb-line"><b>' + esc(name) + '</b> 지난 입고 <b>' + stat.count + '</b>건 · 최근 ' +
      esc(stat.lastDate) + ' <b>' + fmtInt(stat.last) + '</b>원/kg</div>'];
    if (price > 0) {
      var c = ERP.priceCompare(stat, price);
      var arrow = c.dir === 'up' ? '▲ +' : (c.dir === 'down' ? '▼ −' : '＝ ');
      var body;
      if (c.dir === 'same') body = '변동 없음';
      else body = arrow + fmtInt(Math.abs(c.delta)) + '원 (' + (c.pct > 0 ? '+' : '') + c.pct + '%) ' +
        (c.dir === 'up' ? '올랐습니다' : '내렸습니다');
      html.push('<div class="pb-cmp ' + c.dir + '">직전 입고가 <b>' + fmtInt(c.base) + '</b>원 → 지금 <b>' +
        fmtInt(price) + '</b>원 · ' + body + '</div>');
      if (c.warn) {
        html.push('<div class="pb-warn">⚠ 단가 급변 — 오타(0을 하나 더 입력 등)인지 확인하세요. ' +
          (c.warnAvg ? '평균 ' + fmtInt(stat.avg) + '원과 30% 이상 차이' : '직전가와 30% 이상 차이') + '</div>');
      }
    }
    html.push('<div class="pb-range">과거 입고 최저 <b>' + fmtInt(stat.min) + '</b> · 평균 <b>' + fmtInt(stat.avg) +
      '</b> · 최고 <b>' + fmtInt(stat.max) + '</b> 원/kg</div>');
    box.innerHTML = html.join('');
  }

  /* ---------- 모드 ---------- */
  function submitLabel() {
    if (cur.mode === 'in') return (cur.whIn === 'F' ? '냉동고' : '냉장고') + '로 입고 저장';
    if (cur.mode === 'thaw') return '해동 저장 (냉동 → 냉장)';
    if (cur.mode === 're') return '재냉동 저장 (냉장 → 냉동)';
    return '출고 저장';
  }
  function setMode(mode) {
    cur.mode = mode;
    var btns = document.querySelectorAll('.mode');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-mode') === mode);
    var panes = document.querySelectorAll('[data-pane]');
    for (var j = 0; j < panes.length; j++) panes[j].classList.toggle('hidden', panes[j].getAttribute('data-pane') !== mode);
    var sub = $('btnSave');
    sub.className = 'submit ' + (mode === 'in' ? '' : (mode === 'thaw' ? 't-thaw' : (mode === 're' ? 't-re' : 't-out')));
    sub.textContent = submitLabel();
    $('formMsg').textContent = '';
    updatePriceHint();
    return mode;
  }
  function setOutWh(wh) {
    cur.whOut = wh;
    var btns = document.querySelectorAll('#whSegOut button');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-wh') === wh);
  }
  function setInWh(wh) {
    cur.whIn = wh;
    var btns = document.querySelectorAll('#whSegIn button');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-wh') === wh);
    if (cur.mode === 'in') $('btnSave').textContent = submitLabel();
  }
  function setDest(d) {
    cur.dest = ERP.destKey(d);
    var btns = document.querySelectorAll('#destSeg button');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-dest') === cur.dest);
    $('destLabel').textContent = ERP.DEST_LABEL[cur.dest];
    var inp = $('outDest');
    var listId = cur.dest === 'vendor' ? 'dlVendors' : (cur.dest === 'courier' ? 'dlCourier' : (cur.dest === 'other' ? 'dlOther' : 'dlProducts'));
    inp.setAttribute('list', listId);
    inp.placeholder = {
      site: '예: 선진바베큐폭립', vendor: '예: 미트박스',
      courier: '예: 김사장님(김포) · 운송장 1234-5678', other: '예: 샘플 제공 · 폐기'
    }[cur.dest];
    $('destHint').textContent = ERP.DEST_HINT[cur.dest];
    fillDatalists();
  }

  function bindLot(lotId, act) {
    var lot = ERP.getLot(st, lotId);
    if (!lot) return;
    cur.lotId = lotId;
    if (act === 'thaw') {
      setMode('thaw');
      $('thLot').value = lotId;
      fillLotPrice('thaw', lot);
    } else if (act === 're') {
      setMode('re');
      $('reLot').value = lotId;
      fillLotPrice('re', lot);
    } else if (act === 'out') {
      cur.whOut = cur.tab === 'C' ? 'C' : (cur.tab === 'F' ? 'F' : cur.whOut);
      setMode('out');
      setOutWh(cur.whOut);
      $('outLot').value = lotId;
      fillLotPrice('out', lot);
    } else if (cur.mode === 'thaw') {
      if (lot.fq <= ERP.EPS) {
        toast('이 로트는 냉동고 재고가 0입니다. 출고로 전환합니다.', 'warn');
        setOutWh('F');
        setMode('out');
      } else {
        $('thLot').value = lotId;
        fillLotPrice('thaw', lot);
      }
    } else if (cur.mode === 're') {
      if (lot.cq <= ERP.EPS) {
        toast('이 로트는 냉장고 재고가 0입니다. 출고로 전환합니다.', 'warn');
        setOutWh('C');
        setMode('out');
      } else {
        $('reLot').value = lotId;
        fillLotPrice('re', lot);
      }
    }
    syncLotViews();
    renderTable();
    var kg = cur.mode === 'thaw' ? $('thKg') : (cur.mode === 're' ? $('reKg') : (cur.mode === 'out' ? $('outKg') : null));
    if (kg) { kg.value = ''; priceSync(cur.mode, 'kg'); }
  }

  /* ---------- 새로고침 ---------- */
  function refresh() {
    renderKPI();
    renderTable();
    syncLotViews();
    fillDatalists();
    renderRangeBar();
    updatePriceHint();
    if (xls.kind) renderXls();
  }

  function reload(opts) {
    opts = opts || {};
    if (!SB.auth.session()) return Promise.resolve();
    if (loading) { again = true; return Promise.resolve(); }
    loading = true;
    if (!opts.silent) setSync('wait', '불러오는 중…');
    return SB.db.loadAll().then(function (res) {
      st = ERP.stateFrom(res.lots, res.logs);
      refresh();
      if (!opts.silent) setSync('ok', '동기화 ' + clock());
      hideBanner();
      $('baseLabel').textContent = 'Supabase 실시간 공유 · 로트 ' + st.lots.length + '개 · 이력 ' + st.logs.length + '건';
      if (!st.lots.length) {
        showBanner('아직 재고 데이터가 없습니다. Supabase SQL Editor에서 <b>supabase_setup.sql</b>을 실행했는지 확인해 주세요.');
      }
    }, function (e) {
      setSync('err', '동기화 실패');
      if (isSetupError(e)) {
        showBanner('DB 표·함수를 찾을 수 없습니다. Supabase SQL Editor에서 <b>supabase_setup.sql</b>(기존 DB라면 <b>supabase_migrate_v2.sql</b>)을 한 번 실행해 주세요.<br><span class="banner-sub">' + esc(e.message) + '</span>');
      } else if (e.status === 401 || e.kind === 'auth') {
        toast(e.message, 'err');
        doLogout(true);
      } else {
        toast(e.message, 'err');
      }
    }).then(function () {
      loading = false;
      if (again) { again = false; return reload({ silent: true }); }
    });
  }

  function enterApp(ses) {
    $('loginView').classList.add('hidden');
    $('appView').classList.remove('hidden');
    $('whoami').innerHTML = '<b>' + esc(ses.name) + '</b><span>' + esc(ses.email) + '</span>';
    var d = today();
    ['inDate', 'inInDate', 'thDate', 'reDate', 'outDate'].forEach(function (id) { if (!$(id).value) $(id).value = d; });
    if (!$('inMajor').value) $('inMajor').value = '원료육';
    setInWh('F'); setOutWh('C'); setDest('site'); setMode('in');
    reload().then(function () {
      LIVE.start(function () { reload({ silent: true }); }, liveLabel);
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = setInterval(function () {
        if (document.visibilityState === 'visible' && SB.auth.session()) reload({ silent: true });
      }, CONFIG.POLL_MS);
    });
  }

  function doLogout(silent) {
    LIVE.stop();
    if (xls.kind) closeXls();
    closeFilter();
    closeEdit(); closeLot();
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
    SB.auth.signOut().then(function () {
      $('appView').classList.add('hidden');
      $('loginView').classList.remove('hidden');
      $('liPw').value = '';
      setLoginMsg(silent ? '다시 로그인해 주세요.' : '로그아웃했습니다.', 'warn');
    });
  }

  function setLoginMsg(text, kind) {
    var el = $('loginMsg');
    el.textContent = text || '';
    el.className = 'lmsg ' + (kind || '');
  }

  /* ---------- 저장 ---------- */
  function clearErrs() {
    var errs = document.querySelectorAll('.err');
    for (var i = 0; i < errs.length; i++) errs[i].classList.remove('err');
  }
  function fieldId(name) {
    if (name === 'name') return 'inName';
    if (name === 'inDate') return 'inInDate';
    if (name === 'expiry') return 'inExpiry';
    if (name === 'dest') return 'outDest';
    if (name === 'date') return cur.mode === 'in' ? 'inDate' : (cur.mode === 'thaw' ? 'thDate' : (cur.mode === 're' ? 'reDate' : 'outDate'));
    if (name === 'kg') return cur.mode === 'in' ? 'inKg' : (cur.mode === 'thaw' ? 'thKg' : (cur.mode === 're' ? 'reKg' : 'outKg'));
    if (name === 'price') return cur.mode === 'in' ? 'inPrice' : (cur.mode === 'thaw' ? 'thPrice' : (cur.mode === 're' ? 'rePrice' : 'outPrice'));
    if (name === 'amount') return cur.mode === 'in' ? 'inAmount' : (cur.mode === 'thaw' ? 'thAmount' : (cur.mode === 're' ? 'reAmount' : 'outAmount'));
    return null;
  }
  function fieldFromMsg(msg) {
    if (/제품명/.test(msg)) return 'name';
    if (/입고일/.test(msg)) return 'inDate';
    if (/소비기한/.test(msg)) return 'expiry';
    if (/출고처/.test(msg)) return 'dest';
    if (/날짜/.test(msg)) return 'date';
    if (/중량/.test(msg)) return 'kg';
    if (/단가/.test(msg)) return 'price';
    if (/금액/.test(msg)) return 'amount';
    if (/창고/.test(msg)) return 'wh';
    return null;
  }
  function fail(msg, field) {
    $('formMsg').textContent = msg;
    if (field) {
      var id = fieldId(field);
      if (id && $(id)) { $(id).classList.add('err'); $(id).focus(); }
    }
    toast(msg, 'err');
  }
  function busy(on) {
    var b = $('btnSave');
    b.disabled = !!on;
    b.textContent = on ? '저장 중…' : submitLabel();
  }
  function numOrNull(id) {
    var v = $(id).value;
    return v === '' || v === null ? null : Number(v);
  }
  function params() {
    var p = { date: today(), type: cur.mode, wh: cur.whIn, lot_id: null, kg: 0, price: 0, amount: null, major: '' };
    var ids = PRICE_IDS[cur.mode];
    p.price = Number($(ids.price).value || 0);
    p.amount = numOrNull(ids.amount);
    if (cur.mode === 'in') {
      p.date = $('inDate').value || today();
      p.name = $('inName').value;
      p.meat = $('inMeat').value;
      p.origin = $('inOrigin').value;
      p.vendor = $('inVendor').value;
      p.brand = $('inBrand').value;
      p.major = ($('inMajor').value || '').replace(/^\s+|\s+$/g, '') || ERP.MAJOR_DEFAULT;
      p.in_date = $('inInDate').value || null;
      p.exp_date = $('inExpiry').value || null;
      p.kg = Number($('inKg').value || 0);
      p.note = $('inNote').value;
    } else if (cur.mode === 'thaw') {
      p.date = $('thDate').value || today();
      p.wh = 'F';
      p.lot_id = dbId($('thLot').value);
      p.kg = Number($('thKg').value || 0);
      p.note = $('thNote').value;
    } else if (cur.mode === 're') {
      p.date = $('reDate').value || today();
      p.wh = 'C';
      p.lot_id = dbId($('reLot').value);
      p.kg = Number($('reKg').value || 0);
      p.note = $('reNote').value;
    } else {
      p.date = $('outDate').value || today();
      p.wh = cur.whOut;
      p.lot_id = dbId($('outLot').value);
      p.dest_type = cur.dest;
      p.dest = $('outDest').value;
      p.kg = Number($('outKg').value || 0);
      p.note = $('outNote').value;
    }
    return p;
  }
  function dbId(lotId) {
    var lot = ERP.getLot(st, lotId);
    return lot ? lot.dbid : null;
  }
  function okMessage(p, row) {
    var kg = Number(row && row.qty || p.kg).toFixed(2);
    var name = (row && row.product_name) || p.name || '';
    var money = '';
    if (row && Number(row.total_amount) > 0) money = ' · ' + fmtInt(row.total_amount) + '원';
    if (p.type === 'in') {
      var isNew = !st.lots.some(function (l) { return l.dbid === Number(row.lot_id); });
      return '입고 완료: ' + name + ' ' + kg + 'kg' + money + ' → ' + (p.wh === 'F' ? '냉동고' : '냉장고') + (isNew ? ' (신규 로트)' : ' (기존 로트 합산)');
    }
    if (p.type === 'thaw') return '해동 완료: ' + name + ' ' + kg + 'kg' + money + ' (냉동 −' + kg + ' / 냉장 +' + kg + ')';
    if (p.type === 're') return '재냉동 완료: ' + name + ' ' + kg + 'kg' + money + ' (냉장 −' + kg + ' / 냉동 +' + kg + ')';
    return '출고 완료: ' + name + ' ' + kg + 'kg' + money + ' (' + (p.wh === 'F' ? '냉동고' : '냉장고') +
      ' → [' + ERP.destName(row && row.dest_type || p.dest_type) + '] ' + ((row && row.dest_detail) || p.dest) + ')';
  }
  function clearAfterSave() {
    var ids = PRICE_IDS[cur.mode];
    $(ids.price).value = '';
    $(ids.amount).value = '';
    if (cur.mode === 'in') {
      ['inName', 'inKg', 'inNote', 'inOrigin', 'inVendor', 'inBrand', 'inExpiry'].forEach(function (id) { $(id).value = ''; });
      $('inInDate').value = today();
      updatePriceHint();
    } else if (cur.mode === 'thaw') {
      $('thKg').value = ''; $('thNote').value = '';
      var tl = ERP.getLot(st, $('thLot').value);
      if (tl && tl.fq <= ERP.EPS) { $('thLot').value = ''; cur.lotId = null; }
    } else if (cur.mode === 're') {
      $('reKg').value = ''; $('reNote').value = '';
      var rl = ERP.getLot(st, $('reLot').value);
      if (rl && rl.cq <= ERP.EPS) { $('reLot').value = ''; cur.lotId = null; }
    } else {
      $('outKg').value = ''; $('outNote').value = ''; $('outDest').value = '';
      var ol = ERP.getLot(st, $('outLot').value);
      if (ol && ERP.qtyOf(ol, cur.whOut) <= ERP.EPS) { $('outLot').value = ''; cur.lotId = null; }
    }
  }

  function submit() {
    if (!SB.auth.session()) { toast('먼저 로그인해 주세요.', 'err'); return; }
    $('formMsg').textContent = '';
    clearErrs();
    var p = params();
    var bad = ERP.precheck(p);
    if (bad) { fail(bad.msg, bad.field); return; }

    busy(true);
    SB.db.apply(p).then(function (row) {
      toast(okMessage(p, row), cur.mode);
      clearAfterSave();
      cur.hLimit = 250;
      return reload({ silent: true });
    }).then(function () {
      busy(false);
    }, function (e) {
      busy(false);
      fail(e.message, fieldFromMsg(e.message));
    });
  }

  /* ---------- 입력 수정 모달 ---------- */
  function openEdit(logId) {
    var e = ERP.getLog(st, logId);
    if (!e) { toast('내역을 찾을 수 없습니다. 새로고침 후 다시 시도하세요.', 'err'); return; }
    if (!e.act) { toast('엑셀에서 옮긴 원본 이력은 수정할 수 없습니다.', 'warn'); return; }
    editing = e;
    $('editSub').textContent = e.n + ' · ' + ERP.typeName(e.t) + ' · ' + ERP.moveName(e) +
      (e.worker ? ' · 작업자 ' + e.worker : '');
    $('edDate').value = e.d || '';
    $('edKg').value = e.k;
    $('edPrice').value = e.price > 0 ? e.price : '';
    $('edAmount').value = e.amt > 0 ? e.amt : (e.price > 0 ? Math.round(e.k * e.price) : '');
    $('edWh').value = e.w;
    $('edWh').disabled = (e.t === 'thaw' || e.t === 're');
    $('edDest').value = ERP.destKey(e.dt);
    $('edDestDetail').value = e.p || '';
    var isOut = e.t === 'out';
    $('edDestWrap').classList.toggle('hidden', !isOut);
    $('edDestDetailWrap').classList.toggle('hidden', !isOut);
    $('edNote').value = e.note || '';
    $('editMsg').textContent = '';
    $('editModal').classList.remove('hidden');
    setTimeout(function () { try { $('edKg').focus(); } catch (err) { } }, 40);
  }
  function closeEdit() {
    $('editModal').classList.add('hidden');
    editing = null;
  }
  function saveEdit() {
    if (!editing) return;
    var p = {
      logId: editing.dbid, type: editing.t,
      date: $('edDate').value, kg: Number($('edKg').value || 0),
      price: Number($('edPrice').value || 0), amount: $('edAmount').value === '' ? null : Number($('edAmount').value),
      wh: $('edWh').value, dest_type: $('edDest').value, dest: $('edDestDetail').value,
      note: $('edNote').value
    };
    var bad = ERP.precheckUpdate(p);
    if (bad) { $('editMsg').textContent = bad.msg; return; }
    var b = $('editSave');
    b.disabled = true; b.textContent = '저장 중…';
    SB.db.update(p).then(function (row) {
      closeEdit();
      toast('수정 완료: ' + (row && row.product_name || editing && editing.n) + ' ' +
        Number(row && row.qty || p.kg).toFixed(2) + 'kg', 'ok');
      return reload({ silent: true });
    }).then(function () {
      b.disabled = false; b.textContent = '수정 저장';
    }, function (e) {
      b.disabled = false; b.textContent = '수정 저장';
      $('editMsg').textContent = e.message;
    });
  }

  /* ---------- 로트 정보 수정 ---------- */
  function openLot(lotId) {
    var lot = ERP.getLot(st, lotId);
    if (!lot) return;
    lotEditing = lot;
    $('lotSub').textContent = '로트 #' + lot.dbid + ' · 이 로트의 이력에도 같은 이름·분류가 적용됩니다.';
    $('ltMajor').value = lot.major || ERP.MAJOR_DEFAULT;
    $('ltMeat').value = lot.mt || '';
    $('ltName').value = lot.n || '';
    $('ltVendor').value = lot.v || '';
    $('ltBrand').value = lot.b || '';
    $('ltOrigin').value = lot.o || '';
    $('ltPrice').value = lot.price > 0 ? lot.price : '';
    $('ltInDate').value = lot.i || '';
    $('ltExp').value = lot.e || '';
    $('lotMsg').textContent = '';
    $('lotModal').classList.remove('hidden');
  }
  function closeLot() {
    $('lotModal').classList.add('hidden');
    lotEditing = null;
  }
  function saveLot() {
    if (!lotEditing) return;
    var name = ($('ltName').value || '').replace(/^\s+|\s+$/g, '');
    if (!name) { $('lotMsg').textContent = '품목명을 입력하세요.'; return; }
    var p = {
      lotId: lotEditing.dbid,
      major: $('ltMajor').value, meat: $('ltMeat').value, name: name,
      vendor: $('ltVendor').value, brand: $('ltBrand').value, origin: $('ltOrigin').value,
      price: $('ltPrice').value === '' ? null : Number($('ltPrice').value),
      in_date: $('ltInDate').value || null, exp_date: $('ltExp').value || null
    };
    var b = $('lotSave');
    b.disabled = true; b.textContent = '저장 중…';
    SB.db.lotUpdate(p).then(function (row) {
      closeLot();
      toast('로트 수정 완료: ' + (row && row.product_name || name), 'ok');
      return reload({ silent: true });
    }).then(function () {
      b.disabled = false; b.textContent = '수정 저장';
    }, function (e) {
      b.disabled = false; b.textContent = '수정 저장';
      $('lotMsg').textContent = e.message;
    });
  }

  /* ---------- CSV ---------- */
  function download(text, name) {
    var blob = new Blob(['\ufeff' + text], { type: 'text/csv;charset=utf-8;' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    setTimeout(function () {
      URL.revokeObjectURL(a.href);
      if (a.parentNode) a.parentNode.removeChild(a);
    }, 400);
  }
  function csvHistory() {
    download(ERP.csv(st), '입출고내역_' + today().replace(/-/g, '') + '.csv');
    toast('입출고 내역 ' + st.logs.length + '건을 CSV로 내려받았습니다.', 'ok');
  }
  function csvStock(wh) {
    var g = ERP.grouped(st, wh, '', false);
    var n = 0;
    for (var i = 0; i < g.length; i++) n += g[i].live;
    var kg = 0, amt = 0;
    for (var j = 0; j < st.lots.length; j++) {
      if (ERP.qtyOf(st.lots[j], wh) > ERP.EPS) { kg += ERP.qtyOf(st.lots[j], wh); amt += ERP.qtyOf(st.lots[j], wh) * st.lots[j].price; }
    }
    download(ERP.stockCsv(st, wh), (wh === 'F' ? '냉동고' : '냉장고') + '재고_' + today().replace(/-/g, '') + '.csv');
    toast((wh === 'F' ? '냉동고' : '냉장고') + ' 재고 ' + n + '개 로트 · ' + fmt(kg) + 'kg · ' + fmtInt(amt) + '원을 CSV로 내려받았습니다.', 'ok');
  }

  /* ---------- 사방넷 · 경리나라 양식 내려받기 ---------- */
  var xls = { kind: null, range: 'today' };

  function firstOfMonth() {
    var d = today().split('-');
    return d[0] + '-' + d[1] + '-01';
  }
  function rangeText(opt) {
    if (opt.range === 'all') return '전체 기간';
    if (opt.range === 'range') return (opt.from || '처음') + ' ~ ' + (opt.to || '오늘');
    return '오늘 (' + opt.today + ')';
  }
  function rangeTag(opt) {
    if (opt.range === 'all') return '전체';
    if (opt.range === 'range') return (opt.from || 'first') + '_' + (opt.to || 'last');
    return opt.today;
  }
  function xlsOpts() {
    return {
      range: xls.range,
      from: xls.range === 'range' ? ($('xlsFrom').value || '') : '',
      to: xls.range === 'range' ? ($('xlsTo').value || '') : '',
      today: today(),
      thaw: !!($('xlsThaw') && $('xlsThaw').checked),
      allOut: !!($('xlsAllOut') && $('xlsAllOut').checked),
      vat: ($('xlsVat') && $('xlsVat').value) || '면세'
    };
  }
  function xlsRows(kind, opt) {
    return kind === 'sales' ? ERP.salesRows(st, opt) : ERP.sabangnetRows(st, opt);
  }

  function renderXls() {
    if (!xls.kind) return;
    var isSales = xls.kind === 'sales';
    $('xlsRangeBox').classList.toggle('hidden', xls.range !== 'range');
    var opt = xlsOpts();
    var rows = xlsRows(xls.kind, opt);
    var n = rows.length - 1, qtyCol = isSales ? 11 : 3, f = 0, ch = 0, kg = 0, won = 0, i;
    for (i = 1; i < rows.length; i++) {
      if (rows[i][6] === '냉동고') f++; else if (rows[i][6] === '냉장고') ch++;
      kg += Number(rows[i][qtyCol]) || 0;
      if (isSales) won += Number(rows[i][14]) || 0;
    }
    var box = $('xlsCount');
    if (!n) {
      box.className = 'xls-count none';
      box.textContent = rangeText(opt) + '에 해당하는 ' + (isSales ? '출고' : '입고') +
        ' 내역이 없습니다. 날짜 범위를 [전체]로 바꾸거나 기간을 넓혀 보세요.';
    } else {
      box.className = 'xls-count';
      box.textContent = rangeText(opt) + ' · ' + (isSales ? '매출' : '입고') + ' ' + n + '건 · 냉동고 ' + f +
        ' / 냉장고 ' + ch + ' · 합계 ' + fmt(kg) + 'kg' + (isSales && won ? ' · 공급가액 ' + fmtInt(won) + '원' : '');
    }
    $('xlsGo').disabled = !n;
    return n;
  }

  function openXls(kind) {
    xls.kind = kind;
    var isSales = kind === 'sales';
    $('xlsTitle').textContent = isSales ? '경리나라 매출 양식 내려받기' : '사방넷 입고 양식 내려받기';
    $('xlsSub').textContent = isSales
      ? '업체 출고를 경리나라 [매출거래명세표 일괄등록] 양식(.xlsx, 시트 일괄등록)으로 만듭니다. 출고 단가가 있으면 단가·공급가액·세액을 계산해 넣고, 단가가 없으면 0으로 두니 업로드한 뒤 입력하세요.'
      : '입고를 사방넷 풀필먼트 [엑셀입고] 양식(.xlsx, 시트 엑셀입고)으로 만듭니다. 매입처는 업체명, 로케이션은 냉동고·냉장고, 유통기한은 8자리(YYYYMMDD)로 들어갑니다.';
    $('xlsOptSabang').classList.toggle('hidden', isSales);
    $('xlsOptSales').classList.toggle('hidden', !isSales);
    if (xls.range === 'range') {
      if (!$('xlsFrom').value) $('xlsFrom').value = firstOfMonth();
      if (!$('xlsTo').value) $('xlsTo').value = today();
    }
    var segs = document.querySelectorAll('#xlsRangeSeg button');
    for (var i = 0; i < segs.length; i++) {
      segs[i].classList.toggle('active', segs[i].getAttribute('data-range') === xls.range);
    }
    $('xlsModal').classList.remove('hidden');
    renderXls();
    if (!$('xlsGo').disabled) $('xlsGo').focus();
  }
  function closeXls() {
    $('xlsModal').classList.add('hidden');
    xls.kind = null;
  }

  function downloadXls() {
    if (!xls.kind) return;
    var isSales = xls.kind === 'sales';
    var opt = xlsOpts();
    var rows = xlsRows(xls.kind, opt);
    if (rows.length < 2) { toast('내려받을 내역이 없습니다. 날짜 범위를 넓혀 보세요.', 'warn'); return; }
    var bytes = ERP.xlsxBytes([{
      name: isSales ? '일괄등록' : '엑셀입고',
      rows: rows,
      widths: isSales
        ? [12, 8, 20, 14, 10, 12, 9, 9, 10, 24, 16, 9, 7, 9, 11, 9, 26, 10, 10, 20]
        : [16, 14, 26, 10, 11, 11, 10, 34]
    }]);
    var blob = new Blob([new Uint8Array(bytes)], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = (isSales ? '매출거래명세표_일괄등록_' : '사방넷_엑셀입고_') + rangeTag(opt).replace(/-/g, '') + '.xlsx';
    document.body.appendChild(a);
    a.click();
    setTimeout(function () {
      URL.revokeObjectURL(a.href);
      if (a.parentNode) a.parentNode.removeChild(a);
    }, 600);
    toast((isSales ? '경리나라 매출 양식' : '사방넷 입고 양식') + ' ' + (rows.length - 1) + '건을 엑셀로 내려받았습니다.', 'ok');
    closeXls();
  }

  /* ---------- 자동완성 ---------- */
  function datalist(id, arr) {
    var el = $(id);
    if (!el) return;
    var html = [], seen = {}, i;
    for (i = 0; i < arr.length; i++) {
      var v = String(arr[i] === null || arr[i] === undefined ? '' : arr[i]).replace(/^\s+|\s+$/g, '');
      if (!v || seen[v]) continue;
      seen[v] = 1;
      html.push('<option value="' + esc(v) + '"></option>');
    }
    el.innerHTML = html.join('');
  }
  function fillDatalists() {
    var d = ERP.dict(st), h = ERP.destHistory(st);
    datalist('dlNames', d.names);
    datalist('dlVendors', d.vendors);
    datalist('dlOrigins', d.origins);
    datalist('dlBrands', d.brands);
    datalist('dlProducts', d.products);
    datalist('dlCourier', h.courier);
    datalist('dlOther', h.other);
    datalist('dlMajors', d.majors);
    datalist('dlMeats', d.meats);
    var sel = $('majorFilter');
    var curV = cur.major;
    var opts = ['<option value="all">전체</option>'];
    for (var i = 0; i < d.majors.length; i++) {
      opts.push('<option value="' + esc(d.majors[i]) + '">' + esc(d.majors[i]) + '</option>');
    }
    if (curV !== 'all' && d.majors.indexOf(curV) < 0) {
      opts.push('<option value="' + esc(curV) + '">' + esc(curV) + '</option>');
    }
    sel.innerHTML = opts.join('');
    sel.value = curV;
  }

  /* ---------- 이벤트 ---------- */
  function bindAppEvents() {
    var modes = document.querySelectorAll('.mode');
    for (var i = 0; i < modes.length; i++) {
      modes[i].addEventListener('click', function () { setMode(this.getAttribute('data-mode')); });
    }
    var tabs = document.querySelectorAll('.tab');
    for (var j = 0; j < tabs.length; j++) {
      tabs[j].addEventListener('click', function () {
        cur.tab = this.getAttribute('data-tab');
        cur.hLimit = 250;
        for (var k = 0; k < tabs.length; k++) tabs[k].classList.toggle('active', tabs[k] === this);
        var isH = cur.tab === 'H';
        $('zeroWrap').classList.toggle('hidden', isH);
        $('typeFilter').classList.toggle('hidden', !isH);
        $('histNote').classList.toggle('hidden', !isH);
        closeFilter();
        renderRangeBar();
        renderTable();
        $('tableWrap').scrollTop = 0;
        $('tableWrap').scrollLeft = 0;
      });
    }
    $('entryForm').addEventListener('submit', function (e) { e.preventDefault(); submit(); });

    /* 표 클릭: 정렬 / 필터 / 행 동작 */
    $('tableWrap').addEventListener('click', function (ev) {
      var t = ev.target;
      var sortBtn = t.closest ? t.closest('[data-sort]') : null;
      if (sortBtn) {
        ev.preventDefault();
        var tbl = cur.tab === 'H' ? 'log' : 'lot';
        var s0 = tbl === 'log' ? cur.sortLog : cur.sortLot;
        var k0 = sortBtn.getAttribute('data-sort');
        if (s0.k !== k0) { s0.k = k0; s0.dir = 1; }
        else if (s0.dir === 1) { s0.dir = -1; }
        else { s0.k = ''; s0.dir = 1; }
        renderTable();
        return;
      }
      var filtBtn = t.closest ? t.closest('[data-filter]') : null;
      if (filtBtn) {
        ev.preventDefault();
        openFilter(cur.tab === 'H' ? 'log' : 'lot', filtBtn.getAttribute('data-filter'), filtBtn);
        return;
      }
      var und = t.closest ? t.closest('[data-undo]') : null;
      if (und) {
        ev.stopPropagation();
        undoEntry(Number(und.getAttribute('data-undo')), und);
        return;
      }
      var ed = t.closest ? t.closest('[data-edit]') : null;
      if (ed) {
        ev.stopPropagation();
        openEdit(Number(ed.getAttribute('data-edit')));
        return;
      }
      var le = t.closest ? t.closest('[data-lot-edit]') : null;
      if (le) {
        ev.stopPropagation();
        openLot(le.getAttribute('data-lot-edit'));
        return;
      }
      var act = t.closest ? t.closest('[data-act]') : null;
      if (act) {
        ev.stopPropagation();
        bindLot(act.getAttribute('data-lot'), act.getAttribute('data-act'));
        return;
      }
      var tr = t.closest ? t.closest('tr.lot') : null;
      if (tr) bindLot(tr.getAttribute('data-lot'), null);
    });

    $('search').addEventListener('input', function () { cur.search = this.value; cur.hLimit = 250; renderTable(); });
    $('showZero').addEventListener('change', function () { cur.showZero = this.checked; renderTable(); });
    $('typeFilter').addEventListener('change', function () { cur.hFilter = this.value; cur.hLimit = 250; renderTable(); });
    $('majorFilter').addEventListener('change', function () { cur.major = this.value; cur.hLimit = 250; renderTable(); });
    $('btnResetFilters').addEventListener('click', function () {
      cur.fLot = {}; cur.fLog = {};
      renderTable();
    });

    var presets = document.querySelectorAll('#rangePresets .pr');
    for (var p = 0; p < presets.length; p++) {
      presets[p].addEventListener('click', function () { setPreset(this.getAttribute('data-preset')); });
    }
    ['rangeFrom', 'rangeTo'].forEach(function (id) { $(id).addEventListener('change', setCustomRange); });
    $('dateField').addEventListener('change', function () { cur.stock.field = this.value; renderTable(); });
    $('rangeClear').addEventListener('click', function () { setPreset('all'); });

    /* 필터 팝오버 */
    $('fpopSearch').addEventListener('input', function () { fpop.q = this.value; renderFpop(); });
    $('fpopList').addEventListener('change', function (ev) {
      var cb = ev.target;
      if (!cb || !cb.getAttribute) return;
      var v = cb.getAttribute('data-val');
      if (v === null) return;
      fpop.sel[v] = !!cb.checked;
      applyFilter();
      renderFpop();
    });
    $('fpopAll').addEventListener('click', function () {
      for (var i = 0; i < fpop.all.length; i++) fpop.sel[fpop.all[i]] = true;
      applyFilter(); renderFpop();
    });
    $('fpopNone').addEventListener('click', function () {
      for (var i = 0; i < fpop.all.length; i++) fpop.sel[fpop.all[i]] = false;
      applyFilter(); renderFpop();
    });
    $('fpopReset').addEventListener('click', function () {
      delete filterStore(fpop.tbl)[fpop.key];
      renderTable(); closeFilter();
    });
    $('fpopDone').addEventListener('click', closeFilter);
    $('fpopClose').addEventListener('click', closeFilter);
    document.addEventListener('click', function (ev) {
      if (!fpop.open) return;
      var el = $('fpop');
      if (el.contains(ev.target)) return;
      var tf = ev.target.closest ? ev.target.closest('[data-filter]') : null;
      if (tf) return;
      closeFilter();
    });
    window.addEventListener('resize', function () { if (fpop.open) placeFpop(); });
    window.addEventListener('scroll', function () { if (fpop.open) placeFpop(); }, true);

    var inBtns = document.querySelectorAll('#whSegIn button');
    for (var a = 0; a < inBtns.length; a++) inBtns[a].addEventListener('click', function () { setInWh(this.getAttribute('data-wh')); });
    var outBtns = document.querySelectorAll('#whSegOut button');
    for (var b = 0; b < outBtns.length; b++) outBtns[b].addEventListener('click', function () {
      setOutWh(this.getAttribute('data-wh'));
      fillLotSelect($('outLot'), cur.whOut);
      syncLotViews();
      fillLotPrice('out', ERP.getLot(st, $('outLot').value));
    });
    var dBtns = document.querySelectorAll('#destSeg button');
    for (var c = 0; c < dBtns.length; c++) dBtns[c].addEventListener('click', function () { setDest(this.getAttribute('data-dest')); });

    [['thLot', 'thaw', 'F'], ['outLot', 'out', null], ['reLot', 're', 'C']].forEach(function (pair) {
      $(pair[0]).addEventListener('change', function () {
        cur.lotId = this.value || null;
        syncLotViews();
        renderTable();
        fillLotPrice(pair[1], ERP.getLot(st, this.value));
      });
    });
    $('thAll').addEventListener('click', function () {
      var lot = ERP.getLot(st, $('thLot').value);
      if (!lot) { toast('먼저 로트를 선택하세요.', 'warn'); return; }
      $('thKg').value = lot.fq.toFixed(2);
      fillLotPrice('thaw', lot);
    });
    $('outAll').addEventListener('click', function () {
      var lot = ERP.getLot(st, $('outLot').value);
      if (!lot) { toast('먼저 로트를 선택하세요.', 'warn'); return; }
      $('outKg').value = ERP.qtyOf(lot, cur.whOut).toFixed(2);
      fillLotPrice('out', lot);
    });
    $('reAll').addEventListener('click', function () {
      var lot = ERP.getLot(st, $('reLot').value);
      if (!lot) { toast('먼저 로트를 선택하세요.', 'warn'); return; }
      $('reKg').value = lot.cq.toFixed(2);
      fillLotPrice('re', lot);
    });

    /* 단가 ↔ 금액 */
    ['in', 'thaw', 're', 'out'].forEach(function (m) {
      var ids = PRICE_IDS[m];
      $(ids.kg).addEventListener('input', function () { priceSync(m, 'kg'); });
      $(ids.price).addEventListener('input', function () { priceSync(m, 'price'); });
      $(ids.amount).addEventListener('input', function () { priceSync(m, 'amount'); });
    });
    ['inName', 'inMajor'].forEach(function (id) {
      $(id).addEventListener('input', function () { updatePriceHint(); });
      $(id).addEventListener('change', function () { updatePriceHint(); });
    });

    $('btnCsvF').addEventListener('click', function () { csvStock('F'); });
    $('btnCsvC').addEventListener('click', function () { csvStock('C'); });
    $('btnCsvH').addEventListener('click', function () { csvHistory(); });
    $('btnXlsSabang').addEventListener('click', function () { openXls('sabang'); });
    $('btnXlsSales').addEventListener('click', function () { openXls('sales'); });
    $('xlsClose').addEventListener('click', closeXls);
    $('xlsCancel').addEventListener('click', closeXls);
    $('xlsGo').addEventListener('click', downloadXls);
    $('xlsModal').addEventListener('click', function (ev) { if (ev.target === this) closeXls(); });

    /* 수정 모달 */
    $('editClose').addEventListener('click', closeEdit);
    $('editCancel').addEventListener('click', closeEdit);
    $('editSave').addEventListener('click', saveEdit);
    $('editModal').addEventListener('click', function (ev) { if (ev.target === this) closeEdit(); });
    $('edKg').addEventListener('input', function () {
      var kg = Number(this.value || 0), pr = Number($('edPrice').value || 0);
      $('edAmount').value = kg > 0 && pr > 0 ? String(Math.round(kg * pr)) : '';
    });
    $('edPrice').addEventListener('input', function () {
      var kg = Number($('edKg').value || 0), pr = Number(this.value || 0);
      $('edAmount').value = kg > 0 && pr > 0 ? String(Math.round(kg * pr)) : '';
    });
    $('edAmount').addEventListener('input', function () {
      var kg = Number($('edKg').value || 0), am = Number(this.value || 0);
      if (kg > 0) $('edPrice').value = am > 0 ? String(Math.round(am / kg)) : '';
    });

    /* 로트 모달 */
    $('lotClose').addEventListener('click', closeLot);
    $('lotCancel').addEventListener('click', closeLot);
    $('lotSave').addEventListener('click', saveLot);
    $('lotModal').addEventListener('click', function (ev) { if (ev.target === this) closeLot(); });

    document.addEventListener('keydown', function (ev) {
      if (ev.key !== 'Escape') return;
      if (!$('xlsModal').classList.contains('hidden')) { closeXls(); return; }
      if (!$('editModal').classList.contains('hidden')) { closeEdit(); return; }
      if (!$('lotModal').classList.contains('hidden')) { closeLot(); return; }
      if (fpop.open) closeFilter();
    });
    var xlsSegs = document.querySelectorAll('#xlsRangeSeg button');
    for (var s2 = 0; s2 < xlsSegs.length; s2++) {
      xlsSegs[s2].addEventListener('click', function () {
        xls.range = this.getAttribute('data-range');
        for (var q = 0; q < xlsSegs.length; q++) xlsSegs[q].classList.toggle('active', xlsSegs[q] === this);
        if (xls.range === 'range') {
          if (!$('xlsFrom').value) $('xlsFrom').value = firstOfMonth();
          if (!$('xlsTo').value) $('xlsTo').value = today();
        }
        renderXls();
      });
    }
    ['xlsFrom', 'xlsTo', 'xlsThaw', 'xlsAllOut', 'xlsVat'].forEach(function (id) {
      $(id).addEventListener('change', renderXls);
      $(id).addEventListener('input', renderXls);
    });
    $('btnLogout').addEventListener('click', function () { doLogout(false); });

    var nums = document.querySelectorAll('#entryForm input[type=number]');
    for (var d = 0; d < nums.length; d++) nums[d].addEventListener('keydown', function (ev) {
      if (ev.key === 'Enter') { ev.preventDefault(); submit(); }
    });

    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'visible' && SB.auth.session()) reload({ silent: true });
    });
  }

  function undoEntry(logId, btn) {
    if (!window.confirm('이 입력을 취소할까요?\n재고가 입력 전으로 되돌아가고, 이력에서 사라집니다.')) return;
    if (btn) btn.disabled = true;
    SB.db.undo(logId).then(function (row) {
      toast('취소됨: ' + (row && row.product_name ? row.product_name + ' ' + Number(row.qty).toFixed(2) + 'kg' : '입력 건'), 'ok');
      return reload({ silent: true });
    }).then(function () {
      if (btn) btn.disabled = false;
    }, function (e) {
      if (btn) btn.disabled = false;
      toast(e.message, 'err');
    });
  }

  function bindLoginEvents() {
    var ltab = document.querySelectorAll('.ltab');
    for (var i = 0; i < ltab.length; i++) {
      ltab[i].addEventListener('click', function () {
        var which = this.getAttribute('data-ltab');
        for (var k = 0; k < ltab.length; k++) ltab[k].classList.toggle('active', ltab[k] === this);
        $('loginForm').classList.toggle('hidden', which !== 'in');
        $('signupForm').classList.toggle('hidden', which !== 'up');
        setLoginMsg('');
      });
    }
    $('loginForm').addEventListener('submit', function (e) {
      e.preventDefault();
      var email = $('liEmail').value.replace(/^\s+|\s+$/g, '');
      var pw = $('liPw').value;
      if (!email || !pw) { setLoginMsg('이메일과 비밀번호를 입력해 주세요.', 'err'); return; }
      var b = $('btnLogin');
      b.disabled = true; b.textContent = '로그인 중…';
      setLoginMsg('');
      SB.auth.signIn(email, pw).then(function (ses) {
        setLoginMsg('');
        enterApp(ses);
        toast(ses.name + ' 님, 반갑습니다.', 'ok');
      }).then(function () {
        b.disabled = false; b.textContent = '로그인';
      }, function (err) {
        b.disabled = false; b.textContent = '로그인';
        setLoginMsg(err.message, 'err');
      });
    });
    $('signupForm').addEventListener('submit', function (e) {
      e.preventDefault();
      var name = $('suName').value.replace(/^\s+|\s+$/g, '');
      var email = $('suEmail').value.replace(/^\s+|\s+$/g, '');
      var pw = $('suPw').value;
      if (!email || !pw) { setLoginMsg('이메일과 비밀번호를 입력해 주세요.', 'err'); return; }
      if (pw.length < 6) { setLoginMsg('비밀번호는 6자 이상으로 만들어 주세요.', 'err'); return; }
      var b = $('btnSignup');
      b.disabled = true; b.textContent = '만드는 중…';
      setLoginMsg('');
      SB.auth.signUp(email, pw, name).then(function (r) {
        b.disabled = false; b.textContent = '계정 만들기';
        if (r.session) {
          enterApp(r.session);
          toast('계정이 만들어졌습니다. ' + r.session.name + ' 님 반갑습니다.', 'ok');
        } else {
          setLoginMsg('확인 메일을 ' + r.email + ' 로 보냈습니다. 메일의 확인 링크를 누른 뒤 로그인해 주세요.\n' +
            '(회사 내부용이라면 Supabase → Authentication → Sign In / Providers에서 “Confirm email”을 끄면 바로 쓸 수 있습니다)', 'warn');
        }
      }, function (err) {
        b.disabled = false; b.textContent = '계정 만들기';
        setLoginMsg(err.message, 'err');
      });
    });
  }

  /* ---------- 시작 ---------- */
  function boot() {
    bindLoginEvents();
    bindAppEvents();
    setSync('wait', '확인 중');
    var ses = SB.auth.restore();
    if (ses) {
      enterApp(ses);
    } else {
      $('loginView').classList.remove('hidden');
      $('appView').classList.add('hidden');
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
/* ============================== UI:END ============================== */
