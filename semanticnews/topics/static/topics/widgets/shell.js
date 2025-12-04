(function () {
  const registry = window.TopicWidgetRegistry;
  const shared = window.TopicWidgetShared;
  if (!registry || !shared) return;

  const { getCsrfToken, setValidationState, clearValidation } = shared;
  const POLL_INTERVAL_MS = 4000;
  const MAX_POLL_ATTEMPTS = 75;
  const executionPollers = new Map();

  function escapeAttributeName(name) {
    if (typeof name !== 'string') {
      return '';
    }
    if (window.CSS && typeof window.CSS.escape === 'function') {
      return window.CSS.escape(name);
    }
    return name.replace(/["\\]/g, '\\$&');
  }

  function syncRichTextField(field, value) {
    if (!field || !field._easyMDE || typeof field._easyMDE.value !== 'function') {
      return;
    }
    try {
      field._easyMDE.value(value);
      if (field._easyMDE.codemirror && typeof field._easyMDE.codemirror.refresh === 'function') {
        field._easyMDE.codemirror.refresh();
      }
    } catch (error) {
      // eslint-disable-next-line no-console
      console.error('[TopicWidgets][Shell] Failed to sync rich text field', error);
    }
  }

  function setFieldValue(field, value) {
    if (!field) {
      return;
    }
    const normalized = value == null ? '' : String(value);
    if (field.type === 'checkbox') {
      field.checked = Boolean(value);
      return;
    }
    if (field.type === 'radio') {
      field.checked = field.value === normalized;
      return;
    }

    field.value = normalized;
    syncRichTextField(field, normalized);
  }

  function resolveActionBanner(actionId, phase) {
    const normalizedAction = (actionId || '').toLowerCase();
    const normalizedPhase = (phase || '').toLowerCase();

    const banners = {
      summarize: {
        queued: 'Summarizing paragraph…',
        running: 'Summarizing paragraph…',
        success: 'Paragraph summarized',
        timeout: 'Timed out while summarizing paragraph',
        failure: 'Unable to summarize paragraph',
      },
      expand: {
        queued: 'Expanding paragraph…',
        running: 'Expanding paragraph…',
        success: 'Paragraph expanded',
        timeout: 'Timed out while expanding paragraph',
        failure: 'Unable to expand paragraph',
      },
      generate: {
        queued: 'Generating paragraph…',
        running: 'Generating paragraph…',
        success: 'Paragraph generated',
        timeout: 'Timed out while generating paragraph',
        failure: 'Unable to generate paragraph',
      },
    };

    const defaults = banners.generate;
    return (
      (banners[normalizedAction] && banners[normalizedAction][normalizedPhase])
      || defaults[normalizedPhase]
      || 'Action in progress'
    );
  }

  function updateFormFields(container, content) {
    if (!container || !content || typeof content !== 'object') {
      return;
    }
    Object.entries(content).forEach(([key, value]) => {
      if (!key) return;
      const selector = `[name="${escapeAttributeName(String(key))}"]`;
      const fields = container.querySelectorAll(selector);
      if (!fields.length) {
        return;
      }
      fields.forEach((field) => {
        setFieldValue(field, value);
        field.dispatchEvent(new Event('input', { bubbles: true }));
        field.dispatchEvent(new Event('change', { bubbles: true }));
      });
    });
  }

  function createImagePlaceholder() {
    const wrapper = document.createElement('div');
    wrapper.className = 'd-inline-flex flex-column align-items-center gap-2 text-muted';

    const icon = document.createElement('i');
    icon.className = 'bi bi-image fs-1';
    icon.setAttribute('aria-hidden', 'true');
    wrapper.appendChild(icon);

    const label = document.createElement('span');
    label.textContent = 'Image preview will appear here.';
    wrapper.appendChild(label);

    return wrapper;
  }

  function updateImagePreview(container, imageUrl) {
    if (!container) {
      return;
    }
    const preview = container.querySelector('[data-widget-image-preview]');
    if (!preview) {
      return;
    }
    preview.innerHTML = '';
    if (imageUrl) {
      const img = document.createElement('img');
      img.src = imageUrl;
      img.alt = '';
      img.className = 'img-fluid rounded';
      preview.appendChild(img);
      return;
    }
    const placeholder = createImagePlaceholder();
    preview.appendChild(placeholder);
  }

  function updateParagraphPreview(container, text) {
    if (!container) {
      return;
    }
    const preview = container.querySelector('[data-widget-paragraph-preview]');
    if (!preview) {
      return;
    }
    const resolved = typeof text === 'string' ? text.trim() : '';
    preview.innerHTML = '';
    if (resolved) {
      const paragraph = document.createElement('p');
      paragraph.className = 'mb-0';
      const lines = resolved.replace(/\r\n/g, '\n').split('\n');
      lines.forEach((line, index) => {
        paragraph.appendChild(document.createTextNode(line));
        if (index < lines.length - 1) {
          paragraph.appendChild(document.createElement('br'));
        }
      });
      preview.appendChild(paragraph);
      return;
    }
    const placeholder = document.createElement('p');
    placeholder.className = 'text-muted mb-0';
    placeholder.textContent = 'Paragraph preview will appear here.';
    preview.appendChild(placeholder);
  }

  function normaliseWidgetContent(widgetKey, content) {
    if (!content || typeof content !== 'object') {
      return {};
    }

    const normalized = { ...content };
    const key = widgetKey || '';

    if (key === 'paragraph') {
      const resultVal =
        typeof normalized.result === 'string' ? normalized.result.trim() : '';

      if (resultVal) {
        normalized.text = resultVal;
      } else if (typeof normalized.text === 'string') {
        normalized.text = normalized.text.trim();
      }
    }

    if (key === 'image') {
      const resultVal = normalized.result;
      const providedImage = normalized.image_url || normalized.imageUrl;
      const hasValidProvidedImage =
        typeof providedImage === 'string' &&
        (providedImage.trim().startsWith('http://') ||
          providedImage.trim().startsWith('https://') ||
          providedImage.trim().toLowerCase().startsWith('data:image/'));

      if (hasValidProvidedImage) {
        normalized.image_url = providedImage.trim();
      } else {
        delete normalized.image_url;
        if (Object.prototype.hasOwnProperty.call(normalized, 'imageUrl')) {
          delete normalized.imageUrl;
        }
      }

      if (!normalized.image_url && typeof resultVal === 'string') {
        const cleaned = resultVal.trim();
        const lowerCleaned = cleaned.toLowerCase();
        const isLikelyUrl =
          cleaned.startsWith('http://') || cleaned.startsWith('https://');
        const isLikelyDataUrl = lowerCleaned.startsWith('data:image/');
        if (isLikelyUrl || isLikelyDataUrl) {
          normalized.image_url = cleaned;
        } else if (
          /^[a-z0-9+/=\n\r]+$/i.test(cleaned) &&
          !/\s/.test(cleaned) &&
          cleaned.length >= 60
        ) {
          try {
            window.atob(cleaned);
            normalized.image_url = `data:image/png;base64,${cleaned}`;
          } catch (error) {
            // Not a valid base64 image payload; leave as text.
          }
        }
      }
    }

    return normalized;
  }

  function updateWidgetContent(widgetEl, content, widgetKey) {
    if (!widgetEl || !content || typeof content !== 'object') {
      return;
    }
    const contentContainer = widgetEl.querySelector('[data-widget-editor-content]');
    if (!contentContainer) {
      return;
    }

    const normalizedContent = normaliseWidgetContent(widgetKey || widgetEl.dataset.topicWidgetKey, content);
    updateFormFields(contentContainer, normalizedContent);

    const resolvedKey = widgetKey || widgetEl.dataset.topicWidgetKey || '';
    if (resolvedKey === 'image') {
      updateImagePreview(contentContainer, normalizedContent.image_url || normalizedContent.imageUrl || '');
    } else if (resolvedKey === 'paragraph') {
      updateParagraphPreview(contentContainer, normalizedContent.text || '');
    }
  }

  function appendValue(target, name, value) {
    if (Object.prototype.hasOwnProperty.call(target, name)) {
      const current = target[name];
      if (Array.isArray(current)) {
        current.push(value);
      } else {
        target[name] = [current, value];
      }
    } else {
      target[name] = value;
    }
  }

  function getFieldValue(field) {
    if (!field) {
      return '';
    }

    if (field.type === 'checkbox') {
      if (!field.checked) {
        return null;
      }
      return field.value === 'on' ? true : field.value;
    }

    if (field.type === 'radio') {
      if (!field.checked) {
        return null;
      }
      return field.value;
    }

    if (field.multiple && field.options) {
      return Array.from(field.options)
        .filter((option) => option.selected)
        .map((option) => option.value);
    }

    if (field._easyMDE && typeof field._easyMDE.value === 'function') {
      return field._easyMDE.value();
    }

    if (field instanceof HTMLTextAreaElement) {
      return field.value;
    }

    if (field instanceof HTMLInputElement || field instanceof HTMLSelectElement) {
      return field.value;
    }

    return field.value;
  }


  function normaliseTextValue(value) {
    if (value == null) {
      return '';
    }
    return String(value).replace(/\r\n/g, '\n').trim();
  }

  function collectParagraphGenerationContext(widgetEl, baseContext) {
    const context = { ...(baseContext || {}) };

    const titleEl = document.getElementById('topicTitleInput');
    const topicTitle = normaliseTextValue(titleEl ? titleEl.textContent : '');
    if (topicTitle) {
      context.topic_title = topicTitle;
    }

    const recapTextarea = document.getElementById('recapText');
    const recapValue = recapTextarea ? normaliseTextValue(getFieldValue(recapTextarea)) : '';
    if (recapValue) {
      context.latest_recap = recapValue;
    }

    const otherParagraphs = [];
    const currentEntry = widgetEl ? widgetEl.closest('[data-topic-widget-entry]') : null;
    document.querySelectorAll('[data-topic-widget-entry][data-topic-widget-key="paragraph"]').forEach((entry) => {
      if (!entry || entry === currentEntry) {
        return;
      }
      const textField = entry.querySelector('[name="text"]');
      const value = textField ? normaliseTextValue(getFieldValue(textField)) : '';
      if (value) {
        otherParagraphs.push(value);
      }
    });
    if (otherParagraphs.length) {
      context.paragraphs = otherParagraphs;
    }

    const instructionField = widgetEl ? widgetEl.querySelector('[name="instructions"]') : null;
    const instructionValue = instructionField ? normaliseTextValue(getFieldValue(instructionField)) : '';
    if (instructionValue) {
      context.instructions = instructionValue;
    }

    return context;
  }

  function getParagraphInstructions(widgetEl) {
    if (!widgetEl) {
      return '';
    }
    const instructionField = widgetEl.querySelector('[name="instructions"]');
    const value = instructionField ? getFieldValue(instructionField) : '';
    return typeof value === 'string' ? value.trim() : '';
  }

  function serializeWidgetContext(widgetEl) {
    if (!widgetEl) {
      return {};
    }
    const container = widgetEl.querySelector('[data-widget-editor-content]');
    if (!container) {
      return {};
    }

    const fields = container.querySelectorAll('input[name], textarea[name], select[name]');
    if (!fields.length) {
      return {};
    }

    const data = {};
    fields.forEach((field) => {
      if (!field || field.disabled) {
        return;
      }
      const { name, type } = field;
      if (!name) {
        return;
      }

      const value = getFieldValue(field);

      if (value == null) {
        return;
      }

      if (type === 'checkbox') {
        appendValue(data, name, value);
        return;
      }

      if (type === 'radio') {
        data[name] = value;
        return;
      }

      if (Array.isArray(value)) {
        if (value.length) {
          data[name] = value;
        }
        return;
      }

      data[name] = value;
    });

    return data;
  }

  function buildPollKey(topicUuid, sectionId) {
    return `${topicUuid}:${sectionId}`;
  }

  registry.register('shell', (context) => {
    console.log('[TopicWidgets][Shell] Initializing...');
    const { element, definition, topicUuid } = context || {};
    if (!element || !definition || !topicUuid) {
      console.error('[TopicWidgets][Shell] Missing context for initialization.');
      return null;
    }

    const reorderState = { pending: false };

    const deleteModalEl = document.getElementById('confirmDeleteWidgetModal');
    const deleteModal = deleteModalEl && window.bootstrap
      ? window.bootstrap.Modal.getOrCreateInstance(deleteModalEl)
      : null;
    const deleteConfirmBtn = document.getElementById('confirmDeleteWidgetBtn');
    const deleteSpinner = document.getElementById('confirmDeleteWidgetSpinner');
    const deleteTitle = deleteModalEl ? deleteModalEl.querySelector('[data-widget-delete-title]') : null;
    const deleteMessage = deleteModalEl ? deleteModalEl.querySelector('[data-widget-delete-message]') : null;
    const pendingDelete = { entry: null, sectionId: null, label: 'section' };

    function getSectionId(widgetEl) {
      if (!widgetEl) {
        return null;
      }
      const { widgetSectionId } = widgetEl.dataset || {};
      if (!widgetSectionId) {
        return null;
      }
      const parsed = Number(widgetSectionId);
      return Number.isNaN(parsed) ? null : parsed;
    }

    function evaluateWidgetState(widgetEl) {
      const sectionId = getSectionId(widgetEl);
      const widgetKey = widgetEl && widgetEl.dataset && widgetEl.dataset.topicWidgetKey
        ? widgetEl.dataset.topicWidgetKey.toLowerCase()
        : '';
      const contentContainer = widgetEl ? widgetEl.querySelector('[data-widget-editor-content]') : null;

      const findField = (name) => (contentContainer
        ? contentContainer.querySelector(`[name="${name}"]`)
        : null);
      const imageField = findField('image_url') || findField('url');
      const imageValue = imageField ? getFieldValue(imageField) : '';
      const textField = findField('text');
      const textValue = textField ? getFieldValue(textField) : '';

      return {
        widgetKey,
        sectionId,
        hasImage: typeof imageValue === 'string' ? imageValue.trim().length > 0 : false,
        hasText: typeof textValue === 'string' ? textValue.trim().length > 0 : false,
      };
    }

    function updateActionVisibility(widgetEl) {
      if (!widgetEl) {
        return;
      }
      const state = evaluateWidgetState(widgetEl);
      const {
        sectionId,
        hasImage,
        hasText,
        widgetKey,
      } = state;

      const controls = widgetEl.querySelectorAll(
        '[data-widget-action],[data-widget-action-id],[data-widget-action-name],'
        + '[data-widget-delete-section-id]',
      );

      const isParagraph = widgetKey === 'paragraph';

      controls.forEach((button) => {
        if (!button || !button.classList) {
          return;
        }
        const isForceHidden = button.dataset.widgetForceHidden === 'true';
        const visibility = (button.dataset.widgetVisibility || 'always').toLowerCase();
        let shouldShow = true;
        switch (visibility) {
          case 'needs-image':
            shouldShow = !hasImage;
            break;
          case 'saved-with-image':
            shouldShow = Boolean(sectionId && hasImage);
            break;
          case 'saved-with-text':
            shouldShow = Boolean(sectionId && hasText);
            break;
          default:
            shouldShow = true;
            break;
        }
        button.classList.toggle('d-none', !shouldShow || isForceHidden);

        if (button.dataset.widgetDeleteSectionId !== undefined && sectionId) {
          button.dataset.widgetDeleteSectionId = sectionId;
        }

        if (button.dataset.widgetDeleteSectionId !== undefined) {
          const canDelete = sectionId != null;
          button.disabled = !canDelete;
          if (button.disabled) {
            button.setAttribute('aria-disabled', 'true');
          } else {
            button.removeAttribute('aria-disabled');
          }
        }
      });

      if (widgetKey === 'paragraph') {
        const textField = widgetEl.querySelector('[name="text"]');
        if (textField && sectionId) {
          textField.setAttribute('readonly', 'true');
          textField.setAttribute('aria-readonly', 'true');
        }
      }
    }

    function setWidgetButtonsDisabled(widgetEl, disabled) {
      if (!widgetEl) {
        return;
      }

      const buttons = widgetEl.querySelectorAll(
          '[data-widget-action],[data-widget-action-id],[data-widget-action-name],[data-widget-delete-section-id]',
      );

      buttons.forEach((btn) => {
        if (!btn) return;
        btn.disabled = disabled;
        if (disabled) {
          btn.setAttribute('aria-disabled', 'true');
        } else {
          btn.removeAttribute('aria-disabled');
        }
      });
    }

    function shouldDisableWidgetButtons(widgetKey, actionId) {
      const normalizedKey = (widgetKey || '').toLowerCase();
      const normalizedAction = (actionId || '').toLowerCase();
      if (normalizedKey !== 'paragraph') {
        return false;
      }
      return ['generate', 'summarize', 'expand'].includes(normalizedAction);
    }

    function parseSectionId(value) {
      if (value == null) {
        return null;
      }
      const parsed = Number(value);
      return Number.isNaN(parsed) ? null : parsed;
    }

    function getEntrySectionId(entry) {
      if (!entry || !entry.dataset) {
        return null;
      }
      return parseSectionId(entry.dataset.widgetSectionId);
    }

    function getWidgetEntries() {
      return Array.from(element.querySelectorAll('[data-topic-widget-entry]'));
    }

    function getMovableEntries() {
      return getWidgetEntries().filter((entry) => getEntrySectionId(entry) != null);
    }

    function updateMoveButtonStates() {
      const movableEntries = getMovableEntries();
      const lastMovableIndex = movableEntries.length - 1;
      getWidgetEntries().forEach((entry) => {
        const sectionId = getEntrySectionId(entry);
        const index = sectionId != null ? movableEntries.indexOf(entry) : -1;
        const upButton = entry.querySelector('[data-widget-move="up"]');
        const downButton = entry.querySelector('[data-widget-move="down"]');

        const disableUp = reorderState.pending || index <= 0;
        const disableDown = reorderState.pending || index === -1 || index >= lastMovableIndex;

        if (upButton) {
          upButton.disabled = disableUp || sectionId == null;
          if (upButton.disabled) {
            upButton.setAttribute('aria-disabled', 'true');
          } else {
            upButton.removeAttribute('aria-disabled');
          }
        }

        if (downButton) {
          downButton.disabled = disableDown || sectionId == null;
          if (downButton.disabled) {
            downButton.setAttribute('aria-disabled', 'true');
          } else {
            downButton.removeAttribute('aria-disabled');
          }
        }
      });
    }

    function captureWidgetOrder() {
      return getWidgetEntries();
    }

    function restoreWidgetOrder(snapshot) {
      if (!Array.isArray(snapshot)) {
        return;
      }
      snapshot.forEach((node) => {
        if (node && node.parentNode === element) {
          element.appendChild(node);
        }
      });
    }

    async function persistWidgetOrder() {
      const entries = getMovableEntries();
      if (!entries.length) {
        throw new Error('Unable to determine widget section order');
      }

      const sectionIds = entries
        .map((entry) => getEntrySectionId(entry))
        .filter((sectionId) => sectionId != null);

      if (!sectionIds.length) {
        throw new Error('No section identifiers available');
      }

      const response = await fetch('/api/topics/widgets/sections/reorder', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({
          topic_uuid: topicUuid,
          section_ids: sectionIds,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to reorder widget sections');
      }
    }

    function moveEntry(entry, direction) {
      if (!entry) {
        return false;
      }

      const entries = getWidgetEntries();
      const index = entries.indexOf(entry);
      if (index === -1) {
        return false;
      }

      if (direction === 'up' && index > 0) {
        const previousEntry = entries[index - 1];
        if (previousEntry) {
          element.insertBefore(entry, previousEntry);
          return true;
        }
      }

      if (direction === 'down' && index < entries.length - 1) {
        const nextEntry = entries[index + 1];
        if (nextEntry) {
          element.insertBefore(entry, nextEntry.nextSibling);
          return true;
        }
      }

      return false;
    }

    function performDeleteRequest(sectionId) {
      return fetch(`/api/topics/widgets/sections/${sectionId}`, {
        method: 'DELETE',
        headers: {
          'X-CSRFToken': getCsrfToken(),
        },
      }).then((response) => {
        if (!response.ok) {
          throw new Error(`Failed to delete widget section (status ${response.status})`);
        }
        return response.json().catch(() => ({}));
      });
    }

    function resolveActionIdentifier(button) {
      if (!button) {
        return null;
      }
      const { dataset } = button;
      if (!dataset) {
        return null;
      }
      return dataset.widgetActionName
        || dataset.widgetAction
        || dataset.widgetActionId
        || null;
    }

    function hideActionButton(widgetEl, actionId) {
      if (!widgetEl || !actionId) {
        return;
      }
      const normalizedAction = String(actionId).toLowerCase();
      const buttons = widgetEl.querySelectorAll(
        '[data-widget-action],[data-widget-action-id],[data-widget-action-name]',
      );
      buttons.forEach((btn) => {
        const identifier = resolveActionIdentifier(btn);
        if (!identifier) {
          return;
        }
        if (String(identifier).toLowerCase() !== normalizedAction) {
          return;
        }
        btn.dataset.widgetForceHidden = 'true';
        btn.classList.add('d-none');
      });
    }

    function stopPolling(sectionId) {
      if (!sectionId) {
        return;
      }
      const key = buildPollKey(topicUuid, sectionId);
      const poller = executionPollers.get(key);
      if (poller && poller.timeoutId) {
        clearTimeout(poller.timeoutId);
      }
      executionPollers.delete(key);
    }

    function startPolling(sectionId, options) {
      if (!sectionId) {
        return;
      }
      const pollKey = buildPollKey(topicUuid, sectionId);
      if (executionPollers.has(pollKey)) {
        executionPollers.get(pollKey).context = options;
        return;
      }

      const state = {
        attempts: 0,
        timeoutId: null,
        context: options,
        stopped: false,
        hasSeenNonFinishedStatus: false,
      };
      executionPollers.set(pollKey, state);

      const fetchStatus = async () => {
        const params = new URLSearchParams({ topic_uuid: topicUuid });
        const response = await fetch(`/api/topics/widgets/sections/${sectionId}?${params.toString()}`);
        if (!response.ok) {
          return null;
        }
        return response.json();
      };

      const scheduleNext = () => {
        state.timeoutId = window.setTimeout(runPoll, POLL_INTERVAL_MS);
      };

      const finish = () => {
        state.stopped = true;
        if (state.timeoutId) {
          clearTimeout(state.timeoutId);
        }
        executionPollers.delete(pollKey);
      };

      const runPoll = async () => {
        if (state.stopped) {
          return;
        }
        state.attempts += 1;

        let snapshot = null;
        try {
          snapshot = await fetchStatus();
        } catch (error) {
          console.error('[TopicWidgets][Shell] Failed to fetch widget section status', error);
        }

        const actionId = state.context ? state.context.actionId : null;
        const actionBanner = (phase) => resolveActionBanner(actionId, phase);

        if (!snapshot) {
          if (state.attempts >= MAX_POLL_ATTEMPTS) {
            if (state.context.statusEl) {
              setValidationState(state.context.statusEl, actionBanner('timeout'), 'warning');
            }
            if (state.context && state.context.widgetEl) {
              setWidgetButtonsDisabled(state.context.widgetEl, false);
            }
            finish();
            return;
          }
          scheduleNext();
          return;
        }

        const { status, content, error_message: errorMessage, section_id: responseSectionId } = snapshot;

        // Keep section id in sync if backend created/changed it
        if (
          responseSectionId &&
          state.context &&
          state.context.widgetEl &&
          !state.context.widgetEl.dataset.widgetSectionId
        ) {
          state.context.widgetEl.dataset.widgetSectionId = responseSectionId;
          updateActionVisibility(state.context.widgetEl);
        }

        // Always apply the latest content if present
        if (content && state.context.widgetEl) {
          updateWidgetContent(state.context.widgetEl, content, state.context.widgetKey);
          updateActionVisibility(state.context.widgetEl);
        }

        // Track whether we've seen a non-finished status for this execution
        if (status && status !== 'finished') {
          state.hasSeenNonFinishedStatus = true;
        }

        // SUCCESS: only when we have seen a non-finished status first
        if (status === 'finished' && state.hasSeenNonFinishedStatus) {
          if (state.context.statusEl) {
            setValidationState(state.context.statusEl, actionBanner('success'), 'success');
          }

          if (state.context) {
            const { widgetEl, widgetKey, actionId: currentActionId } = state.context;
            const normalizedWidgetKey = (widgetKey || '').toLowerCase();
            const normalizedActionId = currentActionId != null ? String(currentActionId).toLowerCase() : '';

            if (widgetEl) {
              setWidgetButtonsDisabled(widgetEl, false);
            }

            // Special case: paragraph generate → clear instructions
            if (normalizedWidgetKey === 'paragraph' && normalizedActionId === 'generate') {
              if (widgetEl) {
                const instructionField = widgetEl.querySelector('[name="instructions"]');
                if (instructionField) {
                  setFieldValue(instructionField, '');
                  instructionField.dispatchEvent(new Event('input', { bubbles: true }));
                  instructionField.dispatchEvent(new Event('change', { bubbles: true }));
                }
              }
            }
          }

          finish();
          return;
        }

        if (status === 'finished' && !state.hasSeenNonFinishedStatus) {
          if (state.context.statusEl) {
            setValidationState(state.context.statusEl, actionBanner('running'), 'info');
          }
          if (state.attempts >= MAX_POLL_ATTEMPTS) {
            if (state.context && state.context.statusEl) {
              setValidationState(state.context.statusEl, actionBanner('timeout'), 'warning');
            }
            if (state.context && state.context.widgetEl) {
              setWidgetButtonsDisabled(state.context.widgetEl, false);
            }
            finish();
            return;
          }
          scheduleNext();
          return;
        }

        // FAILURE
        if (status === 'failed' || status === 'error') {
          if (state.context.statusEl) {
            const failureMessage = errorMessage || actionBanner('failure');
            setValidationState(state.context.statusEl, failureMessage, 'danger');
          }
          if (state.context && state.context.widgetEl) {
            setWidgetButtonsDisabled(state.context.widgetEl, false);
          }
          finish();
          return;
        }

        // RUNNING / QUEUED
        if (status === 'running' || status === 'queued') {
          if (state.context.statusEl) {
            setValidationState(state.context.statusEl, actionBanner('running'), 'info');
          }
        }

        // TIMEOUT check
        if (state.attempts >= MAX_POLL_ATTEMPTS) {
          if (state.context && state.context.statusEl) {
            setValidationState(state.context.statusEl, actionBanner('timeout'), 'warning');
          }
          if (state.context && state.context.widgetEl) {
            setWidgetButtonsDisabled(state.context.widgetEl, false);
          }
          finish();
          return;
        }

        scheduleNext();
      };

      runPoll();
    }

    async function onActionClick(button) {
      if (!button) {
        return;
      }
      const widgetEl = button.closest('[data-topic-widget]');
      if (!widgetEl) {
        // eslint-disable-next-line no-console
        console.warn('[TopicWidgets][Shell] Action click without widget context');
        return;
      }
      const actionId = resolveActionIdentifier(button);
      if (!actionId) {
        // eslint-disable-next-line no-console
        console.warn('[TopicWidgets][Shell] Action click missing identifier', { widgetKey: widgetEl.dataset.topicWidgetKey });
        return;
      }
      const sectionId = getSectionId(widgetEl);
      const statusEl = widgetEl.querySelector('[data-widget-validation]');
      const entryEl = widgetEl.closest('[data-topic-widget-entry]');
      const widgetKey =
        widgetEl.dataset.topicWidgetKey
        || (entryEl && entryEl.dataset.topicWidgetKey)
        || definition.key;

      const normalizedWidgetKey = (widgetKey || '').toLowerCase();
      const normalizedActionId = (actionId || '').toLowerCase();

      console.log('[TopicWidgets][Shell] Action clicked', {
        topicUuid,
        widget_name: widgetKey,
        action: actionId,
        section_id: sectionId,
      });

      if (statusEl) {
        setValidationState(statusEl, resolveActionBanner(actionId, 'queued'), 'info');
      }

      if (shouldDisableWidgetButtons(normalizedWidgetKey, normalizedActionId)) {
        setWidgetButtonsDisabled(widgetEl, true);
      }

      try {
        let contextPayload = serializeWidgetContext(widgetEl);

        if (normalizedWidgetKey === 'paragraph' && normalizedActionId === 'generate') {
          contextPayload = collectParagraphGenerationContext(widgetEl, contextPayload);
        }

        console.log('[TopicWidgets][Shell] contextPayload', contextPayload);

        const requestBody = {
          topic_uuid: topicUuid,
          widget_name: widgetKey,
          action: actionId,
          section_id: sectionId,
        };

        if (
          normalizedWidgetKey === 'paragraph'
          && (normalizedActionId === 'summarize' || normalizedActionId === 'expand')
        ) {
          const extraInstructions = getParagraphInstructions(widgetEl);
          if (extraInstructions) {
            requestBody.extra_instructions = extraInstructions;
          }
        }

        if (Object.keys(contextPayload).length > 0) {
          requestBody.metadata = { context: contextPayload };
        }

        console.log('[TopicWidgets][Shell] requestBody', requestBody);

        const response = await fetch('/api/topics/widgets/execute', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify(requestBody),
        });
        if (!response.ok) {
          throw new Error(`Error ${response.status}`);
        }
        const payload = await response.json();
        widgetEl.dataset.widgetSectionId = payload.section_id;
        if (entryEl) {
          entryEl.dataset.widgetSectionId = payload.section_id != null
            ? String(payload.section_id)
            : '';
        }
        updateActionVisibility(widgetEl);
        updateMoveButtonStates();
        if (statusEl) {
          setValidationState(statusEl, resolveActionBanner(actionId, 'queued'), 'info');
        }
        startPolling(payload.section_id, { widgetEl, statusEl, widgetKey, actionId });
      } catch (error) {
        console.error(error);
        if (statusEl) {
          setValidationState(statusEl, 'Unable to queue action', 'danger');
        }
        if (shouldDisableWidgetButtons(normalizedWidgetKey, normalizedActionId)) {
          setWidgetButtonsDisabled(widgetEl, false);
        }
      }
    }

    function getDeleteLabel(button) {
      if (!button) {
        return 'section';
      }
      const label = (button.dataset && button.dataset.widgetDeleteLabel) || 'section';
      return label.trim() || 'section';
    }

      function updateDeleteModalText(label) {
        const normalizedLabel = label || 'section';
        if (deleteTitle) {
          deleteTitle.textContent = `Delete ${normalizedLabel}`;
        }
      if (deleteMessage) {
        deleteMessage.textContent = `Are you sure you want to delete this ${normalizedLabel}?`;
      }
    }

    function onDeleteClick(button) {
      if (!button || !element.contains(button)) {
        return;
      }

      const entry = button.closest('[data-topic-widget-entry]');
      const widgetEl = entry ? entry.querySelector('[data-topic-widget]') : null;
      const sectionId = getSectionId(widgetEl);

      const deleteLabel = getDeleteLabel(button);

      pendingDelete.entry = entry;
      pendingDelete.sectionId = sectionId;
      pendingDelete.label = deleteLabel;

      updateDeleteModalText(deleteLabel);

      if (deleteConfirmBtn) {
        deleteConfirmBtn.dataset.sectionId = sectionId != null ? String(sectionId) : '';
      }

      if (deleteModal) {
        deleteModal.show();
      }
    }

    function resetDeleteState() {
      pendingDelete.entry = null;
      pendingDelete.sectionId = null;
      pendingDelete.label = 'section';
      if (deleteConfirmBtn) {
        deleteConfirmBtn.disabled = false;
        deleteConfirmBtn.removeAttribute('aria-busy');
        deleteConfirmBtn.dataset.sectionId = '';
      }
      if (deleteSpinner) {
        deleteSpinner.classList.add('d-none');
      }
    }

    function handleConfirmedDelete() {
      if (!pendingDelete.entry) {
        resetDeleteState();
        if (deleteModal) {
          deleteModal.hide();
        }
        return;
      }

      const { entry, sectionId, label } = pendingDelete;
      const statusEl = entry.querySelector('[data-widget-validation]');

      if (statusEl) {
        setValidationState(statusEl, `Deleting ${label}…`, 'info');
      }

      const finish = () => {
        resetDeleteState();
        if (deleteModal) {
          deleteModal.hide();
        }
      };

        if (deleteConfirmBtn) {
          deleteConfirmBtn.disabled = true;
          deleteConfirmBtn.setAttribute('aria-busy', 'true');
        }
        if (deleteSpinner) {
          deleteSpinner.classList.remove('d-none');
        }

        if (!sectionId) {
          entry.remove();
          if (statusEl) {
            clearValidation(statusEl);
          }
          updateMoveButtonStates();
          finish();
          return;
        }

      performDeleteRequest(sectionId)
        .then(() => {
          stopPolling(sectionId);
          entry.remove();
          if (statusEl) {
            clearValidation(statusEl);
          }
          updateMoveButtonStates();
          document.dispatchEvent(new CustomEvent('topic:changed'));
        })
        .catch((error) => {
          // eslint-disable-next-line no-console
          console.error('[TopicWidgets][Shell] Failed to delete section', error);
          if (statusEl) {
            setValidationState(statusEl, `Unable to delete ${label}`, 'danger');
          }
        })
          .finally(() => {
            finish();
          });
      }

      element.querySelectorAll('[data-topic-widget]').forEach((widgetNode) => {
        updateActionVisibility(widgetNode);
      });

      updateMoveButtonStates();

      element.addEventListener('widget-editor:init', (event) => {
        const widgetEl = event.detail && event.detail.element ? event.detail.element : null;
        if (!widgetEl || !element.contains(widgetEl)) {
          return;
        }
        const contentContainer = widgetEl.querySelector('[data-widget-editor-content]');
        const widgetKey = (widgetEl.dataset.topicWidgetKey || '').toLowerCase();
        if (widgetKey === 'image' && contentContainer) {
          const imageField = contentContainer.querySelector('[name="image_url"]')
            || contentContainer.querySelector('[name="url"]');
          const value = imageField ? getFieldValue(imageField) : '';
          updateImagePreview(contentContainer, typeof value === 'string' ? value : '');
        } else if (widgetKey === 'paragraph' && contentContainer) {
          const textField = contentContainer.querySelector('[name="text"]');
          const value = textField ? getFieldValue(textField) : '';
          updateParagraphPreview(contentContainer, typeof value === 'string' ? value : '');
        }
        updateActionVisibility(widgetEl);
        updateMoveButtonStates();
      });

      element.addEventListener('input', (event) => {
        const widgetEl = event.target && typeof event.target.closest === 'function'
          ? event.target.closest('[data-topic-widget]')
          : null;
        if (!widgetEl || !element.contains(widgetEl)) {
          return;
        }
        const contentContainer = widgetEl.querySelector('[data-widget-editor-content]');
        const widgetKey = (widgetEl.dataset.topicWidgetKey || '').toLowerCase();
        if (widgetKey === 'image' && contentContainer) {
          const imageField = contentContainer.querySelector('[name="image_url"]')
            || contentContainer.querySelector('[name="url"]');
          const value = imageField ? getFieldValue(imageField) : '';
          updateImagePreview(contentContainer, typeof value === 'string' ? value : '');
        } else if (widgetKey === 'paragraph' && contentContainer) {
          const textField = contentContainer.querySelector('[name="text"]');
          const value = textField ? getFieldValue(textField) : '';
          updateParagraphPreview(contentContainer, typeof value === 'string' ? value : '');
        }
        updateActionVisibility(widgetEl);
      });

      console.log('[TopicWidgets][Shell] Attaching delegated event listener to document.');
      document.addEventListener('click', (evt) => {
        const button = evt.target.closest('[data-widget-action],[data-widget-action-id],[data-widget-action-name]');
        if (button && element.contains(button)) {
          onActionClick(button);
        }
      }, { capture: true });

      document.addEventListener('click', (evt) => {
        const deleteButton = evt.target.closest('[data-widget-delete-section-id]');
        if (deleteButton && element.contains(deleteButton)) {
          evt.preventDefault();
          onDeleteClick(deleteButton);
        }
      }, { capture: true });

      document.addEventListener('click', (event) => {
        if (!(event.target instanceof Element)) {
          return;
        }

        const moveButton = event.target.closest('[data-widget-move]');
        if (!moveButton || !element.contains(moveButton)) {
          return;
        }

        event.preventDefault();
        if (reorderState.pending) {
          return;
        }

        const entry = moveButton.closest('[data-topic-widget-entry]');
        const sectionId = getEntrySectionId(entry);
        if (!entry || sectionId == null) {
          updateMoveButtonStates();
          return;
        }

        const direction = (moveButton.dataset && moveButton.dataset.widgetMove === 'up') ? 'up' : 'down';
        const snapshot = captureWidgetOrder();
        const moved = moveEntry(entry, direction);
        if (!moved) {
          updateMoveButtonStates();
          return;
        }

        reorderState.pending = true;
        updateMoveButtonStates();

        const statusEl = entry.querySelector('[data-widget-validation]');
        if (statusEl) {
          clearValidation(statusEl);
        }

        persistWidgetOrder()
          .then(() => {
            document.dispatchEvent(new CustomEvent('topic:changed'));
          })
          .catch((error) => {
            // eslint-disable-next-line no-console
            console.error('[TopicWidgets][Shell] Failed to reorder sections', error);
            restoreWidgetOrder(snapshot);
            if (statusEl) {
              setValidationState(
                statusEl,
                statusEl.dataset && statusEl.dataset.reorderError
                  ? statusEl.dataset.reorderError
                  : 'Unable to reorder sections. Please try again.',
                'danger',
              );
            }
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
      }, { capture: true });

      if (deleteConfirmBtn) {
        deleteConfirmBtn.addEventListener('click', (event) => {
          event.preventDefault();
          handleConfirmedDelete();
      });
    }

    if (deleteModalEl) {
      deleteModalEl.addEventListener('hidden.bs.modal', () => {
        resetDeleteState();
      });
    }

    element.addEventListener('widget-editor:destroy', (event) => {
      const entry = event.target && typeof event.target.closest === 'function'
        ? event.target.closest('[data-topic-widget-entry]')
        : null;
      if (!entry || !element.contains(entry)) {
        return;
      }
      const widgetInstance = entry.querySelector('[data-topic-widget]');
      const sectionId = getSectionId(widgetInstance);
      stopPolling(sectionId);
    });

    return {};
  });
}());
