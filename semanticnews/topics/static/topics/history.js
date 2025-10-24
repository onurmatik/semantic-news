window.setupTopicHistory = function (options) {
  const {
    key,            // e.g. 'recap', 'narrative', 'relation'
    field,          // field name in item (e.g. 'recap', 'narrative', 'relations')
    cardSuffix = 'Text', // suffix for card content element (Text or Graph)
    listUrl,        // function(topicUuid) -> url
    createUrl,      // string url for POST create
    deleteUrl,      // function(id) -> url
    renderItem,     // function(item, cardContent)
    parseInput,     // function(text) -> data for create
    controller,     // generation button controller
    useMarkdown = false, // whether to enhance textarea with EasyMDE
    statusMessageId,
    messages: messageOverrides = {},
    autoSave: autoSaveOptions = null,
  } = options;

  const form = document.getElementById(`${key}Form`);
  const triggerButton = document.getElementById(`${key}Button`);
  const suggestionBtn = document.getElementById(`fetch${capitalize(key)}Suggestion`) || triggerButton;
  const textarea = document.getElementById(`${key}Text`);
  const easyMDE = useMarkdown && textarea && window.EasyMDE ? new EasyMDE({ element: textarea }) : null;
  if (easyMDE && easyMDE.codemirror && typeof easyMDE.codemirror.getWrapperElement === 'function') {
    const wrapperEl = easyMDE.codemirror.getWrapperElement();
    const easyMDEContainer = wrapperEl && wrapperEl.closest('.EasyMDEContainer');
    if (easyMDEContainer) {
      easyMDEContainer.classList.add('rounded-0');
    }
  }
  // expose MDE handle so other scripts can access it (status checker / fallbacks)
  if (textarea && easyMDE) textarea._easyMDE = easyMDE;

  let suppressDirtyTracking = false;
  const getValue = () => easyMDE ? easyMDE.value() : (textarea ? textarea.value : '');
  const setValue = (v) => {
    suppressDirtyTracking = true;
    if (easyMDE) {
      easyMDE.value(v);
    } else if (textarea) {
      textarea.value = v;
    }
    window.setTimeout(() => {
      suppressDirtyTracking = false;
    }, 0);
  };
  const cardContainer = document.getElementById(`topic${capitalize(key)}Container`);
  const cardContent = document.getElementById(`topic${capitalize(key)}${cardSuffix}`);
  const modalEl = document.getElementById(`${key}Modal`);
  const modal = modalEl && window.bootstrap ? bootstrap.Modal.getOrCreateInstance(modalEl) : null;

  const defaultMessages = {
    suggestionError: 'Unable to fetch suggestions. Please try again.',
    updateError: 'Unable to save your changes. Please try again.',
    parseError: 'Please review your input and try again.',
  };
  const messages = { ...defaultMessages, ...(messageOverrides || {}) };
  const fallbackModalErrorMessage = (
    messages.suggestionError || messages.updateError || defaultMessages.updateError || ''
  ).trim();

  const statusMessageEl = statusMessageId
    ? document.getElementById(statusMessageId)
    : document.getElementById(`${key}StatusMessage`);

  // triggerButton declared earlier for suggestion fallback

  const parseJsonIfPossible = async (res) => {
    try {
      return await res.json();
    } catch (err) {
      return null;
    }
  };

  const resolveErrorMessage = (data, fallback) => {
    if (data && typeof data === 'object') {
      const fields = ['error_message', 'error', 'detail', 'message'];
      for (const field of fields) {
        const value = data[field];
        if (typeof value === 'string' && value.trim()) {
          return value.trim();
        }
      }
    }
    return fallback;
  };

  const clearStatusMessage = () => {
    if (!statusMessageEl) return;
    statusMessageEl.classList.add('d-none');
    statusMessageEl.classList.remove('alert-info', 'alert-success', 'alert-danger');
    statusMessageEl.textContent = '';
  };

  const showStatusMessage = (type, message) => {
    if (!statusMessageEl) return;
    const className = type === 'success'
      ? 'alert-success'
      : type === 'error'
        ? 'alert-danger'
        : 'alert-info';
    statusMessageEl.classList.remove('d-none', 'alert-info', 'alert-success', 'alert-danger');
    statusMessageEl.classList.add(className);
    statusMessageEl.textContent = message;
  };

  const setButtonError = (message) => {
    if (!triggerButton) return;
    if (message) {
      triggerButton.dataset.error = message;
    } else if (triggerButton.dataset) {
      delete triggerButton.dataset.error;
    }
  };

  const getButtonError = () => {
    if (!triggerButton || !triggerButton.dataset) return '';
    const value = triggerButton.dataset.error;
    return typeof value === 'string' ? value.trim() : '';
  };

  const syncModalErrorFromButton = () => {
    const existingError = getButtonError();
    if (existingError) {
      showStatusMessage('error', existingError);
      return;
    }
    const status = triggerButton && triggerButton.dataset
      ? (triggerButton.dataset.status || '').trim().toLowerCase()
      : '';
    if (status === 'error' && fallbackModalErrorMessage) {
      showStatusMessage('error', fallbackModalErrorMessage);
      return;
    }
    clearStatusMessage();
  };

  if (modalEl) {
    modalEl.addEventListener('show.bs.modal', syncModalErrorFromButton);
  }

  const notifyTopicChanged = () => {
    document.dispatchEvent(new CustomEvent('topic:changed'));
  };

  if (easyMDE && modalEl) {
    modalEl.addEventListener('shown.bs.modal', () => {
      easyMDE.codemirror.refresh();
    });
  }

  const pagerEl = document.getElementById(`${key}Pager`);
  const prevBtn = document.getElementById(`${key}Prev`);
  const nextBtn = document.getElementById(`${key}Next`);
  const pagerLabel = document.getElementById(`${key}PagerLabel`);
  const createdAtEl = document.getElementById(`${key}CreatedAt`);
  const deleteBtn = document.getElementById(`${key}DeleteBtn`);
  const showWhenMultipleEls = pagerEl ? Array.from(pagerEl.querySelectorAll('[data-show-when-multiple]')) : [];

  const getInitialIndex = typeof options.getInitialIndex === 'function'
    ? options.getInitialIndex
    : null;
  const onInitialItemMissing = typeof options.onInitialItemMissing === 'function'
    ? options.onInitialItemMissing
    : null;
  const onItemsChanged = typeof options.onItemsChanged === 'function'
    ? options.onItemsChanged
    : null;
  const onItemApplied = typeof options.onItemApplied === 'function'
    ? options.onItemApplied
    : null;

  const confirmModalEl = document.getElementById(`confirmDelete${capitalize(key)}Modal`);
  const confirmBtn = document.getElementById(`confirmDelete${capitalize(key)}Btn`);
  const deleteSpinner = document.getElementById(`confirmDelete${capitalize(key)}Spinner`);
  const confirmModal = confirmModalEl && window.bootstrap ? bootstrap.Modal.getOrCreateInstance(confirmModalEl) : null;
  const fallbackDeleteMessage = (messages && messages.deleteConfirm) || 'Are you sure you want to delete this item?';

  const container = document.querySelector('[data-topic-uuid]');
  const topicUuid = container ? container.getAttribute('data-topic-uuid') : null;
  const buildSuggestionPayload = typeof options.buildSuggestionPayload === 'function'
    ? () => options.buildSuggestionPayload({
      topicUuid,
      getValue,
      textarea,
      easyMDE,
    })
    : () => ({ topic_uuid: topicUuid });

  const norm = (s) => (s || '').replace(/\r\n/g, '\n').replace(/[ \t]+/g, ' ').replace(/\n{3,}/g, '\n\n').trim();
  let baseline = textarea ? norm(getValue()) : '';

  // Submit button enable/disable based on diff from baseline
  const submitBtn = form ? form.querySelector('button[type="submit"]') : null;
  const updateSubmitButtonState = () => {
    if (!submitBtn || !textarea) return;
    submitBtn.disabled = norm(getValue()) === baseline;
  };

  const autoSaveConfig = autoSaveOptions && typeof autoSaveOptions === 'object' ? autoSaveOptions : null;
  const autoSaveEnabled = Boolean(autoSaveConfig && autoSaveConfig.enabled && textarea);
  const autoSaveContainerEl = autoSaveEnabled && autoSaveConfig.statusContainerId
    ? document.getElementById(autoSaveConfig.statusContainerId)
    : null;
  const autoSaveTextEl = autoSaveEnabled && autoSaveConfig.statusTextId
    ? document.getElementById(autoSaveConfig.statusTextId)
    : null;
  const autoSaveSpinnerEl = autoSaveEnabled && autoSaveConfig.statusSpinnerId
    ? document.getElementById(autoSaveConfig.statusSpinnerId)
    : null;
  const autoSaveInactivityMs = autoSaveEnabled && typeof autoSaveConfig.inactivityMs === 'number'
    ? Math.max(1000, autoSaveConfig.inactivityMs)
    : 5000;
  let autoSaveTimer = null;
  let autoSaveInFlight = null;
  let autoSavePending = false;
  let lastPersistedAt = null;

  const formatSavedMessage = (date) => {
    if (!(date instanceof Date) || Number.isNaN(date.getTime())) {
      return (autoSaveConfig && autoSaveConfig.savedMessage) || 'Saved';
    }
    const diffMs = Date.now() - date.getTime();
    if (diffMs < 45000) {
      return (autoSaveConfig && autoSaveConfig.savedJustNowMessage) || 'Saved just now';
    }
    if (autoSaveConfig && typeof autoSaveConfig.savedAtFormatter === 'function') {
      return autoSaveConfig.savedAtFormatter(date);
    }
    const prefix = (autoSaveConfig && autoSaveConfig.savedPrefix) || 'Saved at';
    return `${prefix} ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
  };

  const setAutoSaveState = (state, { savedAt, errorMessage } = {}) => {
    if (!autoSaveEnabled) return;
    if (state === 'saved' && savedAt instanceof Date && !Number.isNaN(savedAt.getTime())) {
      lastPersistedAt = savedAt;
    }
    if (autoSaveContainerEl) {
      autoSaveContainerEl.classList.remove('text-success', 'text-danger', 'text-secondary', 'text-muted', 'text-warning');
      if (state === 'saved') {
        autoSaveContainerEl.classList.add('text-success');
      } else if (state === 'error') {
        autoSaveContainerEl.classList.add('text-danger');
      } else if (state === 'dirty') {
        autoSaveContainerEl.classList.add('text-warning');
      } else {
        autoSaveContainerEl.classList.add('text-secondary');
      }
    }
    if (autoSaveSpinnerEl) {
      if (state === 'saving') {
        autoSaveSpinnerEl.classList.remove('d-none');
      } else {
        autoSaveSpinnerEl.classList.add('d-none');
      }
    }
    if (autoSaveTextEl) {
      let message = '';
      switch (state) {
        case 'saving':
          message = (autoSaveConfig && autoSaveConfig.savingMessage) || 'Saving…';
          break;
        case 'dirty':
          message = (autoSaveConfig && autoSaveConfig.dirtyMessage) || 'Unsaved changes';
          break;
        case 'error':
          message = errorMessage || (autoSaveConfig && autoSaveConfig.errorMessage) || 'Failed to save';
          break;
        case 'saved':
          message = formatSavedMessage(savedAt || lastPersistedAt);
          break;
        default:
          message = (autoSaveConfig && autoSaveConfig.idleMessage) || '';
      }
      autoSaveTextEl.textContent = message;
    }
  };

  const cancelAutoSave = () => {
    if (autoSaveTimer) {
      clearTimeout(autoSaveTimer);
      autoSaveTimer = null;
    }
  };

  const isDirty = () => textarea ? norm(getValue()) !== baseline : false;

  let scheduleAutoSave = () => {};

  const markDirtyFromValue = () => {
    if (!autoSaveEnabled) return;
    if (isDirty()) {
      setAutoSaveState('dirty');
      scheduleAutoSave();
    } else {
      cancelAutoSave();
      setAutoSaveState('saved', { savedAt: lastPersistedAt });
    }
  };

  let saveInFlight = false;
  let pendingRestoreValue = null;

  const handleEditorChange = () => {
    if (suppressDirtyTracking) return;
    if (saveInFlight) {
      pendingRestoreValue = getValue();
    }
    updateSubmitButtonState();
    markDirtyFromValue();
  };

  if (easyMDE) {
    easyMDE.codemirror.on('change', handleEditorChange);
  } else {
    textarea && textarea.addEventListener('input', handleEditorChange);
  }
  updateSubmitButtonState();
  markDirtyFromValue();

  const persistChanges = async () => {
    if (!textarea) return false;
    const currentText = getValue();
    const normalized = norm(currentText);
    if (normalized === baseline) {
      return false;
    }
    if (!topicUuid) {
      return false;
    }

    const payload = { topic_uuid: topicUuid };
    let parsedInput = {};
    try {
      parsedInput = parseInput(currentText) || {};
    } catch (err) {
      const error = new Error(err && err.message ? err.message : 'Invalid JSON');
      error.name = err && err.name ? err.name : 'ParseError';
      throw error;
    }
    if (typeof parsedInput !== 'object') {
      const error = new Error('Invalid JSON');
      error.name = 'ParseError';
      throw error;
    }
    Object.assign(payload, parsedInput);

    let res;
    saveInFlight = true;
    pendingRestoreValue = null;
    try {
      res = await fetch(createUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await parseJsonIfPossible(res);
      const fallback = messages.updateError;
      if (!res.ok || (data && typeof data.status === 'string' && data.status.toLowerCase() === 'error')) {
        const errorMessage = resolveErrorMessage(data, fallback);
        const error = new Error(errorMessage || fallback);
        error.name = 'PersistError';
        throw error;
      }

      await afterPersistedChange();
      baseline = norm(getValue());
      if (pendingRestoreValue !== null) {
        setValue(pendingRestoreValue);
        pendingRestoreValue = null;
      }
      updateSubmitButtonState();
      markDirtyFromValue();
      return true;
    } finally {
      saveInFlight = false;
      pendingRestoreValue = null;
    }
  };

  const executeAutoSave = async ({ reason = 'manual', force = false } = {}) => {
    if (!autoSaveEnabled || !textarea) return false;
    if (!force && !isDirty()) {
      setAutoSaveState('saved', { savedAt: lastPersistedAt });
      return false;
    }
    if (autoSaveInFlight) {
      autoSavePending = true;
      return autoSaveInFlight;
    }
    cancelAutoSave();
    setAutoSaveState('saving');
    autoSaveInFlight = (async () => {
      let hadError = false;
      try {
        const changed = await persistChanges();
        if (changed) {
          const savedAt = new Date();
          setAutoSaveState('saved', { savedAt });
        } else {
          setAutoSaveState('saved', { savedAt: lastPersistedAt });
        }
        autoSavePending = false;
        return changed;
      } catch (err) {
        hadError = true;
        const fallback = messages.updateError;
        const message = (!err || !err.message || err.name === 'TypeError')
          ? fallback
          : err.message;
        setAutoSaveState('error', { errorMessage: message });
        throw err;
      } finally {
        autoSaveInFlight = null;
        if (autoSavePending) {
          autoSavePending = false;
          if (isDirty()) {
            executeAutoSave({ reason: 'queued' }).catch(() => {});
          } else if (!hadError) {
            markDirtyFromValue();
          }
        } else if (!hadError) {
          markDirtyFromValue();
        }
      }
    })();
    return autoSaveInFlight;
  };

  scheduleAutoSave = () => {
    if (!autoSaveEnabled) return;
    cancelAutoSave();
    autoSaveTimer = window.setTimeout(() => {
      autoSaveTimer = null;
      executeAutoSave({ reason: 'inactivity' }).catch(() => {});
    }, autoSaveInactivityMs);
  };

  if (autoSaveEnabled) {
    const handleShortcut = (event) => {
      if (!event) return;
      const key = (event.key || '').toLowerCase();
      if (key === 's' && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        executeAutoSave({ reason: 'shortcut', force: true }).catch(() => {});
      }
    };

    if (easyMDE && easyMDE.codemirror) {
      easyMDE.codemirror.on('blur', () => {
        executeAutoSave({ reason: 'blur' }).catch(() => {});
      });
      easyMDE.codemirror.on('keydown', (_cm, event) => {
        handleShortcut(event);
      });
    } else if (textarea) {
      textarea.addEventListener('blur', () => {
        executeAutoSave({ reason: 'blur' }).catch(() => {});
      });
      textarea.addEventListener('keydown', handleShortcut);
    }
  }

  // list + pager
  const recs = [];
  let currentIndex = -1;
  const current = () => (currentIndex >= 0 ? recs[currentIndex] : null);

  const formatDateTime = (iso) => {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit'
    });
  };

  const applyIndex = (i) => {
    if (!recs.length) {
      pagerEl && (pagerEl.style.display = 'none');
      return;
    }
    currentIndex = Math.max(0, Math.min(i, recs.length - 1));
    const item = recs[currentIndex];

    // Fill editor
    setValue(getItemText(item));
    // Show card
    if (cardContainer) cardContainer.style.display = '';
    renderItem && cardContent && renderItem(item, cardContent);

    // Reset baseline & update submit disabled
    baseline = norm(getValue());
    updateSubmitButtonState();

    // Pager/UI
    pagerEl && (pagerEl.style.display = '');
    pagerLabel && (pagerLabel.textContent = `${currentIndex + 1}/${recs.length}`);
    const hasMultiple = recs.length > 1;
    showWhenMultipleEls.forEach((el) => {
      if (hasMultiple) {
        el.classList.remove('d-none');
      } else {
        el.classList.add('d-none');
      }
    });
    prevBtn && (prevBtn.disabled = currentIndex <= 0);
    nextBtn && (nextBtn.disabled = currentIndex >= recs.length - 1);
    createdAtEl && (createdAtEl.textContent = formatDateTime(item.created_at));

    if (autoSaveEnabled) {
      if (item && item.created_at) {
        const savedDate = new Date(item.created_at);
        if (!Number.isNaN(savedDate.getTime())) {
          lastPersistedAt = savedDate;
        }
      }
      markDirtyFromValue();
    }

    if (typeof onItemApplied === 'function') {
      try {
        onItemApplied({
          item,
          items: recs.slice(),
          index: currentIndex,
        });
      } catch (err) {
        console.error('history onItemApplied failed:', err);
      }
    }
  };

  const handleInitialItemMissing = (items) => {
    if (typeof onInitialItemMissing === 'function') {
      try {
        onInitialItemMissing({ items });
      } catch (err) {
        console.error('history onInitialItemMissing failed:', err);
      }
      return;
    }
    if (cardContent) {
      cardContent.textContent = '';
    }
  };

  const getItemText = (item) => {
    const v = item && item[field];
    if (typeof v === 'string') return v;
    return JSON.stringify(v, null, 2);
  };

  let reload = async ({ notify = true } = {}) => {
    if (notify) {
      notifyTopicChanged();
    }
    return true;
  };
  let lastSerializedItems = null;
  if (pagerEl) {
    reload = async ({ notify = true } = {}) => {
      if (!topicUuid) return false;
      try {
        const res = await fetch(listUrl(topicUuid));
        if (!res.ok) throw new Error('Failed to load');
        const data = await res.json();
        const items = Array.isArray(data.items) ? data.items : [];
        const serialized = JSON.stringify(items);
        const changed = serialized !== lastSerializedItems;
        lastSerializedItems = serialized;

        recs.length = 0;
        items.forEach(r => recs.push(r));

        if (typeof onItemsChanged === 'function') {
          try {
            onItemsChanged({ items: recs.slice() });
          } catch (err) {
            console.error('history onItemsChanged failed:', err);
          }
        }
        if (recs.length) {
          let initialIndex = recs.length - 1;
          if (getInitialIndex) {
            try {
              const proposed = getInitialIndex({
                items: recs.slice(),
                previousIndex: currentIndex,
              });
              if (typeof proposed === 'number' && !Number.isNaN(proposed)) {
                initialIndex = Math.max(0, Math.min(proposed, recs.length - 1));
              } else if (proposed === null) {
                initialIndex = null;
              }
            } catch (err) {
              console.error('history getInitialIndex failed:', err);
              initialIndex = recs.length - 1;
            }
          }

          if (typeof initialIndex === 'number' && initialIndex >= 0) {
            applyIndex(initialIndex);
          } else if (initialIndex === null) {
            currentIndex = -1;
            pagerEl && (pagerEl.style.display = '');
            pagerLabel && (pagerLabel.textContent = `0/${recs.length}`);
            const hasMultiple = recs.length > 1;
            showWhenMultipleEls.forEach((el) => {
              if (hasMultiple) {
                el.classList.remove('d-none');
              } else {
                el.classList.add('d-none');
              }
            });
            prevBtn && (prevBtn.disabled = true);
            nextBtn && (nextBtn.disabled = recs.length === 0);
            createdAtEl && (createdAtEl.textContent = '');
            handleInitialItemMissing(recs.slice());
          } else {
            applyIndex(recs.length - 1);
          }
        } else {
          pagerEl && (pagerEl.style.display = 'none');
          currentIndex = -1;
          if (typeof onItemsChanged === 'function') {
            try {
              onItemsChanged({ items: [] });
            } catch (err) {
              console.error('history onItemsChanged failed:', err);
            }
          }
          handleInitialItemMissing([]);
          if (autoSaveEnabled) {
            lastPersistedAt = null;
            markDirtyFromValue();
          }
        }
        if (notify && changed) {
          notifyTopicChanged();
        }
        return changed;
      } catch (e) {
        console.error(e);
        return false;
      }
    };

    // expose generic hooks for status checker (e.g., __narrativeReloadAndJump / __narrativeExternalApply)
    try {
      const lower = key;
      window[`__${lower}ReloadAndJump`] = reload;
      window[`__${lower}ExternalApply`] = (text, createdAtIso) => {
        // card
        if (cardContainer) cardContainer.style.display = '';
        if (renderItem && cardContent) {
          const fakeItem = { [field]: text || '', created_at: createdAtIso || null, id: -1 };
          renderItem(fakeItem, cardContent);
        } else if (cardContent) {
          cardContent.textContent = text || '';
        }
        // editor
        setValue(text || '');
        // reset baseline & disable Update
        baseline = norm(getValue());
        updateSubmitButtonState();
        // created at label
        if (createdAtEl && createdAtIso) {
          const d = new Date(createdAtIso);
          createdAtEl.textContent = d.toLocaleString(undefined, {
            year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit'
          });
        }
        if (autoSaveEnabled) {
          if (createdAtIso) {
            const savedDate = new Date(createdAtIso);
            if (!Number.isNaN(savedDate.getTime())) {
              lastPersistedAt = savedDate;
            }
          }
          markDirtyFromValue();
        }
        notifyTopicChanged();
      };
    } catch (err) {
      console.error('history hooks expose failed:', err);
    }

    // initial load (only when pager exists = edit mode)
    reload({ notify: false });

    // pager controls
    prevBtn && prevBtn.addEventListener('click', () => applyIndex(currentIndex - 1));
    nextBtn && nextBtn.addEventListener('click', () => applyIndex(currentIndex + 1));

    const executeDelete = async () => {
      const item = current();
      if (!item) return;
      const res = await fetch(deleteUrl(item.id), { method: 'DELETE' });
      if (!res.ok && res.status !== 204) throw new Error('Delete failed');
      window.location.reload(); // per requirement
    };

    const performDeleteWithUi = async ({ useUi = true } = {}) => {
      const item = current();
      if (!item) return;
      if (useUi && confirmBtn) {
        confirmBtn.disabled = true;
        deleteSpinner && deleteSpinner.classList.remove('d-none');
      }
      try {
        await executeDelete();
      } catch (e) {
        console.error(e);
        throw e;
      } finally {
        if (useUi && confirmBtn) {
          confirmBtn.disabled = false;
          deleteSpinner && deleteSpinner.classList.add('d-none');
        }
        confirmModal && confirmModal.hide();
      }
    };

    deleteBtn && deleteBtn.addEventListener('click', async () => {
      if (!current()) return;
      if (confirmModal && confirmBtn) {
        confirmModal.show();
        return;
      }
      if (window.confirm(fallbackDeleteMessage)) {
        try {
          await performDeleteWithUi({ useUi: false });
        } catch (e) {
          // already logged in performDeleteWithUi
        }
      }
    });

    confirmBtn && confirmBtn.addEventListener('click', async () => {
      try {
        await performDeleteWithUi({ useUi: true });
      } catch (e) {
        confirmModal && confirmModal.hide();
      }
    });
  }

  // ----- Suggest + Update flows (modal behavior unified for all keys) -----

  const afterPersistedChange = async () => {
    // After AI suggestion or manual Update, ensure list/card/editor/baseline are correct
    const notified = await reload();
    if (!notified) {
      notifyTopicChanged();
    }
  };

  // Suggest flow
  if (suggestionBtn && textarea && form) {
    suggestionBtn.addEventListener('click', async () => {
      clearStatusMessage();
      setButtonError(null);
      controller && controller.showLoading();
      modal && modal.hide();
      suggestionBtn.disabled = true;

      try {
        const payload = buildSuggestionPayload() || {};
        if (!payload.topic_uuid) {
          payload.topic_uuid = topicUuid;
        }
        const res = await fetch(createUrl, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await parseJsonIfPossible(res);
        const fallback = messages.suggestionError || messages.updateError;
        if (!res.ok || (data && typeof data.status === 'string' && data.status.toLowerCase() === 'error')) {
          const errorMessage = resolveErrorMessage(data, fallback);
          throw new Error(errorMessage);
        }

        controller && controller.showSuccess();
        setButtonError(null);
        clearStatusMessage();
        await afterPersistedChange();
      } catch (err) {
        console.error(err);
        controller && controller.showError();
        const fallback = messages.suggestionError || messages.updateError;
        const message = (!err || !err.message || err.name === 'TypeError')
          ? fallback
          : err.message;
        setButtonError(message);
        showStatusMessage('error', message);
        modal && modal.show();
      } finally {
        suggestionBtn.disabled = false;
      }
    });
  }

  // Manual update flow
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      submitBtn && (submitBtn.disabled = true);
      controller && controller.showLoading();
      clearStatusMessage();
      setButtonError(null);
      // Close modal if present
      const modalEl = document.getElementById(`${key}Modal`);
      const modal = modalEl && window.bootstrap ? bootstrap.Modal.getOrCreateInstance(modalEl) : null;
      modal && modal.hide();

      try {
        const changed = await persistChanges();
        controller && controller.reset();
        setButtonError(null);
        clearStatusMessage();
        if (changed && autoSaveEnabled) {
          const savedAt = new Date();
          setAutoSaveState('saved', { savedAt });
        }
      } catch (err) {
        console.error(err);
        controller && controller.showError();
        const fallback = messages.updateError;
        let message = fallback;
        if (err && err.message) {
          if (err.message === 'Invalid JSON') {
            message = messages.parseError || fallback;
          } else if (err.name === 'TypeError') {
            message = fallback;
          } else {
            message = err.message;
          }
        }
        setButtonError(message);
        showStatusMessage('error', message);
        modal && modal.show();
        if (autoSaveEnabled) {
          setAutoSaveState('error', { errorMessage: message });
        }
      } finally {
        if (textarea) {
          submitBtn && (submitBtn.disabled = norm(getValue()) === baseline);
        } else {
          submitBtn && (submitBtn.disabled = false);
        }
      }
    });
  }
};

function capitalize(s){return s.charAt(0).toUpperCase()+s.slice(1);}
