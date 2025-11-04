(function () {
  const card = document.querySelector('[data-related-topics-card][data-topic-uuid]');
  if (!card) return;

  const gettext = window.gettext || ((s) => s);
  const interpolate = window.interpolate || ((fmt, args) => {
    if (!args || !args.length) return fmt;
    return fmt.replace('%s', args[0]);
  });

  const topicUuid = card.getAttribute('data-topic-uuid');
  const listContainer = card.querySelector('[data-related-topic-list]');
  const itemsContainer = card.querySelector('[data-related-topic-items]');
  const searchInput = card.querySelector('[data-related-topic-search-input]');
  const searchResults = card.querySelector('[data-related-topic-search-results]');
  const suggestionSection = card.querySelector('[data-related-topic-suggestions-section]');
  const suggestionList = card.querySelector('[data-related-topic-suggestions-list]');

  async function request(url, options = {}) {
    const response = await fetch(url, options);
    if (!response.ok) {
      let message = `Request failed: ${response.status}`;
      try {
        const data = await response.json();
        if (data && data.detail) message = data.detail;
      } catch (_) {
        /* ignore parse errors */
      }
      throw new Error(message);
    }
    if (response.status === 204) return null;
    try {
      return await response.json();
    } catch (_) {
      return null;
    }
  }

  function renderEmptyState(activeCount) {
    if (!listContainer) return;
    const message = listContainer.getAttribute('data-empty-message') || '';
    let emptyEl = listContainer.querySelector('.empty-msg');
    if (activeCount === 0) {
      if (!emptyEl) {
        emptyEl = document.createElement('p');
        emptyEl.className = 'text-secondary small mb-0 empty-msg';
        emptyEl.textContent = message;
        listContainer.appendChild(emptyEl);
      }
    } else if (emptyEl) {
      emptyEl.remove();
    }
  }

  function renderLinks(links) {
    if (!itemsContainer) return;
    itemsContainer.innerHTML = '';
    let activeCount = 0;
    links.forEach((link) => {
      const topicTitle = link.title || gettext('Untitled topic');
      const li = document.createElement('li');
      li.className = 'border rounded p-2 mb-2 d-flex justify-content-between align-items-start';
      li.dataset.linkId = link.id;
      li.dataset.source = link.source || '';
      if (link.is_deleted) {
        li.classList.add('opacity-50');
      } else {
        activeCount += 1;
      }

      const left = document.createElement('div');
      left.className = 'me-3';

      const titleEl = document.createElement('div');
      titleEl.className = 'fw-semibold';
      if (link.slug && link.username) {
        const anchor = document.createElement('a');
        anchor.href = `/topics/${link.username}/${link.slug}/`;
        anchor.className = 'text-decoration-none';
        anchor.textContent = topicTitle;
        titleEl.appendChild(anchor);
      } else {
        titleEl.textContent = topicTitle;
      }
      left.appendChild(titleEl);

      const meta = document.createElement('div');
      meta.className = 'text-secondary small';
      const pieces = [];
      if (link.username) {
        pieces.push(interpolate(gettext('By %s'), [link.username]));
      }
      if (link.source) {
        const sourceLabel = link.source === 'auto'
          ? gettext('Automatic')
          : (link.source === 'manual' ? gettext('Manual') : link.source);
        pieces.push(sourceLabel);
      }
      if (pieces.length) {
        meta.textContent = pieces.join(' · ');
      }
      left.appendChild(meta);

      const right = document.createElement('div');
      right.className = 'btn-group';
      const button = document.createElement('button');
      button.type = 'button';
      button.className = link.is_deleted
        ? 'btn btn-outline-secondary btn-sm'
        : 'btn btn-outline-danger btn-sm';
      button.textContent = link.is_deleted ? gettext('Restore') : gettext('Remove');
      button.dataset.action = link.is_deleted ? 'restore' : 'remove';
      right.appendChild(button);

      li.appendChild(left);
      li.appendChild(right);
      itemsContainer.appendChild(li);
    });
    renderEmptyState(activeCount);
  }

  async function refreshLinks() {
    try {
      const data = await request(`/api/topics/${topicUuid}/related-topics`);
      if (Array.isArray(data)) {
        renderLinks(data);
        await fetchSuggestions();
      }
    } catch (err) {
      console.error(err);
    }
  }

  let searchTimeout = null;
  async function performSearch(term) {
    if (!searchResults) return;
    if (!term) {
      searchResults.classList.add('d-none');
      searchResults.innerHTML = '';
      return;
    }
    try {
      const data = await request(`/api/topics/${topicUuid}/related-topics/search?query=${encodeURIComponent(term)}`);
      searchResults.innerHTML = '';
      if (!data || data.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'list-group-item text-secondary small';
        empty.textContent = gettext('No matches found.');
        searchResults.appendChild(empty);
        searchResults.classList.remove('d-none');
        return;
      }
      data.forEach((result) => {
        const item = buildTopicButton(result);
        searchResults.appendChild(item);
      });
      searchResults.classList.remove('d-none');
    } catch (err) {
      console.error(err);
    }
  }

  function buildTopicButton(result, options = {}) {
    const opts = { showSimilarity: false, ...options };
    const item = document.createElement('button');
    item.type = 'button';
    item.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';
    item.dataset.topicUuid = result.uuid;
    item.disabled = Boolean(result.is_already_linked);
    item.textContent = result.title || gettext('Untitled topic');

    const meta = document.createElement('span');
    meta.className = 'small text-secondary ms-2';

    if (result.is_already_linked) {
      meta.textContent = gettext('Already linked');
    } else {
      const pieces = [];
      if (result.username) {
        pieces.push(result.username);
      }
      if (opts.showSimilarity && typeof result.similarity === 'number') {
        const similarityPercent = Math.round(result.similarity * 100);
        if (!Number.isNaN(similarityPercent)) {
          pieces.push(`${similarityPercent}%`);
        }
      }
      meta.textContent = pieces.join(' · ');
    }

    item.appendChild(meta);
    return item;
  }

  async function fetchSuggestions() {
    if (!suggestionSection || !suggestionList) return;
    try {
      const data = await request(`/api/topics/${topicUuid}/related-topics/suggest`);
      suggestionList.innerHTML = '';
      if (!data || !Array.isArray(data) || data.length === 0) {
        suggestionSection.classList.add('d-none');
        return;
      }
      data.forEach((result) => {
        const item = buildTopicButton(result, { showSimilarity: true });
        suggestionList.appendChild(item);
      });
      suggestionSection.classList.remove('d-none');
    } catch (err) {
      console.error(err);
      suggestionSection.classList.add('d-none');
    }
  }

  if (searchInput) {
    searchInput.addEventListener('input', (event) => {
      const value = event.target.value.trim();
      if (searchTimeout) clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => performSearch(value), value.length >= 2 ? 200 : 0);
      if (!value) {
        if (searchResults) {
          searchResults.classList.add('d-none');
          searchResults.innerHTML = '';
        }
      }
    });
  }

  if (searchResults) {
    searchResults.addEventListener('click', async (event) => {
      const button = event.target.closest('button[data-topic-uuid]');
      if (!button || button.disabled) return;
      const targetUuid = button.dataset.topicUuid;
      button.disabled = true;
      try {
        await request(`/api/topics/${topicUuid}/related-topics`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ related_topic_uuid: targetUuid })
        });
        searchInput.value = '';
        searchResults.classList.add('d-none');
        searchResults.innerHTML = '';
        await refreshLinks();
      } catch (err) {
        console.error(err);
        button.disabled = false;
      }
    });
  }

  if (itemsContainer) {
    itemsContainer.addEventListener('click', async (event) => {
      const button = event.target.closest('button[data-action]');
      if (!button) return;
      const li = button.closest('[data-link-id]');
      if (!li) return;
      const linkId = li.dataset.linkId;
      button.disabled = true;
      try {
        if (button.dataset.action === 'remove') {
          await request(`/api/topics/${topicUuid}/related-topics/${linkId}`, {
            method: 'DELETE'
          });
        } else {
          await request(`/api/topics/${topicUuid}/related-topics/${linkId}/restore`, {
            method: 'POST'
          });
        }
        await refreshLinks();
      } catch (err) {
        console.error(err);
      } finally {
        button.disabled = false;
      }
    });
  }

  if (suggestionList) {
    suggestionList.addEventListener('click', async (event) => {
      const button = event.target.closest('button[data-topic-uuid]');
      if (!button || button.disabled) return;
      const targetUuid = button.dataset.topicUuid;
      button.disabled = true;
      try {
        await request(`/api/topics/${topicUuid}/related-topics`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ related_topic_uuid: targetUuid })
        });
        await refreshLinks();
      } catch (err) {
        console.error(err);
      } finally {
        button.disabled = false;
      }
    });
  }

  refreshLinks();
})();
