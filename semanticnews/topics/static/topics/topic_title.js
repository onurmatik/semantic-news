function normalizeTitle(value, fallback = '') {
  const trimmed = typeof value === 'string' ? value.trim() : '';
  return trimmed || fallback;
}

document.addEventListener('DOMContentLoaded', () => {
  const topicEl = document.querySelector('[data-topic-uuid]');
  const form = document.getElementById('topicTitleForm');
  const input = document.getElementById('topicTitleInput');
  const errorEl = document.getElementById('editTopicTitleError');
  const suggestBtn = document.getElementById('topicTitleSuggestBtn');
  const statusIcon = document.getElementById('topicTitleStatusIcon');
  const statusText = document.getElementById('topicTitleStatusText');
  const untitledLabel = input?.dataset?.untitled ?? '';

  if (!topicEl || !form || !input) {
    return;
  }

  const topicUuid = topicEl.dataset.topicUuid || '';
  const maxLength = Number.parseInt(input.dataset.maxlength ?? '0', 10) || 0;
  let isSaving = false;
  let pendingTitle = null;
  let inFlightTitle = null;
  let statusResetTimeout = null;

  const messageIdle = statusText?.dataset?.messageIdle || 'Title ready to edit.';
  const messageSaving = statusText?.dataset?.messageSaving || 'Saving title…';
  const messageSuccess = statusText?.dataset?.messageSuccess || 'Title saved.';
  const messageError = statusText?.dataset?.messageError || 'Unable to update the topic title.';

  const STATUS_STATES = {
    idle: {
      iconClass: 'bi bi-pencil text-secondary',
      message: messageIdle,
    },
    saving: {
      iconClass: 'spinner-border spinner-border-sm text-secondary',
      message: messageSaving,
    },
    success: {
      iconClass: 'bi bi-check-lg text-success',
      message: messageSuccess,
    },
    error: {
      iconClass: 'bi bi-x-lg text-danger',
      message: messageError,
    },
  };

  const updateStatus = (state, overrideMessage) => {
    const status = STATUS_STATES[state] ?? STATUS_STATES.idle;
    if (statusIcon) {
      statusIcon.className = status.iconClass;
    }
    if (statusText) {
      statusText.textContent = overrideMessage || status.message;
    }

    if (statusResetTimeout) {
      window.clearTimeout(statusResetTimeout);
      statusResetTimeout = null;
    }

    if (state === 'success' || state === 'error') {
      statusResetTimeout = window.setTimeout(() => {
        updateStatus('idle');
      }, 4000);
    }
  };

  const readResponseMessage = async (response, fallback) => {
    let message = fallback;
    try {
      const data = await response.json();
      if (typeof data?.detail === 'string' && data.detail.trim()) {
        message = data.detail.trim();
      }
    } catch (jsonError) {
      try {
        const text = await response.text();
        if (text && text.trim()) {
          message = text.trim();
        }
      } catch (textError) {
        console.error(textError);
      }
    }
    return message;
  };

  const clearError = () => {
    if (errorEl) {
      errorEl.classList.add('d-none');
      errorEl.textContent = '';
    }
    input.classList.remove('border-danger');
    input.classList.add('border-dark-subtle');
    form.classList.remove('was-validated');
  };

  const showError = (message) => {
    if (errorEl && message) {
      errorEl.textContent = message;
      errorEl.classList.remove('d-none');
    }
    input.classList.remove('border-dark-subtle');
    input.classList.add('border-danger');
    form.classList.add('was-validated');
  };

  const setDocumentTitle = (title) => {
    const normalized = normalizeTitle(title, untitledLabel);
    if (normalized) {
      document.title = normalized;
    }
  };

  const getCurrentTitle = () => topicEl.dataset.topicTitle || '';

  const applyPlaceholder = () => {
    if (!untitledLabel) {
      input.textContent = '';
      input.dataset.placeholderActive = 'false';
      input.classList.remove('text-secondary');
      return;
    }
    input.textContent = untitledLabel;
    input.dataset.placeholderActive = 'true';
    input.classList.add('text-secondary');
  };

  const clearPlaceholder = () => {
    if (input.dataset.placeholderActive === 'true') {
      input.textContent = '';
      input.dataset.placeholderActive = 'false';
      input.classList.remove('text-secondary');
    }
  };

  const syncInputWithDataset = () => {
    const currentTitle = getCurrentTitle();
    if (currentTitle) {
      input.textContent = currentTitle;
      input.dataset.placeholderActive = 'false';
      input.classList.remove('text-secondary');
    } else {
      applyPlaceholder();
    }
    setDocumentTitle(currentTitle);
  };

  syncInputWithDataset();

  const getInputValue = () =>
    input.dataset.placeholderActive === 'true' ? '' : input.textContent.trim();

  const enforceMaxLength = () => {
    if (!maxLength) {
      return;
    }
    const value = input.textContent ?? '';
    if (value.length > maxLength) {
      input.textContent = value.slice(0, maxLength);
      const range = document.createRange();
      const selection = window.getSelection();
      range.selectNodeContents(input);
      range.collapse(false);
      selection?.removeAllRanges();
      selection?.addRange(range);
    }
  };

  const processPendingSave = async () => {
    if (isSaving) {
      return;
    }

    const nextTitle = pendingTitle;
    if (nextTitle === null) {
      return;
    }

    const currentTitle = getCurrentTitle();
    if (nextTitle === currentTitle) {
      pendingTitle = null;
      return;
    }

    pendingTitle = null;
    inFlightTitle = nextTitle;
    clearError();
    updateStatus('saving');
    isSaving = true;

    try {
      const payload = {
        topic_uuid: topicUuid,
        title: nextTitle,
      };
      const response = await fetch('/api/topics/set-title', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const message = await readResponseMessage(
          response,
          'Unable to update the topic title.'
        );
        throw new Error(message);
      }

      const data = await response.json();
      const updatedTitle = data.title ?? '';
      topicEl.dataset.topicTitle = updatedTitle;
      if (typeof data.slug === 'string' && data.slug) {
        topicEl.dataset.topicSlug = data.slug;
      }

      syncInputWithDataset();
      updateStatus('success');

      if (
        typeof data.edit_url === 'string' &&
        data.edit_url &&
        data.edit_url !== window.location.pathname
      ) {
        window.location.href = data.edit_url;
      }
    } catch (error) {
      console.error(error);
      showError(error?.message || 'Unable to update the topic title.');
      updateStatus('error', error?.message);
    } finally {
      isSaving = false;
      inFlightTitle = null;
      if (pendingTitle !== null) {
        void processPendingSave();
      }
    }
  };

  const queueTitleSave = () => {
    const newTitle = getInputValue();
    const baselineTitle =
      pendingTitle ?? inFlightTitle ?? getCurrentTitle();

    if (newTitle === baselineTitle) {
      return;
    }

    pendingTitle = newTitle;
    void processPendingSave();
  };

  input.addEventListener('focus', () => {
    clearPlaceholder();
  });

  input.addEventListener('blur', () => {
    const value = getInputValue();
    if (!value) {
      applyPlaceholder();
    }
    queueTitleSave();
  });

  input.addEventListener('input', () => {
    enforceMaxLength();
    clearError();
  });

  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      input.blur();
    }
  });

  form.addEventListener('submit', (event) => {
    event.preventDefault();
  });

  if (suggestBtn) {
    suggestBtn.addEventListener('click', async () => {
      clearError();
      suggestBtn.disabled = true;

      try {
        const params = new URLSearchParams({ limit: '1' });
        if (topicUuid) {
          params.set('topic_uuid', topicUuid);
        }
        const response = await fetch(`/api/topics/suggest?${params.toString()}`);
        if (!response.ok) {
          const message = await readResponseMessage(
            response,
            'Unable to suggest a title.'
          );
          throw new Error(message);
        }
        const data = await response.json();
        if (!Array.isArray(data) || data.length === 0) {
          showError('No suggestions available yet.');
          return;
        }
        const suggestion = data.find((item) => typeof item === 'string' && item.trim());
        if (!suggestion) {
          showError('No suggestions available yet.');
          return;
        }
        clearPlaceholder();
        input.textContent = suggestion;
        input.focus();
        const length = suggestion.length;
        const range = document.createRange();
        const selection = window.getSelection();
        if (selection) {
          range.selectNodeContents(input);
          range.collapse(false);
          selection.removeAllRanges();
          selection.addRange(range);
        }
      } catch (error) {
        console.error(error);
        showError(error?.message || 'Unable to suggest a title.');
        updateStatus('error', error?.message || 'Unable to suggest a title.');
      } finally {
        suggestBtn.disabled = false;
      }
    });
  }

  updateStatus('idle');
});
