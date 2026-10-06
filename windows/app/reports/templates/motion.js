(() => {
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const main = document.querySelector('main');
  delete document.documentElement.dataset.pageEntering;
  const animated = () => !reduced.matches && !!Element.prototype.animate;
  const dialogs = new WeakMap();
  window.bllaMotion = {
    enter(element){if(animated() && element)element.animate([{opacity:0,transform:"translateY(4px)"},{opacity:1,transform:"none"}],{duration:160,easing:"ease-out"});},
    showDialog(dialog) {
      if (!dialogs.has(dialog)) {
        dialog.addEventListener('cancel', event => {event.preventDefault(); window.bllaMotion.closeDialog(dialog);});
        dialogs.set(dialog, null);
      }
      dialogs.get(dialog)?.cancel(); dialogs.set(dialog,null);
      if (!dialog.open) dialog.showModal();
      if (animated()) dialog.animate([{opacity:0,transform:'translateY(4px)'},{opacity:1,transform:'none'}],{duration:160,easing:'ease-out'});
    },
    closeDialog(dialog) {
      if (!dialog.open || dialogs.get(dialog)) return Promise.resolve();
      if (!animated()) {dialog.close();return Promise.resolve();}
      const animation=dialog.animate([{opacity:1,transform:'none'},{opacity:0,transform:'translateY(4px)'}],{duration:120,easing:'ease-in',fill:'forwards'});
      dialogs.set(dialog,animation);
      return animation.finished.catch(()=>{}).then(()=>{if(dialogs.get(dialog)===animation){dialog.close();animation.cancel();dialogs.set(dialog,null);}});
    }
  };
  if (!Element.prototype.animate) return;
  if (!reduced.matches && main) main.animate([{opacity:0, transform:'translateY(4px)'}, {opacity:1, transform:'none'}], {duration:160, easing:'ease-out'});
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || !link || link.target || link.hasAttribute('download') || reduced.matches || !main) return;
    const url = new URL(link.href);
    if (url.origin !== location.origin || (url.pathname === location.pathname && url.search === location.search)) return;
    event.preventDefault();
    if (main.dataset.leaving) return;
    main.dataset.leaving = '1';
    main.animate([{opacity:1}, {opacity:0}], {duration:120, fill:'forwards'}).finished.then(() => location.assign(url.href)).catch(() => { delete main.dataset.leaving; });
  });
  for (const detail of document.querySelectorAll('details')) {
    const summary = detail.querySelector(':scope > summary');
    if (!summary) continue;
    const body = document.createElement('div');
    body.className = 'details-body';
    for (const node of [...detail.childNodes]) if (node !== summary) body.append(node);
    detail.append(body);
    let animation = null;
    let expanded = detail.open;
    summary.addEventListener('click', event => {
      if (event.target.closest('a, button, input, select') || reduced.matches) return;
      event.preventDefault();
      expanded = !expanded;
      const height = detail.open ? body.getBoundingClientRect().height : 0;
      if (animation) animation.cancel();
      detail.open = true;
      body.style.overflow = 'hidden';
      animation = body.animate([{height:`${height}px`, opacity:expanded ? 0.6 : 1}, {height:expanded ? `${body.scrollHeight}px` : '0px', opacity:expanded ? 1 : 0}], {duration:220, easing:'cubic-bezier(.4,0,.2,1)'});
      const current = animation;
      current.finished.then(() => {
        if (animation !== current) return;
        animation = null;
        body.style.overflow = '';
        detail.open = expanded;
        if (expanded) window.dispatchEvent(new Event('resize'));
      }).catch(() => {});
    });
    detail.addEventListener('toggle', () => { if (!animation) expanded = detail.open; });
  }
  document.addEventListener('submit', event => {
    const form=event.target;
    if (event.defaultPrevented || form.target || form.method==='dialog' || !animated() || !main) return;
    if(form.dataset.motionSubmitted==='ready'){delete form.dataset.motionSubmitted;return;}
    if(form.dataset.motionSubmitted==='pending'){event.preventDefault();return;}
    event.preventDefault();form.dataset.motionSubmitted='pending';
    main.animate([{opacity:1},{opacity:0}],{duration:120,easing:'ease-in',fill:'forwards'}).finished.then(()=>{form.dataset.motionSubmitted='ready';form.requestSubmit(event.submitter || undefined);}).catch(()=>{delete form.dataset.motionSubmitted;});
  });
  // A page restored from the history cache must not retain the exit fade.
  window.addEventListener('pageshow', event => {
    if (event.persisted && main) { main.getAnimations().forEach(a => a.cancel()); delete main.dataset.leaving; }
  });
})();
