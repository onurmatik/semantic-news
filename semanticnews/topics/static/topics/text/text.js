document.addEventListener('DOMContentLoaded', () => {
  const container = document.querySelector('[data-topic-uuid]');
  if (!container) return;
  const topicUuid = container.getAttribute('data-topic-uuid');
  if (!topicUuid) return;

  const apiBase = '/api/topics/text';
  const layoutRoot = document.querySelector('[data-topic-layout]');
  const moduleList = layoutRoot
    ? layoutRoot.querySelector('[data-layout-list]')
    : null;
  const cardTemplate = document.querySelector('template[data-text-card-template]');

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

  const renumberModules = () => {
    if (!moduleList) return;
    const modules = moduleList.querySelectorAll('[data-layout-reorderable="true"]');
    modules.forEach((moduleEl, index) => {
      moduleEl.dataset.displayOrder = String(index);
    });
  };

  const focusEditor = (card) => {
    if (!card) return;
    const textarea = card.querySelector('[data-text-editor]');
    if (!textarea) return;
    if (textarea._easyMDE && textarea._easyMDE.codemirror) {
      textarea._easyMDE.codemirror.focus();
    } else {
      textarea.focus();
    }

  const createModuleFromTemplate = (data) => {
    if (!cardTemplate) return null;
    const fragment = cardTemplate.content
      ? cardTemplate.content.cloneNode(true)
      : null;
    if (!fragment) return null;
    const moduleEl = fragment.querySelector('.topic-module-wrapper');
    const card = fragment.querySelector('[data-text-card]');
    if (!moduleEl || !card) return null;

    const moduleKey = data.module_key || 'text:' + data.id;
    const placement = data.placement || 'primary';
    const displayOrder = typeof data.display_order === 'number'
      ? data.display_order
      : Number.MAX_SAFE_INTEGER;
    const content = data.content || '';

    moduleEl.dataset.module = moduleKey;
    moduleEl.dataset.baseModule = 'text';
    moduleEl.dataset.placement = placement;
    moduleEl.dataset.displayOrder = String(displayOrder);
    moduleEl.dataset.hasContent = content.trim() ? 'true' : 'false';

    const deleteBtn = moduleEl.querySelector('[data-action="delete-text"]');
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

    return moduleEl;
  };

  const insertModule = (moduleEl, data) => {
    if (!moduleList) return;
    const displayOrder = typeof data.display_order === 'number'
      ? data.display_order
      : Number.MAX_SAFE_INTEGER;
    const reorderable = Array.from(moduleList.querySelectorAll('[data-layout-reorderable="true"]'));
    const insertBeforeTarget = reorderable.find((el) => {
      const currentOrder = Number.parseInt(el.dataset.displayOrder || '0', 10);
      return Number.isFinite(currentOrder) && currentOrder > displayOrder;
    });
    if (insertBeforeTarget) {
      moduleList.insertBefore(moduleEl, insertBeforeTarget);
    } else {
      moduleList.appendChild(moduleEl);
    }
    renumberModules();
    if (layoutRoot) {
      layoutRoot.dispatchEvent(new CustomEvent('topicLayout:addModule', { detail: moduleEl }));
      layoutRoot.dispatchEvent(new CustomEvent('topicLayout:save'));
    }
    document.dispatchEvent(new CustomEvent('topic:changed'));
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
        if (!moduleList || !cardTemplate) {
          window.location.reload();
          return;
        }
        const moduleEl = createModuleFromTemplate(data);
        if (!moduleEl) {
          window.location.reload();
          return;
        }
        insertModule(moduleEl, data);
        const card = moduleEl.querySelector('[data-text-card]');
        if (card) {
          setupCard(card);
          window.setTimeout(() => {
            focusEditor(card);
          }, 0);
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

  document.addEventListener('click', (event) => {
    if (!(event.target instanceof Element)) {
      return;
    }
    const deleteBtn = event.target.closest('[data-action="delete-text"]');
    if (!deleteBtn) return;
    event.preventDefault();
    const textId = deleteBtn.getAttribute('data-text-id');
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

      fetch(apiBase + '/' + textId, {
        method: 'DELETE',
        headers: {
          'X-CSRFToken': getCsrfToken()
        }
      })
        .then((res) => {
          if (!res.ok && res.status !== 204) {
            throw new Error('Failed to delete text');
          }
          window.location.reload();
        })
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
