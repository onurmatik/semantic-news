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
  const suggestionsModalEl = document.getElementById('referenceSuggestionsModal');
  const suggestionsModal = suggestionsModalEl && window.bootstrap
    ? window.bootstrap.Modal.getOrCreateInstance(suggestionsModalEl)
    : null;
  const suggestionsModalAlert = suggestionsModalEl
    ? suggestionsModalEl.querySelector('[data-reference-suggestions-modal-alert]')
    : null;
  const suggestionsSummary = suggestionsModalEl
    ? suggestionsModalEl.querySelector('[data-reference-suggestions-summary]')
    : null;
  const suggestionsPreview = suggestionsModalEl
    ? suggestionsModalEl.querySelector('[data-reference-suggestions-preview]')
    : null;
  const suggestionsEmpty = suggestionsModalEl
    ? suggestionsModalEl.querySelector('[data-reference-suggestions-empty]')
    : null;
  const suggestionsApplyBtn = suggestionsModalEl
    ? suggestionsModalEl.querySelector('[data-reference-suggestions-apply]')
    : null;
  const suggestionsApplySpinner = suggestionsModalEl
    ? suggestionsModalEl.querySelector('[data-reference-suggestions-apply-spinner]')
    : null;
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
  let suggestionsState = 'idle';
  let latestSuggestionPayload = null;
  let latestSuggestionId = null;

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

  function setModalAlert(message) {
    if (!suggestionsModalAlert) return;
    if (message) {
      suggestionsModalAlert.textContent = message;
      suggestionsModalAlert.classList.remove('d-none');
    } else {
      suggestionsModalAlert.textContent = '';
      suggestionsModalAlert.classList.add('d-none');
    }
  }

  function updateApplyState() {
    if (!suggestionsApplyBtn || !suggestionsPreview) return;
    const checked = suggestionsPreview.querySelectorAll('input[data-suggestion-type]:checked');
    suggestionsApplyBtn.disabled = checked.length === 0;
  }

  function setRemoveButtonsDisabled(disabled) {
    if (!listEl) return;
    listEl.querySelectorAll(deleteButtonSelector).forEach((btn) => {
      btn.disabled = disabled;
      btn.classList.toggle('disabled', disabled);
    });
  }

  function setSuggestionsState(nextState) {
    if (!suggestionsBtn) return;
    suggestionsState = nextState;
    suggestionsBtn.classList.remove('btn-outline-primary', 'btn-success');
    if (nextState === 'loading') {
      suggestionsBtn.disabled = true;
      suggestionsBtn.classList.add('btn-outline-primary');
      suggestionsBtn.innerHTML = `<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>${_('Getting suggestions…')}`;
    } else if (nextState === 'ready') {
      const checkLabel = suggestionsBtn.getAttribute('data-check-label') || _('Check suggestions');
      suggestionsBtn.disabled = false;
      suggestionsBtn.classList.add('btn-success');
      suggestionsBtn.innerHTML = checkLabel;
    } else {
      suggestionsBtn.disabled = false;
      suggestionsBtn.classList.add('btn-outline-primary');
      suggestionsBtn.innerHTML = defaultSuggestionsLabel || _('Get suggestions');
    }
    setRemoveButtonsDisabled(nextState === 'loading');
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

  function getSectionEntries() {
    return Array.from(document.querySelectorAll('[data-topic-widget-entry][data-widget-section-id]'));
  }

  function getCurrentSectionOrder() {
    return getSectionEntries()
      .map((el) => el.getAttribute('data-widget-section-id'))
      .filter(Boolean);
  }

  function getSectionLabels() {
    const labels = new Map();
    getSectionEntries().forEach((el) => {
      const sectionId = el.getAttribute('data-widget-section-id');
      if (!sectionId) return;
      const key = el.getAttribute('data-topic-widget-key');
      labels.set(sectionId, key || _('Section'));
    });
    return labels;
  }

  function formatContentPreview(content) {
    if (content == null) return '';
    if (typeof content === 'string') return content;
    try {
      return JSON.stringify(content, null, 2);
    } catch (err) {
      return String(content);
    }
  }

  function renderSuggestionsPreview(payload) {
    if (!suggestionsPreview || !suggestionsEmpty) return;
    suggestionsPreview.innerHTML = '';
    setModalAlert('');

    if (!payload) {
      suggestionsEmpty.classList.remove('d-none');
      if (suggestionsSummary) suggestionsSummary.textContent = _('No suggestions available.');
      if (suggestionsApplyBtn) suggestionsApplyBtn.disabled = true;
      return;
    }

    const createEntries = Array.isArray(payload.create) ? payload.create : [];
    const updateEntries = Array.isArray(payload.update) ? payload.update : [];
    const reorderIds = Array.isArray(payload.reorder) ? payload.reorder.map(String) : [];
    const deleteIds = new Set(Array.isArray(payload.delete) ? payload.delete.map(String) : []);
    const updatesById = new Map(updateEntries.map((entry) => [String(entry.section_id), entry]));

    const baseOrder = reorderIds.length
      ? reorderIds
      : getCurrentSectionOrder();
    const filteredOrder = baseOrder.filter((id) => !deleteIds.has(String(id)));
    const ordered = filteredOrder.map((id) => ({ type: 'existing', id: String(id) }));

    const sortedCreates = [...createEntries].sort((a, b) => (a.order || 0) - (b.order || 0));
    sortedCreates.forEach((entry, idx) => {
      entry.__createIndex = idx;
      const desiredOrder = Math.max(1, Number(entry.order || 1));
      const position = Math.min(desiredOrder, ordered.length + 1);
      ordered.splice(position - 1, 0, { type: 'new', entry });
    });

    if (!ordered.length) {
      suggestionsEmpty.classList.remove('d-none');
      if (suggestionsSummary) suggestionsSummary.textContent = _('No suggestions available.');
      if (suggestionsApplyBtn) suggestionsApplyBtn.disabled = true;
      return;
    }

    suggestionsEmpty.classList.add('d-none');
    if (suggestionsApplyBtn) suggestionsApplyBtn.disabled = false;

    const labels = getSectionLabels();
    ordered.forEach((item, index) => {
      const row = document.createElement('div');
      row.className = 'list-group-item d-flex gap-3';

      const checkboxWrap = document.createElement('div');
      checkboxWrap.className = 'form-check mt-1';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.className = 'form-check-input';
      checkbox.checked = true;
      checkbox.dataset.suggestionType = item.type;
      if (item.type === 'new') {
        checkbox.dataset.createIndex = String(item.entry.__createIndex ?? index);
      } else {
        checkbox.dataset.sectionId = item.id;
      }
      checkboxWrap.appendChild(checkbox);
      row.appendChild(checkboxWrap);

      const content = document.createElement('div');
      content.className = 'flex-grow-1';

      const title = document.createElement('div');
      title.className = 'fw-semibold';
      if (item.type === 'new') {
        const widgetName = item.entry.widget_name || _('section');
        title.textContent = `${index + 1}. ${_('New')} ${widgetName}`;
      } else {
        const label = labels.get(item.id) || _('Section');
        const updateEntry = updatesById.get(item.id);
        title.textContent = updateEntry
          ? `${index + 1}. ${label} #${item.id} (${_('updated')})`
          : `${index + 1}. ${label} #${item.id}`;
      }
      content.appendChild(title);

      const detail = document.createElement('pre');
      detail.className = 'small text-secondary mb-0 mt-2';
      if (item.type === 'new') {
        detail.textContent = formatContentPreview(item.entry.content);
      } else {
        const updateEntry = updatesById.get(item.id);
        detail.textContent = updateEntry ? formatContentPreview(updateEntry.content) : _('No changes suggested.');
      }
      content.appendChild(detail);
      row.appendChild(content);
      suggestionsPreview.appendChild(row);
    });

    if (deleteIds.size) {
      deleteIds.forEach((id) => {
        const row = document.createElement('div');
        row.className = 'list-group-item d-flex gap-3 align-items-start';

        const checkboxWrap = document.createElement('div');
        checkboxWrap.className = 'form-check mt-1';
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'form-check-input';
        checkbox.checked = true;
        checkbox.dataset.suggestionType = 'delete';
        checkbox.dataset.sectionId = id;
        checkboxWrap.appendChild(checkbox);
        row.appendChild(checkboxWrap);

        const content = document.createElement('div');
        content.className = 'flex-grow-1';
        const title = document.createElement('div');
        title.className = 'fw-semibold text-danger';
        title.textContent = `${_('Delete')} ${labels.get(String(id)) || _('Section')} #${id}`;
        content.appendChild(title);
        row.appendChild(content);
        suggestionsPreview.appendChild(row);
      });
    }

    const summaryParts = [
      `${_('Created')}: ${createEntries.length}`,
      `${_('Updated')}: ${updateEntries.length}`,
      `${_('Deleted')}: ${deleteIds.size}`,
    ];
    if (suggestionsSummary) suggestionsSummary.textContent = summaryParts.join(' · ');

    updateApplyState();
    suggestionsPreview.querySelectorAll('input[data-suggestion-type]').forEach((input) => {
      input.addEventListener('change', updateApplyState);
    });
  }

  function buildSelectedPayload() {
    if (!latestSuggestionPayload || !suggestionsPreview) return null;

    const selectedExistingIds = new Set();
    const selectedDeleteIds = new Set();
    const selectedCreateIndexes = new Set();

    suggestionsPreview.querySelectorAll('input[data-suggestion-type]').forEach((input) => {
      if (!input.checked) return;
      const type = input.dataset.suggestionType;
      if (type === 'new') {
        if (input.dataset.createIndex != null) {
          selectedCreateIndexes.add(Number(input.dataset.createIndex));
        }
      } else if (type === 'delete') {
        if (input.dataset.sectionId != null) {
          selectedDeleteIds.add(String(input.dataset.sectionId));
        }
      } else if (input.dataset.sectionId != null) {
        selectedExistingIds.add(String(input.dataset.sectionId));
      }
    });

    const createEntries = Array.isArray(latestSuggestionPayload.create)
      ? [...latestSuggestionPayload.create]
      : [];
    const orderedCreates = createEntries.sort((a, b) => (a.order || 0) - (b.order || 0));
    const filteredCreates = orderedCreates.filter((entry, idx) => selectedCreateIndexes.has(idx));

    const updateEntries = Array.isArray(latestSuggestionPayload.update)
      ? latestSuggestionPayload.update.filter((entry) => selectedExistingIds.has(String(entry.section_id)))
      : [];

    const reorderIds = Array.isArray(latestSuggestionPayload.reorder)
      ? latestSuggestionPayload.reorder.map(String).filter((id) => selectedExistingIds.has(id))
      : [];

    const deleteEntries = Array.isArray(latestSuggestionPayload.delete)
      ? latestSuggestionPayload.delete.map(String).filter((id) => selectedDeleteIds.has(id))
      : [];

    return {
      create: filteredCreates,
      update: updateEntries,
      reorder: reorderIds,
      delete: deleteEntries,
    };
  }

  async function fetchLatestSuggestions() {
    if (!topicUuid) return null;
    try {
      const data = await api(`/api/topics/${topicUuid}/references/suggestions/latest`);
      latestSuggestionPayload = data?.payload || null;
      latestSuggestionId = data?.suggestion_id || null;
      if (data?.has_suggestions) {
        setSuggestionsState('ready');
      } else {
        setSuggestionsState('idle');
      }
      return data;
    } catch (err) {
      console.error(err);
      setSuggestionsState('idle');
      return null;
    }
  }

  async function openSuggestionsModal() {
    if (!suggestionsModal || !suggestionsModalEl) return;
    if (!latestSuggestionPayload) {
      const data = await fetchLatestSuggestions();
      latestSuggestionPayload = data?.payload || null;
      latestSuggestionId = data?.suggestion_id || null;
    }
    renderSuggestionsPreview(latestSuggestionPayload);
    suggestionsModal.show();
  }

  async function applySuggestions() {
    if (!topicUuid || !latestSuggestionId) {
      setModalAlert(_('Unable to apply suggestions.'));
      return;
    }

    const selectedPayload = buildSelectedPayload();
    const hasSelection = selectedPayload
      && (selectedPayload.create.length
        || selectedPayload.update.length
        || selectedPayload.reorder.length
        || selectedPayload.delete.length);
    if (!hasSelection) {
      setModalAlert(_('Select at least one section to apply.'));
      return;
    }

    if (suggestionsApplyBtn) suggestionsApplyBtn.disabled = true;
    if (suggestionsApplySpinner) suggestionsApplySpinner.classList.remove('d-none');
    setModalAlert('');

    try {
      await api(`/api/topics/${topicUuid}/references/suggestions/apply/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ suggestion_id: latestSuggestionId, payload: selectedPayload }),
      });
      window.location.reload();
    } catch (err) {
      console.error(err);
      setModalAlert(err.message || _('Unable to apply suggestions.'));
      if (suggestionsApplyBtn) suggestionsApplyBtn.disabled = false;
      if (suggestionsApplySpinner) suggestionsApplySpinner.classList.add('d-none');
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

    const pollInterval = 1500;
    const maxWaitMs = 10 * 60 * 1000;
    const maxAttempts = Math.ceil(maxWaitMs / pollInterval);

    try {
      const data = await api(`/api/topics/${topicUuid}/references/suggestions/${taskId}`);
      const state = (data?.state || '').toLowerCase();

      if (data?.success === false) {
        const message = data?.message || _('Unable to generate suggestions.');
        showSuggestionsAlert('error', message);
        setSuggestionsState('idle');
        clearSuggestionsPoll();
        return;
      }

      if (state === 'success' || state === 'succeeded') {
        const message = data?.message || _('Suggestions generated successfully.');
        showSuggestionsAlert('success', message);
        latestSuggestionPayload = data?.payload || null;
        latestSuggestionId = data?.suggestion_id || null;
        setSuggestionsState('ready');
        clearSuggestionsPoll();
        return;
      }

      if (state === 'failure' || state === 'failed') {
        const message = data?.message || _('Unable to generate suggestions.');
        showSuggestionsAlert('error', message);
        setSuggestionsState('idle');
        clearSuggestionsPoll();
        return;
      }

      if (attempt >= maxAttempts) {
        showSuggestionsAlert('error', _('Suggestions are taking longer than expected. Please try again later.'));
        setSuggestionsState('idle');
        clearSuggestionsPoll();
        return;
      }

      suggestionsPollTimer = setTimeout(() => pollSuggestionStatus(taskId, attempt + 1), pollInterval);
    } catch (err) {
      console.error(err);
      showSuggestionsAlert('error', err.message || _('Unable to generate suggestions.'));
      setSuggestionsState('idle');
      clearSuggestionsPoll();
    }
  }

  async function requestSuggestions(event) {
    event.preventDefault();
    if (!topicUuid) return;

    hideSuggestionsAlert();
    setSuggestionsState('loading');
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
      setSuggestionsState('idle');
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
    suggestionsBtn.addEventListener('click', (event) => {
      if (suggestionsState === 'ready') {
        event.preventDefault();
        openSuggestionsModal();
        return;
      }
      requestSuggestions(event);
    });
  }

  if (suggestionsAlertClose) {
    suggestionsAlertClose.addEventListener('click', (event) => {
      event.preventDefault();
      hideSuggestionsAlert();
    });
  }

  if (suggestionsApplyBtn) {
    suggestionsApplyBtn.addEventListener('click', (event) => {
      event.preventDefault();
      applySuggestions();
    });
  }

  loadReferences();
  if (suggestionsBtn) {
    fetchLatestSuggestions();
  }
})();
