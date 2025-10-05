document.addEventListener('DOMContentLoaded', () => {
  const container = document.querySelector('[data-topic-uuid]');
  if (!container) return;
  const topicUuid = container.getAttribute('data-topic-uuid');
  if (!topicUuid) return;

  const modalEl = document.getElementById('textModal');
  if (!modalEl) return;

  const getCsrfToken = () => {
    const name = 'csrftoken=';
    const cookies = document.cookie ? document.cookie.split(';') : [];
    for (let i = 0; i < cookies.length; i += 1) {
      const cookie = cookies[i].trim();
      if (cookie.startsWith(name)) {
        return decodeURIComponent(cookie.substring(name.length));
      }
    }
    return '';
  };

  const modal = window.bootstrap ? window.bootstrap.Modal.getOrCreateInstance(modalEl) : null;
  const form = document.getElementById('textForm');
  const textarea = document.getElementById('textContent');
  const textIdInput = document.getElementById('textId');
  const titleEl = modalEl.querySelector('[data-text-modal-title]');
  const saveBtn = document.getElementById('textSaveBtn');

  const confirmModalEl = document.getElementById('confirmDeleteTextModal');
  const confirmModal = confirmModalEl && window.bootstrap ? window.bootstrap.Modal.getOrCreateInstance(confirmModalEl) : null;
  const confirmBtn = document.getElementById('confirmDeleteTextBtn');
  const confirmSpinner = document.getElementById('confirmDeleteTextSpinner');

  const apiBase = `/api/topics/text`;

  const getLabel = (element, key, fallback) => {
    if (!element) return fallback;
    if (element.dataset && element.dataset[key]) {
      return element.dataset[key];
    }
    return fallback;
  };

  const setModalMode = (mode) => {
    if (!titleEl) return;
    if (mode === 'edit') {
      titleEl.textContent = getLabel(titleEl, 'editLabel', 'Edit text');
    } else {
      const initial = titleEl.dataset.initialLabel || titleEl.textContent;
      titleEl.textContent = getLabel(titleEl, 'createLabel', initial || 'Add text');
    }
  };

  if (titleEl) {
    titleEl.dataset.initialLabel = titleEl.textContent;
    const createLabelAttr = titleEl.getAttribute('data-create-label');
    if (createLabelAttr) {
      titleEl.dataset.createLabel = createLabelAttr;
      titleEl.textContent = createLabelAttr;
    }
    const editLabelAttr = titleEl.getAttribute('data-edit-label');
    if (editLabelAttr) {
      titleEl.dataset.editLabel = editLabelAttr;
    }
  }

  const openCreateModal = () => {
    if (textIdInput) textIdInput.value = '';
    if (textarea) textarea.value = '';
    setModalMode('create');
    modal && modal.show();
  };

  const openEditModal = (id, content) => {
    if (textIdInput) textIdInput.value = id;
    if (textarea) textarea.value = content || '';
    setModalMode('edit');
    modal && modal.show();
  };

  document.querySelectorAll('[data-action="create-text"]').forEach((btn) => {
    btn.addEventListener('click', (event) => {
      event.preventDefault();
      openCreateModal();
    });
  });

  document.addEventListener('click', (event) => {
    const editBtn = event.target.closest('[data-action="edit-text"]');
    if (editBtn) {
      event.preventDefault();
      const card = editBtn.closest('[data-text-card]');
      const textId = editBtn.getAttribute('data-text-id');
      const raw = card ? card.getAttribute('data-text-raw') : '';
      openEditModal(textId, raw || '');
      return;
    }

    const deleteBtn = event.target.closest('[data-action="delete-text"]');
    if (deleteBtn) {
      event.preventDefault();
      const textId = deleteBtn.getAttribute('data-text-id');
      confirmBtn && confirmBtn.setAttribute('data-text-id', textId || '');
      if (confirmModal) confirmModal.show();
    }
  });

  const submitForm = async (event) => {
    event.preventDefault();
    if (!textarea) return;
    const content = textarea.value || '';
    const textId = textIdInput ? textIdInput.value : '';
    const payload = textId ? { content } : { topic_uuid: topicUuid, content };
    const method = textId ? 'PUT' : 'POST';
    const url = textId ? `${apiBase}/${textId}` : `${apiBase}/create`;

    if (saveBtn) saveBtn.disabled = true;

    try {
      const res = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('Failed to save text');
      await res.json();
      modal && modal.hide();
      window.location.reload();
    } catch (error) {
      console.error(error);
      if (saveBtn) saveBtn.disabled = false;
    }
  };

  form && form.addEventListener('submit', submitForm);

  confirmBtn && confirmBtn.addEventListener('click', async () => {
    const textId = confirmBtn.getAttribute('data-text-id');
    if (!textId) return;
    confirmBtn.disabled = true;
    confirmSpinner && confirmSpinner.classList.remove('d-none');
    try {
      const res = await fetch(`${apiBase}/${textId}`, {
        method: 'DELETE',
        headers: {
          'X-CSRFToken': getCsrfToken(),
        },
      });
      if (!res.ok && res.status !== 204) throw new Error('Failed to delete text');
      window.location.reload();
    } catch (error) {
      console.error(error);
      confirmBtn.disabled = false;
      confirmSpinner && confirmSpinner.classList.add('d-none');
      if (confirmModal) confirmModal.hide();
    }
  });
});
