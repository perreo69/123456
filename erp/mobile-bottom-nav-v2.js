/* Mobile navigation, account preferences only. */
(()=>{
'use strict';
if(document.getElementById('erpBottomNav')||!document.getElementById('sidebar')||typeof quickOptions==='undefined')return;
const defaults=['stock','input','history'];
const fixed=[{key:'home',label:'홈',icon:'home',action:'page',target:'대시보드',group:'기본'},{key:'stock',label:'재고',icon:'box',action:'page',target:'재고현황',group:'기본'},{key:'input',label:'입력',icon:'plus',action:'input',target:'',group:'기본'},{key:'history',label:'내역',icon:'list',action:'page',target:'입출고내역',group:'기본'}];
const menu={key:'menu',label:'전체메뉴',icon:'menu'};
const catalog=()=>[...fixed,...quickOptions.filter(([label,target,icon,action])=>!(action==='page'&&fixed.some(x=>x.target===target))).map(([label,target,icon,action,group])=>({key:'quick:'+label,label,target,icon,action,group:group||'기타'}))];
const find=k=>k==='menu'?menu:catalog().find(x=>x.key===k);
const clean=v=>{const allowed=k=>k!=='home'&&k!=='menu'&&!!find(k);const a=Array.isArray(v)?[...new Set(v.filter(allowed))].slice(0,3):[];for(const k of defaults)if(a.length<3&&!a.includes(k))a.push(k);return a};
const current=()=>clean(preferences().mobileBottomNav);
const css=document.createElement('style');css.textContent=`
#erpBottomNav,#erpBottomEditEntry{display:none}
#erpBottomEditor,#erpBottomInput{width:min(420px,calc(100vw - 20px));max-height:85dvh;margin:auto;border-radius:14px}
#erpBottomEditor .dialoghead,#erpBottomInput .dialoghead{font-size:18px}
#erpBottomEditor .dialogbody{display:grid;gap:12px}
#erpBottomEditor .bottom-label{font-size:12px;color:var(--muted);font-weight:600}
#erpBottomEditor .bottom-row{display:flex;align-items:center;gap:7px;min-width:0;border-bottom:1px solid var(--line);padding:7px 0}
#erpBottomEditor .bottom-row>span{flex:1;min-width:0;overflow-wrap:anywhere}
#erpBottomEditor .bottom-row button{min-width:36px;min-height:36px;padding:4px}
#erpBottomEditor .bottom-catalog{display:grid;gap:3px}
#erpBottomEditor .bottom-catalog h4{margin:9px 0 3px;font-size:12px;color:var(--muted)}
#erpBottomEditor .bottom-choice,#erpBottomInput .dialogbody button{width:100%;text-align:left;min-height:44px;display:flex;align-items:center;gap:8px;white-space:normal}
#erpBottomEditor .bottom-choice{border:0;border-radius:6px;background:white;box-shadow:none;padding:9px;color:var(--ink)}
#erpBottomEditor .bottom-choice>span{flex:1;text-align:left;min-width:0;overflow-wrap:anywhere}
#erpBottomEditor .bottom-choice[aria-pressed=true]{background:#e5e5ea}
#erpBottomEditor .bottom-search{width:100%;min-height:42px;font-size:16px}
#erpBottomEditor .bottom-preview{display:flex;justify-content:space-evenly;gap:3px;background:#f2f4f8;padding:9px 3px;border-radius:8px}
#erpBottomEditor .bottom-preview>div{flex:1;min-width:0;text-align:center;font-size:10px;overflow:hidden}
#erpBottomEditor .bottom-preview span{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#erpBottomEditor .bottom-drag{touch-action:none;cursor:grab}
#erpBottomEditor .bottom-row.dragging{background:#e5e5ea}
#erpBottomEditor .bottom-context .bottom-choice{border-bottom:1px solid var(--line);border-radius:0}
#erpBottomEditor .dialogfoot{display:flex;justify-content:flex-end;gap:8px;padding:12px 15px;border-top:1px solid var(--line);flex-wrap:wrap}
#erpBottomEditor .dialogfoot button{min-height:40px}
#erpBottomEditor .dialogfoot[hidden]{display:none!important}
#erpBottomInput .dialogbody{display:grid;gap:8px}
@media(max-width:760px){
main#main{padding-bottom:calc(82px + env(safe-area-inset-bottom,0px))!important}
#erpBottomNav{position:fixed;display:flex;align-items:stretch;justify-content:space-evenly;bottom:0;left:0;right:0;z-index:23;min-height:62px;padding:4px 3px calc(4px + env(safe-area-inset-bottom,0px));background:#fff;border-top:1px solid var(--line,#ddd);box-shadow:0 -2px 12px #20273309}
#erpBottomNav button{display:flex;flex:1 1 0;min-width:0;min-height:52px;align-items:center;justify-content:center;flex-direction:column;gap:3px;border:0;background:transparent;box-shadow:none;padding:3px 1px;color:var(--muted,#697483);font-size:11px;line-height:1.2;font-weight:500;border-radius:8px;touch-action:manipulation;user-select:none;-webkit-user-select:none;-webkit-touch-callout:none}
#erpBottomNav button .ico{width:23px;height:23px;stroke-width:1.7;flex:none;margin:0;color:inherit}
#erpBottomNav button span{max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#erpBottomNav button[aria-current=page]{color:var(--blue,#1260db);font-weight:700}
body:has(dialog[open]) #erpBottomNav,body:has(#sidebar.shown) #erpBottomNav,body:has(#filterpanel:not([hidden])) #erpBottomNav,body.erp-bottom-keyboard #erpBottomNav{display:none!important}
#erpBottomEditEntry{display:flex;width:100%;align-items:center;gap:8px;padding:10px 12px;margin:4px 0 12px;background:transparent;color:inherit;border:1px solid currentColor;border-radius:7px;font-size:13px;text-align:left}
#erpBottomEditEntry .ico{width:18px;height:18px}.toast{bottom:calc(76px + env(safe-area-inset-bottom,0px))}
#erpBottomEditor[open]{display:flex;flex-direction:column;overflow:hidden;max-height:min(85dvh,calc(100dvh - 20px))}
#erpBottomEditor>.dialoghead,#erpBottomEditor>.dialogfoot{flex:none;background:#fff}
#erpBottomEditor>.dialogbody{min-height:0;overflow:auto;overscroll-behavior:contain}
}`;document.head.append(css);
const bar=document.createElement('nav');bar.id='erpBottomNav';bar.setAttribute('aria-label','하단 메뉴');document.body.append(bar);
const input=document.createElement('dialog');input.id='erpBottomInput';input.setAttribute('aria-label','입력 선택');input.innerHTML='<div class="dialoghead"><strong>입력</strong><button type="button" class="iconbtn" aria-label="닫기">'+I('x')+'</button></div><div class="dialogbody">'+[['입고입력','box'],['출고입력','truck'],['이동입력','move']].map(([p,ic])=>'<button type="button" data-bottom-input="'+p+'">'+I(ic)+esc(p)+'</button>').join('')+'</div>';document.body.append(input);
input.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;e.stopPropagation();input.close();if(b.dataset.bottomInput)openEditor(b.dataset.bottomInput)});
const editor=document.createElement('dialog');editor.id='erpBottomEditor';editor.setAttribute('aria-labelledby','bottom-editor-title');editor.innerHTML='<div class="dialoghead"><strong id="bottom-editor-title"></strong><button type="button" class="iconbtn" data-bottom-close aria-label="닫기">'+I('x')+'</button></div><div class="dialogbody"></div><div class="dialogfoot"></div>';document.body.append(editor);
const body=editor.querySelector('.dialogbody'),foot=editor.querySelector('.dialogfoot'),title=editor.querySelector('strong');
let draft=[],mode='',slot=0,chosen='',signature='',drag=null;
const action=(a,t,ic)=>'<button type="button" class="bottom-choice" data-bottom-action="'+a+'">'+I(ic)+'<span>'+esc(t)+'</span></button>';
const preview=keys=>'<div class="bottom-preview">'+['home',...keys,'menu'].map(k=>{const x=find(k);return '<div>'+I(x.icon)+'<span>'+esc(x.label)+'</span></div>'}).join('')+'</div>';
function execute(x){if(!x)return;if(x.action==='page')go(x.target);else if(x.action==='new')openEditor(x.target);else if(x.action==='thaw')openThaw(x.target);else if(x.action==='input')input.showModal()}
function drawBar(){if(device()!=='mobile')return;const keys=current(),sig=JSON.stringify([keys,page]);if(sig!==signature){signature=sig;bar.innerHTML=['home',...keys,'menu'].map(k=>{const x=find(k);return '<button type="button" data-bottom-key="'+esc(k)+'" aria-label="'+esc(x.label)+'"'+(x.action==='page'&&x.target===page?' aria-current="page"':'')+'>'+I(x.icon)+'<span>'+esc(x.label)+'</span></button>'}).join('')}
 const sidebar=document.getElementById('sidebar');if(!document.getElementById('erpBottomEditEntry')){const b=document.createElement('button');b.type='button';b.id='erpBottomEditEntry';b.innerHTML=I('editSliders')+'하단 메뉴 편집';b.addEventListener('click',e=>{e.stopPropagation();closeNav();openMode('manage')});sidebar.prepend(b)}
}
function footer(save='저장'){foot.innerHTML='<button type="button" data-bottom-close>취소</button><button type="button" class="primary" data-bottom-save>'+save+'</button>'}
function openMode(m,k){draft=current();slot=Math.max(0,draft.indexOf(k));chosen=draft[slot];drawMode(m);if(!editor.open)editor.showModal()}
function drawMode(m){mode=m;body.scrollTop=0;foot.innerHTML='';title.textContent=({context:find(draft[slot]).label+' 메뉴',manage:'하단 메뉴 편집',change:'메뉴 변경',position:'위치 변경',reset:'기본값 복원'})[m];
 if(m==='context'){body.innerHTML='<div class="bottom-context">'+action('change','메뉴 변경','editSliders')+action('position','위치 변경','move')+action('reset','기본값 복원','reset')+'</div>';foot.hidden=true;return}
 foot.hidden=false;
 if(m==='manage'){body.innerHTML='<div class="bottom-label">홈과 전체메뉴는 고정됩니다.</div>'+preview(draft)+'<div>'+draft.map((k,i)=>'<div class="bottom-row">'+I(find(k).icon)+'<span>'+esc(find(k).label)+'</span><button type="button" data-bottom-slot="'+i+'">변경</button></div>').join('')+'</div>'+action('position','위치 변경','move')+action('reset','기본값 복원','reset');foot.innerHTML='<button type="button" data-bottom-close>닫기</button>';return}
 if(m==='change'){body.innerHTML='<div class="bottom-label">현재 메뉴: '+esc(find(draft[slot]).label)+'</div><input class="bottom-search" type="search" placeholder="메뉴 또는 분류 검색" aria-label="메뉴 검색"><div class="bottom-catalog"></div>';drawCatalog();footer();return}
 if(m==='position'){body.innerHTML='<div class="bottom-label">화살표 또는 손잡이로 순서를 변경하세요.</div><div id="bottom-position-preview">'+preview(draft)+'</div><div id="bottom-position-rows"></div>';drawPositions();footer();return}
 if(m==='reset'){body.innerHTML='<p>하단 메뉴를 처음 설정으로 복원하시겠습니까?</p>'+preview(defaults);footer('복원')}
}
function drawCatalog(){const q=body.querySelector('input').value.normalize('NFKC').toLowerCase().replace(/\s+/g,'');const opts=catalog().filter(x=>x.key!=='home'&&(!draft.includes(x.key)||x.key===draft[slot])&&(!q||(x.label+' '+x.group+' '+x.target).normalize('NFKC').toLowerCase().replace(/\s+/g,'').includes(q)));body.querySelector('.bottom-catalog').innerHTML=opts.length?[...new Set(opts.map(x=>x.group))].map(g=>'<h4>'+esc(g)+'</h4>'+opts.filter(x=>x.group===g).map(x=>'<button type="button" class="bottom-choice" data-bottom-choice="'+esc(x.key)+'" aria-pressed="'+(x.key===chosen)+'">'+I(x.icon)+'<span>'+esc(x.label)+'</span>'+(x.key===draft[slot]?'<small>현재</small>':'')+'</button>').join('')).join(''):'<small>검색 결과 없음</small>'}
function drawPositions(){body.querySelector('#bottom-position-preview').innerHTML=preview(draft);body.querySelector('#bottom-position-rows').innerHTML=draft.map((k,i)=>'<div class="bottom-row" data-position="'+i+'">'+I(find(k).icon)+'<span>'+esc(find(k).label)+'</span><button type="button" data-bottom-move="'+i+'" data-dir="-1" aria-label="위로" '+(i===0?'disabled':'')+'>↑</button><button type="button" data-bottom-move="'+i+'" data-dir="1" aria-label="아래로" '+(i===2?'disabled':'')+'>↓</button><button type="button" class="bottom-drag" data-bottom-drag="'+i+'" aria-label="순서 끌기">'+I('menu')+'</button></div>').join('')}
function save(){if(device()!=='mobile')return;const value=mode==='reset'?[...defaults]:mode==='change'?draft.map((k,i)=>i===slot?chosen:k):draft;const old=data.__prefs;data.__prefs={...(old||{}),mobile:{...preferences(),mobileBottomNav:['home',...clean(value)]}};if(!persist()){data.__prefs=old;toast('설정 저장 실패');return}editor.close();drawBar();toast('하단 메뉴를 저장했습니다.')}
editor.addEventListener('input',e=>{if(mode==='change'&&e.target.matches('.bottom-search'))drawCatalog()});
editor.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;e.stopPropagation();const d=b.dataset;if(d.bottomClose!==undefined){editor.close();return}if(d.bottomSave!==undefined){save();return}if(d.bottomSlot!==undefined){slot=Number(d.bottomSlot);chosen=draft[slot];drawMode('change');return}if(d.bottomAction){chosen=draft[slot];drawMode(d.bottomAction);return}if(d.bottomChoice!==undefined){chosen=d.bottomChoice;drawCatalog();return}if(d.bottomMove!==undefined){const i=Number(d.bottomMove),j=i+Number(d.dir);if(i>=0&&j>=0&&i<3&&j<3){[draft[i],draft[j]]=[draft[j],draft[i]];drawPositions()}}});
editor.addEventListener('pointerdown',e=>{const b=e.target.closest('[data-bottom-drag]');if(!b||mode!=='position'||!e.isPrimary)return;e.preventDefault();drag={id:e.pointerId,index:Number(b.dataset.bottomDrag)};editor.setPointerCapture(e.pointerId);b.closest('.bottom-row').classList.add('dragging')});
editor.addEventListener('pointermove',e=>{if(!drag||drag.id!==e.pointerId)return;const row=document.elementFromPoint(e.clientX,e.clientY)?.closest('[data-position]');if(!row)return;const j=Number(row.dataset.position),i=drag.index;if(j!==i&&j>=0&&j<3){const [k]=draft.splice(i,1);draft.splice(j,0,k);drag.index=j;drawPositions();body.querySelector('[data-position="'+j+'"]').classList.add('dragging')}});
function endDrag(e){if(drag&&drag.id===e.pointerId){drag=null;body.querySelectorAll('.dragging').forEach(x=>x.classList.remove('dragging'));if(editor.hasPointerCapture(e.pointerId))editor.releasePointerCapture(e.pointerId)}}editor.addEventListener('pointerup',endDrag);editor.addEventListener('pointercancel',endDrag);editor.addEventListener('close',()=>{drag=null});
let press=null,suppress=0;
function cancelPress(){if(press){clearTimeout(press.timer);press=null}}
const editable=k=>k&&k!=='home'&&k!=='menu';
bar.addEventListener('pointerdown',e=>{suppress=0;const k=e.target.closest('button')?.dataset.bottomKey;if(!editable(k)||!e.isPrimary||e.button!==0)return;cancelPress();press={id:e.pointerId,x:e.clientX,y:e.clientY,timer:setTimeout(()=>{press=null;suppress=Date.now()+1000;openMode('context',k)},500)}});
bar.addEventListener('pointermove',e=>{if(press&&press.id===e.pointerId&&Math.hypot(e.clientX-press.x,e.clientY-press.y)>10)cancelPress()});
window.addEventListener('pointerup',cancelPress,true);window.addEventListener('pointercancel',cancelPress,true);bar.addEventListener('pointerleave',cancelPress);
bar.addEventListener('contextmenu',e=>{const k=e.target.closest('button')?.dataset.bottomKey;if(!editable(k))return;e.preventDefault();cancelPress();suppress=Date.now()+1000;if(!editor.open)openMode('context',k)});
bar.addEventListener('keydown',e=>{const k=e.target.closest('button')?.dataset.bottomKey;if(editable(k)&&(e.key==='ContextMenu'||(e.shiftKey&&e.key==='F10'))){e.preventDefault();openMode('context',k)}});
bar.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;e.stopPropagation();if(Date.now()<suppress){e.preventDefault();suppress=0;return}const k=b.dataset.bottomKey;if(k==='menu')document.getElementById('hamb').click();else execute(find(k))});
const observer=new MutationObserver(drawBar);observer.observe(document.getElementById('main'),{childList:true});observer.observe(document.getElementById('sidebar'),{childList:true});
window.addEventListener('resize',()=>{if(device()!=='mobile'){cancelPress();if(editor.open)editor.close();if(input.open)input.close()}drawBar()});
const keyboard=()=>{const v=window.visualViewport;document.body.classList.toggle('erp-bottom-keyboard',!!v&&innerHeight-v.height>130)};window.visualViewport?.addEventListener('resize',keyboard);drawBar();
})();
