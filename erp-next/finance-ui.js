/* Finance display and editor adapter. It never mutates the original quantity ledger or CSS. */
(function(root){
"use strict";
root.createERPFinanceUI=function(api){
 const F=root.ERPFinance;
 const docs={'발주관리':'buy_docs','매입관리':'buy_docs','주문관리':'sale_docs','매출관리':'sale_docs','거래명세서':'sale_docs','매입정산':'buy_balance','매출정산':'sale_balance'};
 const moneyCols=['매입단가','매입금액','매출단가','매출금액','재고단가','재고금액','매입원가','매출총이익'];
 const stockPages=['재고현황','냉동고','냉장고','재고보고서'];
 const txPages=['입고입력','출고입력','입출고내역','이력추적'];
 const types={'입고입력':['미분류','매입','자체생산','기타'],'출고입력':['미분류','판매','생산 투입','폐기','기타']};
 const labels={buy_read:'매입단가 조회',buy_write:'매입단가 입력·수정',sale_read:'매출단가 조회',sale_write:'매출단가 입력·수정',inventory_read:'재고금액 표시',profit_read:'원가·이익 표시',ledger_read:'매입·매출내역 조회',balance_read:'정산내역 조회'};
 const can=k=>api.data().__financeRights?.[k]===true;
 const group=g=>api.data().__finance?.[g]||{};
 function put(g,k,v){const d=api.data();d.__finance={...(d.__finance||{}),[g]:{...group(g),[k]:v}}}
 const docPage=p=>p==='매입보고서'?'매입관리':p==='매출보고서'?'매출관리':p==='미지급금'?'매입정산':p==='미수금'?'매출정산':p;
 const financePage=p=>Object.hasOwn(docs,docPage(p));
 function docRead(p){const g=docs[docPage(p)];if(!g)return true;return can(g.startsWith('buy')?'buy_read':'sale_read')&&can(g.endsWith('docs')?'ledger_read':'balance_read')}
 function docWrite(p){const g=docs[p];return !!g&&docRead(p)&&can(g.startsWith('buy')?'buy_write':'sale_write')}
 function fieldAllowed(c,p){
  if(c==='매입단가'||c==='매입금액')return can('buy_read');
  if(c==='매출단가'||c==='매출금액')return can('sale_read');
  if(c==='재고단가'||c==='재고금액')return can('buy_read')&&can('inventory_read');
  if(c==='매입원가')return can('buy_read')&&can('profit_read');
  if(c==='매출총이익')return can('buy_read')&&can('sale_read')&&can('profit_read');
  return docRead(p);
 }
 function configure(cfg){
  const add=(p,fields)=>{if(!cfg[p])return;const a=cfg[p].slice();const i=a.indexOf('비고');a.splice(i<0?a.length:i,0,...fields);cfg[p]=a};
  add('입고입력',['거래유형','매입단가','매입금액']);
  add('출고입력',['거래유형','판매처','매출단가','매출금액','매입원가','매출총이익']);
  for(const p of ['입출고내역','이력추적'])add(p,['거래유형','판매처','매입단가','매입금액','매출단가','매출금액','매입원가','매출총이익']);
  for(const p of stockPages)add(p,['재고단가','재고금액']);
  // All price labels and units are independent of the existing stock identity columns.
  for(const p of ['발주관리','매입관리','주문관리','매출관리','거래명세서']){const a=cfg[p].slice();a.splice(a.indexOf('수량')+1,0,'단위');cfg[p]=a}
 }
 const price=(r,buy)=>group(buy?'buy_prices':'sale_prices')[String(r._seq)]??null;
 function transactionType(r,p){
  if(r['거래유형'])return r['거래유형'];
  if(r['구분']==='생산 투입')return '생산 투입';
  if(p==='입고입력'&&r['분류']==='완제품'&&r['하위분류']==='자체생산')return '자체생산';
  return '미분류';
 }
 let key='',cache;
 function cost(){
  const d=api.data(),k=JSON.stringify([d['입고입력'],d['이동입력'],d['출고입력'],group('buy_prices'),group('sale_prices')]);
  if(k!==key||!cache){
   key=k;
   const events=F.events(d).map(x=>({...x,row:{...x.row,'매입단가':x.section==='입고입력'?price(x.row,true):null,'매출단가':x.section==='출고입력'?price(x.row,false):null,'거래유형':transactionType(x.row,x.section)}}));
   cache=F.replay(events,{key:api.stockKey,qty:api.qty,state:api.state,place:api.place});
  }
  return cache;
 }
 function getValue(r,c,p){
  if(!fieldAllowed(c,p))return null;
  if(c==='거래유형'&&txPages.includes(p))return transactionType(r,p);
  if(!moneyCols.includes(c))return undefined;
  const inbound=p==='입고입력'||r['구분']==='입고',outbound=p==='출고입력'||['출고','생산 투입'].includes(r['구분']);
  if(c==='매입단가')return inbound?price(r,true):null;
  if(c==='매입금액')return inbound?F.multiply(api.qty(r),price(r,true)):null;
  if(c==='매출단가')return outbound&&transactionType(r,p)==='판매'?price(r,false):null;
  if(c==='매출금액')return outbound&&transactionType(r,p)==='판매'?F.multiply(api.qty(r),price(r,false)):null;
  if(c==='매입원가'||c==='매출총이익'){const x=outbound?cost().result.get(r._seq):null;return c==='매입원가'?x?.amount??null:x?.profit??null}
  const x=cost().inventory.get(api.stockKey(r,r['보관상태'],r['창고']));
  return c==='재고단가'?x?.average??null:x?.amount??null;
 }
 function moneyText(c,v){if(!moneyCols.includes(c)&&!['단가','금액','정산금액','잔액'].includes(c))return null;return v===null||v===undefined||v===''||v==='—'?'미확정':Number.isFinite(Number(v))?F.won(Number(v)):String(v)}
 function docRows(p){if(!docs[p]||!docRead(p))return [];const a=group(docs[p])[p];return Array.isArray(a)?a:[]}
 function linked(p){
  if(!docRead(p)||!['매입관리','매출관리','거래명세서'].includes(p))return [];
  const buy=p==='매입관리',section=buy?'입고입력':'출고입력';
  return (api.data()[section]||[]).filter(r=>transactionType(r,section)===(buy?'매입':'판매')).map(r=>{
   const u=price(r,buy);return {'날짜':r['날짜'],'전표번호':(buy?'IN-':'OUT-')+r._seq,'업체명':buy?r['업체명']:r['판매처'],'품목명':r['품목명'],'수량':api.qty(r),'단위':api.unit(r),'단가':u,'금액':F.multiply(api.qty(r),u),'상태':u===null?'단가 미확정':'입출고 연동','비고':'입출고 원본에서 수정',_linked:true,_source:section,_seq:r._seq}
  });
 }
 function source(p){
  const base=docPage(p);
  if(!docRead(p))return [];
  if(p==='미지급금'||p==='미수금')return docRows(base).filter(r=>Number(r['잔액'])>0);
  return [...docRows(base),...linked(base)];
 }
 function editorFields(p,cols){return cols.filter(c=>fieldAllowed(c,p)&&(!moneyCols.includes(c)||c==='매입단가'||c==='매출단가')&&!(docs[p]&&c==='금액'&&!p.endsWith('정산'))&&!(p.endsWith('정산')&&c==='잔액'))}
 function editorValue(p,r,c,index){
  if(c==='거래유형'&&types[p])return index<0?'미분류':transactionType(r,p);
  if(c==='매입단가'&&p==='입고입력')return price(r,true)??'';
  if(c==='매출단가'&&p==='출고입력')return price(r,false)??'';
  return undefined;
 }
 function editorChoices(p,c){if(c==='거래유형'&&types[p])return types[p];if(docs[p]&&c==='단위')return api.units;return undefined}
 function bindEditor(p,r,index){
  const box=document.getElementById('fields'),type=box.querySelector('[name="거래유형"]'),buyer=box.querySelector('[name="판매처"]'),qty=box.querySelector('[name="수량"]');
  const c=p==='입고입력'?'매입단가':p==='출고입력'?'매출단가':docs[p]&&!p.endsWith('정산')?'단가':null;
  const input=c?box.querySelector('[name="'+c+'"]'):null;
  if(input){input.inputMode='numeric';input.placeholder='미확정';input.disabled=p==='입고입력'&&!can('buy_write')||p==='출고입력'&&!can('sale_write')}
  const result=input||p.endsWith('정산')&&docs[p]?document.createElement('div'):null;
  if(result){result.className='field';const label=p==='입고입력'?'매입금액 (원)':p==='출고입력'?'매출금액 (원)':p.endsWith('정산')?'잔액 (원)':'금액 (원)';result.innerHTML='<label>'+label+'</label><output style="display:block;padding:8px 0;font-variant-numeric:tabular-nums;font-weight:600"></output>';box.append(result)}
  const update=()=>{
   const sale=p!=='출고입력'||type?.value==='판매';
   if(buyer){buyer.required=sale;buyer.closest('.field').hidden=!sale;buyer.disabled=!sale}
   if(input&&p==='출고입력')input.disabled=!sale||!can('sale_write');
   if(input&&p==='입고입력'){input.disabled=!can('buy_write');const l=box.querySelector('label[for="'+input.id+'"]');if(l)l.textContent=type?.value==='자체생산'?'입고원가 (원/단위)':'매입단가 (원/단위)'}
   if(result){result.hidden=!sale;let a=input?F.multiply(qty?.value,input.value):null;if(p.endsWith('정산')){const total=F.parsePrice(box.querySelector('[name="금액"]')?.value),paid=F.parsePrice(box.querySelector('[name="정산금액"]')?.value);a=Number.isFinite(total)&&Number.isFinite(paid)&&paid<=total?total-paid:null}result.querySelector('output').textContent=a===null?'미확정':F.won(a)+'원'}
  };
  box.addEventListener('input',update,{once:false});type?.addEventListener('change',update);update();
  // Remove listeners when the popup is replaced; the next editor binds to its own fields.
  document.getElementById('editor').addEventListener('close',()=>box.removeEventListener('input',update),{once:true});
 }
 function validate(p,r){
  let value,field;
  if(types[p]){
   field=p==='입고입력'?'매입단가':'매출단가';
   if(Object.hasOwn(r,field)){value=F.parsePrice(r[field]);if(Number.isNaN(value))return {error:'단가는 0 이상 10억 원 이하의 정수로 입력하세요.'};delete r[field]}
   if(p==='출고입력'&&transactionType(r,p)==='판매'&&!String(r['판매처']||'').trim())return {error:'판매처를 입력하세요.'};
   if(p==='출고입력'&&transactionType(r,p)!=='판매')delete r['판매처'];
   if(p==='출고입력'&&transactionType(r,p)==='판매'&&value!==undefined&&!can('sale_write')||p==='입고입력'&&value!==undefined&&!can('buy_write'))return {error:'단가 수정 권한이 없습니다.'};
   return {value};
  }
  if(docs[p]){
   if(!docWrite(p))return {error:'금액 수정 권한이 없습니다.'};
   if(p.endsWith('정산')){const total=F.parsePrice(r['금액']),paid=F.parsePrice(r['정산금액']);if(!Number.isFinite(total)||!Number.isFinite(paid)||paid>total)return {error:'정산금액은 전체 금액 이하로 입력하세요.'};r['금액']=total;r['정산금액']=paid;r['잔액']=total-paid;r['상태']=r['잔액']?'미정산':'완료'}
   else{const n=F.parsePrice(r['단가']);if(Number.isNaN(n)||F.quantity(r['수량'])===null)return {error:'수량과 단가를 확인하세요.'};r['단가']=n;r['금액']=F.multiply(r['수량'],n);if(n!==null&&r['금액']===null)return {error:'금액 계산 범위를 초과했습니다.'}}
  }
  return {};
 }
 function savePrice(p,r,v){if(!types[p])return;const buy=p==='입고입력',g=buy?'buy_prices':'sale_prices';if(!can(buy?'buy_write':'sale_write'))return;if(v!==undefined)put(g,String(r._seq),v);if(!buy&&transactionType(r,p)!=='판매'&&Object.hasOwn(group(g),String(r._seq)))put(g,String(r._seq),null)}
 function saveDoc(p,r,i){const a=docRows(p).slice();if(i<0)a.push(r);else a[i]=r;put(docs[p],p,a)}
 function total(rr){if(!can('buy_read')||!can('inventory_read'))return '';let known=0,unknown=0;const calculated=cost();for(const r of rr){const v=calculated.inventory.get(api.stockKey(r,r['보관상태'],r['창고']));if(!v||v.amount===null){unknown++;known+=v?.knownAmount??0}else known+=v.amount}if(!Number.isSafeInteger(known))return '재고금액 계산 범위 초과';return (unknown?'확정 재고금액 ':'재고금액 ')+F.won(known)+'원'+(unknown?' · 미확정 '+unknown+'건':'')+(calculated.issues.length?' · 재고 이력 검토 필요':'')}
 let staff=null,busy=false,error='';
 function permissions(){
  if(!api.actor()?.admin)return '<section class="panel prefs-panel"><p>관리자만 권한을 설정할 수 있습니다.</p></section>';
  if(!staff&&!busy&&!error){busy=true;api.manage('list',{}).then(a=>{staff=a;busy=false;if(api.page()==='권한관리')api.render()}).catch(()=>{busy=false;error='권한 조회 실패';if(api.page()==='권한관리')api.render()})}
  const html=error?'<p>'+api.esc(error)+'</p><button id="financeReload">다시 조회</button>':busy?'<p>불러오는 중…</p>':(staff||[]).map(s=>'<div class="prefs-row" style="margin-top:12px"><strong>'+api.esc(s.name||'이름 미등록')+(s.admin?' · 관리자':'')+'</strong></div><div class="prefs-options">'+Object.entries(labels).map(([k,l])=>'<label><input type="checkbox" data-fin-user="'+api.esc(s.id)+'" data-fin-key="'+k+'" '+(s.rights[k]?'checked ':'')+(s.admin?'disabled':'')+'>'+api.esc(l)+'</label>').join('')+'</div>'+(s.admin?'':'<div class="prefs-row"><button type="button" data-fin-save="'+api.esc(s.id)+'">권한 저장</button></div>')).join('');
  return '<section class="panel prefs-panel"><p class="prefs-muted">기본값: 모든 권한 허용. 원시 매입·매출단가 조회는 서버에서 제한합니다. 재고금액 및 이익 표시는 조회가 허용된 원시 단가로 계산할 수 있습니다.</p>'+html+'</section>'
 }
 function handleButton(b){
  if(b.id==='financeReload'){staff=null;error='';api.render();return true}
  if(!b.dataset.finSave)return false;
  const id=b.dataset.finSave,r={};for(const el of document.querySelectorAll('[data-fin-user]'))if(el.dataset.finUser===id)r[el.dataset.finKey]=el.checked;
  b.disabled=true;api.manage('set',{id,rights:r}).then(()=>{staff=null;api.toast('권한을 저장했습니다.');api.render()}).catch(()=>{api.toast('권한 저장 실패');b.disabled=false});return true;
 }
 return {moneyCols,stockPages,txPages,docs,can,configure,fieldAllowed,financePage,docRead,docWrite,docRows,source,getValue,moneyText,editorFields,editorValue,editorChoices,bindEditor,validate,savePrice,saveDoc,total,transactionType,permissions,handleButton};
};
})(globalThis);