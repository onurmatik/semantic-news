(function () {
  function ready(callback) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', callback, { once: true });
    } else {
      callback();
    }
  }

  ready(() => {
    const form = document.getElementById('externalContentForm');
    if (!form) {
      return;
    }

    const card = document.getElementById('externalContentCard');
    const typeSelect = document.getElementById('externalContentType');
    const urlInput = document.getElementById('externalContentUrl');
    const titleInput = document.getElementById('externalContentTitle');
    const descriptionInput = document.getElementById('externalContentDescription');
    const saveBtn = document.getElementById('externalContentSaveBtn');
    const statusMessage = document.getElementById('externalContentStatus');
    const metadataFields = Array.from(form.querySelectorAll('[data-content-fields="metadata"]'));
    const messages = {
      invalid: form.dataset.errorMessage || 'Please provide a valid URL.',
      saving: form.dataset.savingMessage || 'Saving…',
      failure: form.dataset.failureMessage || 'Unable to save the content. Please try again.',
    };

    const setStatus = (variant, message) => {
      if (!statusMessage) return;
      statusMessage.textContent = message || '';
      statusMessage.classList.remove('alert-success', 'alert-danger', 'alert-info');
      if (variant === 'error') {
        statusMessage.classList.add('alert-danger');
      } else if (variant === 'success') {
        statusMessage.classList.add('alert-success');
      } else if (variant === 'info') {
        statusMessage.classList.add('alert-info');
      }
      if (!message) {
        statusMessage.classList.add('d-none');
      } else {
        statusMessage.classList.remove('d-none');
      }
    };

    const updateFieldVisibility = () => {
      const type = typeSelect ? typeSelect.value : 'document';
      const showMetadata = type === 'document' || type === 'webpage';
      metadataFields.forEach((field) => {
        if (showMetadata) {
          field.classList.remove('d-none');
        } else {
          field.classList.add('d-none');
        }
      });
    };

    const resetForm = () => {
      form.reset();
      updateFieldVisibility();
      setStatus(null, '');
      if (saveBtn) {
        saveBtn.disabled = false;
        saveBtn.removeAttribute('aria-busy');
      }
    };

    updateFieldVisibility();
    if (typeSelect) {
      typeSelect.addEventListener('change', updateFieldVisibility);
    }

    if (card) {
      card.addEventListener('content-toolbar:show', () => {
        resetForm();
      });
    }

    const getEndpointForType = (type) => {
      switch (type) {
        case 'webpage':
          return '/api/topics/document/webpage/create';
        case 'video':
          return '/api/topics/embed/video/add';
        case 'tweet':
          return '/api/topics/embed/tweet/add';
        case 'document':
        default:
          return '/api/topics/document/create';
      }
    };

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const type = typeSelect ? typeSelect.value : 'document';
      const endpoint = getEndpointForType(type);
      const formData = new FormData(form);
      const payload = {
        topic_uuid: formData.get('topic_uuid') || '',
        url: urlInput ? urlInput.value.trim() : '',
      };

      if (type === 'document' || type === 'webpage') {
        payload.title = titleInput ? titleInput.value.trim() : '';
        payload.description = descriptionInput ? descriptionInput.value.trim() : '';
      }

      if (!payload.topic_uuid || !payload.url) {
        setStatus('error', messages.invalid);
        return;
      }

      if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.setAttribute('aria-busy', 'true');
      }
      setStatus('info', messages.saving);

      try {
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!response.ok) {
          throw new Error('Request failed');
        }
        await response.json();
        window.location.reload();
      } catch (error) {
        console.error(error);
        setStatus('error', messages.failure);
        if (saveBtn) {
          saveBtn.disabled = false;
          saveBtn.removeAttribute('aria-busy');
        }
      }
    });
  });
}());
