(function () {
  const extractErrorMessage = async (response, fallback = '') => {
    if (!response) {
      return fallback;
    }

    try {
      const data = await response.json();
      if (data && typeof data.detail === 'string' && data.detail.trim()) {
        return data.detail.trim();
      }
      if (Array.isArray(data) && data.length > 0) {
        return data.join(', ');
      }
    } catch (jsonError) {
      try {
        const text = await response.text();
        if (text && text.trim()) {
          return text.trim();
        }
      } catch (textError) {
        console.error(textError);
      }
    }

    return fallback;
  };

  document.addEventListener('DOMContentLoaded', () => {
    const modalEl = document.getElementById('createTopicModal');
    if (!modalEl) {
      return;
    }

    const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
    const form = modalEl.querySelector('#createTopicForm');
    const input = form?.querySelector('input[name="title"]') || null;
    const errorEl = modalEl.querySelector('#createTopicError');
    const suggestBtn = modalEl.querySelector('#createTopicSuggestBtn');
    const suggestionsContainer = modalEl.querySelector('#createTopicTitleSuggestions');
    const suggestionsList = modalEl.querySelector('#createTopicTitleSuggestionsList');
    const topicDatasetEl = document.querySelector('[data-topic-uuid]');
    const topicUuid = topicDatasetEl?.dataset?.topicUuid || '';
    const skipBtn = modalEl.querySelector('#createTopicSkipBtn');

    const currentUser = document.body?.dataset?.currentUser || '';
    let activeContext = { defaultTitle: '', eventUuid: '' };

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

    const setFormLoading = (isLoading) => {
      const submitBtn = form?.querySelector('button[type="submit"]');
      if (submitBtn) {
        submitBtn.disabled = isLoading;
      }
      if (skipBtn) {
        skipBtn.disabled = isLoading;
      }
      if (suggestBtn) {
        suggestBtn.disabled = isLoading;
      }
      if (input) {
        input.disabled = isLoading;
      }
    };

    const buildEditUrl = (topicUuid) => {
      if (currentUser) {
        return `/${currentUser}/${topicUuid}/edit/`;
      }
      return `/topics/${topicUuid}/`;
    };

    const handleCreate = async (titleValue) => {
      if (!form) {
        return;
      }

      clearError();
      hideSuggestions();
      setFormLoading(true);

      try {
        const createResponse = await fetch('/api/topics/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({}),
        });

        if (!createResponse.ok) {
          const message = await extractErrorMessage(createResponse, 'Unable to create topic.');
          throw new Error(message || 'Unable to create topic.');
        }

        const createData = await createResponse.json();
        const topicUuid = createData?.uuid;
        if (!topicUuid) {
          throw new Error('Unable to create topic.');
        }

        if (activeContext.eventUuid) {
          const eventResponse = await fetch('/api/topics/add-event', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              topic_uuid: topicUuid,
              event_uuid: activeContext.eventUuid,
            }),
          });

          if (!eventResponse.ok) {
            const message = await extractErrorMessage(eventResponse, 'Unable to link the selected event.');
            throw new Error(message || 'Unable to link the selected event.');
          }
        }

        if (titleValue.trim()) {
          const titleResponse = await fetch('/api/topics/set-title', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              topic_uuid: topicUuid,
              title: titleValue.trim(),
            }),
          });

          if (!titleResponse.ok) {
            const message = await extractErrorMessage(titleResponse, 'Unable to update the topic title.');
            throw new Error(message || 'Unable to update the topic title.');
          }

          const titleData = await titleResponse.json();
          const editUrl = titleData?.edit_url || buildEditUrl(topicUuid);
          window.location.href = editUrl;
          return;
        }

        window.location.href = buildEditUrl(topicUuid);
      } catch (error) {
        console.error(error);
        showError(error?.message || 'Unable to create topic.');
        setFormLoading(false);
        if (input) {
          input.disabled = false;
          input.focus();
        }
        if (suggestBtn) {
          resetSuggestBtn();
        }
      }
    };

    if (form) {
      form.addEventListener('submit', (event) => {
        event.preventDefault();
        const value = input ? input.value.trim() : '';
        handleCreate(value);
      });
    }

    if (skipBtn) {
      skipBtn.addEventListener('click', (event) => {
        event.preventDefault();
        handleCreate('');
      });
    }

    modalEl.addEventListener('show.bs.modal', () => {
      clearError();
      hideSuggestions();
      resetSuggestBtn();
      setFormLoading(false);

      if (input) {
        input.disabled = false;
        input.value = activeContext.defaultTitle || '';
        requestAnimationFrame(() => {
          input.focus();
          if (input.value) {
            const length = input.value.length;
            if (typeof input.setSelectionRange === 'function') {
              input.setSelectionRange(length, length);
            }
          }
        });
      }
    });

    modalEl.addEventListener('hidden.bs.modal', () => {
      hideSuggestions();
      clearError();
      setFormLoading(false);
      if (input) {
        input.value = '';
        input.disabled = false;
      }
      activeContext = { defaultTitle: '', eventUuid: '' };
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

    document.addEventListener('click', (event) => {
      const trigger = event.target instanceof HTMLElement
        ? event.target.closest('[data-topic-create]')
        : null;
      if (!trigger) {
        return;
      }

      event.preventDefault();

      activeContext = {
        defaultTitle: trigger.dataset.topicCreateDefaultTitle || '',
        eventUuid: trigger.dataset.topicCreateEventUuid || '',
      };

      if (modal) {
        modal.show();
      }
    });
  });
})();
