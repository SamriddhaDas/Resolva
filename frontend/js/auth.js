// Auth state helpers shared across pages.
window.auth = {
  set(token, user) {
    localStorage.setItem('resolva_token', token);
    localStorage.setItem('resolva_user',  JSON.stringify(user));
  },
  user() {
    try { return JSON.parse(localStorage.getItem('resolva_user') || 'null'); }
    catch { return null; }
  },
  clear() {
    localStorage.removeItem('resolva_token');
    localStorage.removeItem('resolva_user');
  },
  requireAuth() {
    if (!localStorage.getItem('resolva_token')) location.href = '/login.html';
  },
  redirectIfAuthed() {
    if (localStorage.getItem('resolva_token')) location.href = '/dashboard.html';
  },
};

// Wire global logout buttons if present
document.addEventListener('click', (e) => {
  const t = e.target.closest('#logoutBtn');
  if (!t) return;
  auth.clear();
  location.href = '/login.html';
});
