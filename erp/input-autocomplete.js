/* Shared substring autocomplete for authenticated ERP text fields. */
(() => {
'use strict';
if(typeof rows!=='function'||!document.getElementById('editorform')||document.getElementById('erp-auto-style'))return;
const style=document.createElement('style');style.id='erp-auto-style';style.textContent=
'.erp-auto-list{position:fixed;z-index:1500;box-sizing:border-box;background:#fff;border:1px solid #d1d6df;border-radius:8px;box-shadow:0 5px 18px #20273320;padding:4px;overflow:auto;overscroll-behavior:contain;color:#202733;touch-action:pan-y;max-height:260px;text-align:left}'+
'.erp-auto-list[hidden]{display:none!important}.erp-auto-list .erp-auto-option{display:block;width:100%;text-align:left;min-height:40px;padding:9px 10px;margin:0;border:0;border-radius:5px;background:transparent;color:#202733;font:inherit;font-size:14px;font-weight:400;line-height:1.4;overflow-wrap:anywhere;box-shadow:none;cursor:pointer}'+
'.erp-auto-list .erp-auto-option[aria-selected="true"]{background:#e5e5ea;color:#202733}.erp-auto-list .erp-auto-empty{padding:10px;color:#697483;font-size:13px}'+
'@media (hover:hover){.erp-auto-list .erp-auto-option:hover{background:#e5e5ea;color:#202733}}@media(max-width:760px){.erp-auto-list .erp-auto-option{min-height:44px;font-size:16px}}';
document.head.append(style);
const normal=v=>String(v??'').normalize('NFKC').toLowerCase().replace(/\s+/g,'');
const itemFields=new Set(['품목명','완제품','원료품목','생산품목','품목코드']);
const vendorFields=new Set(['업체명','업체','거래처','납품업체','공급업체']);
const known=new Set([...itemFields,...vendorFields,'브랜드','원산지','규격','LOT']);
const masterPages=['품목관리','거래처관리','브랜드관리'];
const historyPages=['입고입력','출고입력','이동입력','매입관리','매출관리','발주관리','주문관리','생산계획','생산실적','거래명세서','검수관리','재고조정'];
function matchValues(values,q){
  const seen=new Set(),out=[],needle=normal(q);
  for(const v of values){const s=String(v??'').trim(),key=normal(s);if(!key||seen.has(key)||!key.includes(needle))continue;seen.add(key);out.push(s)}
  return out.sort((a,b)=>a.localeCompare(b,'ko',{numeric:true,sensitivity:'base'}));
}
function candidates(field,q){
  const keys=vendorFields.has(field)?['업체명','업체','거래처','납품업체','공급업체']:itemFields.has(field)&&field!=='품목코드'?['품목명','완제품','원료품목','생산품목']:[field];
  const primary=vendorFields.has(field)?['거래처관리']:itemFields.has(field)?['품목관리']:field==='브랜드'?['브랜드관리','품목관리']:field==='원산지'?['품목관리','브랜드관리']:masterPages;
  const values=[];
  for(const p of new Set([...primary,...historyPages]))for(const r of rows(p))for(const k of keys)values.push(r[k]);
  return matchValues(values,q);
}
function fieldOf(el){
  if(!(el instanceof HTMLInputElement)||el.disabled||el.readOnly||!['text','search'].includes(el.type))return '';
  if(el.closest('#editorform')&&known.has(el.name))return el.name;
  if(el.matches('#filterpanel input[data-val]')){const f=el.closest('.condition')?.querySelector('select')?.value;return known.has(f)?f:''}
  return '';
}
let active=null,list=null,items=[],index=-1,serial=0,composing=false,choosing=false;
const touch=()=>matchMedia('(pointer:coarse)').matches;
function hide(){
  if(active){active.setAttribute('aria-expanded','false');active.removeAttribute('aria-activedescendant')}
  list?.remove();active=null;list=null;items=[];index=-1;
}
function place(){
  if(!active?.isConnected||!list?.isConnected||!active.getClientRects().length){hide();return;}
  const r=active.getBoundingClientRect(),v=window.visualViewport,top=v?.offsetTop||0,left=v?.offsetLeft||0,bottom=top+(v?.height||innerHeight),right=left+(v?.width||innerWidth);
  const parent=active.closest('dialog,#filterpanel');
  const clip=parent?.getBoundingClientRect(),minY=Math.max(top+5,clip?.top||top),maxY=Math.min(bottom-5,clip?.bottom||bottom);
  if(r.bottom<=minY||r.top>=maxY){hide();return}
  const below=Math.max(0,maxY-r.bottom-4),above=Math.max(0,r.top-minY-4),up=below<120&&above>below;
  const height=Math.min(260,up?above:below);
  if(height<36){hide();return}
  list.style.width=Math.max(80,Math.min(r.width,right-left-10))+'px';
  list.style.left=Math.max(left+5,Math.min(r.left,right-5-list.offsetWidth))+'px';
  list.style.maxHeight=height+'px';
  list.style.top=(up?r.top-4-Math.min(list.scrollHeight,height):r.bottom+4)+'px';
}
function highlight(i){
  if(!items.length){index=-1;return}
  index=Math.max(0,Math.min(i,items.length-1));
  for(const [j,b] of Array.from(list.querySelectorAll('[role=option]')).entries())b.setAttribute('aria-selected',String(j===index));
  const b=list.children[index];active.setAttribute('aria-activedescendant',b.id);
  if(b.offsetTop<list.scrollTop)list.scrollTop=b.offsetTop;
  else if(b.offsetTop+b.offsetHeight>list.scrollTop+list.clientHeight)list.scrollTop=b.offsetTop+b.offsetHeight-list.clientHeight;
}
function nextField(el){
  const form=el.closest('form')||el.closest('#filterpanel');if(!form)return;
  const fields=[...form.querySelectorAll('input:not([type=hidden]),select,textarea')].filter(x=>!x.disabled&&!x.readOnly&&x.getClientRects().length);
  const next=fields[fields.indexOf(el)+1];if(next)next.focus();else el.blur();
}
function choose(i,keyboard){
  if(!active||i<0||i>=items.length)return;
  const el=active,value=items[i];choosing=true;hide();el.value=value;
  el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));choosing=false;
  if(keyboard)nextField(el);else if(touch())el.blur();else el.focus();
}
function show(el,allowEmpty=false){
  const field=fieldOf(el);if(!field||(!allowEmpty&&!normal(el.value))){hide();return}
  const values=candidates(field,el.value);hide();active=el;items=values;
  el.setAttribute('autocomplete','off');el.setAttribute('role','combobox');el.setAttribute('aria-autocomplete','list');
  el.setAttribute('aria-expanded','true');el.setAttribute('aria-haspopup','listbox');
  list=document.createElement('div');list.className='erp-auto-list';list.id='erp-auto-list-'+(++serial);list.setAttribute('role','listbox');el.setAttribute('aria-controls',list.id);
  const frag=document.createDocumentFragment();
  for(const [i,value] of items.entries()){const b=document.createElement('button');b.type='button';b.className='erp-auto-option';b.id=list.id+'-'+i;b.setAttribute('role','option');b.setAttribute('aria-selected','false');b.tabIndex=-1;b.dataset.autoIndex=String(i);b.textContent=value;frag.append(b)}
  if(!items.length){const empty=document.createElement('div');empty.className='erp-auto-empty';empty.textContent='검색 결과 없음';frag.append(empty)}
  list.append(frag);(el.closest('dialog')||document.body).append(list);
  list.addEventListener('mousedown',e=>{if(e.target.closest('[data-auto-index]'))e.preventDefault()});
  list.addEventListener('click',e=>{const b=e.target.closest('[data-auto-index]');if(b){e.preventDefault();e.stopPropagation();choose(Number(b.dataset.autoIndex),false)}});
  place();
}
document.addEventListener('focusin',e=>{if(active&&active!==e.target&&!list?.contains(e.target))hide();if(fieldOf(e.target))e.target.setAttribute('autocomplete','off')});
document.addEventListener('input',e=>{if(choosing||composing||e.isComposing)return;if(fieldOf(e.target))show(e.target)});
document.addEventListener('compositionstart',e=>{if(fieldOf(e.target))composing=true});
document.addEventListener('compositionend',e=>{composing=false;if(fieldOf(e.target))show(e.target)});
document.addEventListener('keydown',e=>{
  const el=e.target;if(!fieldOf(el)||composing||e.isComposing||e.keyCode===229)return;
  if(e.key==='ArrowDown'||e.key==='ArrowUp'){
    if(active!==el)show(el,true);
    if(active===el&&items.length){e.preventDefault();e.stopImmediatePropagation();highlight(index===-1?(e.key==='ArrowDown'?0:items.length-1):index+(e.key==='ArrowDown'?1:-1))}
  }else if(e.key==='Escape'&&active===el){e.preventDefault();e.stopImmediatePropagation();hide()}
  else if(e.key==='Enter'){
    e.preventDefault();e.stopImmediatePropagation();
    if(active===el&&index>=0)choose(index,true);else{hide();nextField(el)}
  }else if(e.key==='Tab')hide();
},true);
document.addEventListener('pointerdown',e=>{if(active&&e.target!==active&&!list?.contains(e.target))hide()},true);
document.addEventListener('focusout',e=>{if(e.target===active&&e.relatedTarget&&!list?.contains(e.relatedTarget))hide()});
document.addEventListener('scroll',e=>{if(active&&e.target!==list)place()},true);
window.addEventListener('resize',place);window.visualViewport?.addEventListener('resize',place);window.visualViewport?.addEventListener('scroll',place);
document.addEventListener('close',hide,true);
new MutationObserver(()=>{if(active&&(!active.isConnected||active.closest('dialog:not([open]),#filterpanel[hidden]')))hide()}).observe(document.body,{subtree:true,childList:true,attributes:true,attributeFilter:['open','hidden']});
})();