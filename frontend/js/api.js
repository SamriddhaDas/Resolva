// Tiny fetch wrapper. Adds JWT and parses JSON errors uniformly.
window.api = (() => {
  function base() {
    return ((window.RESOLVA_API_BASE || '') + '').replace(/\/$/, '');
  }
  function token() { return localStorage.getItem('resolva_token'); }
  function url(path) {
    if (/^https?:\/\//.test(path)) return path;
    return base() + path;
  }
  async function request(method, path, body) {
    const target = url(path);
    if (!base() && !/^https?:\/\//.test(path)) {
      throw new Error("Backend URL not set. Open js/config.js and set RESOLVA_API_BASE to your Render URL.");
    }
    let res;
    try {
      res = await fetch(target, {
        method,
        headers: {
          'Content-Type': 'application/json',
          ...(token() ? { 'Authorization': 'Bearer ' + token() } : {}),
        },
        body: body ? JSON.stringify(body) : undefined,
      });
    } catch (netErr) {
      throw new Error("Cannot reach backend at " + target + ". (Server may be sleeping — wait 30s and retry.)");
    }
    const ct = res.headers.get('content-type') || '';
    const data = ct.includes('json') ? await res.json().catch(() => ({})) : await res.text();
    if (!res.ok) {
      const msg = (data && data.detail) ? data.detail : (typeof data === 'string' ? data : 'Request failed');
      throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
    }
    return data;
  }
  return {
    get:    (p)    => request('GET',    p),
    post:   (p, b) => request('POST',   p, b),
    patch:  (p, b) => request('PATCH',  p, b),
    del:    (p)    => request('DELETE', p),
  };
})();
