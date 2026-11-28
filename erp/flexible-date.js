/* Flexible date entry for authenticated ERP, preserving ISO storage. */
(() => {
'use strict';
if(!document.getElementById('editorform')||document.getElementById('erp-flex-date-style'))return;
function parseDate(raw,year=new Date().getFullYear()){
  const s=String(raw??'').normalize('NFKC').trim();if(!s)return '';
  let y,m,d,p;
  if(/^\d{4}$/.test(s)){y=year;m=+s.slice(0,2);d=+s.slice(2)}
  else if(/^\d{6}$/.test(s)){y=2000+ +s.slice(0,2);m=+s.slice(2,4);d=+s.slice(4)}
  else if(/^\d{8}$/.test(s)){y=+s.slice(0,4);m=+s.slice(4,6);d=+s.slice(6)}
  else if((p=s.match(/^(\d{1,2})([\/-])(\d{1,2})$/))){y=year;m=+p[1];d=+p[3]}
  else if((p=s.match(/^(\d{2}|\d{4})([\/-])(\d{1,2})\2(\d{1,2})$/))){y=+p[1]+(p[1].length===2?2000:0);m=+p[3];d=+p[4]}
  else return null;
  if(y<1900||y>2199||m<1||m>12||d<1||d>31)return null;
  const date=new Date(Date.UTC(y,m-1,d));
  if(date.getUTCFullYear()!==y||date.getUTCMonth()!==m-1||date.getUTCDate()!==d)return null;
  return String(y).padStart(4,'0')+'-'+String(m).padStart(2,'0')+'-'+String(d).padStart(2,'0');
}
const style=document.createElement('style');style.id='erp-flex-date-style';style.textContent=
'.erp-date-wrap{position:relative;display:flex;align-items:center;width:100%;min-width:0;gap:5px}'+
'.erp-date-wrap>input[data-erp-flex-date]{flex:1 1 auto;min-width:0;width:100%;padding-right:43px!important}'+
'.erp-date-wrap>.erp-date-button{position:absolute;right:3px;top:50%;transform:translateY(-50%);display:grid;place-items:center;width:36px;height:36px;min-width:36px;min-height:36px;padding:0;border:0;border-radius:5px;color:#697483;background:transparent;box-shadow:none}'+
'.erp-date-wrap>.erp-date-picker{position:absolute;right:0;bottom:0;width:38px;height:38px;opacity:0;pointer-events:none;z-index:-1}'+
'.erp-date-wrap>.erp-date-picker.erp-date-fallback{opacity:1;pointer-events:auto;z-index:5;width:100%;background:white}'+
'.erp-date-wrap>[hidden]{display:none!important}input[data-erp-flex-date][aria-invalid="true"]{border-color:#b42318!important}'+
'@media(max-width:760px){input[data-erp-flex-date]{font-size:16px!important}}';
document.head.append(style);
const message='날짜를 확인하세요. 예: 1120, 261120, 2026-11-20';
function validate(el,normalize=true){
  const value=parseDate(el.value),bad=value===null||(value!==''&&((el.getAttribute('min')&&value<el.getAttribute('min'))||(el.getAttribute('max')&&value>el.getAttribute('max'))));
  el.setCustomValidity(bad?message:'');el.toggleAttribute('data-erp-date-invalid',bad);
  if(bad)el.setAttribute('aria-invalid','true');else el.removeAttribute('aria-invalid');
  if(!bad&&normalize)el.value=value;return !bad;
}
function updateRange(el,redraw=false){
  if(!el.isConnected||!el.dataset.rangeInput||typeof rangeDraft==='undefined'||!rangeDraft)return;
  const r=rangeDraft,field=el.dataset.rangeInput,side=field==='a'?'left':'right';
  r[field]=el.value;r.key='custom';
  if(redraw){if(el.value)r[side]=el.value.slice(0,7);drawRange();scan();return}
  const valid=rangeValid(r),empty=!r.a&&!r.b,dialog=document.getElementById('rangeDialog');
  const summary=dialog.querySelector('.range-summary'),apply=dialog.querySelector('#rangeApply');
  if(summary)summary.innerHTML='<b>조회기간</b><span>'+esc(empty?'전체 기간':(r.a||'미선택')+' ~ '+(r.b||'미선택'))+'</span>'+(valid?'<span class="range-count">총 '+rangeCount(r.a,r.b)+'일</span>':'');
  if(apply)apply.disabled=!(valid||empty)||!!dialog.querySelector('[data-erp-date-invalid]');
  for(const b of dialog.querySelectorAll('[data-range-day]')){
    const day=b.dataset.rangeDay,endpoint=day===r[b.dataset.side==='left'?'a':'b'];
    b.classList.toggle('endpoint',endpoint);b.classList.toggle('inrange',!!r.a&&!!r.b&&day>=r.a&&day<=r.b);b.setAttribute('aria-pressed',String(endpoint))
  }
  for(const b of dialog.querySelectorAll('[data-range-preset]')){b.classList.toggle('primary',b.dataset.rangePreset==='custom');b.setAttribute('aria-pressed',String(b.dataset.rangePreset==='custom'))}
  let err=dialog.querySelector('.range-error');if(!valid&&!empty){if(!err){err=document.createElement('p');err.className='range-error';dialog.querySelector('#rangeBody').append(err)}err.textContent='시작일과 종료일을 올바르게 선택하세요.'}else err?.remove();
}
function commit(el){
  if(!validate(el)){if(el.dataset.rangeInput){const b=document.getElementById('rangeApply');if(b)b.disabled=true}return false}
  if(el.dataset.rangeInput)updateRange(el);return true
}
function next(el){const form=el.closest('form');if(!form){el.blur();return}
  const all=[...form.querySelectorAll('input:not([type=hidden]),select,textarea')].filter(x=>!x.disabled&&!x.readOnly&&x.tabIndex!==-1&&x.getClientRects().length);
  const n=all[all.indexOf(el)+1];if(n)n.focus();else el.blur()
}
let activePicker=null;
function closePicker(){if(!activePicker)return;activePicker.hidden=true;activePicker.classList.remove('erp-date-fallback');activePicker=null}
function enhance(el){
  if(el.dataset.erpFlexDate||el.classList.contains('erp-date-picker'))return;
  const value=el.value,focused=document.activeElement===el;el.type='text';el.value=value;el.dataset.erpFlexDate='1';
  el.inputMode='numeric';el.autocomplete='off';el.placeholder='YYYY-MM-DD';el.spellcheck=false;
  if(el.dataset.rangeInput)return;
  const wrap=document.createElement('div');wrap.className='erp-date-wrap';el.before(wrap);wrap.append(el);
  const btn=document.createElement('button');btn.type='button';btn.className='erp-date-button';btn.setAttribute('aria-label','달력 열기');btn.innerHTML=typeof I==='function'?I('calendar'):'▦';
  const picker=document.createElement('input');picker.type='date';picker.className='erp-date-picker';picker.tabIndex=-1;picker.hidden=true;picker.setAttribute('aria-label','달력 날짜 선택');picker.min=el.getAttribute('min')||'1900-01-01';picker.max=el.getAttribute('max')||'2199-12-31';
  wrap.append(btn,picker);
  btn.addEventListener('click',e=>{e.stopPropagation();closePicker();picker.value=parseDate(el.value)||'';picker.hidden=false;activePicker=picker;
    try{if(typeof picker.showPicker!=='function')throw Error('unsupported');picker.showPicker()}
    catch{picker.classList.add('erp-date-fallback');picker.focus()}
  });
  picker.addEventListener('change',()=>{if(picker.value){el.value=picker.value;el.dispatchEvent(new Event('input',{bubbles:true}));commit(el);el.dispatchEvent(new Event('change',{bubbles:true}))}closePicker()});
  picker.addEventListener('blur',()=>{if(picker.classList.contains('erp-date-fallback'))closePicker()});
  if(focused)el.focus({preventScroll:true});
}
function scan(){for(const el of document.querySelectorAll('input[type=date]:not(.erp-date-picker)'))enhance(el)}
document.addEventListener('pointerdown',e=>{if(activePicker&&!activePicker.parentElement?.contains(e.target))closePicker()},true);
document.addEventListener('input',e=>{const el=e.target;if(!el.matches?.('[data-erp-flex-date]'))return;el.setCustomValidity('');el.removeAttribute('aria-invalid');el.removeAttribute('data-erp-date-invalid')});
document.addEventListener('change',e=>{const el=e.target;if(!el.matches?.('[data-erp-flex-date]'))return;if(el.dataset.rangeInput)e.stopImmediatePropagation();commit(el)},true);
document.addEventListener('blur',e=>{const el=e.target;if(el.matches?.('[data-erp-flex-date]')&&el.isConnected)commit(el)},true);
document.addEventListener('keydown',e=>{
  const el=e.target;if(e.key!=='Enter'||e.isComposing||e.keyCode===229||!el.matches?.('[data-erp-flex-date]'))return;
  e.preventDefault();e.stopImmediatePropagation();if(!commit(el)){el.reportValidity();return}
  if(el.dataset.rangeInput){const field=el.dataset.rangeInput;updateRange(el,true);if(field==='a')document.getElementById('range-b')?.focus();return}
  next(el);
},true);
document.addEventListener('submit',e=>{for(const el of e.target.querySelectorAll('[data-erp-flex-date]'))if(!commit(el)){e.preventDefault();e.stopImmediatePropagation();el.reportValidity();return}},true);
document.addEventListener('click',e=>{if(!e.target.closest?.('#rangeApply'))return;for(const el of document.querySelectorAll('#rangeDialog [data-erp-flex-date]'))if(!commit(el)){e.preventDefault();e.stopImmediatePropagation();el.reportValidity();return}},true);
new MutationObserver(records=>{scan();for(const r of records)if(r.type==='attributes'&&r.target.matches?.('dialog[open]'))for(const el of r.target.querySelectorAll('[data-erp-flex-date]'))validate(el,false);if(activePicker&&!activePicker.isConnected)closePicker()}).observe(document.body,{subtree:true,childList:true,attributes:true,attributeFilter:['open']});
scan();
})();