document.addEventListener('DOMContentLoaded', () => {
  const container = document.querySelector('[data-topic-uuid]');
  if (!container) return;
  const topicUuid = container.getAttribute('data-topic-uuid');
  if (!topicUuid) return;

  const apiBase = '/api/topics/text';
  const widgetList = document.querySelector('[data-topic-primary-widgets]');
  const cardTemplate = document.querySelector('template[data-text-card-template]');
  const reorderState = { pending: false };

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

  const normalize = (value) => {
    const base = typeof value === 'string' ? value : '';
    return base.replace(/\r\n/g, '\n');
  };

  const setStatus = (containerEl, textEl, spinnerEl, state) => {
    if (!containerEl || !textEl) return;
    const getLabel = (key, fallback) => {
      const value = textEl.dataset && textEl.dataset[key];
      return typeof value === 'string' && value.trim() ? value.trim() : fallback;
    };

    const classList = containerEl.classList;
    if (classList) {
      classList.remove('text-danger', 'text-warning', 'text-secondary');
      if (state === 'error') {
        classList.add('text-danger');
      } else if (state === 'dirty') {
        classList.add('text-warning');
      } else {
        classList.add('text-secondary');
      }
    }

    if (spinnerEl) {
      spinnerEl.classList.toggle('d-none', state !== 'saving');
    }

    if (state === 'saving') {
      textEl.textContent = getLabel('savingLabel', 'Saving…');
    } else if (state === 'dirty') {
      textEl.textContent = getLabel('dirtyLabel', 'Unsaved changes');
    } else if (state === 'error') {
      textEl.textContent = getLabel('errorLabel', 'Unable to save');
    } else {
      textEl.textContent = getLabel('savedLabel', 'Saved');
    }
  };

  const showError = (el, message, statusText) => {
    if (!el) return;
    const fallback = statusText && statusText.dataset
      ? statusText.dataset.errorMessage
      : '';
    const resolved = typeof message === 'string' && message.trim()
      ? message.trim()
      : (fallback || 'Unable to save changes. Please try again.');
    el.textContent = resolved;
    el.classList.remove('d-none');
  };

  const clearError = (el) => {
    if (!el) return;
    el.textContent = '';
    el.classList.add('d-none');
  };

  const setupCard = (card) => {
    if (!(card instanceof HTMLElement)) return;
    const textId = card.getAttribute('data-text-id');
    if (!textId) return;

    const textarea = card.querySelector('[data-text-editor]');
    if (!textarea) return;

    const statusContainer = card.querySelector('[data-text-status]');
    const statusText = card.querySelector('[data-text-status-text]');
    const statusSpinner = card.querySelector('[data-text-status-spinner]');
    const errorEl = card.querySelector('[data-text-error]');

    const easyMDE = window.EasyMDE
      ? new EasyMDE({
          element: textarea,
          autoDownloadFontAwesome: false,
          spellChecker: false,
          status: false,
        })
      : null;

    if (easyMDE) {
      textarea._easyMDE = easyMDE; // eslint-disable-line no-underscore-dangle
    }

    const getValue = () => {
      if (easyMDE) {
        return easyMDE.value();
      }
      return textarea.value || '';
    };

    const setValue = (value) => {
      const next = value || '';
      if (easyMDE) {
        easyMDE.value(next);
      } else {
        textarea.value = next;
      }
    };

    const updateDataAttr = (value) => {
      card.setAttribute('data-text-raw', value || '');
    };

    let lastSaved = normalize(getValue());
    let saveTimer = null;
    let saving = false;

    setStatus(statusContainer, statusText, statusSpinner, 'saved');

    const saveContent = async () => {
      if (saving) return;
      const currentValue = normalize(getValue());
      if (currentValue === lastSaved) {
        setStatus(statusContainer, statusText, statusSpinner, 'saved');
        return;
      }

      saving = true;
      setStatus(statusContainer, statusText, statusSpinner, 'saving');
      clearError(errorEl);

      try {
        const res = await fetch(apiBase + '/' + textId, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify({ content: getValue() }),
        });
        if (!res.ok) {
          throw new Error('Failed to save text');
        }
        await res.json();
        lastSaved = normalize(getValue());
        updateDataAttr(getValue());
        setStatus(statusContainer, statusText, statusSpinner, 'saved');
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error(error);
        setStatus(statusContainer, statusText, statusSpinner, 'error');
        showError(errorEl, error && error.message, statusText);
      } finally {
        saving = false;
      }
    };

    const scheduleSave = () => {
      if (saveTimer) {
        window.clearTimeout(saveTimer);
      }
      const currentValue = normalize(getValue());
      if (currentValue === lastSaved) {
        setStatus(statusContainer, statusText, statusSpinner, 'saved');
        return;
      }
      setStatus(statusContainer, statusText, statusSpinner, 'dirty');
      saveTimer = window.setTimeout(saveContent, 1500);
    };

    const handleChange = () => {
      clearError(errorEl);
      scheduleSave();
    };

    if (easyMDE && easyMDE.codemirror) {
      easyMDE.codemirror.on('change', handleChange);
      window.setTimeout(() => {
        if (easyMDE.codemirror && typeof easyMDE.codemirror.refresh === 'function') {
          easyMDE.codemirror.refresh();
        }
      }, 0);
    } else {
      textarea.addEventListener('input', handleChange);
    }

    card.addEventListener('text:save-now', () => {
      if (saveTimer) {
        window.clearTimeout(saveTimer);
        saveTimer = null;
      }
      saveContent();
    });

    const handleTransform = (button, mode) => {
      if (!button || !mode) return;
      const defaultLabel = button.textContent;
      const loadingLabel = button.dataset.loadingLabel || defaultLabel;

      button.addEventListener('click', async (event) => {
        event.preventDefault();
        const content = getValue().trim();
        if (!content) {
          return;
        }

        button.disabled = true;
        button.dataset.defaultLabel = defaultLabel;
        button.textContent = loadingLabel;
        button.setAttribute('aria-busy', 'true');

        try {
          const res = await fetch(apiBase + '/' + mode, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-CSRFToken': getCsrfToken(),
            },
            body: JSON.stringify({
              topic_uuid: topicUuid,
              content,
            }),
          });
          if (!res.ok) {
            throw new Error('Failed to transform text');
          }
          const data = await res.json();
          if (data && typeof data.content === 'string') {
            setValue(data.content);
            handleChange();
          }
        } catch (error) {
          // eslint-disable-next-line no-console
          console.error(error);
          showError(errorEl, error && error.message, statusText);
        } finally {
          button.disabled = false;
          button.textContent = button.dataset.defaultLabel || defaultLabel;
          button.removeAttribute('aria-busy');
        }
      });
    };

    card.querySelectorAll('[data-text-transform]').forEach((button) => {
      handleTransform(button, button.dataset.textTransform);
    });
  };

  document.querySelectorAll('[data-text-card]').forEach((card) => {
    setupCard(card);
  });

  const getTextEntries = () => {
    if (!widgetList) return [];
    return Array.from(widgetList.querySelectorAll('[data-topic-widget-entry]'))
      .filter((entry) => entry.dataset && entry.dataset.topicWidget === 'text');
  };

  const updateMoveButtonStates = () => {
    const entries = getTextEntries();
    const lastIndex = entries.length - 1;
    entries.forEach((entry, index) => {
      const upButton = entry.querySelector('[data-action="move-text-up"]');
      const downButton = entry.querySelector('[data-action="move-text-down"]');
      const disableUp = reorderState.pending || index <= 0;
      const disableDown = reorderState.pending || index >= lastIndex;
      if (upButton) {
        upButton.disabled = disableUp;
        if (disableUp) {
          upButton.setAttribute('aria-disabled', 'true');
        } else {
          upButton.removeAttribute('aria-disabled');
        }
      }
      if (downButton) {
        downButton.disabled = disableDown;
        if (disableDown) {
          downButton.setAttribute('aria-disabled', 'true');
        } else {
          downButton.removeAttribute('aria-disabled');
        }
      }
    });
  };

  const captureWidgetOrder = () => {
    if (!widgetList) return [];
    return Array.from(widgetList.children);
  };

  const restoreWidgetOrder = (snapshot) => {
    if (!widgetList || !Array.isArray(snapshot)) return;
    snapshot.forEach((node) => {
      if (node && node.parentNode === widgetList) {
        widgetList.appendChild(node);
      }
    });
  };

  const persistTextOrder = async () => {
    if (!widgetList) return;
    const entries = getTextEntries();
    if (!entries.length) return;

    const items = [];
    let missingId = false;

    entries.forEach((entry, index) => {
      const card = entry.querySelector('[data-text-card]');
      const textId = card && card.dataset ? card.dataset.textId : null;
      const numericId = textId ? parseInt(textId, 10) : NaN;
      if (!numericId || Number.isNaN(numericId)) {
        missingId = true;
        return;
      }
      items.push({ id: numericId, display_order: index });
    });

    if (missingId || !items.length) {
      throw new Error('Unable to determine text card identifiers');
    }

    const res = await fetch(apiBase + '/reorder', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken(),
      },
      body: JSON.stringify({
        topic_uuid: topicUuid,
        items,
      }),
    });

    if (!res.ok) {
      throw new Error('Failed to reorder text cards');
    }
  };

  const moveEntry = (entry, direction) => {
    if (!widgetList || !entry) return false;
    const entries = getTextEntries();
    const index = entries.indexOf(entry);
    if (index === -1) {
      return false;
    }

    if (direction === 'up' && index > 0) {
      const previousEntry = entries[index - 1];
      if (previousEntry) {
        widgetList.insertBefore(entry, previousEntry);
        return true;
      }
    }

    if (direction === 'down' && index < entries.length - 1) {
      const nextEntry = entries[index + 1];
      if (nextEntry) {
        widgetList.insertBefore(entry, nextEntry.nextSibling);
        return true;
      }
    }

    return false;
  };

  updateMoveButtonStates();

  const focusEditor = (card) => {
    if (!card) return;
    const textarea = card.querySelector('[data-text-editor]');
    if (!textarea) return;
    if (textarea._easyMDE && textarea._easyMDE.codemirror) {
      textarea._easyMDE.codemirror.focus();
    } else {
      textarea.focus();
    }
  }

  const createModuleFromTemplate = (data) => {
    if (!cardTemplate) return null;
    const fragment = cardTemplate.content
      ? cardTemplate.content.cloneNode(true)
      : null;
    if (!fragment) return null;
    const entry = fragment.querySelector('[data-topic-widget-entry]');
    const card = fragment.querySelector('[data-text-card]');
    if (!entry || !card) return null;

    const moduleKey = data.module_key || 'text:' + data.id;
    const content = data.content || '';

    entry.dataset.topicWidget = 'text';
    entry.dataset.topicWidgetKey = moduleKey;

    const deleteBtn = entry.querySelector('[data-action="delete-text"]');
    if (deleteBtn) {
      deleteBtn.setAttribute('data-text-id', data.id);
    }

    card.setAttribute('data-text-id', data.id);
    card.dataset.textId = String(data.id);
    card.setAttribute('data-module-key', moduleKey);
    card.dataset.moduleKey = moduleKey;
    card.setAttribute('data-text-raw', content);
    card.dataset.textRaw = content;

    const textarea = card.querySelector('[data-text-editor]');
    if (textarea) {
      textarea.value = content;
    }

    return entry;
  };

  const insertModule = (entryEl) => {
    if (!widgetList) return;
    widgetList.appendChild(entryEl);
    document.dispatchEvent(new CustomEvent('topic:changed'));
    updateMoveButtonStates();
  };

  document.querySelectorAll('[data-action="create-text"]').forEach((button) => {
    button.addEventListener('click', async (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      if (button.disabled) return;

      button.disabled = true;
      button.setAttribute('aria-busy', 'true');

      try {
        const res = await fetch(apiBase + '/create', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify({ topic_uuid: topicUuid, content: '' }),
        });
        if (!res.ok) {
          throw new Error('Failed to create text block');
        }
        const data = await res.json();
        if (!widgetList || !cardTemplate) {
          window.location.reload();
          return;
        }
        const entry = createModuleFromTemplate(data);
        if (!entry) {
          window.location.reload();
          return;
        }
        insertModule(entry);
        const card = entry.querySelector('[data-text-card]');
        if (card) {
          setupCard(card);
          window.setTimeout(() => {
            focusEditor(card);
          }, 0);
          updateMoveButtonStates();
        }
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error(error);
      } finally {
        button.disabled = false;
        button.removeAttribute('aria-busy');
      }
    });
  });

  const confirmModalEl = document.getElementById('confirmDeleteTextModal');
  const confirmModal = confirmModalEl && window.bootstrap
    ? window.bootstrap.Modal.getOrCreateInstance(confirmModalEl)
    : null;
  const confirmBtn = document.getElementById('confirmDeleteTextBtn');
  const confirmSpinner = document.getElementById('confirmDeleteTextSpinner');

  const performDeleteRequest = (textId) => fetch(apiBase + '/' + textId, {
    method: 'DELETE',
    headers: {
      'X-CSRFToken': getCsrfToken(),
    },
  }).then((res) => {
    if (!res.ok && res.status !== 204) {
      throw new Error('Failed to delete text');
    }
    window.location.reload();
  });

  const cardHasContent = (card) => {
    if (!card) return false;
    const valuesToCheck = [];

    const textarea = card.querySelector('[data-text-editor]');
    if (textarea) {
      if (textarea._easyMDE && typeof textarea._easyMDE.value === 'function') { // eslint-disable-line no-underscore-dangle
        valuesToCheck.push(textarea._easyMDE.value());
      } else if (typeof textarea.value === 'string') {
        valuesToCheck.push(textarea.value);
      }
    }

    if (card.dataset && typeof card.dataset.textRaw === 'string') {
      valuesToCheck.push(card.dataset.textRaw);
    }

    return valuesToCheck.some((value) => normalize(value || '').trim().length > 0);
  };

  document.addEventListener('click', (event) => {
    if (!(event.target instanceof Element)) {
      return;
    }

    const moveButton = event.target.closest('[data-action="move-text-up"], [data-action="move-text-down"]');
    if (moveButton) {
      if (!widgetList) {
        return;
      }
      event.preventDefault();
      if (reorderState.pending) {
        return;
      }

      const entry = moveButton.closest('[data-topic-widget-entry]');
      if (!entry || entry.dataset.topicWidget !== 'text') {
        return;
      }

      const direction = moveButton.matches('[data-action="move-text-up"]') ? 'up' : 'down';
      const snapshot = captureWidgetOrder();
      const moved = moveEntry(entry, direction);
      if (!moved) {
        updateMoveButtonStates();
        return;
      }

      reorderState.pending = true;
      updateMoveButtonStates();

      persistTextOrder()
        .then(() => {
          document.dispatchEvent(new CustomEvent('topic:changed'));
        })
        .catch((error) => {
          // eslint-disable-next-line no-console
          console.error(error);
          restoreWidgetOrder(snapshot);
          const card = entry.querySelector('[data-text-card]');
          const errorEl = card ? card.querySelector('[data-text-error]') : null;
          const message = card && card.dataset && card.dataset.reorderErrorMessage
            ? card.dataset.reorderErrorMessage
            : 'Unable to reorder text cards. Please try again.';
          showError(errorEl, message, null);
        })
        .finally(() => {
          reorderState.pending = false;
          updateMoveButtonStates();
          window.requestAnimationFrame(() => {
            if (typeof moveButton.focus === 'function') {
              moveButton.focus();
            }
          });
        });
      return;
    }

    const deleteBtn = event.target.closest('[data-action="delete-text"]');
    if (!deleteBtn) return;
    event.preventDefault();
    const textId = deleteBtn.getAttribute('data-text-id');
    if (!textId) {
      return;
    }

    const card = deleteBtn.closest('[data-text-card]');
    if (card && !cardHasContent(card)) {
      deleteBtn.disabled = true;
      deleteBtn.setAttribute('aria-busy', 'true');
      performDeleteRequest(textId)
        .catch((error) => {
          // eslint-disable-next-line no-console
          console.error(error);
          deleteBtn.disabled = false;
          deleteBtn.removeAttribute('aria-busy');
        });
      return;
    }

    if (confirmBtn) {
      confirmBtn.setAttribute('data-text-id', textId || '');
    }
    if (confirmModal) {
      confirmModal.show();
    }
  });

  if (confirmBtn) {
    confirmBtn.addEventListener('click', (event) => {
      event.preventDefault();
      const textId = confirmBtn.getAttribute('data-text-id');
      if (!textId) return;

      confirmBtn.disabled = true;
      if (confirmSpinner) {
        confirmSpinner.classList.remove('d-none');
      }

      const finishFailureState = () => {
        confirmBtn.disabled = false;
        if (confirmSpinner) {
          confirmSpinner.classList.add('d-none');
        }
      };

      performDeleteRequest(textId)
        .catch((error) => {
          // eslint-disable-next-line no-console
          console.error(error);
          finishFailureState();
          if (confirmModal) {
            confirmModal.hide();
          }
        });
    });
  }
});
