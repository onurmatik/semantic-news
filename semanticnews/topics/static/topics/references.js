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

  let pendingDeleteId = null;

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

  function buildItem(item) {
    const el = document.createElement('div');
    el.className = 'list-group-item d-flex gap-2 justify-content-between align-items-start';
    el.dataset.referenceItem = 'true';
    el.dataset.linkId = item.id;

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

    const openBtn = document.createElement('a');
    openBtn.className = 'btn btn-outline-secondary btn-sm';
    openBtn.href = item.url;
    openBtn.target = '_blank';
    openBtn.rel = 'noreferrer noopener';
    openBtn.textContent = _('Open');
    actions.appendChild(openBtn);

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
      const btn = event.target.closest('button[data-remove-reference]');
      if (!btn) return;
      event.preventDefault();
      const parent = btn.closest('[data-link-id]');
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

  loadReferences();
})();
