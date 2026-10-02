(() => {
  const libraryUrl = document.currentScript?.dataset.libraryUrl || '/assets/plotly.min.js';
  let library;
  function loadLibrary() {
    if (window.Plotly) return Promise.resolve(window.Plotly);
    if (!library) library = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = libraryUrl;
      script.onload = () => resolve(window.Plotly);
      script.onerror = () => { script.remove(); library = null; reject(new Error('图表组件加载失败')); };
      document.head.append(script);
    });
    return library;
  }
  const states = new WeakMap();
  function visible(wrapper) {
    return !document.hidden && !wrapper.closest('details:not([open])');
  }
  async function update(wrapper) {
    const target = wrapper.querySelector('.lazy-chart-target');
    const state = states.get(wrapper) || { busy: false };
    states.set(wrapper, state);
    if (state.busy) return;
    if (!visible(wrapper)) return;
    // Keep an initialized instance across toggles. Purge/recreate increased
    // allocations in the native benchmark and lost the user's zoom state.
    if (target.layout) {
      Plotly.Plots.resize(target).catch(() => {});
      return;
    }
    state.busy = true;
    try {
      const plotly = await loadLibrary();
      if (!visible(wrapper)) return;
      const figure = JSON.parse(wrapper.querySelector('[data-chart-json]').textContent);
      const css = getComputedStyle(document.documentElement);
      const ink = css.getPropertyValue('--text').trim(), panel = css.getPropertyValue('--panel').trim(), line = css.getPropertyValue('--line').trim();
      Object.assign(figure.layout, {paper_bgcolor: panel, plot_bgcolor: panel, font: {...figure.layout.font, color: ink}});
      for (const key of Object.keys(figure.layout)) if (/^[xy]axis\d*$/.test(key)) Object.assign(figure.layout[key], {color: ink, gridcolor: line, zerolinecolor: line});
      for (const annotation of figure.layout.annotations || []) annotation.font = {...annotation.font, color: ink};
      target.textContent = '';
      await plotly.newPlot(target, figure.data, figure.layout, {responsive: true, displaylogo: false});
    } catch (error) {
      console.warn('图表初始化失败', error);
      target.textContent = '图表暂不可用，重新展开可重试';
    } finally {
      state.busy = false;
    }
  }
  function refresh() {
    document.querySelectorAll('.lazy-chart').forEach(update);
  }
  document.addEventListener('toggle', refresh, true);
  document.addEventListener('visibilitychange', refresh);
  refresh();
})();
