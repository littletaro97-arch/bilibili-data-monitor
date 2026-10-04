(() => {
  const root = document.documentElement;
  const system = matchMedia('(prefers-color-scheme: dark)');
  const read = key => { try { return localStorage.getItem(key); } catch (_) { return null; } };
  const write = (key, value) => { try { localStorage.setItem(key, value); } catch (_) {} };
  function apply(theme) {
    root.dataset.theme = theme;
    root.style.colorScheme = theme;
    window.dispatchEvent(new CustomEvent('appearancechange'));
  }
  apply(read('blla:theme') || (system.matches ? 'dark' : 'light'));
  system.addEventListener('change', () => { if (!read('blla:theme')) apply(system.matches ? 'dark' : 'light'); });
  function preferenceUrl(href, metrics) {
    const url = new URL(href);
    for (const name of ['left_metric', 'right_metric', 'ratio_numerator', 'ratio_denominator']) {
      const stored = read(`blla:${url.pathname}:select:${name}`);
      if (!url.searchParams.has(name) && metrics.includes(stored)) url.searchParams.set(name, stored);
    }
    return url.toString();
  }
  // Cards and ordinary links must resolve the same URL before navigation.
  // Otherwise the head script restores preferences with a second document load.
  window.bllaDetailUrl = href => preferenceUrl(href, window.bllaMetricNames || []);
  window.restoreChartPreferences = metrics => {
    const target = preferenceUrl(location.href, metrics);
    // Direct entry also restores before parsing body/images.
    if (target !== location.href) location.replace(target);
  };
  document.addEventListener('DOMContentLoaded', () => {
    const prepareLink = link => {
      if (link && link.origin === location.origin && /^\/videos\/[^/]+$/.test(link.pathname)) link.href = window.bllaDetailUrl(link.href);
    };
    for (const link of document.querySelectorAll('a[href]')) prepareLink(link);
    document.addEventListener('click', event => prepareLink(event.target.closest('a[href]')));
    const button = document.querySelector('[data-theme-toggle]');
    function render() {
      const dark = root.dataset.theme === 'dark';
      if (button) { button.textContent = dark ? '☀' : '☾'; button.title = button.ariaLabel = dark ? '切换为浅色模式' : '切换为深色模式'; button.setAttribute('aria-pressed', String(dark)); }
      if (window.Plotly) {
        const css = getComputedStyle(root), ink = css.getPropertyValue('--text').trim(), panel = css.getPropertyValue('--panel').trim(), line = css.getPropertyValue('--line').trim();
        for (const chart of document.querySelectorAll('.plotly-graph-div')) {
          if (!chart.layout) continue;
          const update = {'paper_bgcolor': panel, 'plot_bgcolor': panel, 'font.color': ink, 'legend.bgcolor': panel};
          for (const key of Object.keys(chart.layout)) if (/^[xy]axis\d*$/.test(key)) { update[`${key}.color`] = ink; update[`${key}.gridcolor`] = line; update[`${key}.zerolinecolor`] = line; }
          for (let i = 0; i < (chart.layout.annotations || []).length; i++) update[`annotations[${i}].font.color`] = ink;
          Plotly.relayout(chart, update);
        }
      }
      if (navigator.userAgent.includes('BilibiliMonitorDesktopPanel')) fetch('/desktop/theme', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({dark})}).catch(() => {});
    }
    button?.addEventListener('click', () => { const theme = root.dataset.theme === 'dark' ? 'light' : 'dark'; write('blla:theme', theme); apply(theme); });
    window.addEventListener('appearancechange', render);
    window.addEventListener('storage', event => { if (event.key === 'blla:theme') apply(event.newValue || (system.matches ? 'dark' : 'light')); });
    render();
  });
})();
