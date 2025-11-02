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

  registry.register('text', (context) => {
    const { element, definition, topicUuid } = context || {};
    if (!element || !definition || !topicUuid) {
      return null;
    }

    const body = element.querySelector('[data-widget-editor-body]');
    if (!body) {
      return null;
    }

    body.innerHTML = '';

    const textarea = document.createElement('textarea');
    textarea.className = 'form-control';
    textarea.rows = 10;
    textarea.placeholder = 'Write your summary…';

    const controls = document.createElement('div');
    controls.className = 'd-flex align-items-center gap-2';

    const saveBtn = document.createElement('button');
    saveBtn.type = 'button';
    saveBtn.className = 'btn btn-primary btn-sm';
    saveBtn.textContent = 'Save';

    const status = element.querySelector('[data-widget-validation]');
    clearValidation(status);

    controls.appendChild(saveBtn);
    body.appendChild(textarea);
    body.appendChild(controls);

    let sectionId = null;
    let saving = false;

    async function createSection() {
      if (saving) return;
      saving = true;
      setValidationState(status, 'Saving…', 'info');
      try {
        const response = await fetch('/api/topics/widget/sections', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify({
            topic_uuid: topicUuid,
            widget_id: definition.id,
            content: textarea.value || '',
          }),
        });
        if (!response.ok) {
          throw new Error('Unable to save section');
        }
        const payload = await response.json();
        sectionId = payload && payload.id ? payload.id : null;
        if (sectionId) {
          element.dataset.widgetSectionId = String(sectionId);
        }
        setValidationState(status, 'Saved', 'success');
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error(error);
        setValidationState(status, 'Unable to save section', 'danger');
      } finally {
        saving = false;
      }
    }

    async function updateSection() {
      if (!sectionId || saving) {
        return;
      }
      saving = true;
      setValidationState(status, 'Saving…', 'info');
      try {
        const response = await fetch(`/api/topics/widget/sections/${sectionId}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
          },
          body: JSON.stringify({
            topic_uuid: topicUuid,
            content: textarea.value || '',
          }),
        });
        if (!response.ok) {
          throw new Error('Unable to update section');
        }
        setValidationState(status, 'Saved', 'success');
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error(error);
        setValidationState(status, 'Unable to save section', 'danger');
      } finally {
        saving = false;
      }
    }

    saveBtn.addEventListener('click', () => {
      if (sectionId) {
        updateSection();
      } else {
        createSection();
      }
    });

    return {
      save: () => {
        if (sectionId) {
          return updateSection();
        }
        return createSection();
      },
    };
  });
}());
