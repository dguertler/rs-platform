window.BACKEND_URL = 'https://rs-platform.onrender.com';

(function () {
  const HEALTH_URL = window.BACKEND_URL + '/health';
  const PING_INTERVAL = 3000;
  const SHOW_OVERLAY_AFTER = 1500;
  let overlayTimer = null;
  let overlay = null;

  function createOverlay() {
    overlay = document.createElement('div');
    overlay.id = 'render-wake-overlay';
    overlay.style.cssText = [
      'position:fixed', 'inset:0', 'z-index:99999',
      'background:rgba(10,10,20,0.92)',
      'display:flex', 'flex-direction:column',
      'align-items:center', 'justify-content:center',
      'font-family:system-ui,sans-serif', 'color:#e2e8f0'
    ].join(';');
    overlay.innerHTML = `
      <div style="width:48px;height:48px;border:4px solid #334155;border-top-color:#38bdf8;border-radius:50%;animation:rs-spin 0.8s linear infinite;margin-bottom:20px"></div>
      <div style="font-size:1.1rem;font-weight:600;margin-bottom:8px">Backend wird gestartet&hellip;</div>
      <div style="font-size:0.85rem;color:#94a3b8">Render Free Tier – bitte kurz warten</div>
      <style>@keyframes rs-spin{to{transform:rotate(360deg)}}</style>
    `;
    document.body.appendChild(overlay);
  }

  function removeOverlay() {
    if (overlay) { overlay.remove(); overlay = null; }
    if (overlayTimer) { clearTimeout(overlayTimer); overlayTimer = null; }
  }

  function ping() {
    fetch(HEALTH_URL, { method: 'GET', cache: 'no-store' })
      .then(r => { if (r.ok) removeOverlay(); else scheduleRetry(); })
      .catch(() => scheduleRetry());
  }

  function scheduleRetry() {
    setTimeout(ping, PING_INTERVAL);
  }

  function startWakeCheck() {
    overlayTimer = setTimeout(() => {
      if (!overlay) createOverlay();
    }, SHOW_OVERLAY_AFTER);
    ping();
  }

  const _origFetch = window.fetch.bind(window);
  window.fetch = function (input, init) {
    if (typeof input === 'string' && input.startsWith('/api/')) {
      input = window.BACKEND_URL + input;
    } else if (input instanceof Request && input.url.includes('/api/')) {
      const url = window.BACKEND_URL + new URL(input.url).pathname + new URL(input.url).search;
      input = new Request(url, input);
    }
    return _origFetch(input, init);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startWakeCheck);
  } else {
    startWakeCheck();
  }
})();
