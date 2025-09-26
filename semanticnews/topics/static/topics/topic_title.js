document.addEventListener('DOMContentLoaded', () => {
  const modalEl = document.getElementById('editTopicTitleModal');
  const topicEl = document.querySelector('[data-topic-uuid]');
  if (!modalEl || !topicEl) {
    return;
  }

  const form = modalEl.querySelector('form');
  if (!form) {
    return;
  }

  const input = form.querySelector('input[name="title"]');
  const errorEl = modalEl.querySelector('#editTopicTitleError');
  const displayEl = document.getElementById('topicTitleDisplay');
  const defaultTitle = displayEl?.dataset.untitled ?? '';

  modalEl.addEventListener('show.bs.modal', () => {
    if (errorEl) {
      errorEl.classList.add('d-none');
      errorEl.textContent = '';
    }
    if (input) {
      input.value = topicEl.dataset.topicTitle ?? '';
      requestAnimationFrame(() => {
        input.focus();
        input.select();
      });
    }
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!input) {
      return;
    }

    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) {
      submitBtn.disabled = true;
    }
    if (errorEl) {
      errorEl.classList.add('d-none');
      errorEl.textContent = '';
    }

    const payload = {
      topic_uuid: topicEl.dataset.topicUuid,
      title: input.value.trim(),
    };

    try {
      const response = await fetch('/api/topics/set-title', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        let message = 'Unable to update the topic title.';
        try {
          const errorData = await response.json();
          if (typeof errorData?.detail === 'string' && errorData.detail.trim()) {
            message = errorData.detail;
          }
        } catch (jsonError) {
          const text = await response.text();
          if (text.trim()) {
            message = text;
          }
        }
        throw new Error(message);
      }

      const data = await response.json();
      const newTitle = data.title ?? '';
      topicEl.dataset.topicTitle = newTitle;

      if (displayEl) {
        displayEl.textContent = newTitle.trim() ? newTitle : defaultTitle;
      }
      if (newTitle.trim()) {
        document.title = newTitle;
      } else if (defaultTitle) {
        document.title = defaultTitle;
      }

      const modalInstance =
        bootstrap.Modal.getInstance(modalEl) ||
        bootstrap.Modal.getOrCreateInstance(modalEl);
      if (typeof data.slug === 'string' && data.slug) {
        topicEl.dataset.topicSlug = data.slug;
      }

      if (typeof data.edit_url === 'string' && data.edit_url && data.edit_url !== window.location.pathname) {
        window.location.href = data.edit_url;
        return;
      }

      if (modalInstance) {
        modalInstance.hide();
      }
    } catch (error) {
      console.error(error);
      if (errorEl) {
        errorEl.textContent = error.message || 'Unable to update the topic title.';
        errorEl.classList.remove('d-none');
      }
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
      }
    }
  });
});
