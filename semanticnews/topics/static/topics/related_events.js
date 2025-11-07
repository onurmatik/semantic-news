(function () {
  const card = document.querySelector('[data-related-events-card][data-topic-uuid]');
  if (!card) return;

  const _ = window.gettext || ((s) => s);

  const topicUuid = card.getAttribute('data-topic-uuid');
  const listWrap = card.querySelector('[data-related-event-list]');
  const itemsEl = card.querySelector('[data-related-event-items]');
  const searchInput = card.querySelector('[data-related-event-search-input]');
  const searchResults = card.querySelector('[data-related-event-search-results]');
  const suggestionsSection = card.querySelector('[data-related-event-suggestions-section]');
  const suggestionsList = card.querySelector('[data-related-event-suggestions-list]');

  async function api(url, options = {}) {
    const res = await fetch(url, options);
    if (!res.ok) {
      let msg = `HTTP ${res.status}`;
      try {
        const data = await res.json();
        if (data?.detail) msg = data.detail;
      } catch (err) {
        // ignore JSON parse errors
      }
      throw new Error(msg);
    }
    if (res.status === 204) return null;
    try {
      return await res.json();
    } catch (err) {
      return null;
    }
  }

  function showEmptyState(container, message) {
    if (!container) return;
    container.innerHTML = '';
    const empty = document.createElement('div');
    empty.className = 'list-group-item text-secondary small';
    empty.textContent = message;
    container.appendChild(empty);
  }

  function buildResultButton(event, { disableIfLinked = false, showSimilarity = true } = {}) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';
    btn.dataset.eventUuid = event.uuid;
    if (disableIfLinked && event.is_already_linked) {
      btn.disabled = true;
    }

    const title = document.createElement('span');
    title.textContent = event.title || _('Untitled event');
    btn.appendChild(title);

    const meta = document.createElement('span');
    meta.className = 'small text-secondary ms-2 text-nowrap';
    if (disableIfLinked && event.is_already_linked) {
      meta.textContent = _('Already added');
    } else {
      const bits = [];
      if (event.date) bits.push(event.date);
      if (showSimilarity && typeof event.similarity === 'number') {
        const pct = Math.round(event.similarity * 100);
        if (!Number.isNaN(pct)) bits.push(`${pct}%`);
      }
      meta.textContent = bits.join(' · ');
    }
    btn.appendChild(meta);

    return btn;
  }

  async function relateEvent(eventUuid, button) {
    if (!eventUuid) return;

    if (button) button.disabled = true;
    try {
      await api('/api/topics/timeline/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic_uuid: topicUuid, event_uuids: [eventUuid] }),
      });
      window.location.reload();
    } catch (err) {
      console.error(err);
      if (button) button.disabled = false;
    }
  }

  async function runSearch(query) {
    console.log("testo")
    if (!searchResults) return;

    const trimmed = query.trim();
    if (!topicUuid) return;

    if (!trimmed) {
      searchResults.classList.add('d-none');
      searchResults.innerHTML = '';
      return;
    }

    searchResults.classList.remove('d-none');
    showEmptyState(searchResults, _('Searching…'));

    try {
      const params = new URLSearchParams();
      params.set('query', trimmed);
      const results = await api(`/api/topics/${topicUuid}/timeline/related-events/search?${params.toString()}`);
      searchResults.innerHTML = '';
      if (!Array.isArray(results) || results.length === 0) {
        showEmptyState(searchResults, _('No matching events.'));
        return;
      }
      results.forEach((event) => {
        const showSimilarity = typeof event.similarity === 'number' && !Number.isNaN(event.similarity);
        searchResults.appendChild(
          buildResultButton(event, { disableIfLinked: true, showSimilarity })
        );
      });
    } catch (err) {
      console.error(err);
      showEmptyState(searchResults, _('Unable to load results.'));
    }
  }

  async function loadSuggestions() {
    if (!topicUuid || !suggestionsSection || !suggestionsList) return;

    suggestionsList.innerHTML = '';
    suggestionsSection.classList.remove('d-none');
    showEmptyState(suggestionsList, _('Loading suggestions…'));

    try {
      const data = await api(`/api/topics/${topicUuid}/timeline/related-events/suggest`);
      suggestionsList.innerHTML = '';
      if (!Array.isArray(data) || data.length === 0) {
        suggestionsSection.classList.add('d-none');
        return;
      }
      data.forEach((event) => {
        suggestionsList.appendChild(buildResultButton(event, { showSimilarity: true }));
      });
      suggestionsSection.classList.remove('d-none');
    } catch (err) {
      console.error(err);
      suggestionsSection.classList.add('d-none');
    }
  }

  if (searchInput) {
    let timer = null;
    searchInput.addEventListener('input', (ev) => {
      const value = ev.target.value || '';
      if (timer) clearTimeout(timer);
      if (value.trim().length === 0) {
        runSearch('');
        return;
      }
      const delay = value.trim().length >= 2 ? 200 : 400;
      timer = setTimeout(() => runSearch(value), delay);
    });
  }

  if (searchResults) {
    searchResults.addEventListener('click', (ev) => {
      const btn = ev.target.closest('button[data-event-uuid]');
      if (!btn || btn.disabled) return;
      relateEvent(btn.dataset.eventUuid, btn);
    });
  }

  if (suggestionsList) {
    suggestionsList.addEventListener('click', (ev) => {
      const btn = ev.target.closest('button[data-event-uuid]');
      if (!btn || btn.disabled) return;
      relateEvent(btn.dataset.eventUuid, btn);
    });
  }

  document.addEventListener('topic:changed', () => {
    loadSuggestions();

  });

  if (listWrap && itemsEl) {
    const emptyMessage = listWrap.getAttribute('data-empty-message');
    if (emptyMessage) {
      const hasItems = itemsEl.querySelector('.event-item[data-event-uuid]');
      const existingMsg = listWrap.querySelector('.empty-msg');
      if (!hasItems && !existingMsg) {
        const p = document.createElement('p');
        p.className = 'text-secondary small mb-0 empty-msg';
        p.textContent = emptyMessage;
        listWrap.appendChild(p);
      } else if (hasItems && existingMsg) {
        existingMsg.remove();
      }
    }
  }

  loadSuggestions();
})();
