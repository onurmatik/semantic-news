(function () {
  const card = document.querySelector('[data-related-topics-card][data-topic-uuid]');
  if (!card) return;

  const _ = window.gettext || (s => s);
  const topicUuid = card.getAttribute('data-topic-uuid');

  const listWrap = card.querySelector('[data-related-topic-list]');
  const itemsEl = card.querySelector('[data-related-topic-items]');
  const searchInput = card.querySelector('[data-related-topic-search-input]');
  const searchResults = card.querySelector('[data-related-topic-search-results]');
  const suggSection = card.querySelector('[data-related-topic-suggestions-section]');
  const suggList = card.querySelector('[data-related-topic-suggestions-list]');

  // --- helpers
  async function api(url, options = {}) {
    const res = await fetch(url, options);
    if (!res.ok) {
      let msg = `HTTP ${res.status}`;
      try {
        const data = await res.json();
        if (data?.detail) msg = data.detail;
      } catch {}
      throw new Error(msg);
    }
    if (res.status === 204) return null;
    try { return await res.json(); } catch { return null; }
  }

  function emptyState(count) {
    const msg = listWrap.getAttribute('data-empty-message') || '';
    let el = listWrap.querySelector('.empty-msg');
    if (count === 0) {
      if (!el) {
        el = document.createElement('p');
        el.className = 'text-secondary small mb-0 empty-msg';
        el.textContent = msg;
        listWrap.appendChild(el);
      }
    } else if (el) {
      el.remove();
    }
  }

  function sourceLabel(src) {
    if (!src) return '';
    // Only user | agent are valid
    if (src === 'user') return _('User');
    if (src === 'agent') return _('Agent');
    // fallback, just in case
    return String(src).charAt(0).toUpperCase() + String(src).slice(1);
    }

  function renderLinks(links) {
    itemsEl.innerHTML = '';
    let active = 0;

    links.forEach(link => {
      const li = document.createElement('li');
      li.className = 'border rounded p-2 mb-2';
      if (link.is_deleted) li.classList.add('opacity-50');

      // left side
      const left = document.createElement('div');
      const title = document.createElement('div');
      title.className = 'fw-semibold';

      const displayTitle = link.title || _('Untitled topic');
      if (link.slug && link.username) {
        const a = document.createElement('a');
        a.href = `/${link.username}/${link.slug}/`;
        a.className = 'text-decoration-none';
        a.textContent = displayTitle;
        title.appendChild(a);
      } else {
        title.textContent = displayTitle;
      }

      const meta = document.createElement('div');
      meta.className = 'text-secondary small';
      const bits = [];
      if (link.username) bits.push(_('By %s').replace('%s', link.username));
      if (link.source) bits.push(sourceLabel(link.source));
      if (bits.length) meta.textContent = bits.join(' · ');

      left.appendChild(title);
      left.appendChild(meta);

      // right side
      const right = document.createElement('div');
      right.className = 'btn-group';
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = link.is_deleted ? 'btn btn-outline-secondary btn-sm' : 'btn btn-outline-danger btn-sm';
      btn.textContent = link.is_deleted ? _('Restore') : _('Remove');
      btn.dataset.action = link.is_deleted ? 'restore' : 'remove';
      btn.dataset.linkId = link.id;
      right.appendChild(btn);

      // row
      const row = document.createElement('div');
      row.className = 'd-flex justify-content-between align-items-start';
      row.appendChild(left);
      row.appendChild(right);
      li.appendChild(row);
      itemsEl.appendChild(li);

      if (!link.is_deleted) active += 1;
    });

    emptyState(active);
  }

  async function refresh() {
    try {
      const data = await api(`/api/topics/${topicUuid}/related-topics`);
      renderLinks(Array.isArray(data) ? data : []);
      await loadSuggestions();
    } catch (e) {
      // keep silent in UI
      console.error(e);
    }
  }

  // --- search
  let t = null;
  async function runSearch(q) {
    if (!q) {
      searchResults.classList.add('d-none');
      searchResults.innerHTML = '';
      return;
    }
    try {
      const results = await api(`/api/topics/${topicUuid}/related-topics/search?query=${encodeURIComponent(q)}`);
      searchResults.innerHTML = '';
      if (!results || results.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'list-group-item text-secondary small';
        empty.textContent = _('No matches found.');
        searchResults.appendChild(empty);
      } else {
        results.forEach(r => searchResults.appendChild(buildResultButton(r)));
      }
      searchResults.classList.remove('d-none');
    } catch (e) {
      console.error(e);
    }
  }

  function buildResultButton(r, { showSimilarity = false } = {}) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';
    btn.dataset.topicUuid = r.uuid;
    btn.disabled = !!r.is_already_linked;
    btn.textContent = r.title || _('Untitled topic');

    const meta = document.createElement('span');
    meta.className = 'small text-secondary ms-2';
    if (r.is_already_linked) {
      meta.textContent = _('Already linked');
    } else {
      const bits = [];
      if (r.username) bits.push(r.username);
      if (showSimilarity && typeof r.similarity === 'number') {
        const pct = Math.round(r.similarity * 100);
        if (!Number.isNaN(pct)) bits.push(`${pct}%`);
      }
      meta.textContent = bits.join(' · ');
    }
    btn.appendChild(meta);
    return btn;
  }

  // --- suggestions
  async function loadSuggestions() {
    if (!suggSection || !suggList) return;
    try {
      const data = await api(`/api/topics/${topicUuid}/related-topics/suggest`);
      suggList.innerHTML = '';
      if (!Array.isArray(data) || data.length === 0) {
        suggSection.classList.add('d-none');
        return;
      }
      data.forEach(r => suggList.appendChild(buildResultButton(r, { showSimilarity: true })));
      suggSection.classList.remove('d-none');
    } catch (e) {
      console.error(e);
      suggSection.classList.add('d-none');
    }
  }

  // --- events
  if (searchInput) {
    searchInput.addEventListener('input', (ev) => {
      const v = ev.target.value.trim();
      if (t) clearTimeout(t);
      t = setTimeout(() => runSearch(v), v.length >= 2 ? 200 : 0);
      if (!v) {
        searchResults.classList.add('d-none');
        searchResults.innerHTML = '';
      }
    });
  }

  if (searchResults) {
    searchResults.addEventListener('click', async (ev) => {
      const btn = ev.target.closest('button[data-topic-uuid]');
      if (!btn || btn.disabled) return;
      btn.disabled = true;
      try {
        await api(`/api/topics/${topicUuid}/related-topics`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ related_topic_uuid: btn.dataset.topicUuid })
        });
        if (searchInput) searchInput.value = '';
        searchResults.classList.add('d-none');
        searchResults.innerHTML = '';
        await refresh();
      } catch (e) {
        console.error(e);
        btn.disabled = false;
      }
    });
  }

  if (itemsEl) {
    itemsEl.addEventListener('click', async (ev) => {
      const btn = ev.target.closest('button[data-action][data-link-id]');
      if (!btn) return;
      btn.disabled = true;
      const linkId = btn.dataset.linkId;
      try {
        if (btn.dataset.action === 'remove') {
          await api(`/api/topics/${topicUuid}/related-topics/${linkId}`, { method: 'DELETE' });
        } else {
          await api(`/api/topics/${topicUuid}/related-topics/${linkId}/restore`, { method: 'POST' });
        }
        await refresh();
      } catch (e) {
        console.error(e);
      } finally {
        btn.disabled = false;
      }
    });
  }

  if (suggList) {
    suggList.addEventListener('click', async (ev) => {
      const btn = ev.target.closest('button[data-topic-uuid]');
      if (!btn || btn.disabled) return;
      btn.disabled = true;
      try {
        await api(`/api/topics/${topicUuid}/related-topics`, {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({ related_topic_uuid: btn.dataset.topicUuid })
        });
        await refresh();
      } catch (e) {
        console.error(e);
      } finally {
        btn.disabled = false;
      }
    });
  }

  // bootstrap
  refresh();
})();
