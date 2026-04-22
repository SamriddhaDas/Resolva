// Tiny fetch wrapper. Adds JWT and parses JSON errors uniformly.
// Configure backend URL by setting window.RESOLVA_API_BASE in config.js
// or leave blank to call same-origin (useful for local dev with the Node proxy).
window.api = (() => {
  const BASE = (window.RESOLVA_API_BASE || '').replace(/\/$/, '');
  function token() { return localStorage.getItem('resolva_token'); }
  function url(path) {
    if (/^https?:\/\//.test(path)) return path;
    return BASE + path;
  }
  async function request(method, path, body) {
    const res = await fetch(url(path), {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(token() ? { 'Authorization': 'Bearer ' + token() } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    });
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
