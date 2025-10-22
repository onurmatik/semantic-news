document.addEventListener('DOMContentLoaded', () => {
  const modalEl = document.getElementById('editTopicTitleModal');
  const topicEl = document.querySelector('[data-topic-uuid]');
  if (!modalEl || !topicEl) {
    return;
  }

  const form = modalEl.querySelector('form');
  if (!form) {
    return;
  }

  const input = form.querySelector('input[name="title"]');
  const errorEl = modalEl.querySelector('#editTopicTitleError');
  const displayEl = document.getElementById('topicTitleDisplay');
  const untitledLabel = displayEl?.dataset.untitled ?? '';
  const suggestBtn = modalEl.querySelector('#topicTitleSuggestBtn');
  const suggestionsContainer = modalEl.querySelector('#topicTitleSuggestions');
  const suggestionsList = modalEl.querySelector('#topicTitleSuggestionsList');
  const topicUuid = topicEl.dataset.topicUuid || '';
  const formatDisplayTitle = (rawTitle) => {
    const trimmedTitle = typeof rawTitle === 'string' ? rawTitle.trim() : '';
    if (trimmedTitle) {
      return trimmedTitle;
    }
    return untitledLabel || '';
  };

  const setDisplayTitle = (rawTitle) => {
    const formatted = formatDisplayTitle(rawTitle);
    if (displayEl) {
      displayEl.textContent = formatted;
    }
    if (formatted) {
      document.title = formatted;
    }
  };

  const clearError = () => {
    if (errorEl) {
      errorEl.classList.add('d-none');
      errorEl.textContent = '';
    }
  };

  const showError = (message) => {
    if (errorEl && message) {
      errorEl.textContent = message;
      errorEl.classList.remove('d-none');
    }
  };

  const resetSuggestBtn = () => {
    if (!suggestBtn) {
      return;
    }
    suggestBtn.disabled = false;
    const defaultLabel = suggestBtn.dataset.defaultLabel || suggestBtn.textContent || '';
    if (defaultLabel) {
      suggestBtn.textContent = defaultLabel;
    }
  };

  const setSuggestBtnLoading = (isLoading) => {
    if (!suggestBtn) {
      return;
    }
    suggestBtn.disabled = isLoading;
    const label = isLoading
      ? suggestBtn.dataset.loadingLabel || suggestBtn.dataset.defaultLabel || ''
      : suggestBtn.dataset.defaultLabel || '';
    if (label) {
      suggestBtn.textContent = label;
    }
  };

  const hideSuggestions = () => {
    if (suggestionsContainer) {
      suggestionsContainer.classList.add('d-none');
    }
    if (suggestionsList) {
      suggestionsList.innerHTML = '';
    }
  };

  const renderSuggestions = (suggestions) => {
    if (!suggestionsContainer || !suggestionsList) {
      return;
    }

    suggestionsList.innerHTML = '';

    if (!Array.isArray(suggestions) || suggestions.length === 0) {
      const message = suggestionsContainer.dataset.noResultsMessage || '';
      if (message) {
        const item = document.createElement('div');
        item.className = 'list-group-item text-body-secondary';
        item.textContent = message;
        suggestionsList.appendChild(item);
        suggestionsContainer.classList.remove('d-none');
      } else {
        hideSuggestions();
      }
      return;
    }

    suggestions.forEach((suggestion) => {
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

    if (suggestionsList.childElementCount > 0) {
      suggestionsContainer.classList.remove('d-none');
    } else {
      hideSuggestions();
    }
  };

  modalEl.addEventListener('show.bs.modal', () => {
    clearError();
    hideSuggestions();
    resetSuggestBtn();
    if (input) {
      input.value = topicEl.dataset.topicTitle ?? '';
      requestAnimationFrame(() => {
        input.focus();
        input.select();
      });
    }
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!input) {
      return;
    }

    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) {
      submitBtn.disabled = true;
    }
    clearError();

    const payload = {
      topic_uuid: topicEl.dataset.topicUuid,
      title: input.value.trim(),
    };

    try {
      const response = await fetch('/api/topics/set-title', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        let message = 'Unable to update the topic title.';
        try {
          const errorData = await response.json();
          if (typeof errorData?.detail === 'string' && errorData.detail.trim()) {
            message = errorData.detail;
          }
        } catch (jsonError) {
          const text = await response.text();
          if (text.trim()) {
            message = text;
          }
        }
        throw new Error(message);
      }

      const data = await response.json();
      const newTitle = data.title ?? '';
      topicEl.dataset.topicTitle = newTitle;

      setDisplayTitle(newTitle);

      const modalInstance =
        bootstrap.Modal.getInstance(modalEl) ||
        bootstrap.Modal.getOrCreateInstance(modalEl);
      if (typeof data.slug === 'string' && data.slug) {
        topicEl.dataset.topicSlug = data.slug;
      }

      if (typeof data.edit_url === 'string' && data.edit_url && data.edit_url !== window.location.pathname) {
        window.location.href = data.edit_url;
        return;
      }

      if (modalInstance) {
        modalInstance.hide();
      }
    } catch (error) {
      console.error(error);
      if (errorEl) {
        errorEl.textContent = error.message || 'Unable to update the topic title.';
        errorEl.classList.remove('d-none');
      }
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
      if (!suggestion || !input) {
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

  if (suggestBtn && input) {
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
          let message = suggestBtn.dataset.genericErrorMessage || '';
          try {
            const raw = await response.text();
            if (raw) {
              try {
                const data = JSON.parse(raw);
                if (typeof data?.detail === 'string' && data.detail.trim()) {
                  message = data.detail;
                } else if (Array.isArray(data) && data.length > 0) {
                  renderSuggestions(data);
                  return;
                }
              } catch (parseError) {
                if (raw.trim()) {
                  message = raw;
                }
              }
            }
          } catch (readError) {
            console.error(readError);
          }
          throw new Error(message || '');
        }

        const data = await response.json();
        renderSuggestions(Array.isArray(data) ? data : []);
      } catch (error) {
        console.error(error);
        const message =
          (error && typeof error.message === 'string' && error.message.trim())
            ? error.message
            : suggestBtn.dataset.genericErrorMessage || '';
        if (message) {
          showError(message);
        }
      } finally {
        setSuggestBtnLoading(false);
      }
    });
  }
});
