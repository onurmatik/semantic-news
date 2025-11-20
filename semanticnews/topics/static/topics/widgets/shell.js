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
    const placeholder = document.createElement('p');
    placeholder.className = 'text-muted mb-0';
    placeholder.textContent = 'No preview available yet.';
    preview.appendChild(placeholder);
  }

  function normaliseWidgetContent(widgetKey, content) {
    if (!content || typeof content !== 'object') {
      return {};
    }

    const normalized = { ...content };
    const key = widgetKey || '';

    if (key === 'paragraph' && typeof normalized.text !== 'string') {
      const resultVal = normalized.result;
      if (typeof resultVal === 'string' && resultVal.trim()) {
        normalized.text = resultVal;
      }
    }

    if (key === 'image') {
      const resultVal = normalized.result;
      if (!normalized.image_url && !normalized.imageUrl && typeof resultVal === 'string') {
        const cleaned = resultVal.trim();
        if (cleaned.startsWith('http://') || cleaned.startsWith('https://') || cleaned.startsWith('data:')) {
          normalized.image_url = cleaned;
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
        if (!snapshot) {
          if (state.attempts >= MAX_POLL_ATTEMPTS) {
            if (state.context.statusEl) {
              setValidationState(state.context.statusEl, 'Timed out while waiting for action', 'warning');
            }
            finish();
            return;
          }
          scheduleNext();
          return;
        }

        const { status, content, error_message: errorMessage, section_id: responseSectionId } = snapshot;
        if (responseSectionId && state.context && state.context.widgetEl && !state.context.widgetEl.dataset.widgetSectionId) {
          state.context.widgetEl.dataset.widgetSectionId = responseSectionId;
        }

        if (content && state.context.widgetEl) {
          updateWidgetContent(state.context.widgetEl, content, state.context.widgetKey);
        }

        if (status === 'finished' || (!status && content)) {
          if (state.context.statusEl) {
            setValidationState(state.context.statusEl, 'Action completed', 'success');
          }
          finish();
          return;
        }

        if (status === 'failed' || status === 'error') {
          if (state.context.statusEl) {
            setValidationState(state.context.statusEl, errorMessage || 'Unable to complete action', 'danger');
          }
          finish();
          return;
        }

        if (status === 'running' && state.context.statusEl) {
          setValidationState(state.context.statusEl, 'Processing action…', 'info');
        }

        if (state.attempts >= MAX_POLL_ATTEMPTS) {
          if (state.context.statusEl) {
            setValidationState(state.context.statusEl, 'Timed out while waiting for action', 'warning');
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

      console.log('[TopicWidgets][Shell] Action clicked', {
        topicUuid,
        widget_name: widgetKey,
        action: actionId,
        section_id: sectionId,
      });

      if (statusEl) {
        setValidationState(statusEl, 'Queuing action…', 'info');
      }

      try {
        const contextPayload = serializeWidgetContext(widgetEl);

        console.log('[TopicWidgets][Shell] contextPayload', contextPayload);

        const requestBody = {
          topic_uuid: topicUuid,
          widget_name: widgetKey,
          action: actionId,
          section_id: sectionId,
        };

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
        if (statusEl) {
          setValidationState(statusEl, 'Action queued', 'success');
        }
        startPolling(payload.section_id, { widgetEl, statusEl, widgetKey });
      } catch (error) {
        console.error(error);
        if (statusEl) {
          setValidationState(statusEl, 'Unable to queue action', 'danger');
        }
      }
    }

    console.log('[TopicWidgets][Shell] Attaching delegated event listener to document.');
    document.addEventListener('click', (evt) => {
      const button = evt.target.closest('[data-widget-action],[data-widget-action-id],[data-widget-action-name]');
      if (button && element.contains(button)) {
        onActionClick(button);
      }
    }, { capture: true });

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
