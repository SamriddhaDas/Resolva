/* Dashboard logic: stats, list, filters, create, status updates, delete. */
auth.requireAuth();

const me = auth.user() || {};
document.getElementById('firstName').textContent = (me.name || 'there').split(' ')[0];
document.getElementById('userBadge').textContent =
  `${me.email} · ${me.role === 'admin' ? 'Admin' : 'Member'}`;
if (me.role === 'admin') {
  document.getElementById('subtitle').textContent =
    'You\'re viewing all complaints across the platform.';
}

const PRIORITY_STYLES = {
  critical: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
  high:     'bg-orange-500/15 text-orange-300 border-orange-500/30',
  medium:   'bg-amber-500/15 text-amber-300 border-amber-500/30',
  low:      'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
};
const STATUS_STYLES = {
  pending:     'bg-amber-500/15 text-amber-300 border-amber-500/30',
  in_progress: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  resolved:    'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  rejected:    'bg-slate-500/15 text-slate-300 border-slate-500/30',
};

let allComplaints = [];
let activeFilter = 'all';

function fmt(d) {
  try { return new Date(d.replace(' ', 'T') + 'Z').toLocaleString(); }
  catch { return d; }
}

function renderStats(s) {
  const items = [
    { label: 'Total',       value: s.total,                       hue: 'from-brand-500/20 to-brand-500/5' },
    { label: 'Pending',     value: s.by_status.pending     || 0,  hue: 'from-amber-500/20 to-amber-500/5' },
    { label: 'In progress', value: s.by_status.in_progress || 0,  hue: 'from-sky-500/20 to-sky-500/5' },
    { label: 'Resolved',    value: s.by_status.resolved    || 0,  hue: 'from-emerald-500/20 to-emerald-500/5' },
  ];
  document.getElementById('stats').innerHTML = items.map(i => `
    <div class="rounded-2xl border border-white/10 bg-gradient-to-br ${i.hue} p-5 fade-up">
      <p class="text-xs uppercase tracking-wider text-slate-400">${i.label}</p>
      <p class="font-display text-3xl font-semibold mt-2">${i.value}</p>
    </div>
  `).join('');
}

function row(c) {
  const isAdmin = me.role === 'admin';
  const author = c.user_name ? `<span class="text-slate-500">·</span> <span class="text-slate-400">${c.user_name}</span>` : '';
  const adminControls = isAdmin ? `
    <select data-id="${c.id}" class="statusSel text-xs bg-ink-800 border border-white/10 rounded-md px-2 py-1">
      ${['pending','in_progress','resolved','rejected'].map(s =>
        `<option value="${s}" ${s===c.status?'selected':''}>${s.replace('_',' ')}</option>`).join('')}
    </select>` : '';
  return `
  <article class="fade-up rounded-2xl border border-white/10 bg-white/[.02] hover:bg-white/[.04] transition p-5">
    <div class="flex items-start justify-between gap-4">
      <div class="min-w-0">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="text-xs px-2 py-0.5 rounded-full border ${PRIORITY_STYLES[c.priority] || ''}">${c.priority}</span>
          <span class="text-xs px-2 py-0.5 rounded-full border ${STATUS_STYLES[c.status] || ''}">${c.status.replace('_',' ')}</span>
          <span class="text-xs px-2 py-0.5 rounded-full border border-white/10 text-slate-300">${c.category}</span>
        </div>
        <h3 class="mt-2 font-semibold truncate">${escapeHtml(c.title)}</h3>
        <p class="mt-1 text-sm text-slate-400 line-clamp-2">${escapeHtml(c.description)}</p>
        <p class="mt-2 text-xs text-slate-500">#${c.id} · ${fmt(c.created_at)} ${author}</p>
      </div>
      <div class="flex flex-col items-end gap-2 shrink-0">
        ${adminControls}
        <button data-id="${c.id}" class="delBtn text-xs text-slate-400 hover:text-rose-400">Delete</button>
      </div>
    </div>
  </article>`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
}

function renderList() {
  const filtered = activeFilter === 'all'
    ? allComplaints
    : allComplaints.filter(c => c.status === activeFilter);
  const list = document.getElementById('list');
  const empty = document.getElementById('empty');
  if (!filtered.length) { list.innerHTML = ''; empty.classList.remove('hidden'); return; }
  empty.classList.add('hidden');
  list.innerHTML = filtered.map(row).join('');
}

async function refresh() {
  const [list, stats] = await Promise.all([api.get('/api/complaints'), api.get('/api/stats')]);
  allComplaints = list;
  renderStats(stats);
  renderList();
}

// filter buttons
document.querySelectorAll('.filter-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    activeFilter = btn.dataset.f;
    document.querySelectorAll('.filter-btn').forEach(b => {
      b.classList.toggle('bg-white/10', b === btn);
      b.classList.toggle('hover:bg-white/5', b !== btn);
    });
    renderList();
  });
});

// list events (delegate)
document.getElementById('list').addEventListener('change', async (e) => {
  const sel = e.target.closest('.statusSel');
  if (!sel) return;
  try {
    await api.patch(`/api/complaints/${sel.dataset.id}/status`, { status: sel.value });
    await refresh();
  } catch (err) { alert(err.message); }
});
document.getElementById('list').addEventListener('click', async (e) => {
  const del = e.target.closest('.delBtn');
  if (!del) return;
  if (!confirm('Delete this complaint?')) return;
  try { await api.del(`/api/complaints/${del.dataset.id}`); await refresh(); }
  catch (err) { alert(err.message); }
});

// modal
const modal = document.getElementById('modal');
document.getElementById('newBtn').addEventListener('click', () => modal.classList.remove('hidden'));
document.querySelectorAll('.closeModal').forEach(b => b.addEventListener('click', () => modal.classList.add('hidden')));
modal.addEventListener('click', (e) => { if (e.target === modal) modal.classList.add('hidden'); });

document.getElementById('cForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const msg = document.getElementById('cmsg'); msg.textContent = '';
  try {
    await api.post('/api/complaints', {
      title: fd.get('title'),
      category: fd.get('category'),
      description: fd.get('description'),
    });
    e.target.reset();
    modal.classList.add('hidden');
    await refresh();
  } catch (err) { msg.textContent = err.message; }
});

refresh().catch(err => {
  if (/401|token/i.test(err.message)) { auth.clear(); location.href = '/login.html'; }
  else alert(err.message);
});
