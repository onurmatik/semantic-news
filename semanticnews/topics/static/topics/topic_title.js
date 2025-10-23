function normalizeTitle(value, fallback = '') {
  const trimmed = typeof value === 'string' ? value.trim() : '';
  return trimmed || fallback;
}

document.addEventListener('DOMContentLoaded', () => {
  const topicEl = document.querySelector('[data-topic-uuid]');
  const displayEl = document.getElementById('topicTitleDisplay');
  const editToggle = document.getElementById('topicTitleEditToggle');
  const editorCard = document.getElementById('topicTitleEditor');
  const form = document.getElementById('topicTitleForm');
  const input = document.getElementById('topicTitleInput');
  const cancelBtn = document.getElementById('topicTitleCancelBtn');
  const errorEl = document.getElementById('editTopicTitleError');
  const suggestBtn = document.getElementById('topicTitleSuggestBtn');
  const suggestionsContainer = document.getElementById('topicTitleSuggestions');
  const suggestionsList = document.getElementById('topicTitleSuggestionsList');
  const untitledLabel = displayEl?.dataset?.untitled ?? '';

  if (!topicEl || !displayEl || !form || !input) {
    return;
  }

  const topicUuid = topicEl.dataset.topicUuid || '';

  const hideSuggestions = () => {
    if (suggestionsContainer) {
      suggestionsContainer.classList.add('d-none');
    }
    if (suggestionsList) {
      suggestionsList.innerHTML = '';
    }
  };

  const clearError = () => {
    if (errorEl) {
      errorEl.classList.add('d-none');
      errorEl.textContent = '';
    }
    form.classList.remove('was-validated');
    input.classList.remove('is-invalid');
  };

  const showError = (message) => {
    if (errorEl && message) {
      errorEl.textContent = message;
      errorEl.classList.remove('d-none');
      input.classList.add('is-invalid');
    }
  };

  const setDisplayTitle = (title) => {
    const normalized = normalizeTitle(title, untitledLabel);
    displayEl.textContent = normalized;
    document.title = normalized || document.title;
  };

  const getCurrentTitle = () => topicEl.dataset.topicTitle || '';

  const resetEditorValue = () => {
    input.value = getCurrentTitle();
    clearError();
    hideSuggestions();
  };

  const toggleEditor = (show) => {
    const shouldShow = show === undefined ? editorCard.classList.contains('d-none') : show;
    if (shouldShow) {
      editorCard.classList.remove('d-none');
      resetEditorValue();
      requestAnimationFrame(() => {
        input.focus();
        input.setSelectionRange(input.value.length, input.value.length);
      });
    } else {
      editorCard.classList.add('d-none');
      clearError();
      hideSuggestions();
    }
  };

  editToggle?.addEventListener('click', () => toggleEditor(true));
  cancelBtn?.addEventListener('click', () => {
    resetEditorValue();
    toggleEditor(false);
  });

  setDisplayTitle(getCurrentTitle());

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
        let message = 'Unable to update the topic title.';
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
        throw new Error(message);
      }

      const data = await response.json();
      const newTitle = data.title ?? '';
      topicEl.dataset.topicTitle = newTitle;
      if (typeof data.slug === 'string' && data.slug) {
        topicEl.dataset.topicSlug = data.slug;
      }

      setDisplayTitle(newTitle);
      toggleEditor(false);

      if (typeof data.edit_url === 'string' && data.edit_url && data.edit_url !== window.location.pathname) {
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

  if (suggestionsList) {
    suggestionsList.addEventListener('click', (event) => {
      const target = event.target;
      if (!(target instanceof HTMLElement)) {
        return;
      }
      const suggestion = target.dataset?.suggestion;
      if (!suggestion) {
        return;
      }
      input.value = suggestion;
      input.focus();
      const length = suggestion.length;
      if (typeof input.setSelectionRange === 'function') {
        input.setSelectionRange(length, length);
      }
    });
  }

  const suggestLabel = suggestBtn ? suggestBtn.querySelector('[data-topic-title-suggest-label]') : null;

  const setSuggestBtnLoading = (isLoading) => {
    if (!suggestBtn) return;
    const defaultLabel = suggestBtn.dataset.defaultLabel || (suggestLabel ? suggestLabel.textContent : '') || '';
    const loadingLabel = suggestBtn.dataset.loadingLabel || defaultLabel;
    suggestBtn.disabled = isLoading;
    if (suggestLabel) {
      suggestLabel.textContent = isLoading ? loadingLabel : defaultLabel;
    }
  };

  if (suggestBtn) {
    suggestBtn.addEventListener('click', async () => {
      const about = input.value.trim();
      clearError();
      hideSuggestions();
      setSuggestBtnLoading(true);

      try {
        const params = new URLSearchParams({ limit: '5' });
        if (about) {
          params.set('about', about);
        }
        if (topicUuid) {
          params.set('topic_uuid', topicUuid);
        }
        const response = await fetch(`/api/topics/suggest?${params.toString()}`);
        if (!response.ok) {
          throw new Error('Unable to fetch suggestions.');
        }
        const data = await response.json();
        if (!Array.isArray(data) || data.length === 0) {
          const message = suggestionsContainer?.dataset?.noResultsMessage;
          if (message && suggestionsList) {
            suggestionsList.innerHTML = '';
            const item = document.createElement('div');
            item.className = 'list-group-item text-body-secondary';
            item.textContent = message;
            suggestionsList.appendChild(item);
            suggestionsContainer.classList.remove('d-none');
          }
          return;
        }
        if (suggestionsList) {
          suggestionsList.innerHTML = '';
          data.forEach((suggestion) => {
            if (typeof suggestion !== 'string' || !suggestion.trim()) {
              return;
            }
            const button = document.createElement('button');
            button.type = 'button';
            button.className = 'list-group-item list-group-item-action';
            button.dataset.suggestion = suggestion;
            button.textContent = suggestion;
            suggestionsList.appendChild(button);
          });
          suggestionsContainer?.classList.remove('d-none');
        }
      } catch (error) {
        console.error(error);
        showError('Unable to fetch title suggestions.');
      } finally {
        setSuggestBtnLoading(false);
      }
    });
  }
});
