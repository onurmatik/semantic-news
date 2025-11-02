(function () {
  const registry = window.TopicWidgetRegistry;

  if (!registry) {
    return;
  }

  function getCsrfToken() {
    const name = 'csrftoken=';
    const cookies = document.cookie ? document.cookie.split(';') : [];
    for (let i = 0; i < cookies.length; i += 1) {
      const cookie = cookies[i].trim();
      if (cookie.startsWith(name)) {
        return decodeURIComponent(cookie.substring(name.length));
      }
    }
    return '';
  }

  function setValidationState(wrapper, message, variant) {
    if (!wrapper) return;
    const classes = ['alert-info', 'alert-success', 'alert-danger', 'alert-warning', 'alert-secondary'];
    wrapper.classList.remove('d-none');
    wrapper.classList.remove(...classes);
    wrapper.classList.add(`alert-${variant || 'info'}`);
    wrapper.textContent = message || '';
  }

  function clearValidation(wrapper) {
    if (!wrapper) return;
    wrapper.classList.add('d-none');
    wrapper.textContent = '';
  }

  registry.register('url', (context) => {
    const { element, definition, topicUuid } = context || {};
    if (!element || !definition || !topicUuid) {
      return null;
    }

    const body = element.querySelector('[data-widget-editor-body]');
    if (!body) {
      return null;
    }

    body.innerHTML = '';

    const urlGroup = document.createElement('div');
    urlGroup.className = 'mb-3';

    const urlLabel = document.createElement('label');
    urlLabel.className = 'form-label';
    urlLabel.textContent = 'Source URL';

    const urlInput = document.createElement('input');
    urlInput.type = 'url';
    urlInput.className = 'form-control';
    urlInput.placeholder = 'https://example.com/article';

    urlGroup.appendChild(urlLabel);
    urlGroup.appendChild(urlInput);

    const noteGroup = document.createElement('div');
    noteGroup.className = 'mb-3';

    const noteLabel = document.createElement('label');
    noteLabel.className = 'form-label';
    noteLabel.textContent = 'Notes';

    const noteInput = document.createElement('textarea');
    noteInput.className = 'form-control';
    noteInput.rows = 4;

    noteGroup.appendChild(noteLabel);
    noteGroup.appendChild(noteInput);

    const saveBtn = document.createElement('button');
    saveBtn.type = 'button';
    saveBtn.className = 'btn btn-primary btn-sm';
    saveBtn.textContent = 'Save link';

    const status = element.querySelector('[data-widget-validation]');
    clearValidation(status);

    body.appendChild(urlGroup);
    body.appendChild(noteGroup);
    body.appendChild(saveBtn);

    let sectionId = null;
    let saving = false;

    async function persist() {
      const content = {
        url: urlInput.value || '',
        notes: noteInput.value || '',
      };

      const url = sectionId
        ? `/api/topics/widget/sections/${sectionId}`
        : '/api/topics/widget/sections';
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
        throw new Error('Unable to save link');
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
        await persist();
        setValidationState(status, 'Link saved', 'success');
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error(error);
        setValidationState(status, 'Unable to save link', 'danger');
      } finally {
        saving = false;
      }
    });

    return null;
  });
}());
