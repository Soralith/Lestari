(() => {
  const CACHE_KEY = 'lestari-recent-sessions-v1';
  const CACHE_TTL_MS = 60_000;
  const list = document.getElementById('session-list');
  let cached = null;
  let pendingRequest = null;

  const escapeHtml = (value) => String(value).replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);

  function readCache() {
    try {
      const entry = JSON.parse(sessionStorage.getItem(CACHE_KEY) || 'null');
      if (entry && Array.isArray(entry.sessions)) return entry;
    } catch { /* Ignore unavailable storage or malformed cache. */ }
    return null;
  }

  function render(sessions) {
    if (!list) return;
    list.setAttribute('aria-busy', 'false');
    if (!sessions.length) {
      list.innerHTML = '<p class="px-space-md py-space-xs font-body-sm text-body-sm text-outline">Belum ada sesi</p>';
      return;
    }
    const canManageSessions = /^\/konsultasi\/(?:\d+\/)?$/.test(location.pathname);
    list.innerHTML = sessions.slice(0, 8).map((session) => {
      const id = Number(session.id);
      const link = `<a class="flex-1 min-w-0 block px-space-md py-2 rounded-xl text-on-surface-variant hover:text-on-surface transition-all cursor-pointer" data-session-id="${id}" href="/konsultasi/${id}/">
        <p class="font-body-md text-body-md font-medium truncate">${escapeHtml(session.title || 'Konsultasi baru')}</p>
        <span class="font-label-sm text-label-sm text-outline">${new Date(session.updated_at).toLocaleString('id-ID', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>
      </a>`;
      if (!canManageSessions) return link;
      return `<div class="group relative flex items-center rounded-xl hover:bg-surface-container transition-all">
        ${link}
        <button type="button" class="shrink-0 mr-1 w-9 h-9 rounded-lg text-on-surface-variant hover:text-error hover:bg-error-container/60 flex items-center justify-center opacity-0 group-hover:opacity-100 focus:opacity-100 transition-all" data-delete-session="${id}" title="Hapus sesi" aria-label="Hapus sesi ${escapeHtml(session.title || '')}">
          <span class="material-symbols-outlined text-[18px]" aria-hidden="true">delete</span>
        </button>
      </div>`;
    }).join('');
  }

  async function refresh({ force = false } = {}) {
    if (!list) return;
    if (pendingRequest) {
      await pendingRequest;
      if (!force) return;
    }
    if (!force && cached && Date.now() - cached.updatedAt < CACHE_TTL_MS) return;

    pendingRequest = (async () => {
      try {
        const response = await fetch('/api/sessions/', { credentials: 'same-origin' });
        if (!response.ok) throw new Error('Could not load sessions');
        const data = await response.json();
        cached = { updatedAt: Date.now(), sessions: Array.isArray(data.sessions) ? data.sessions : [] };
        try { sessionStorage.setItem(CACHE_KEY, JSON.stringify(cached)); } catch { /* Cache is an enhancement only. */ }
        render(cached.sessions);
      } catch {
        if (!cached && list.getAttribute('aria-busy') === 'true') {
          list.innerHTML = '<p class="px-space-md py-space-xs font-body-sm text-body-sm text-outline">Riwayat sesi tidak tersedia.</p>';
          list.setAttribute('aria-busy', 'false');
        }
      } finally {
        pendingRequest = null;
      }
    })();
    return pendingRequest;
  }

  function prefetchNavigation() {
    if (navigator.connection?.saveData || navigator.connection?.effectiveType === '2g') return;
    const urls = [...document.querySelectorAll('#sidebar nav a[href]')]
      .map((anchor) => new URL(anchor.href, location.href))
      .filter((url) => url.origin === location.origin && url.pathname !== location.pathname);
    const added = new Set();
    for (const url of urls) {
      if (added.has(url.href)) continue;
      added.add(url.href);
      const hint = document.createElement('link');
      hint.rel = 'prefetch';
      hint.as = 'document';
      hint.href = url.href;
      document.head.appendChild(hint);
    }
  }

  if (list) {
    cached = readCache();
    if (cached) render(cached.sessions);
    else list.setAttribute('aria-busy', 'true');
    window.LestariSessions = { refresh };
    refresh();

    document.querySelector('form[action="/logout/"]')?.addEventListener('submit', () => {
      try { sessionStorage.removeItem(CACHE_KEY); } catch { /* Ignore unavailable storage. */ }
    });

    const schedulePrefetch = window.requestIdleCallback || ((callback) => window.setTimeout(callback, 350));
    schedulePrefetch(prefetchNavigation, { timeout: 1200 });
  }
})();
