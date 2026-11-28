/* Mobile bottom navigation for the authenticated ChatGPT ERP only. */
(() => {
  'use strict';
  if (document.getElementById('erpBottomNav') || !document.getElementById('sidebar') ||
      typeof preferences !== 'function' || typeof quickOptions === 'undefined') return;
  const defaults = ['home','stock','input','history'];
  const fixed = [
    {key:'home',label:'홈',icon:'home',action:'page',target:'대시보드',group:'기본'},
    {key:'stock',label:'재고',icon:'box',action:'page',target:'재고현황',group:'기본'},
    {key:'input',label:'입력',icon:'plus',action:'input',target:'',group:'기본'},
    {key:'history',label:'내역',icon:'list',action:'page',target:'입출고내역',group:'기본'}
  ];
  const catalog = () => [...fixed,...quickOptions.filter(([label,target,icon,action]) =>
    !(action==='page' && fixed.some(x=>x.target===target))).map(([label,target,icon,action,group]) =>
      ({key:'quick:'+label,label,target,icon,action,group:group||'기타'}))];
  const clean = value => Array.isArray(value) ? [...new Set(value.filter(k=>catalog().some(x=>x.key===k)))].slice(0,4) : [...defaults];
  const current = () => clean(preferences().mobileBottomNav);
  const style = document.createElement('style');
  style.textContent = '#erpBottomNav,#erpBottomEditEntry{display:none}'+
    '#erpBottomEditor,#erpBottomInput{width:min(420px,calc(100vw - 20px));max-height:85dvh;margin:auto;border-radius:14px}'+
    '#erpBottomEditor .dialoghead,#erpBottomInput .dialoghead{font-size:18px}'+
    '#erpBottomEditor .bottom-selected{display:grid;gap:6px;margin:10px 0 16px}'+
    '#erpBottomEditor .bottom-row{display:flex;align-items:center;gap:5px;min-width:0}'+
    '#erpBottomEditor .bottom-row span{flex:1;min-width:0;overflow-wrap:anywhere}'+
    '#erpBottomEditor .bottom-row button{min-width:36px;min-height:36px;padding:5px}'+
    '#erpBottomEditor .bottom-catalog{display:grid;gap:6px;max-height:31dvh;overflow:auto;padding:2px}'+
    '#erpBottomEditor .bottom-catalog button,#erpBottomInput .dialogbody button{width:100%;text-align:left;min-height:42px;display:flex;align-items:center;gap:8px;white-space:normal}'+
    '#erpBottomEditor .bottom-catalog h4{margin:7px 0 0;font-size:12px;color:var(--muted)}'+
    '#erpBottomEditor .bottom-search{width:100%;min-height:42px;font-size:16px;margin:8px 0}'+
    '#erpBottomInput .dialogbody{display:grid;gap:8px}'+
    '@media(max-width:760px){'+
    'main#main{padding-bottom:calc(82px + env(safe-area-inset-bottom,0px))!important}'+
    '#erpBottomNav{position:fixed;display:flex;align-items:stretch;justify-content:space-evenly;bottom:0;left:0;right:0;z-index:23;min-height:62px;padding:4px 3px calc(4px + env(safe-area-inset-bottom,0px));background:#fff;border-top:1px solid var(--line,#ddd);box-shadow:0 -2px 12px #20273309}'+
    '#erpBottomNav button{display:flex;flex:1 1 0;min-width:0;min-height:52px;align-items:center;justify-content:center;flex-direction:column;gap:3px;border:0;background:transparent;box-shadow:none;padding:3px 1px;color:var(--muted,#697483);font-size:11px;line-height:1.2;font-weight:500;border-radius:8px}'+
    '#erpBottomNav button .ico{width:23px;height:23px;stroke-width:1.7;flex:none;margin:0;color:inherit}'+
    '#erpBottomNav button span{max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}'+
    '#erpBottomNav button[aria-current="page"]{color:var(--blue,#1260db);font-weight:700}'+
    'body:has(dialog[open]) #erpBottomNav,body:has(#sidebar.shown) #erpBottomNav,body:has(#filterpanel:not([hidden])) #erpBottomNav,body.erp-bottom-keyboard #erpBottomNav{display:none!important}'+
    '#erpBottomEditEntry{display:flex;width:100%;align-items:center;gap:8px;padding:10px 12px;margin:4px 0 12px;background:transparent;color:inherit;border:1px solid currentColor;border-radius:7px;font-size:13px;text-align:left}'+
    '#erpBottomEditEntry .ico{width:18px;height:18px}'+
    '.toast{bottom:calc(76px + env(safe-area-inset-bottom,0px))}'+
    '}';
  document.head.append(style);
  const bar=document.createElement('nav');bar.id='erpBottomNav';bar.setAttribute('aria-label','하단 메뉴');document.body.append(bar);
  const input=document.createElement('dialog');input.id='erpBottomInput';input.setAttribute('aria-label','입력 선택');
  input.innerHTML='<div class="dialoghead"><strong>입력</strong><button type="button" class="iconbtn" aria-label="닫기">'+I('x')+'</button></div><div class="dialogbody"></div>';
  document.body.append(input);
  const editor=document.createElement('dialog');editor.id='erpBottomEditor';editor.setAttribute('aria-label','하단 메뉴 편집');
  editor.innerHTML='<div class="dialoghead"><strong>하단 메뉴 편집</strong><button type="button" class="iconbtn" aria-label="닫기">'+I('x')+'</button></div><div class="dialogbody"><small>내 계정의 모바일에만 적용됩니다. 최대 4개를 선택하세요. 전체메뉴는 항상 표시됩니다.</small><div class="bottom-selected"></div><strong>항목 추가</strong><input class="bottom-search" type="search" placeholder="메뉴 검색" aria-label="메뉴 검색"><div class="bottom-catalog"></div><div class="dialogactions" style="margin-top:14px"><button type="button" data-bottom-reset>기본값</button><button type="button" class="primary" data-bottom-save>저장</button></div></div>';
  document.body.append(editor);
  let draft=[],signature='';
  const find = k => catalog().find(x=>x.key===k);
  function execute(x){
    if(!x)return;
    if(x.action==='page')go(x.target);
    else if(x.action==='new')openEditor(x.target);
    else if(x.action==='thaw')openThaw(x.target);
    else if(x.action==='input')input.showModal();
  }
  input.querySelector('.dialogbody').innerHTML=[['입고입력','box'],['출고입력','truck'],['이동입력','move']].map(([p,ic])=>'<button type="button" data-bottom-input="'+p+'">'+I(ic)+esc(p)+'</button>').join('');
  input.addEventListener('click',e=>{
    const b=e.target.closest('button');if(!b)return;
    e.stopPropagation();input.close();if(b.dataset.bottomInput)openEditor(b.dataset.bottomInput);
  });
  function drawBar(){
    if(device()!=='mobile')return;
    const keys=current(), sig=JSON.stringify([keys,page]);
    if(sig!==signature){
      signature=sig;
      bar.innerHTML=keys.map(find).filter(Boolean).map(x=>'<button type="button" data-bottom-key="'+esc(x.key)+'" aria-label="'+esc(x.label)+'"'+(x.action==='page'&&x.target===page?' aria-current="page"':'')+'>'+I(x.icon)+'<span>'+esc(x.label)+'</span></button>').join('')+
        '<button type="button" data-bottom-menu aria-label="전체메뉴">'+I('menu')+'<span>전체메뉴</span></button>';
    }
    const sidebar=document.getElementById('sidebar');
    if(!document.getElementById('erpBottomEditEntry')){
      const b=document.createElement('button');b.type='button';b.id='erpBottomEditEntry';
      b.innerHTML=I('editSliders')+'하단 메뉴 편집';b.addEventListener('click',e=>{e.stopPropagation();closeNav();openEdit()});sidebar.prepend(b);
    }
  }
  function drawCatalog(){
    const q=editor.querySelector('input').value.trim().toLowerCase();
    const opts=catalog().filter(x=>!draft.includes(x.key)&&(!q||(x.label+' '+x.group+' '+x.target).toLowerCase().includes(q)));
    editor.querySelector('.bottom-catalog').innerHTML=opts.length?[...new Set(opts.map(x=>x.group))].map(g=>'<h4>'+esc(g)+'</h4>'+opts.filter(x=>x.group===g).map(x=>'<button type="button" data-bottom-add="'+esc(x.key)+'" '+(draft.length>=4?'disabled':'')+'>'+I(x.icon)+esc(x.label)+'</button>').join('')).join(''):'<small>추가할 항목이 없습니다.</small>';
  }
  function drawEdit(){
    editor.querySelector('.bottom-selected').innerHTML=draft.length?draft.map((k,i)=>'<div class="bottom-row"><span>'+esc(find(k)?.label||k)+'</span><button type="button" data-bottom-move="'+i+'" data-dir="-1" aria-label="위로" '+(i===0?'disabled':'')+'>↑</button><button type="button" data-bottom-move="'+i+'" data-dir="1" aria-label="아래로" '+(i===draft.length-1?'disabled':'')+'>↓</button><button type="button" data-bottom-remove="'+i+'" aria-label="제거">×</button></div>').join(''):'<small>선택 항목 없음</small>';
    drawCatalog();
  }
  function openEdit(){draft=current();editor.querySelector('input').value='';drawEdit();editor.showModal();}
  editor.querySelector('input').addEventListener('input',drawCatalog);
  editor.addEventListener('click',e=>{
    const b=e.target.closest('button');if(!b)return;
    e.stopPropagation();const d=b.dataset;
    if(b.getAttribute('aria-label')==='닫기'){editor.close();return;}
    if(d.bottomReset!==undefined){draft=[...defaults];drawEdit();return;}
    if(d.bottomSave!==undefined){
      if(device()!=='mobile'){editor.close();return;}
      const old=data.__prefs;
      data.__prefs={...(old||{}),mobile:{...preferences(),mobileBottomNav:clean(draft)}};
      if(!persist()){data.__prefs=old;toast('설정 저장 실패');return;}
      editor.close();drawBar();toast('하단 메뉴를 저장했습니다.');return;
    }
    if(d.bottomAdd!==undefined&&draft.length<4&&find(d.bottomAdd)&&!draft.includes(d.bottomAdd))draft.push(d.bottomAdd);
    else if(d.bottomRemove!==undefined)draft.splice(Number(d.bottomRemove),1);
    else if(d.bottomMove!==undefined){const i=Number(d.bottomMove),j=i+Number(d.dir);if(i>=0&&j>=0&&i<draft.length&&j<draft.length)[draft[i],draft[j]]=[draft[j],draft[i]];}
    drawEdit();
  });
  bar.addEventListener('click',e=>{
    const b=e.target.closest('button');if(!b)return;e.stopPropagation();
    if(b.hasAttribute('data-bottom-menu'))document.getElementById('hamb').click();
    else execute(find(b.dataset.bottomKey));
  });
  const observer=new MutationObserver(drawBar);
  observer.observe(document.getElementById('main'),{childList:true});
  observer.observe(document.getElementById('sidebar'),{childList:true});
  window.addEventListener('resize',()=>{if(device()!=='mobile'){if(editor.open)editor.close();if(input.open)input.close();}drawBar();});
  const keyboard=()=>{const v=window.visualViewport;document.body.classList.toggle('erp-bottom-keyboard',!!v&&window.innerHeight-v.height>130);};
  window.visualViewport?.addEventListener('resize',keyboard);
  drawBar();
})();
