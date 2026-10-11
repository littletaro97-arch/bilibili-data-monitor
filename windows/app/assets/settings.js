(() => {
  const overview=document.querySelector('.settings-overview');
  const runtime=document.getElementById('runtime-settings');
  const account=document.getElementById('bili-account');
  const manual=account?.querySelector('.manual-session');
  let manualChosen=false,fitFrame;
  manual?.querySelector('summary').addEventListener('click',()=>{manualChosen=true;});
  function fitSession(){
    if(!manual || manualChosen)return;
    if(!matchMedia('(min-width:901px)').matches){manual.open=false;return;}
    manual.open=true;
    const css=getComputedStyle(account), table=runtime.querySelector('table'),heading=runtime.querySelector('h2');
    const outer=el=>{const c=getComputedStyle(el);return el.getBoundingClientRect().height+parseFloat(c.marginTop)+parseFloat(c.marginBottom);};
    const padding=parseFloat(css.paddingTop)+parseFloat(css.paddingBottom)+2;
    const minimum=parseFloat(getComputedStyle(table).minHeight)+outer(heading)+padding;
    const expanded=[...account.children].reduce((height,el)=>height+outer(el),padding);
    manual.open=expanded<=minimum;
  }
  window.addEventListener('resize',()=>{cancelAnimationFrame(fitFrame);fitFrame=requestAnimationFrame(fitSession);});
  window.addEventListener('bllaAuthRender',fitSession);
  fitSession();

  for (const form of document.querySelectorAll('[data-auto-settings]')) {
    const status = form.querySelector('[data-save-status]');
    let queued = Promise.resolve();
    function save() {
      const values = new FormData(form);
      const password = form.querySelector('[name="password"]');
      const submittedPassword = password?.value;
      status.hidden = false;
      status.textContent = '正在保存…';
      queued = queued.then(async () => {
        try {
          const response = await fetch(form.action, {method:'POST', headers:{Accept:'application/json'}, body:values});
          const data = await response.json();
          if (!response.ok) throw Error(data.error || '保存失败');
          status.textContent = data.message;
          if (password && password.value === submittedPassword) password.value = '';
        } catch (error) {
          status.textContent = `${error.message}，请重新修改以重试。`;
        }
      });
    }
    form.addEventListener('change', event => {
      if (event.target.hasAttribute('data-toggle-password')) return;
      if (event.target.name) save();
    });
    form.addEventListener('submit', event => {event.preventDefault(); save();});
  }
})();
