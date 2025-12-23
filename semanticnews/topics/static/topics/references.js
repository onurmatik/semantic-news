(function () {
  const card = document.querySelector('[data-topic-references-card]');
  if (!card) return;

  const topicUuid = card.getAttribute('data-topic-uuid');
  const listEl = card.querySelector('[data-reference-list]');
  const form = card.querySelector('[data-reference-form]');
  const input = card.querySelector('[data-reference-url-input]');
  const errorEl = card.querySelector('[data-reference-error]');
  const submitBtn = card.querySelector('[data-reference-submit]');
  const suggestionsSection = card.querySelector('[data-reference-suggestions]');
  const suggestionsBtn = card.querySelector('[data-reference-suggestions-btn]');
  const suggestionsAlert = card.querySelector('[data-reference-suggestions-alert]');
  const suggestionsAlertBody = card.querySelector('[data-reference-suggestions-alert-body]');
  const suggestionsAlertMessage = card.querySelector('[data-reference-suggestions-message]');
  const suggestionsAlertClose = card.querySelector('[data-reference-suggestions-close]');
  const _ = window.gettext || ((s) => s);
  const confirmModalEl = document.getElementById('confirmDeleteReferenceModal');
  const confirmModal = confirmModalEl && window.bootstrap
    ? window.bootstrap.Modal.getOrCreateInstance(confirmModalEl)
    : null;
  const confirmBtn = document.getElementById('confirmDeleteReferenceBtn');
  const confirmSpinner = document.getElementById('confirmDeleteReferenceSpinner');
  const defaultSuggestionsLabel = suggestionsBtn ? suggestionsBtn.innerHTML : '';
  const deleteButtonSelector = '[data-remove-reference]';

  let pendingDeleteId = null;
  let suggestionsPollTimer = null;

  async function api(url, options = {}) {
    const res = await fetch(url, options);
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try {
        const data = await res.json();
        if (data?.detail) detail = data.detail;
      } catch (err) {
        // ignore JSON parse failures
      }
      throw new Error(detail);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  function showError(message) {
    if (!errorEl) return;
    errorEl.textContent = message;
    errorEl.classList.remove('d-none');
  }

  function clearError() {
    if (!errorEl) return;
    errorEl.textContent = '';
    errorEl.classList.add('d-none');
  }

  function renderEmptyState() {
    if (!listEl) return;
    const message = listEl.getAttribute('data-empty-message') || _('No references yet.');
    listEl.innerHTML = '';
    const empty = document.createElement('div');
    empty.className = 'list-group-item text-secondary small';
    empty.textContent = message;
    listEl.appendChild(empty);
  }

  function updateSuggestionsVisibility() {
    if (!suggestionsSection) return;
    const hasReferences = listEl?.querySelectorAll('[data-reference-item]').length > 0;
    suggestionsSection.classList.toggle('d-none', !hasReferences);
  }

  function hideSuggestionsAlert() {
    if (!suggestionsAlert || !suggestionsAlertBody) return;
    suggestionsAlert.classList.add('d-none');
    suggestionsAlertBody.classList.remove('alert-success', 'alert-danger');
    if (suggestionsAlertMessage) suggestionsAlertMessage.textContent = '';
  }

  function showSuggestionsAlert(type, message) {
    if (!suggestionsAlert || !suggestionsAlertBody || !suggestionsAlertMessage) return;
    suggestionsAlert.classList.remove('d-none');
    suggestionsAlertBody.classList.remove('alert-success', 'alert-danger');
    suggestionsAlertBody.classList.add(type === 'success' ? 'alert-success' : 'alert-danger');
    suggestionsAlertMessage.textContent = message || '';
  }

  function setRemoveButtonsDisabled(disabled) {
    if (!listEl) return;
    listEl.querySelectorAll(deleteButtonSelector).forEach((btn) => {
      btn.disabled = disabled;
      btn.classList.toggle('disabled', disabled);
    });
  }

  function setSuggestionsLoading(isLoading) {
    if (!suggestionsBtn) return;
    if (isLoading) {
      suggestionsBtn.disabled = true;
      suggestionsBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>${_('Getting suggestions…')}`;
    } else {
      suggestionsBtn.disabled = false;
      suggestionsBtn.innerHTML = defaultSuggestionsLabel || _('Get suggestions');
    }
    setRemoveButtonsDisabled(isLoading);
  }

  function buildItem(item) {
    const el = document.createElement('div');
    el.className = 'list-group-item d-flex gap-2 justify-content-between align-items-start';
    el.dataset.referenceItem = 'true';
    el.dataset.linkId = item.id;
    if (item.uuid) el.dataset.referenceUuid = item.uuid;
    else if (item.reference_uuid) el.dataset.referenceUuid = item.reference_uuid;

    const content = document.createElement('div');
    content.className = 'flex-grow-1';

    const title = document.createElement('div');
    title.className = 'fw-semibold small';
    title.textContent = item.meta_title || item.url || _('Untitled');
    content.appendChild(title);

    const meta = document.createElement('div');
    meta.className = 'text-secondary small';

    if (item.url) {
      const link = document.createElement('a');
      link.className = 'link-secondary text-decoration-none';
      link.href = item.url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.textContent = item.domain || item.url;
      meta.appendChild(link);
    } else if (item.domain) {
      meta.textContent = item.domain;
    }

    if (item.meta_published_at) {
      const dateText = document.createTextNode(` · ${item.meta_published_at.split('T')[0]}`);
      meta.appendChild(dateText);
    }

    content.appendChild(meta);

    const actions = document.createElement('div');
    actions.className = 'd-flex flex-column gap-1 align-items-end';

    if (form) {
      const removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.className = 'btn btn-link text-danger p-0';
      removeBtn.dataset.removeReference = 'true';
      removeBtn.setAttribute('aria-label', _('Remove reference'));
      removeBtn.innerHTML = '<i class="bi bi-trash"></i>';
      actions.appendChild(removeBtn);
    }

    el.appendChild(content);
    el.appendChild(actions);
    return el;
  }

  async function loadReferences() {
    if (!topicUuid || !listEl) return;

    listEl.innerHTML = '';
    const loading = document.createElement('div');
    loading.className = 'list-group-item text-secondary small';
    loading.textContent = _('Loading…');
    listEl.appendChild(loading);

    try {
      const data = await api(`/api/topics/${topicUuid}/references`);
      listEl.innerHTML = '';
      if (!Array.isArray(data) || data.length === 0) {
        renderEmptyState();
        updateSuggestionsVisibility();
        return;
      }
      data.forEach((item) => listEl.appendChild(buildItem(item)));
      updateSuggestionsVisibility();
    } catch (err) {
      console.error(err);
      renderEmptyState();
      updateSuggestionsVisibility();
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!form || !input || !topicUuid) return;

    const url = (input.value || '').trim();
    if (!url) {
      showError(_('Please enter a URL.'));
      return;
    }

    clearError();
    if (submitBtn) submitBtn.disabled = true;

    try {
      const payload = { url };
      const data = await api(`/api/topics/${topicUuid}/references`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (listEl) {
        if (listEl.children.length === 1 && listEl.firstElementChild?.classList.contains('text-secondary')) {
          listEl.innerHTML = '';
        }
        listEl.prepend(buildItem(data));
        updateSuggestionsVisibility();
      }
      form.reset();
    } catch (err) {
      console.error(err);
      showError(err.message || _('Unable to add reference.'));
    } finally {
      if (submitBtn) submitBtn.disabled = false;
    }
  }

  async function handleDelete(linkId) {
    if (!topicUuid || !linkId) return;
    await api(`/api/topics/${topicUuid}/references/${linkId}`, { method: 'DELETE' });
    const row = listEl?.querySelector(`[data-link-id="${linkId}"]`);
    if (row) row.remove();
    if (listEl && listEl.children.length === 0) {
      renderEmptyState();
    }
    updateSuggestionsVisibility();
  }

  function clearSuggestionsPoll() {
    if (suggestionsPollTimer) {
      clearTimeout(suggestionsPollTimer);
      suggestionsPollTimer = null;
    }
  }

  async function pollSuggestionStatus(taskId, attempt = 0) {
    if (!taskId || !topicUuid) return;

    const maxAttempts = 20;
    const pollInterval = 1500;

    try {
      const data = await api(`/api/topics/${topicUuid}/references/suggestions/${taskId}`);
      const state = (data?.state || '').toLowerCase();

      if (state === 'success' || state === 'succeeded') {
        const message = data?.message || _('Suggestions generated successfully.');
        showSuggestionsAlert('success', message);
        setSuggestionsLoading(false);
        clearSuggestionsPoll();
        return;
      }

      if (state === 'failure' || state === 'failed') {
        const message = data?.message || _('Unable to generate suggestions.');
        showSuggestionsAlert('error', message);
        setSuggestionsLoading(false);
        clearSuggestionsPoll();
        return;
      }

      if (attempt >= maxAttempts) {
        showSuggestionsAlert('error', _('Suggestions are taking longer than expected. Please try again later.'));
        setSuggestionsLoading(false);
        clearSuggestionsPoll();
        return;
      }

      suggestionsPollTimer = setTimeout(() => pollSuggestionStatus(taskId, attempt + 1), pollInterval);
    } catch (err) {
      console.error(err);
      showSuggestionsAlert('error', err.message || _('Unable to generate suggestions.'));
      setSuggestionsLoading(false);
      clearSuggestionsPoll();
    }
  }

  async function requestSuggestions(event) {
    event.preventDefault();
    if (!topicUuid) return;

    hideSuggestionsAlert();
    setSuggestionsLoading(true);
    clearSuggestionsPoll();

    try {
      const data = await api(`/api/topics/${topicUuid}/references/suggestions/`, { method: 'POST' });
      const taskId = data?.task_id;
      if (!taskId) {
        throw new Error(_('Unable to start suggestion request.'));
      }
      pollSuggestionStatus(taskId);
    } catch (err) {
      console.error(err);
      showSuggestionsAlert('error', err.message || _('Unable to generate suggestions.'));
      setSuggestionsLoading(false);
    }
  }

  function resetConfirmState() {
    if (confirmBtn) confirmBtn.disabled = false;
    if (confirmSpinner) confirmSpinner.classList.add('d-none');
    pendingDeleteId = null;
  }

  if (form) {
    form.addEventListener('submit', handleSubmit);
  }

  if (listEl && form) {
    listEl.addEventListener('click', (event) => {
      const removeBtn = event.target.closest('button[data-remove-reference]');
      if (!removeBtn) return;
      event.preventDefault();
      const parent = removeBtn.closest('[data-link-id]');
      const linkId = parent?.getAttribute('data-link-id');
      if (!linkId) return;
      pendingDeleteId = linkId;
      if (confirmModal) {
        confirmModal.show();
      } else {
        handleDelete(linkId).catch((err) => console.error(err));
      }
    });
  }

  if (confirmModalEl) {
    confirmModalEl.addEventListener('hidden.bs.modal', resetConfirmState);
  }

  if (confirmBtn) {
    confirmBtn.addEventListener('click', async (event) => {
      event.preventDefault();
      if (!pendingDeleteId) return;
      confirmBtn.disabled = true;
      if (confirmSpinner) confirmSpinner.classList.remove('d-none');
      try {
        await handleDelete(pendingDeleteId);
        if (confirmModal) {
          confirmModal.hide();
        } else {
          resetConfirmState();
        }
      } catch (err) {
        console.error(err);
        confirmBtn.disabled = false;
        if (confirmSpinner) confirmSpinner.classList.add('d-none');
      }
    });
  }

  if (suggestionsBtn) {
    suggestionsBtn.addEventListener('click', requestSuggestions);
  }

  if (suggestionsAlertClose) {
    suggestionsAlertClose.addEventListener('click', (event) => {
      event.preventDefault();
      hideSuggestionsAlert();
    });
  }

  loadReferences();
})();
