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
  function nz(x) { return x === undefined || x === null ? '' : String(x); }
  function s(x) { return nz(x).replace(/^\s+|\s+$/g, ''); }

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
        id: 'L' + r.id, dbid: Number(r.id), n: nz(r.product_name), mt: nz(r.meat_type),
        o: nz(r.origin), v: nz(r.vendor), b: nz(r.brand),
        i: nz(r.in_date), e: nz(r.exp_date),
        fq: r2(r.frozen_qty), cq: r2(r.chilled_qty), up: nz(r.updated_at)
      });
    }
    for (i = 0; i < logRows.length; i++) {
      r = logRows[i];
      logs.push({
        id: 'H' + r.id, dbid: Number(r.id), d: nz(r.tx_date), w: nz(r.warehouse) || 'F',
        t: nz(r.tx_type) || 'out', n: nz(r.product_name), v: nz(r.vendor),
        i: nz(r.in_date), e: nz(r.exp_date), k: r2(r.qty),
        p: nz(r.dest_detail), dt: nz(r.dest_type), note: nz(r.note),
        lid: r.lot_id === null || r.lot_id === undefined ? '' : String(r.lot_id),
        worker: nz(r.worker_name), email: nz(r.worker_email),
        act: r.is_manual !== false, at: nz(r.created_at)
      });
    }
    return { lots: lots, logs: logs, loadedAt: Date.now() };
  }

  function totals(st) {
    var f = 0, c = 0, lf = 0, lc = 0, live = 0, mine = 0, i;
    for (i = 0; i < st.lots.length; i++) {
      var l = st.lots[i];
      f += l.fq; c += l.cq;
      if (l.fq > EPS) lf++;
      if (l.cq > EPS) lc++;
      if (l.fq > EPS || l.cq > EPS) live++;
    }
    for (i = 0; i < st.logs.length; i++) if (st.logs[i].act) mine++;
    return { frozen: r2(f), chilled: r2(c), liveFrozen: lf, liveChilled: lc, live: live, manual: mine };
  }

  function getLot(st, id) {
    for (var i = 0; i < st.lots.length; i++) if (st.lots[i].id === id) return st.lots[i];
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

  /* 제품명 묶음 + 선입선출 순서. wh 재고가 0인 로트는 showZero 일 때만. */
  function grouped(st, wh, q, showZero) {
    var rows = [], i, l, groups = {}, order = [], out = [], qq = s(q).toLowerCase();
    for (i = 0; i < st.lots.length; i++) {
      l = st.lots[i];
      if (!showZero && qtyOf(l, wh) <= EPS) continue;
      if (qq) {
        var hay = [l.n, l.v, l.o, l.i, l.b, l.e, l.mt].join(' ').toLowerCase();
        if (hay.indexOf(qq) < 0) continue;
      }
      rows.push(l);
    }
    for (i = 0; i < rows.length; i++) {
      var k = rows[i].n;
      if (!groups[k]) { groups[k] = []; order.push(k); }
      groups[k].push(rows[i]);
    }
    order.sort(function (a, b) { return a.localeCompare(b, 'ko'); });
    for (i = 0; i < order.length; i++) {
      var list = groups[order[i]];
      list.sort(sortLots);
      var sum = 0, live = 0;
      for (var j = 0; j < list.length; j++) {
        sum += qtyOf(list[j], wh);
        if (qtyOf(list[j], wh) > EPS) live++;
      }
      out.push({ name: order[i], lots: list, sum: r2(sum), live: live });
    }
    return out;
  }

  function countLive(st, wh) {
    var n = 0;
    for (var i = 0; i < st.lots.length; i++) if (qtyOf(st.lots[i], wh) > EPS) n++;
    return n;
  }

  function sortLogsDesc(logs) {
    var out = logs.slice();
    out.sort(function (a, b) {
      if (a.d !== b.d) return a.d < b.d ? 1 : -1;
      return (b.dbid || 0) - (a.dbid || 0);
    });
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

  /* 입출고 내역 CSV — 날짜, 구분, 창고, …, 출고처 · 비고, 작업자 */
  function csv(st) {
    var head = ['날짜', '구분', '창고', '제품명', '업체명', '입고일', '소비기한', '중량(kg)',
      '출고처 구분', '출고처 / 생산품목', '비고', '작업자'];
    var rows = [head];
    var list = sortLogsDesc(st.logs);
    for (var i = 0; i < list.length; i++) {
      var e = list[i];
      rows.push([
        e.d, typeName(e.t), moveName(e), e.n, e.v, e.i, e.e, Number(e.k).toFixed(2),
        e.t === 'out' ? destName(e.dt) : '', e.p || '', e.note || '', e.worker || ''
      ]);
    }
    return csvQuote(rows);
  }

  /* 재고 CSV — 제품명, 육류, 원산지, 업체명, 브랜드, 입고일, 소비기한, 재고(kg) */
  function stockCsv(st, wh) {
    var head = ['제품명', '육류', '원산지', '업체명', '브랜드', '입고일', '소비기한',
      wh === 'F' ? '냉동고 재고(kg)' : '냉장고 재고(kg)'];
    var rows = [head];
    var groups = grouped(st, wh, '', false);
    for (var i = 0; i < groups.length; i++) {
      for (var j = 0; j < groups[i].lots.length; j++) {
        var l = groups[i].lots[j];
        var q = qtyOf(l, wh);
        if (q <= EPS) continue;
        rows.push([l.n, l.mt, l.o, l.v, l.b, l.i, l.e, Number(q).toFixed(2)]);
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
  function pad2(n) { return (n < 10 ? '0' : '') + n; }

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

  function sortLogsAsc(logs) {
    var out = logs.slice();
    out.sort(function (a, b) {
      if (a.d !== b.d) return a.d < b.d ? -1 : 1;
      return (a.dbid || 0) - (b.dbid || 0);
    });
    return out;
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

  /* 경리나라 '매출거래명세표 일괄등록' 양식 — 헤더 20열 */
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
        0, 0, 0,                                       /* 단가·공급가액·세액 (업로드 후 입력) */
        s(e.note),                                     /* 품목비고 */
        '', '', ''                                     /* 입금액·인수자·공통메모 */
      ]);
    }
    return rows;
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
    var names = [], vendors = [], origins = [], brands = [], products = [];
    var seen = { n: {}, v: {}, o: {}, b: {}, p: {} };
    function add(arr, seenMap, v) {
      v = s(v);
      if (!v || seenMap[v]) return;
      seenMap[v] = 1;
      arr.push(v);
    }
    var i, l, e;
    for (i = 0; i < st.lots.length; i++) {
      l = st.lots[i];
      add(names, seen.n, l.n);
      add(vendors, seen.v, l.v);
      add(origins, seen.o, l.o);
      add(brands, seen.b, l.b);
    }
    for (i = 0; i < st.logs.length; i++) {
      e = st.logs[i];
      add(names, seen.n, e.n);
      add(vendors, seen.v, e.v);
      if (e.t === 'out' && e.p) add(products, seen.p, e.p);
    }
    return { names: names, vendors: vendors, origins: origins, brands: brands, products: products };
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
    return null;
  }

  return {
    EPS: EPS, r2: r2, DESTS: DEST_KEYS, DEST_NAME: DEST_NAME, DEST_LABEL: DEST_LABEL, DEST_HINT: DEST_HINT,
    destKey: destKey, destName: destName, typeName: typeName, whName: whName, moveName: moveName,
    stateFrom: stateFrom, totals: totals, getLot: getLot, qtyOf: qtyOf, sortLots: sortLots,
    grouped: grouped, countLive: countLive, sortLogsDesc: sortLogsDesc,
    csv: csv, stockCsv: stockCsv, csvQuote: csvQuote, dict: dict, destHistory: destHistory, precheck: precheck,
    SABANG_HEAD: SABANG_HEAD, SALES_HEAD: SALES_HEAD, sabangnetRows: sabangnetRows, salesRows: salesRows,
    lotOf: lotOf, ymd8: ymd8, mmdd: mmdd, sortLogsAsc: sortLogsAsc, inDateRange: inDateRange,
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
        p_brand: p.brand || ''
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
    db: { loadAll: loadAll, apply: apply, undo: undo, rest: rest },
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
    search: '', showZero: false, hFilter: 'all', hLimit: 250, lotId: null
  };
  var prev = {};
  var loading = false, again = false;
  var pollTimer = null;

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
    return e && (/supabase_setup\.sql|DB 표를 찾을 수 없습니다/.test(e.message || ''));
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
    kpi('kLive', t.live, 0);
    var tp = 0, d0 = today();
    for (var i = 0; i < st.logs.length; i++) if (st.logs[i].d === d0) tp++;
    kpi('kToday', tp, 0);
    $('kFreeSub').textContent = '보관 로트 ' + t.liveFrozen + '개';
    $('kChillSub').textContent = '보관 로트 ' + t.liveChilled + '개';
    $('kLiveSub').textContent = '전체 ' + st.lots.length + '개 로트 중';
    $('kTodaySub').textContent = d0 + ' 입력 기준';
    $('cntF').textContent = ERP.countLive(st, 'F');
    $('cntC').textContent = ERP.countLive(st, 'C');
    $('cntH').textContent = st.logs.length;
  }

  /* ---------- 재고표 ---------- */
  function renderStock(wh) {
    var wrap = $('tableWrap');
    var keep = wrap.scrollTop;
    var groups = ERP.grouped(st, wh, cur.search, cur.showZero);

    if (!groups.length) {
      wrap.innerHTML = '<table><tbody><tr class="empty-row"><td>조건에 맞는 로트가 없습니다.</td></tr></tbody></table>';
      wrap.scrollTop = 0;
      return;
    }
    var html = ['<table class="fixed"><colgroup>',
      '<col style="width:62px"><col style="width:92px"><col><col style="width:104px">',
      '<col style="width:100px"><col style="width:132px"><col style="width:116px"><col style="width:126px">',
      '</colgroup><thead><tr>',
      '<th>육류</th><th>원산지</th><th>업체명</th><th>브랜드</th>',
      '<th>입고일</th><th>소비기한</th><th class="num">' + (wh === 'F' ? '냉동고' : '냉장고') + ' 재고(kg)</th>',
      '<th class="num">작업</th></tr></thead><tbody>'];

    for (var i = 0; i < groups.length; i++) {
      var g = groups[i];
      html.push('<tr class="group"><td colspan="8"><span class="g-name">' + esc(g.name) + '</span>' +
        '<span class="g-meta">' + g.lots.length + '개 로트 · 보관 ' + g.live + '개 · <b>' + fmt(g.sum) + '</b> kg</span></td></tr>');
      for (var m = 0; m < g.lots.length; m++) {
        var lot = g.lots[m];
        var qv = ERP.qtyOf(lot, wh);
        var sel = cur.lotId === lot.id ? ' sel' : '';
        html.push('<tr class="lot' + sel + '" data-lot="' + lot.id + '">');
        html.push('<td><span class="mtag mt-' + esc(lot.mt || '기타') + '">' + esc(lot.mt || '-') + '</span></td>');
        html.push('<td>' + esc(lot.o || '-') + '</td>');
        html.push('<td class="ellip">' + esc(lot.v || '-') + '</td>');
        html.push('<td>' + esc(lot.b || '-') + '</td>');
        html.push('<td>' + esc(lot.i || '-') + '</td>');
        html.push('<td>' + esc(lot.e || '-') + ddayHtml(lot.e) + '</td>');
        html.push('<td class="num' + (qv <= ERP.EPS ? ' zero' : '') + '">' + fmt(qv) + '</td>');
        html.push('<td><div class="acts">' +
          (wh === 'F'
            ? '<button class="act thaw" data-act="thaw" data-lot="' + lot.id + '"' + (qv <= ERP.EPS ? ' disabled' : '') + '>해동</button>'
            : '<button class="act re" data-act="re" data-lot="' + lot.id + '"' + (qv <= ERP.EPS ? ' disabled' : '') + '>재냉동</button>') +
          '<button class="act out" data-act="out" data-lot="' + lot.id + '"' + (qv <= ERP.EPS ? ' disabled' : '') + '>출고</button>' +
          '</div></td>');
        html.push('</tr>');
      }
    }
    html.push('</tbody></table>');
    wrap.innerHTML = html.join('');
    wrap.scrollTop = keep;
  }

  /* ---------- 입출고 내역 ---------- */
  function renderHistNote() {
    var orig = 0, mine = 0, i;
    for (i = 0; i < st.logs.length; i++) {
      if (st.logs[i].act) mine++; else orig++;
    }
    $('histNote').textContent = '처음 엑셀에서 옮긴 이력 ' + orig + '건 + 화면에서 입력한 이력 ' + mine + '건. ' +
      '해동은 냉동고 출고·냉장고 입고 두 줄이던 것을 한 줄(창고: 냉동고→냉장고)로 묶었고, ' +
      '원본 출고는 생산품목만 적혀 있어 [현장]으로 표시합니다. ' +
      '화면에서 입력한 건만 [취소]로 되돌릴 수 있고, 취소하면 재고도 함께 원복됩니다.';
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
  function renderHistory() {
    var wrap = $('tableWrap');
    renderHistNote();
    var list = ERP.sortLogsDesc(st.logs);
    var q = cur.search.trim().toLowerCase();
    var shown = [], i, e;
    for (i = 0; i < list.length; i++) {
      e = list[i];
      if (cur.hFilter !== 'all' && e.t !== cur.hFilter) continue;
      if (q) {
        var hay = [e.n, e.v, e.p, e.note, e.i, e.d, e.worker, ERP.typeName(e.t),
          e.t === 'out' ? ERP.destName(e.dt) : '', ERP.moveName(e)].join(' ').toLowerCase();
        if (hay.indexOf(q) < 0) continue;
      }
      shown.push(e);
    }
    if (!shown.length) {
      wrap.innerHTML = '<table><tbody><tr class="empty-row"><td>조건에 맞는 내역이 없습니다.</td></tr></tbody></table>';
      return;
    }
    var page = shown.slice(0, cur.hLimit);
    var html = ['<table class="fixed"><colgroup>',
      '<col style="width:86px"><col style="width:62px"><col style="width:92px"><col style="width:116px">',
      '<col style="width:94px"><col style="width:82px"><col style="width:82px"><col style="width:74px">',
      '<col><col style="width:76px"><col style="width:46px">',
      '</colgroup><thead><tr>',
      '<th>날짜</th><th>구분</th><th>창고</th><th>제품명</th><th>업체명</th>',
      '<th>입고일</th><th>소비기한</th><th class="num">중량(kg)</th>',
      '<th>출고처 · 비고</th><th>작업자</th><th></th></tr></thead><tbody>'];
    for (i = 0; i < page.length; i++) {
      e = page[i];
      html.push('<tr>' +
        '<td>' + esc(e.d || '-') + '</td>' +
        '<td><span class="badge ' + esc(e.t) + '">' + ERP.typeName(e.t) + '</span></td>' +
        '<td><span class="move">' + ERP.moveName(e) + '</span></td>' +
        '<td class="ellip"><b>' + esc(e.n) + '</b></td>' +
        '<td class="ellip">' + esc(e.v || '-') + '</td>' +
        '<td>' + esc(e.i || '-') + '</td>' +
        '<td>' + esc(e.e || '-') + '</td>' +
        '<td class="num">' + fmt(e.k) + '</td>' +
        '<td class="ellip" title="' + esc(destTitle(e)) + '">' + destCell(e) + '</td>' +
        '<td class="ellip">' + (e.worker ? '<span class="worker" title="' + esc(e.email) + '">' + esc(e.worker) + '</span>' : '<span class="ttag">-</span>') + '</td>' +
        '<td>' + (e.act ? '<button class="cancel" data-undo="' + e.dbid + '">취소</button>' : '') + '</td>' +
        '</tr>');
    }
    html.push('</tbody></table>');
    if (shown.length > cur.hLimit) {
      html.push('<button class="more" id="btnMore">더 보기 (' + (shown.length - cur.hLimit) + '건 남음)</button>');
    }
    wrap.innerHTML = html.join('');
    var more = $('btnMore');
    if (more) more.addEventListener('click', function () { cur.hLimit += 250; renderHistory(); });
  }

  function renderTable() {
    if (cur.tab === 'H') { renderHistory(); return; }
    renderStock(cur.tab);
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
      ' · ' + esc(lot.mt || '-') + '/' + esc(lot.o || '-') + '<br>' +
      '입고 ' + esc(lot.i || '-') + ' · 소비기한 ' + esc(lot.e || '-') + ddayHtml(lot.e) +
      '<br>' + (wh === 'F' ? '냉동고' : '냉장고') + ' 현재고 <b>' + fmt(q) + ' kg</b>' +
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
    } else if (act === 're') {
      setMode('re');
      $('reLot').value = lotId;
    } else if (act === 'out') {
      cur.whOut = cur.tab === 'C' ? 'C' : (cur.tab === 'F' ? 'F' : cur.whOut);
      setMode('out');
      setOutWh(cur.whOut);
    } else if (cur.mode === 'thaw') {
      if (lot.fq <= ERP.EPS) {
        toast('이 로트는 냉동고 재고가 0입니다. 출고로 전환합니다.', 'warn');
        setOutWh('F');
        setMode('out');
      } else {
        $('thLot').value = lotId;
      }
    } else if (cur.mode === 're') {
      if (lot.cq <= ERP.EPS) {
        toast('이 로트는 냉장고 재고가 0입니다. 출고로 전환합니다.', 'warn');
        setOutWh('C');
        setMode('out');
      } else {
        $('reLot').value = lotId;
      }
    }
    syncLotViews();
    renderTable();
    var kg = cur.mode === 'thaw' ? $('thKg') : (cur.mode === 're' ? $('reKg') : (cur.mode === 'out' ? $('outKg') : null));
    if (kg) { kg.value = ''; kg.focus(); }
  }

  /* ---------- 새로고침 ---------- */
  function refresh() {
    renderKPI();
    renderTable();
    syncLotViews();
    fillDatalists();
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
        showBanner('DB 표를 찾을 수 없습니다. Supabase SQL Editor에서 <b>supabase_setup.sql</b>을 한 번 실행해 주세요.<br><span class="banner-sub">' + esc(e.message) + '</span>');
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
    return null;
  }
  function fieldFromMsg(msg) {
    if (/제품명/.test(msg)) return 'name';
    if (/입고일/.test(msg)) return 'inDate';
    if (/소비기한/.test(msg)) return 'expiry';
    if (/출고처/.test(msg)) return 'dest';
    if (/날짜/.test(msg)) return 'date';
    if (/중량/.test(msg)) return 'kg';
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
  function params() {
    var p = { date: today(), type: cur.mode, wh: cur.whIn, lot_id: null, kg: 0 };
    if (cur.mode === 'in') {
      p.date = $('inDate').value || today();
      p.name = $('inName').value;
      p.meat = $('inMeat').value;
      p.origin = $('inOrigin').value;
      p.vendor = $('inVendor').value;
      p.brand = $('inBrand').value;
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
    if (p.type === 'in') {
      var isNew = !st.lots.some(function (l) { return l.dbid === Number(row.lot_id); });
      return '입고 완료: ' + name + ' ' + kg + 'kg → ' + (p.wh === 'F' ? '냉동고' : '냉장고') + (isNew ? ' (신규 로트)' : ' (기존 로트 합산)');
    }
    if (p.type === 'thaw') return '해동 완료: ' + name + ' ' + kg + 'kg (냉동 −' + kg + ' / 냉장 +' + kg + ')';
    if (p.type === 're') return '재냉동 완료: ' + name + ' ' + kg + 'kg (냉장 −' + kg + ' / 냉동 +' + kg + ')';
    return '출고 완료: ' + name + ' ' + kg + 'kg (' + (p.wh === 'F' ? '냉동고' : '냉장고') +
      ' → [' + ERP.destName(row && row.dest_type || p.dest_type) + '] ' + ((row && row.dest_detail) || p.dest) + ')';
  }
  function clearAfterSave() {
    if (cur.mode === 'in') {
      ['inName', 'inKg', 'inNote', 'inOrigin', 'inVendor', 'inBrand', 'inExpiry'].forEach(function (id) { $(id).value = ''; });
      $('inInDate').value = today();
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
    download(ERP.csv(st), '원료육_입출고내역_' + today().replace(/-/g, '') + '.csv');
    toast('입출고 내역 ' + st.logs.length + '건을 CSV로 내려받았습니다.', 'ok');
  }
  function csvStock(wh) {
    var g = ERP.grouped(st, wh, '', false);
    var n = 0;
    for (var i = 0; i < g.length; i++) n += g[i].live;
    var kg = 0;
    for (var j = 0; j < st.lots.length; j++) if (ERP.qtyOf(st.lots[j], wh) > ERP.EPS) kg += ERP.qtyOf(st.lots[j], wh);
    download(ERP.stockCsv(st, wh), '원료육_' + (wh === 'F' ? '냉동고' : '냉장고') + '재고_' + today().replace(/-/g, '') + '.csv');
    toast((wh === 'F' ? '냉동고' : '냉장고') + ' 재고 ' + n + '개 로트 · ' + fmt(kg) + 'kg을 CSV로 내려받았습니다.', 'ok');
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
    var n = rows.length - 1, qtyCol = isSales ? 11 : 3, f = 0, ch = 0, kg = 0, i;
    for (i = 1; i < rows.length; i++) {
      if (rows[i][6] === '냉동고') f++; else if (rows[i][6] === '냉장고') ch++;
      kg += Number(rows[i][qtyCol]) || 0;
    }
    var box = $('xlsCount');
    if (!n) {
      box.className = 'xls-count none';
      box.textContent = rangeText(opt) + '에 해당하는 ' + (isSales ? '출고' : '입고') +
        ' 내역이 없습니다. 날짜 범위를 [전체]로 바꾸거나 기간을 넓혀 보세요.';
    } else {
      box.className = 'xls-count';
      box.textContent = rangeText(opt) + ' · ' + (isSales ? '매출' : '입고') + ' ' + n + '건 · 냉동고 ' + f +
        ' / 냉장고 ' + ch + ' · 합계 ' + fmt(kg) + 'kg';
    }
    $('xlsGo').disabled = !n;
    return n;
  }

  function openXls(kind) {
    xls.kind = kind;
    var isSales = kind === 'sales';
    $('xlsTitle').textContent = isSales ? '경리나라 매출 양식 내려받기' : '사방넷 입고 양식 내려받기';
    $('xlsSub').textContent = isSales
      ? '업체 출고를 경리나라 [매출거래명세표 일괄등록] 양식(.xlsx, 시트 일괄등록)으로 만듭니다. 거래처명은 출고 업체명, 단가·공급가액·세액은 0으로 넣으니 업로드한 뒤 입력하세요.'
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
        renderTable();
        $('tableWrap').scrollTop = 0;
      });
    }
    $('entryForm').addEventListener('submit', function (e) { e.preventDefault(); submit(); });

    $('tableWrap').addEventListener('click', function (ev) {
      var act = ev.target.closest ? ev.target.closest('[data-act]') : null;
      if (act) {
        ev.stopPropagation();
        bindLot(act.getAttribute('data-lot'), act.getAttribute('data-act'));
        return;
      }
      var und = ev.target.closest ? ev.target.closest('[data-undo]') : null;
      if (und) {
        ev.stopPropagation();
        undoEntry(Number(und.getAttribute('data-undo')), und);
        return;
      }
      var tr = ev.target.closest ? ev.target.closest('tr.lot') : null;
      if (tr) bindLot(tr.getAttribute('data-lot'), null);
    });

    $('search').addEventListener('input', function () { cur.search = this.value; cur.hLimit = 250; renderTable(); });
    $('showZero').addEventListener('change', function () { cur.showZero = this.checked; renderTable(); });
    $('typeFilter').addEventListener('change', function () { cur.hFilter = this.value; cur.hLimit = 250; renderTable(); });

    var inBtns = document.querySelectorAll('#whSegIn button');
    for (var a = 0; a < inBtns.length; a++) inBtns[a].addEventListener('click', function () { setInWh(this.getAttribute('data-wh')); });
    var outBtns = document.querySelectorAll('#whSegOut button');
    for (var b = 0; b < outBtns.length; b++) outBtns[b].addEventListener('click', function () {
      setOutWh(this.getAttribute('data-wh'));
      fillLotSelect($('outLot'), cur.whOut);
      syncLotViews();
    });
    var dBtns = document.querySelectorAll('#destSeg button');
    for (var c = 0; c < dBtns.length; c++) dBtns[c].addEventListener('click', function () { setDest(this.getAttribute('data-dest')); });

    ['thLot', 'outLot', 'reLot'].forEach(function (id) {
      $(id).addEventListener('change', function () {
        cur.lotId = this.value || null;
        syncLotViews();
        renderTable();
      });
    });
    $('thAll').addEventListener('click', function () {
      var lot = ERP.getLot(st, $('thLot').value);
      if (!lot) { toast('먼저 로트를 선택하세요.', 'warn'); return; }
      $('thKg').value = lot.fq.toFixed(2);
    });
    $('outAll').addEventListener('click', function () {
      var lot = ERP.getLot(st, $('outLot').value);
      if (!lot) { toast('먼저 로트를 선택하세요.', 'warn'); return; }
      $('outKg').value = ERP.qtyOf(lot, cur.whOut).toFixed(2);
    });
    $('reAll').addEventListener('click', function () {
      var lot = ERP.getLot(st, $('reLot').value);
      if (!lot) { toast('먼저 로트를 선택하세요.', 'warn'); return; }
      $('reKg').value = lot.cq.toFixed(2);
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
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape' && !$('xlsModal').classList.contains('hidden')) closeXls();
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

    var nums = document.querySelectorAll('input[type=number]');
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
