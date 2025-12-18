(function () {
  const card = document.querySelector('[data-topic-references-card]');
  if (!card) return;

  const topicUuid = card.getAttribute('data-topic-uuid');
  const listEl = card.querySelector('[data-reference-list]');
  const form = card.querySelector('[data-reference-form]');
  const input = card.querySelector('[data-reference-url-input]');
  const errorEl = card.querySelector('[data-reference-error]');
  const submitBtn = card.querySelector('[data-reference-submit]');
  const _ = window.gettext || ((s) => s);
  const confirmModalEl = document.getElementById('confirmDeleteReferenceModal');
  const confirmModal = confirmModalEl && window.bootstrap
    ? window.bootstrap.Modal.getOrCreateInstance(confirmModalEl)
    : null;
  const confirmBtn = document.getElementById('confirmDeleteReferenceBtn');
  const confirmSpinner = document.getElementById('confirmDeleteReferenceSpinner');
  const RUN_POLL_INTERVAL_MS = 2000;

  let pendingDeleteId = null;
  const runPollers = new Map();

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

  function normalizeStatus(status) {
    const value = (status || '').toString().toLowerCase();
    if (['pending', 'queued', 'running', 'in_progress'].includes(value)) return 'running';
    if (['finished', 'success', 'succeeded', 'completed', 'complete'].includes(value)) return 'finished';
    if (['failed', 'error', 'canceled', 'cancelled'].includes(value)) return 'failed';
    return 'idle';
  }

  function getRunElements(row) {
    return {
      button: row?.querySelector('[data-reference-run]'),
      spinner: row?.querySelector('[data-reference-run-spinner]'),
      label: row?.querySelector('[data-reference-run-label]'),
      addButton: row?.querySelector('[data-reference-add-section]'),
      error: row?.querySelector('[data-reference-run-error]'),
    };
  }

  function setRunState(row, state = {}) {
    if (!row) return;
    const status = state.status || 'idle';
    const runId = state.runId || null;
    const error = state.error || null;

    row.dataset.runStatus = status;
    if (runId) row.dataset.runId = runId;
    else delete row.dataset.runId;

    const { button, spinner, label, addButton, error: errorElRow } = getRunElements(row);
    const isRunning = status === 'running';
    const isFinished = status === 'finished';
    const isFailed = status === 'failed';

    if (button) {
      button.disabled = isRunning;
      if (spinner) spinner.classList.toggle('d-none', !isRunning);
      if (label) {
        if (isRunning) label.textContent = _('Running…');
        else if (isFinished) label.textContent = _('Re-fetch data');
        else if (isFailed) label.textContent = _('Try again');
        else label.textContent = _('Fetch data');
      }
    }

    if (addButton) {
      if (isFinished) {
        addButton.classList.remove('d-none');
        addButton.disabled = !runId;
        if (runId) addButton.dataset.runId = runId;
      } else {
        addButton.classList.add('d-none');
        addButton.disabled = true;
        delete addButton.dataset.runId;
      }
    }

    if (errorElRow) {
      if (error) {
        errorElRow.textContent = error;
        errorElRow.classList.remove('d-none');
      } else {
        errorElRow.textContent = '';
        errorElRow.classList.add('d-none');
      }
    }
  }

  function parseRunState(item) {
    const run = item?.latest_run || item?.run || item?.analysis_run || null;
    const runId = run?.id || run?.run_id || run?.uuid || item?.latest_run_id || item?.run_id || null;
    const status = normalizeStatus(run?.status || run?.state || item?.run_status);
    const error = run?.error || run?.error_message || item?.run_error || null;
    const resolvedStatus = status || 'idle';
    if (resolvedStatus === 'running' && !runId) {
      return {
        runId: null,
        status: 'failed',
        error: error || _('Missing run identifier.'),
      };
    }
    return {
      runId,
      status: resolvedStatus,
      error,
    };
  }

  function stopPoller(runId) {
    const key = `${runId}`;
    const existing = runPollers.get(key);
    if (existing?.timeoutId) {
      clearTimeout(existing.timeoutId);
    }
    runPollers.delete(key);
  }

  function schedulePoll(runId, row) {
    if (!runId || !row || !topicUuid) return;
    const key = `${runId}`;

    stopPoller(key);

    const poll = async () => {
      try {
        const data = await api(`/api/topics/${topicUuid}/references/runs/${runId}`);
        const status = normalizeStatus(data?.status || data?.run_status);
        const error = data?.error || data?.error_message || null;
        setRunState(row, { status, runId, error });
        if (row && row.isConnected && status === 'running') {
          const timeoutId = window.setTimeout(poll, RUN_POLL_INTERVAL_MS);
          runPollers.set(key, { timeoutId });
        } else {
          stopPoller(key);
        }
      } catch (err) {
        console.error(err);
        setRunState(row, { status: 'failed', runId, error: err.message || _('Unable to load status.') });
        stopPoller(key);
      }
    };

    poll();
  }

  async function triggerRun(linkId, row) {
    if (!topicUuid || !linkId) return;
    setRunState(row, { status: 'running' });
    try {
      const data = await api(`/api/topics/${topicUuid}/references/${linkId}/run`, { method: 'POST' });
      const runId = data?.id || data?.run_id || data?.uuid || null;
      const status = normalizeStatus(data?.status || data?.run_status || 'running');
      const error = data?.error || data?.error_message || null;
      const nextStatus = status === 'running' && !runId ? 'failed' : status;
      setRunState(row, { status: nextStatus, runId, error: error || (nextStatus === 'failed' && !runId ? _('Missing run identifier.') : null) });
      if (status === 'running' && runId) {
        schedulePoll(runId, row);
      }
    } catch (err) {
      console.error(err);
      setRunState(row, { status: 'failed', runId: null, error: err.message || _('Unable to fetch data.') });
    }
  }

  function handleAddToSection(button, row) {
    if (!button || !row) return;
    const runId = button.getAttribute('data-run-id');
    if (!runId) return;
    const detail = {
      topicUuid,
      runId,
      linkId: row.getAttribute('data-link-id') || null,
      referenceUuid: row.getAttribute('data-reference-uuid') || null,
    };
    const customEvent = new CustomEvent('reference:add-to-section', { detail });
    document.dispatchEvent(customEvent);
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
    const bits = [];
    if (item.domain) bits.push(item.domain);
    if (item.meta_published_at) bits.push(item.meta_published_at.split('T')[0]);
    meta.textContent = bits.join(' · ');
    content.appendChild(meta);

    const actions = document.createElement('div');
    actions.className = 'd-flex flex-column gap-1 align-items-end';

    const runBtn = document.createElement('button');
    runBtn.type = 'button';
    runBtn.className = 'btn btn-outline-primary btn-sm d-flex align-items-center gap-2';
    runBtn.dataset.referenceRun = 'true';
    runBtn.innerHTML = `
      <span class="spinner-border spinner-border-sm d-none" role="status" aria-hidden="true" data-reference-run-spinner></span>
      <span data-reference-run-label>${_('Fetch data')}</span>
    `;
    actions.appendChild(runBtn);

    const addBtn = document.createElement('button');
    addBtn.type = 'button';
    addBtn.className = 'btn btn-outline-secondary btn-sm d-none';
    addBtn.dataset.referenceAddSection = 'true';
    addBtn.disabled = true;
    addBtn.textContent = _('Add to topic section');
    actions.appendChild(addBtn);

    const runError = document.createElement('div');
    runError.className = 'text-danger small text-end d-none';
    runError.dataset.referenceRunError = 'true';
    actions.appendChild(runError);

    if (form) {
      const removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.className = 'btn btn-outline-danger btn-sm';
      removeBtn.dataset.removeReference = 'true';
      removeBtn.textContent = _('Remove');
      actions.appendChild(removeBtn);
    }

    el.appendChild(content);
    el.appendChild(actions);

    const runState = parseRunState(item);
    setRunState(el, runState);
    if (runState.status === 'running' && runState.runId) {
      schedulePoll(runState.runId, el);
    }
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
        return;
      }
      data.forEach((item) => listEl.appendChild(buildItem(item)));
    } catch (err) {
      console.error(err);
      renderEmptyState();
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

  if (listEl) {
    listEl.addEventListener('click', (event) => {
      const runBtn = event.target.closest('button[data-reference-run]');
      if (runBtn) {
        event.preventDefault();
        const row = runBtn.closest('[data-link-id]');
        const linkId = row?.getAttribute('data-link-id');
        triggerRun(linkId, row);
        return;
      }

      const addBtn = event.target.closest('button[data-reference-add-section]');
      if (addBtn && !addBtn.disabled) {
        event.preventDefault();
        const row = addBtn.closest('[data-link-id]');
        handleAddToSection(addBtn, row);
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

  loadReferences();
})();
