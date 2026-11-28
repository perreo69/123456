"use strict";
self.addEventListener("install",e=>e.waitUntil(self.skipWaiting()));
self.addEventListener("activate",e=>e.waitUntil(self.clients.claim()));
self.addEventListener("push",e=>{
 let p={};try{p=e.data?.json()||{}}catch{}
 const kind=["new","remind","read","done","test"].includes(p.kind)?p.kind:"new";
 const body={new:"새 업무가 전달되었습니다.",remind:"미완료 업무를 확인해 주세요.",read:"전달한 업무를 상대방이 확인했습니다.",done:"전달한 업무가 완료되었습니다.",test:"테스트 알림입니다. 정상 수신되었습니다."}[kind];
 e.waitUntil(self.registration.showNotification("미르스타푸드 ERP",{body,icon:"./push-icon.svg",data:{kind}}));
});
self.addEventListener("notificationclick",e=>{
 e.notification.close();const kind=e.notification.data?.kind==="test"?"test":"work";
 const target=new URL("./",self.registration.scope);target.searchParams.set("erp_notice",kind);
 e.waitUntil((async()=>{const list=await self.clients.matchAll({type:"window",includeUncontrolled:true});for(const c of list){const u=new URL(c.url);if(u.origin===target.origin&&(u.pathname===target.pathname||u.pathname===target.pathname+"index.html")){await c.focus();c.postMessage({type:"ERP_PUSH_OPEN",kind});return}}await self.clients.openWindow(target.href)})());
});