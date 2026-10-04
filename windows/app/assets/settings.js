(() => {
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
