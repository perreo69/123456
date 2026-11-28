/* Isolated finance engine. Stock quantity and identity rules are supplied by the existing ERP. */
(function(root){
"use strict";
const MAX_PRICE=1000000000, MAX_MILLI=9007199254740991;
const parsePrice=v=>{if(v===null||v===undefined||String(v).trim()==="")return null;const s=String(v).trim();if(!/^(?:\d+|\d{1,3}(?:,\d{3})+)$/.test(s))return NaN;const n=Number(s.replace(/,/g,""));return Number.isSafeInteger(n)&&n>=0&&n<=MAX_PRICE?n:NaN};
const quantity=v=>{const s=String(v??"").trim().replace(/,/g,"");if(!/^\d+(?:\.\d{1,3})?$/.test(s))return null;const [a,b=""]=s.split(".");const n=BigInt(a)*1000n+BigInt(b.padEnd(3,"0"));return n>0n&&n<=BigInt(MAX_MILLI)?n:null};
const roundWon=m=>{const n=(m+500n)/1000n;return n<=BigInt(Number.MAX_SAFE_INTEGER)?Number(n):null};
const multiply=(qty,price)=>{const q=quantity(qty),p=parsePrice(price);return q===null||p===null||!Number.isFinite(p)?null:roundWon(q*BigInt(p))};
const won=n=>n===null||n===undefined?"미확정":Number(n).toLocaleString("ko-KR");
function replay(events,api){
 const pools=new Map(),result=new Map(),issues=[];
 const get=(r,st,loc)=>api.key(r,st,loc);
 const push=(k,parts)=>{const list=pools.get(k)||[];for(const p of parts)if(p.q>0n)list.push({q:p.q,p:p.p});if(list.length)pools.set(k,list)};
 const take=(k,n)=>{const list=pools.get(k)||[];if(list.reduce((sum,p)=>sum+p.q,0n)<n)return null;let left=n,out=[];while(left){const p=list[0],q=p.q<left?p.q:left;out.push({q,p:p.p});p.q-=q;left-=q;if(!p.q)list.shift()}if(!list.length)pools.delete(k);return out};
 const stats=parts=>{let known=0n,unknown=0n,total=0n;for(const p of parts){if(p.p===null)unknown+=p.q;else{known+=p.q;total+=p.q*BigInt(p.p)}}const all=known+unknown;return {quantity:Number(all)/1000,unknownQuantity:Number(unknown)/1000,knownAmount:roundWon(total),amount:unknown>0n?null:roundWon(total),average:unknown>0n||!all?null:Number((total*100n/all+50n)/100n)}};
 for(const {section,row:r} of events){
  const q=quantity(api.qty(r));if(!q){issues.push({seq:r._seq,reason:"invalid quantity"});continue}
  if(section==="입고입력"){
   const st=r["보관상태"]||api.state(r["창고"]),loc=r["창고"]||api.place(st),price=parsePrice(r["매입단가"]);if(!st||!loc){issues.push({seq:r._seq,reason:"invalid warehouse"});continue}
   push(get(r,st,loc),[{q,p:Number.isFinite(price)?price:null}]);
  }else if(section==="이동입력"){
   const kind=r["구분"],a=r["출발상태"]||(kind==="재냉동"?"해동":api.state(r["출발창고"])),b=r["도착상태"]||(kind==="해동"?"해동":kind==="재냉동"?"냉동":api.state(r["도착창고"])),fl=r["출발창고"]||api.place(a),tl=r["도착창고"]||api.place(b);
   if(!a||!b||!fl||!tl){issues.push({seq:r._seq,reason:"invalid transfer"});continue}
   const parts=take(get(r,a,fl),q);if(!parts){issues.push({seq:r._seq,reason:"insufficient stock"});continue}push(get(r,b,tl),parts);result.set(r._seq,stats(parts));
  }else if(section==="출고입력"){
   const st=r["보관상태"]||api.state(r["창고"]),loc=r["창고"]||api.place(st);
   const parts=st&&loc?take(get(r,st,loc),q):null;if(!parts){issues.push({seq:r._seq,reason:"insufficient stock"});continue}
   const x=stats(parts),sales=r["거래유형"]==="판매"?multiply(api.qty(r),r["매출단가"]):null;
   result.set(r._seq,{...x,sales,profit:sales===null||x.amount===null?null:sales-x.amount});
  }
 }
 const inventory=new Map([...pools].map(([k,parts])=>[k,stats(parts)]));
 return {inventory,result,issues};
}
function events(data){return ["입고입력","이동입력","출고입력"].flatMap((section,i)=>(Array.isArray(data[section])?data[section]:[]).map((row,j)=>({section,row,order:i*100000+j}))).sort((a,b)=>String(a.row["날짜"]||"").localeCompare(String(b.row["날짜"]||""))||((a.row._seq||0)-(b.row._seq||0))||a.order-b.order)}
root.ERPFinance=Object.freeze({parsePrice,quantity,multiply,won,replay,events});
})(globalThis);