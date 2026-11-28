/* Mobile stock presentation only; never writes ERP data. */
(() => {
'use strict';
if(document.getElementById('erp-mobile-stock-style')||typeof mobileStockList!=='function'||typeof mobileSortBar!=='function')return;
const baseList=mobileStockList,baseBar=mobileSortBar;
const fields=[['품목명','품목명'],['원산지','원산지'],['업체명','업체'],['브랜드','브랜드'],['수량','수량(단위별)'],['소비기한','소비기한'],['분류','분류'],['보관상태','보관상태'],['LOT','LOT']];
let field='품목명',direction=1;
const mobileStock=()=>device()==='mobile'&&page==='재고현황';
const str=v=>String(v??'').trim();
const compare=(a,b)=>str(a).localeCompare(str(b),'ko',{numeric:true,sensitivity:'base'});
function compareMissing(a,b,dir=1){a=str(a);b=str(b);if(!a||!b)return a? -1:b?1:0;return compare(a,b)*dir}
function ordered(rr,key=field,dir=direction){
 return rr.slice().sort((a,b)=>{
  let n=0;
  if(key==='수량'){
   n=compare(unitOf(a),unitOf(b));if(n)return n;
   const av=qtyOf(a),bv=qtyOf(b),x=Number(av),y=Number(bv);
   if(av==null||av===''||!Number.isFinite(x))n=bv==null||bv===''||!Number.isFinite(y)?0:1;
   else if(bv==null||bv===''||!Number.isFinite(y))n=-1;else n=(x-y)*dir;
  }else n=compareMissing(a[key],b[key],dir);
  if(n)return n;
  for(const k of ['품목명','원산지','업체명','브랜드','소비기한','LOT','창고','보관상태']){if(k===key)continue;n=compareMissing(a[k],b[k]);if(n)return n}
  return 0;
 });
}
const css=document.createElement('style');css.id='erp-mobile-stock-style';css.textContent=`
@media(max-width:760px){
 #mobileStockList:has(>.erp-stock-compact-item){display:block;gap:0;margin:0 12px 10px;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}
 #mobileStockList>.erp-stock-compact-item{border:0;border-bottom:1px solid var(--line);border-radius:0;overflow:hidden;min-width:0;background:#fff}
 #mobileStockList>.erp-stock-compact-item:last-child{border-bottom:0}
 #mobileStockList>.erp-stock-compact-item>summary{padding:8px 5px;min-width:0}
 #mobileStockList>.erp-stock-compact-item .stock-mobile-top{gap:6px;align-items:center}
 #mobileStockList>.erp-stock-compact-item .stock-mobile-top strong{font-size:15px;font-weight:650;line-height:1.35;min-width:0;overflow-wrap:anywhere}
 #mobileStockList>.erp-stock-compact-item .stock-mobile-state{font-size:12px;flex:none}
 #mobileStockList>.erp-stock-compact-item .stock-mobile-chevron{width:15px;height:15px;flex:none}
 #mobileStockList>.erp-stock-compact-item .erp-stock-meta{font-size:12px;line-height:1.35;color:var(--muted);margin:3px 0;overflow-wrap:anywhere;min-width:0}
 #mobileStockList>.erp-stock-compact-item .stock-mobile-bottom{margin-top:3px;gap:4px 9px;align-items:baseline;flex-wrap:wrap}
 #mobileStockList>.erp-stock-compact-item .stock-mobile-qty{font-size:15px;font-weight:600;letter-spacing:0;line-height:1.4}
 #mobileStockList>.erp-stock-compact-item .stock-mobile-expiry{flex-direction:row;align-items:baseline;gap:4px;max-width:100%;flex-wrap:wrap;justify-content:flex-end}
 #mobileStockList>.erp-stock-compact-item .stock-mobile-expiry span{font-size:11px}
 #mobileStockList>.erp-stock-compact-item .stock-mobile-expiry time{font-size:12px;overflow-wrap:anywhere}
 main[data-font="large"] #mobileStockList>.erp-stock-compact-item .stock-mobile-top strong,main[data-font="large"] #mobileStockList>.erp-stock-compact-item .stock-mobile-qty{font-size:17px}
 main[data-font="small"] #mobileStockList>.erp-stock-compact-item .stock-mobile-top strong,main[data-font="small"] #mobileStockList>.erp-stock-compact-item .stock-mobile-qty{font-size:13px}
 #erpStockSortControls{max-width:64%;min-width:0;gap:4px;align-items:center}
 #erpStockSortControls select{min-height:34px;padding:3px 5px}
 #erpStockSortControls button{min-width:34px;min-height:34px}
}
@media(min-width:761px){#erpStockSortControls{display:none!important}}
`;
document.head.append(css);
mobileStockList=function(rr){
 if(!mobileStock())return baseList(rr);
 const sorted=ordered(rr),html=baseList(sorted);
 const template=document.createElement('template');template.innerHTML=html;
 const details=template.content.querySelectorAll('details.stock-mobile-item');
 details.forEach((el,i)=>{
  const r=sorted[i];if(!r)return;el.classList.add('erp-stock-compact-item');
  const meta=[r['원산지'],r['업체명'],r['브랜드']].map(str).filter(Boolean);
  if(meta.length){const line=document.createElement('div');line.className='erp-stock-meta';line.textContent=meta.join(' · ');const bottom=el.querySelector('.stock-mobile-bottom');if(bottom)bottom.before(line)}
 });
 return template.innerHTML;
};
mobileSortBar=function(){
 if(!mobileStock())return baseBar();
 return '<div class="mobile-list-sort" id="erpStockSortControls"><select id="erpStockSortField" aria-label="재고 정렬 기준">'+fields.map(([k,l])=>'<option value="'+esc(k)+'"'+(field===k?' selected':'')+'>'+esc(l)+'</option>').join('')+'</select><button type="button" id="erpStockSortDirection" aria-label="'+(direction===1?'오름차순':'내림차순')+'">'+(direction===1?'↑':'↓')+'</button></div>';
};
document.addEventListener('change',e=>{if(mobileStock()&&e.target.id==='erpStockSortField'&&fields.some(x=>x[0]===e.target.value)){field=e.target.value;direction=1;const b=document.getElementById('erpStockSortDirection');if(b){b.textContent='↑';b.setAttribute('aria-label','오름차순')}refresh()} });
document.addEventListener('click',e=>{if(!mobileStock())return;const b=e.target.closest('button');if(!b)return;
 if(b.id==='erpStockSortDirection'){direction=-direction;b.textContent=direction===1?'↑':'↓';b.setAttribute('aria-label',direction===1?'오름차순':'내림차순');refresh()}
 else if(b.id==='reset'){field='품목명';direction=1}
},true);
if(mobileStock())render();
})();
