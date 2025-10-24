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
    autoSave: autoSaveOptions = {},
    saveIndicatorId,
    messages: messageOverrides = {},
  } = options;

  const form = document.getElementById(`${key}Form`);
  const triggerButton = document.getElementById(`${key}Button`);
  const suggestionBtn = document.getElementById(`fetch${capitalize(key)}Suggestion`) || triggerButton;
  const textarea = document.getElementById(`${key}Text`);
  const easyMDE = useMarkdown && textarea && window.EasyMDE ? new EasyMDE({ element: textarea }) : null;
  // expose MDE handle so other scripts can access it (status checker / fallbacks)
  if (textarea && easyMDE) textarea._easyMDE = easyMDE;

  const getValue = () => easyMDE ? easyMDE.value() : (textarea ? textarea.value : '');
  const setValue = (v) => { if (easyMDE) easyMDE.value(v); else if (textarea) textarea.value = v; };
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

  const saveIndicatorEl = saveIndicatorId
    ? document.getElementById(saveIndicatorId)
    : null;
  const autoSaveEnabled = !!(autoSaveOptions && autoSaveOptions.enabled);
  const autoSaveDelay = autoSaveEnabled
    ? Math.max(0, Number.isFinite(Number(autoSaveOptions.debounceMs))
      ? Number(autoSaveOptions.debounceMs)
      : Math.max(0, Number(autoSaveOptions.delayMs) || 2000))
    : 0;
  const autoSaveOnBlur = autoSaveEnabled ? autoSaveOptions.saveOnBlur !== false : false;
  const autoSaveOnShortcut = autoSaveEnabled ? autoSaveOptions.saveOnShortcut !== false : false;

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
  const hasUnsavedChanges = () => (textarea ? norm(getValue()) !== baseline : false);
  let autoSaveTimer = null;
  let isSaving = false;
  let pendingSave = false;
  let lastSavedAt = null;

  const formatSaveTime = (date) => {
    if (!(date instanceof Date) || Number.isNaN(date.getTime())) {
      return '';
    }
    return date.toLocaleString(undefined, { hour: '2-digit', minute: '2-digit' });
  };

  const setSaveIndicator = (state, options = {}) => {
    if (!saveIndicatorEl) return;
    const classMap = {
      idle: 'text-muted',
      dirty: 'text-warning',
      saving: 'text-muted',
      saved: 'text-success',
      error: 'text-danger',
    };
    saveIndicatorEl.dataset.state = state;
    saveIndicatorEl.classList.remove('text-muted', 'text-warning', 'text-success', 'text-danger');
    const className = classMap[state] || 'text-muted';
    saveIndicatorEl.classList.add(className);

    let message = '';
    if (state === 'dirty') {
      message = 'Unsaved changes';
    } else if (state === 'saving') {
      message = 'Saving…';
    } else if (state === 'saved') {
      const savedAt = options.savedAt instanceof Date && !Number.isNaN(options.savedAt.getTime())
        ? options.savedAt
        : lastSavedAt;
      if (savedAt instanceof Date && !Number.isNaN(savedAt.getTime())) {
        lastSavedAt = savedAt;
        message = `Last saved ${formatSaveTime(savedAt)}`;
      } else if (lastSavedAt instanceof Date && !Number.isNaN(lastSavedAt.getTime())) {
        message = `Last saved ${formatSaveTime(lastSavedAt)}`;
      } else {
        message = 'All changes saved';
      }
    } else if (state === 'error') {
      message = options.error || 'Unable to save changes.';
    } else {
      message = '';
    }

    saveIndicatorEl.textContent = message;
  };

  const clearAutoSaveTimer = () => {
    if (autoSaveTimer) {
      window.clearTimeout(autoSaveTimer);
      autoSaveTimer = null;
    }
  };

  const requestAutoSave = ({ immediate = false } = {}) => {
    if (!autoSaveEnabled || !textarea) {
      return;
    }
    if (!hasUnsavedChanges()) {
      clearAutoSaveTimer();
      setSaveIndicator('saved');
      return;
    }

    setSaveIndicator('dirty');
    if (isSaving) {
      pendingSave = true;
      return;
    }

    clearAutoSaveTimer();
    if (immediate || autoSaveDelay === 0) {
      // Allow the current stack to unwind to avoid recursive locking
      window.setTimeout(() => {
        persistChanges();
      }, 0);
    } else {
      autoSaveTimer = window.setTimeout(() => {
        autoSaveTimer = null;
        persistChanges();
      }, autoSaveDelay);
    }
  };

  // Submit button enable/disable based on diff from baseline
  const submitBtn = form ? form.querySelector('button[type="submit"]') : null;
  const updateSubmitButtonState = () => {
    if (!submitBtn || !textarea) return;
    submitBtn.disabled = !hasUnsavedChanges();
  };

  const handleEditorChange = () => {
    updateSubmitButtonState();
    if (autoSaveEnabled) {
      requestAutoSave();
    }
  };

  const handleEditorBlur = () => {
    if (autoSaveEnabled && autoSaveOnBlur) {
      requestAutoSave({ immediate: true });
    }
  };

  if (easyMDE) {
    easyMDE.codemirror.on('change', handleEditorChange);
    easyMDE.codemirror.on('blur', handleEditorBlur);
    if (autoSaveEnabled && autoSaveOnShortcut && easyMDE.codemirror.addKeyMap) {
      easyMDE.codemirror.addKeyMap({
        'Cmd-S': () => requestAutoSave({ immediate: true }),
        'Ctrl-S': () => requestAutoSave({ immediate: true }),
      });
    }
  } else if (textarea) {
    textarea.addEventListener('input', handleEditorChange);
    textarea.addEventListener('blur', handleEditorBlur);
  }

  updateSubmitButtonState();
  if (autoSaveEnabled) {
    if (hasUnsavedChanges()) {
      setSaveIndicator('dirty');
    } else {
      setSaveIndicator('saved');
    }
  }

  const handleShortcutEvent = (event) => {
    if (!autoSaveEnabled || !autoSaveOnShortcut) {
      return;
    }
    if (!(event.metaKey || event.ctrlKey)) {
      return;
    }
    if ((event.key || '').toLowerCase() !== 's') {
      return;
    }
    if (form && !form.contains(event.target)) {
      return;
    }
    event.preventDefault();
    requestAutoSave({ immediate: true });
  };

  if (autoSaveEnabled && autoSaveOnShortcut) {
    window.addEventListener('keydown', handleShortcutEvent);
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
    if (autoSaveEnabled) {
      const createdAt = item && item.created_at ? new Date(item.created_at) : null;
      if (createdAt instanceof Date && !Number.isNaN(createdAt.getTime())) {
        setSaveIndicator('saved', { savedAt: createdAt });
      } else if (!hasUnsavedChanges()) {
        setSaveIndicator('saved');
      }
    }

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
        if (recs.length) {
          applyIndex(recs.length - 1);
        } else {
          pagerEl.style.display = 'none';
          if (autoSaveEnabled && !hasUnsavedChanges()) {
            setSaveIndicator('saved');
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

  async function persistChanges({ userInitiated = false } = {}) {
    if (!form || !topicUuid) {
      return false;
    }
    const canTrackUnsavedChanges = !!textarea;
    const shouldPersist = canTrackUnsavedChanges ? hasUnsavedChanges() : true;
    if (!shouldPersist) {
      if (autoSaveEnabled) {
        setSaveIndicator('saved');
      }
      return false;
    }
    if (isSaving) {
      pendingSave = true;
      return false;
    }

    clearAutoSaveTimer();
    isSaving = true;
    pendingSave = false;

    submitBtn && (submitBtn.disabled = true);
    if (userInitiated) {
      controller && controller.showLoading();
      setButtonError(null);
    }
    clearStatusMessage();
    if (userInitiated && modal) {
      modal.hide();
    }
    if (autoSaveEnabled) {
      setSaveIndicator('saving');
    }

    try {
      const payload = { topic_uuid: topicUuid };
      const currentText = textarea ? getValue() : '';
      const normalizedText = textarea ? norm(currentText) : '';
      Object.assign(payload, parseInput(currentText));
      const res = await fetch(createUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await parseJsonIfPossible(res);
      const fallback = messages.updateError;
      if (!res.ok || (data && typeof data.status === 'string' && data.status.toLowerCase() === 'error')) {
        const errorMessage = resolveErrorMessage(data, fallback);
        throw new Error(errorMessage);
      }

      if (userInitiated) {
        controller && controller.reset();
      }
      if (userInitiated) {
        setButtonError(null);
      }
      clearStatusMessage();
      baseline = normalizedText;
      await afterPersistedChange();
      baseline = norm(getValue());
      updateSubmitButtonState();
      if (autoSaveEnabled) {
        setSaveIndicator('saved', { savedAt: new Date() });
      }
      return true;
    } catch (err) {
      console.error(err);
      if (userInitiated) {
        controller && controller.showError();
      }
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
      if (userInitiated) {
        setButtonError(message);
      }
      showStatusMessage('error', message);
      if (userInitiated && modal) {
        modal.show();
      }
      if (autoSaveEnabled) {
        setSaveIndicator('error', { error: message });
      }
      return false;
    } finally {
      isSaving = false;
      if (textarea) {
        submitBtn && (submitBtn.disabled = !hasUnsavedChanges());
      } else {
        submitBtn && (submitBtn.disabled = false);
      }
      if (pendingSave && autoSaveEnabled) {
        pendingSave = false;
        requestAutoSave({ immediate: true });
      }
    }
  }

  // Manual update flow
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      await persistChanges({ userInitiated: true });
    });
  }
};

function capitalize(s){return s.charAt(0).toUpperCase()+s.slice(1);}
