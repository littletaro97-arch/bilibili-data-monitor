(() => {
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');
  const main = document.querySelector('main');
  if (!Element.prototype.animate) return;
  // This script runs after body parsing: content may already have painted.
  // Never turn that visible content transparent again, even during slow loads.
  if (!reduced.matches && main) main.animate([{transform:'translateY(2px)'}, {transform:'none'}], {duration:120, easing:'ease-out'});
  document.addEventListener('click', event => {
    const link = event.target.closest('a[href]');
    if (event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || !link || link.target || link.hasAttribute('download') || reduced.matches || !main) return;
    const url = new URL(link.href);
    if (url.origin !== location.origin || (url.pathname === location.pathname && url.search === location.search)) return;
    event.preventDefault();
    if (main.dataset.leaving) return;
    main.dataset.leaving = '1';
    // Keep the outgoing page visible while the next document is loading.
    main.animate([{transform:'none'}, {transform:'translateY(-2px)'}], {duration:80, fill:'forwards'}).finished.then(() => location.assign(url.href)).catch(() => { delete main.dataset.leaving; });
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
      animation = body.animate([{height:`${height}px`, opacity:expanded ? 0.6 : 1}, {height:expanded ? `${body.scrollHeight}px` : '0px', opacity:expanded ? 1 : 0}], {duration:160, easing:'ease-out'});
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
  // A page restored from the history cache must not retain the exit fade.
  window.addEventListener('pageshow', event => {
    if (event.persisted && main) { main.getAnimations().forEach(a => a.cancel()); delete main.dataset.leaving; }
  });
})();
