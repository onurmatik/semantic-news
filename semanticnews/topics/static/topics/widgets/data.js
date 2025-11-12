(function () {
  const registry = window.TopicWidgetRegistry;
  const shared = window.TopicWidgetShared;

  if (!registry || !shared) {
    return;
  }

  const { getCsrfToken, setValidationState, clearValidation } = shared;

  registry.register('data', (context) => {
    const { element, definition, topicUuid } = context || {};
    if (!element || !definition || !topicUuid) {
      return null;
    }

    const body = element.querySelector('[data-widget-editor-body]');
    if (!body) {
      return null;
    }

    body.innerHTML = '';

    const widgetIdentifier = definition.id != null && !Number.isNaN(definition.id)
      ? String(definition.id)
      : (definition.key || '');
    const sectionsEndpoint = widgetIdentifier
      ? `/api/topics/widgets/${encodeURIComponent(widgetIdentifier)}/sections`
      : '/api/topics/widgets/sections';

    const instructions = document.createElement('p');
    instructions.className = 'text-secondary small';
    instructions.textContent = 'Paste JSON data below to attach it to this topic.';

    const textarea = document.createElement('textarea');
    textarea.className = 'form-control';
    textarea.rows = 8;
    textarea.placeholder = '{\n  "values": []\n}';

    const saveBtn = document.createElement('button');
    saveBtn.type = 'button';
    saveBtn.className = 'btn btn-primary btn-sm mt-2';
    saveBtn.textContent = 'Save dataset';

    const status = element.querySelector('[data-widget-validation]');
    clearValidation(status);

    body.appendChild(instructions);
    body.appendChild(textarea);
    body.appendChild(saveBtn);

    let sectionId = null;
    let saving = false;

    async function persist(content) {
      const url = sectionId
        ? (widgetIdentifier
            ? `${sectionsEndpoint}/${sectionId}`
            : `/api/topics/widgets/sections/${sectionId}`)
        : sectionsEndpoint;
      const method = sectionId ? 'PUT' : 'POST';

      const payload = {
        topic_uuid: topicUuid,
        content,
      };
      if (!sectionId) {
        payload.widget_id = definition.id;
      }

      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error('Unable to save dataset');
      }

      const data = await response.json();
      if (!sectionId && data && data.id) {
        sectionId = data.id;
        element.dataset.widgetSectionId = String(sectionId);
      }
    }

    saveBtn.addEventListener('click', async () => {
      if (saving) {
        return;
      }
      saving = true;
      setValidationState(status, 'Saving…', 'info');
      try {
        const parsed = textarea.value ? JSON.parse(textarea.value) : {};
        await persist(parsed);
        setValidationState(status, 'Dataset saved', 'success');
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error(error);
        setValidationState(status, 'Unable to save dataset', 'danger');
      } finally {
        saving = false;
      }
    });

    return null;
  });
}());
