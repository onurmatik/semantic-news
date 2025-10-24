document.addEventListener('DOMContentLoaded', () => {
  const controller = setupGenerationButton({
    buttonId: 'imageButton',
    spinnerId: 'imageSpinner',
    errorIconId: 'imageErrorIcon',
    successIconId: 'imageSuccessIcon',
  });

  const container = document.getElementById('topicImageContainer');
  const topicUuid = (() => {
    const topicContext = document.querySelector('[data-topic-uuid]');
    return topicContext ? topicContext.getAttribute('data-topic-uuid') : null;
  })();
  const badge = document.getElementById('imageActiveBadge');
  const previewWrapper = document.getElementById('imagePreviewWrapper');
  const imageEl = document.getElementById('topicImageLatest');
  const emptyState = document.getElementById('imageEmptyState');
  const inactiveNote = document.getElementById('imageInactiveNote');
  const statusMessageEl = document.getElementById('imageStatusMessage');
  const clearBtn = document.getElementById('imageClearBtn');
  const deleteBtn = document.getElementById('imageDeleteBtn');
  const createdAtEl = document.getElementById('imageCreatedAt');

  const hide = (el) => { if (el) el.classList.add('d-none'); };
  const show = (el) => { if (el) el.classList.remove('d-none'); };

  const setBadge = (isActive) => {
    if (!badge) return;
    const activeLabel = badge.dataset.labelActive || 'Active';
    const inactiveLabel = badge.dataset.labelInactive || 'Inactive';
    badge.textContent = isActive ? activeLabel : inactiveLabel;
    badge.classList.toggle('text-bg-success', isActive);
    badge.classList.toggle('text-bg-secondary', !isActive);
  };

  const setActiveState = ({ isActive, hasImage }) => {
    setBadge(Boolean(isActive && hasImage));

    if (previewWrapper) {
      if (hasImage) {
        previewWrapper.style.display = '';
        previewWrapper.classList.toggle('image-preview--inactive', !isActive);
      } else {
        previewWrapper.style.display = 'none';
        previewWrapper.classList.remove('image-preview--inactive');
      }
    }

    if (inactiveNote) {
      if (!hasImage || isActive) hide(inactiveNote);
      else show(inactiveNote);
    }

    if (emptyState) {
      if (hasImage) hide(emptyState);
      else show(emptyState);
    }

    if (clearBtn) {
      clearBtn.classList.toggle('d-none', !(isActive && hasImage));
      clearBtn.disabled = false;
    }

    if (deleteBtn) {
      deleteBtn.classList.toggle('d-none', !hasImage);
      deleteBtn.disabled = false;
    }
  };

  const clearStatusMessage = () => {
    if (!statusMessageEl) return;
    statusMessageEl.classList.add('d-none');
    statusMessageEl.classList.remove('alert-info', 'alert-danger', 'alert-success');
    statusMessageEl.textContent = '';
  };

  const showStatusMessage = (variant, message) => {
    if (!statusMessageEl) return;
    if (!variant || !message) {
      clearStatusMessage();
      return;
    }
    statusMessageEl.classList.remove('d-none', 'alert-info', 'alert-danger', 'alert-success');
    const className = variant === 'error'
      ? 'alert-danger'
      : variant === 'success'
        ? 'alert-success'
        : 'alert-info';
    statusMessageEl.classList.add(className);
    statusMessageEl.textContent = message;
  };

  const initialHasImage = Boolean(imageEl && imageEl.getAttribute('src'));
  const heroActive = container && container.dataset.heroActive === 'true';
  setActiveState({ isActive: heroActive && initialHasImage, hasImage: initialHasImage });

  const defaultErrorMessage = 'Unable to generate the cover image. Please try again.';
  const defaultClearError = 'Unable to remove the cover image. Please try again.';

  const triggerReload = async () => {
    if (typeof window.__imageReloadAndJump === 'function') {
      try {
        await window.__imageReloadAndJump();
      } catch (err) {
        console.error(err);
      }
    }
  };

  const performImageGeneration = async () => {
    if (!topicUuid) return;
    clearStatusMessage();
    const button = document.getElementById('imageButton');
    if (button && button.dataset) delete button.dataset.error;
    controller && controller.showLoading();

    try {
      const styleSel = document.getElementById('imageStyle');
      const payload = {
        topic_uuid: topicUuid,
      };
      if (styleSel && styleSel.value) {
        payload.style = styleSel.value;
      }

      const res = await fetch('/api/topics/image/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => null);
      const status = data && typeof data.status === 'string' ? data.status.toLowerCase() : '';
      if (!res.ok || status === 'error') {
        const message = (data && data.error_message) || defaultErrorMessage;
        controller && controller.showError();
        if (button && button.dataset) button.dataset.error = message;
        showStatusMessage('error', message);
        return;
      }

      controller && controller.showSuccess();
      if (button && button.dataset) delete button.dataset.error;
      await triggerReload();
      clearStatusMessage();
      document.dispatchEvent(new CustomEvent('topic:changed'));
    } catch (err) {
      console.error(err);
      controller && controller.showError();
      const button = document.getElementById('imageButton');
      if (button && button.dataset) button.dataset.error = defaultErrorMessage;
      showStatusMessage('error', defaultErrorMessage);
    }
  };

  const performClearHero = async () => {
    if (!topicUuid) return;
    if (clearBtn) clearBtn.disabled = true;
    clearStatusMessage();

    try {
      const res = await fetch(`/api/topics/image/${topicUuid}/clear`, { method: 'POST' });
      const data = await res.json().catch(() => null);
      const status = data && typeof data.status === 'string' ? data.status.toLowerCase() : '';
      if (!res.ok || status === 'error') {
        const message = (data && data.error_message) || defaultClearError;
        showStatusMessage('error', message);
        return;
      }

      await triggerReload();
      if (imageEl) imageEl.src = '';
      if (createdAtEl) createdAtEl.textContent = '';
      setActiveState({ isActive: false, hasImage: false });
      showStatusMessage('info', 'Cover image removed.');
      document.dispatchEvent(new CustomEvent('topic:changed'));
    } catch (err) {
      console.error(err);
      showStatusMessage('error', defaultClearError);
    } finally {
      if (clearBtn) clearBtn.disabled = false;
    }
  };

  const generationButton = document.getElementById('imageButton');
  if (generationButton && topicUuid) {
    generationButton.addEventListener('click', () => {
      performImageGeneration();
    });
  }

  if (clearBtn && topicUuid) {
    clearBtn.addEventListener('click', () => {
      performClearHero();
    });
  }

  window.setupTopicHistory({
    key: 'image',
    field: 'image_url',
    listUrl: (uuid) => `/api/topics/image/${uuid}/list`,
    createUrl: '/api/topics/image/create',
    deleteUrl: (id) => `/api/topics/image/${id}`,
    cardSuffix: 'Container',
    renderItem: (item) => {
      const img = document.getElementById('topicImageLatest');
      const imageUrl = item.image_url || item.thumbnail_url || '';
      if (img) {
        if (imageUrl) {
          img.src = imageUrl;
        }
      }
      const hasImage = Boolean(imageUrl);
      setActiveState({ isActive: Boolean(item.is_hero), hasImage });
      clearStatusMessage();
    },
    parseInput: () => {
      const styleSel = document.getElementById('imageStyle');
      return { style: styleSel ? styleSel.value : undefined };
    },
    controller,
    useMarkdown: false,
    messages: {
      updateError: defaultErrorMessage,
    },
  });

  // Override/extend the exposed hooks for image so status_checker can paint without reload
  window.__imageExternalApply = (imageUrl, thumbUrl, createdAtIso) => {
    const img = document.getElementById('topicImageLatest');
    const resolvedUrl = imageUrl || thumbUrl || '';
    if (img && resolvedUrl) img.src = resolvedUrl;
    if (previewWrapper) {
      previewWrapper.style.display = resolvedUrl ? '' : 'none';
      previewWrapper.classList.remove('image-preview--inactive');
    }
    setActiveState({ isActive: Boolean(resolvedUrl), hasImage: Boolean(resolvedUrl) });
    if (createdAtEl && createdAtIso) {
      const d = new Date(createdAtIso);
      createdAtEl.textContent = d.toLocaleString(undefined, {
        year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit'
      });
    }
    clearStatusMessage();
    document.dispatchEvent(new CustomEvent('topic:changed'));
  };
});
