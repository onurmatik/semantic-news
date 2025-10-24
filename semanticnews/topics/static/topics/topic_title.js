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
  const untitledLabel = input?.dataset?.untitled ?? '';

  if (!topicEl || !form || !input) {
    return;
  }

  const topicUuid = topicEl.dataset.topicUuid || '';

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
    input.classList.remove('is-invalid');
    form.classList.remove('was-validated');
  };

  const showError = (message) => {
    if (errorEl && message) {
      errorEl.textContent = message;
      errorEl.classList.remove('d-none');
    }
    input.classList.add('is-invalid');
    form.classList.add('was-validated');
  };

  const setDocumentTitle = (title) => {
    const normalized = normalizeTitle(title, untitledLabel);
    if (normalized) {
      document.title = normalized;
    }
  };

  const getCurrentTitle = () => topicEl.dataset.topicTitle || '';

  const syncInputWithDataset = () => {
    const currentTitle = getCurrentTitle();
    input.value = currentTitle;
    setDocumentTitle(currentTitle);
  };

  syncInputWithDataset();

  input.addEventListener('input', () => {
    if (input.classList.contains('is-invalid')) {
      clearError();
    }
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    clearError();

    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) {
      submitBtn.disabled = true;
    }

    try {
      const payload = {
        topic_uuid: topicUuid,
        title: input.value.trim(),
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
      const newTitle = data.title ?? '';
      topicEl.dataset.topicTitle = newTitle;
      if (typeof data.slug === 'string' && data.slug) {
        topicEl.dataset.topicSlug = data.slug;
      }

      syncInputWithDataset();

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
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
      }
    }
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
        input.value = suggestion;
        input.focus();
        const length = suggestion.length;
        if (typeof input.setSelectionRange === 'function') {
          input.setSelectionRange(length, length);
        }
      } catch (error) {
        console.error(error);
        showError(error?.message || 'Unable to suggest a title.');
      } finally {
        suggestBtn.disabled = false;
      }
    });
  }
});
