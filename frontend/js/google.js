// Google Identity Services helper.
// Renders the "Continue with Google" button into #gbtn and posts the
// returned ID token to /api/google. On success: stores JWT and redirects.
(function () {
  function showError(msg) {
    const el = document.getElementById('msg');
    if (el) el.textContent = msg;
    else console.error(msg);
  }

  async function handleCredential(resp) {
    try {
      const r = await api.post('/api/google', { credential: resp.credential });
      auth.set(r.token, r.user);
      location.href = '/dashboard.html';
    } catch (err) {
      showError(err.message);
    }
  }

  function renderButton() {
    const slot = document.getElementById('gbtn');
    if (!slot) return;

    const clientId = window.GOOGLE_CLIENT_ID;
    if (!clientId) {
      slot.innerHTML =
        '<div class="text-xs text-amber-300/90 bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">' +
        'Google sign-in is not configured yet. Set <code class="font-mono">GOOGLE_CLIENT_ID</code> on the backend ' +
        '(or in <code class="font-mono">js/config.js</code>) to enable it.</div>';
      return;
    }
    if (!window.google || !google.accounts || !google.accounts.id) {
      // GIS script still loading; retry shortly.
      return setTimeout(renderButton, 200);
    }
    google.accounts.id.initialize({
      client_id: clientId,
      callback: handleCredential,
      ux_mode: 'popup',
      auto_select: false,
    });
    slot.innerHTML = '';
    google.accounts.id.renderButton(slot, {
      type: 'standard',
      theme: 'filled_black',
      size: 'large',
      shape: 'pill',
      text: 'continue_with',
      logo_alignment: 'left',
      width: 320,
    });
    // Optional: One Tap prompt
    try { google.accounts.id.prompt(); } catch (_) {}
  }

  // Try to load runtime config (GOOGLE_CLIENT_ID, RESOLVA_API_BASE) from backend
  // so the user doesn't have to hardcode anything in config.js.
  async function loadRuntimeConfig() {
    if (!window.RESOLVA_API_BASE) return; // nothing to query yet
    try {
      const u = window.RESOLVA_API_BASE.replace(/\/$/, '') + '/api/config.js';
      const code = await fetch(u).then(r => r.ok ? r.text() : '');
      if (code) {
        // Backend value should win over local placeholder
        const fnBody = code.replace(/window\.RESOLVA_API_BASE\s*=\s*window\.RESOLVA_API_BASE\s*\|\|[^;]+;/, '');
        new Function(fnBody)();
      }
    } catch (_) { /* ignore */ }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    await loadRuntimeConfig();
    renderButton();
  });
})();
