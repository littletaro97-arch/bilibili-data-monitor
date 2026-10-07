(() => {
  const key='blla:nav-load';
  let preserveMode=true;
  const buttons=new WeakMap();
  function start(element){
    if(!element || !element.matches('button,a'))return ()=>{};
    if(buttons.has(element))return ()=>{};
    const marker=document.createElement('span');marker.className='loading-mark';marker.ariaHidden='true';
    element.prepend(marker);element.setAttribute('aria-busy','true');buttons.set(element,marker);
    return ()=>{marker.remove();element.removeAttribute('aria-busy');buttons.delete(element);};
  }
  window.bllaLoading={start};
  function remember(preserve){
    preserveMode=preserve;
    const anchor=[...document.querySelectorAll('main [data-detail-url],main [data-nav-title][id]')].find(el=>{const box=el.getBoundingClientRect();return box.bottom>0&&box.top<innerHeight;});
    const point=anchor?{id:anchor.id,url:anchor.dataset.detailUrl,top:anchor.getBoundingClientRect().top}:null;
    try{sessionStorage.setItem(key,JSON.stringify({path:location.pathname,x:scrollX,y:scrollY,preserve,time:Date.now(),anchor:point}));}catch{}
  }
  let pending=false;
  function go(href,element,preserve=false,reload=false){
    if(pending)return;
    pending=true;remember(preserve);start(element);
    if(!element){const status=document.createElement('div');status.className='page-loading-status';status.setAttribute('role','status');status.innerHTML='<span class="loading-mark" aria-hidden="true"></span>正在刷新…';document.body.append(status);}
    if(reload)location.reload();else location.assign(href);
  }
  window.bllaNavigate={go,reload:element=>go(location.href,element,true,true)};
  document.addEventListener('click',event=>{
    const link=event.target.closest('a[href]');
    if(event.defaultPrevented || event.button!==0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || !link || link.target || link.hasAttribute('download'))return;
    const url=new URL(link.href);
    if(url.origin!==location.origin || /\/(export|download)$|\.csv$/.test(url.pathname))return;
    const refresh=link.hasAttribute('data-refresh-page');
    if(!refresh && url.pathname===location.pathname && url.search===location.search)return;
    event.preventDefault();go(url.href,link,url.pathname===location.pathname,refresh && url.pathname===location.pathname);
  });
  document.addEventListener('submit',event=>{
    const form=event.target;
    if(event.defaultPrevented || form.target || form.method==='dialog')return;
    if(pending){event.preventDefault();return;}
    pending=true;remember(true);start(event.submitter || form.querySelector('button[type=submit],button:not([type])'));
  });
  function restore(){
    const state=window.bllaNavigationIntent;
    if(state?.preserve && state.path===location.pathname){
      const apply=()=>{let top=state.y;const point=state.anchor;const anchor=point?.id?document.getElementById(point.id):(point?.url?[...document.querySelectorAll('[data-detail-url]')].find(el=>el.dataset.detailUrl===point.url):null);if(anchor)top=anchor.getBoundingClientRect().top+scrollY-point.top;scrollTo({left:state.x,top,behavior:'instant'});};
      requestAnimationFrame(()=>requestAnimationFrame(apply));window.addEventListener('load',apply,{once:true});
    }
    try{sessionStorage.removeItem(key);}catch{}
  }
  restore();
  window.addEventListener('pagehide',()=>remember(preserveMode));
  window.addEventListener('pageshow',event=>{if(event.persisted){pending=false;for(const el of document.querySelectorAll('[aria-busy="true"]')){el.querySelector('.loading-mark')?.remove();el.removeAttribute('aria-busy');}document.querySelector('.page-loading-status')?.remove();}});
})();
