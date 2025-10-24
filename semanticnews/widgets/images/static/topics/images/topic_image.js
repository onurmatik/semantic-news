document.addEventListener('DOMContentLoaded', () => {
  const controller = setupGenerationButton({
    buttonId: 'imageButton',
    spinnerId: 'imageSpinner',
    errorIconId: 'imageErrorIcon',
    successIconId: 'imageSuccessIcon',
  });

  const topicUuid = (() => {
    const topicContext = document.querySelector('[data-topic-uuid]');
    return topicContext ? topicContext.getAttribute('data-topic-uuid') : null;
  })();
  const previewWrapper = document.getElementById('imagePreviewWrapper');
  const imageEl = document.getElementById('topicImageLatest');
  const statusMessageEl = document.getElementById('imageStatusMessage');
  const clearBtn = document.getElementById('imageClearBtn');
  const clearBtnDefaultTitle = clearBtn ? clearBtn.getAttribute('title') || '' : '';
  const clearBtnDefaultLabel = clearBtn ? clearBtn.getAttribute('aria-label') || '' : '';
  const clearBtnRemovedLabel = 'Cover image removed';

  const setImageState = ({ hasImage }) => {
    const effectiveHasImage = Boolean(hasImage);
    if (previewWrapper) {
      if (effectiveHasImage) {
        previewWrapper.style.display = '';
      } else {
        previewWrapper.style.display = 'none';
      }
    }

    if (clearBtn) {
      clearBtn.classList.remove('d-none');
      clearBtn.disabled = false;
      clearBtn.classList.toggle('btn-outline-secondary', effectiveHasImage);
      clearBtn.classList.toggle('btn-outline-warning', !effectiveHasImage);
      clearBtn.classList.toggle('text-warning', !effectiveHasImage);
      if (effectiveHasImage) {
        if (clearBtnDefaultTitle) {
          clearBtn.setAttribute('title', clearBtnDefaultTitle);
        }
        if (clearBtnDefaultLabel) {
          clearBtn.setAttribute('aria-label', clearBtnDefaultLabel);
        }
      } else {
        const removedTitle = clearBtnDefaultTitle || clearBtnRemovedLabel;
        const removedLabel = clearBtnDefaultLabel || clearBtnRemovedLabel;
        clearBtn.setAttribute('title', removedTitle);
        clearBtn.setAttribute('aria-label', removedLabel);
      }
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
  setImageState({ hasImage: initialHasImage });

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
      setImageState({ hasImage: false });
      clearStatusMessage();
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
        } else {
          img.removeAttribute('src');
        }
      }
      const hasImage = Boolean(imageUrl);
      setImageState({ hasImage });
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
    getInitialIndex: ({ items }) => {
      if (!Array.isArray(items) || !items.length) {
        return null;
      }
      const heroIndex = items.findIndex((item) => item && item.is_hero);
      if (heroIndex >= 0) {
        return heroIndex;
      }
      return null;
    },
    onInitialItemMissing: () => {
      if (imageEl) {
        imageEl.removeAttribute('src');
      }
      setImageState({ hasImage: false });
      clearStatusMessage();
    },
  });

  // Override/extend the exposed hooks for image so status_checker can paint without reload
  window.__imageExternalApply = (imageUrl, thumbUrl, _createdAtIso) => {
    const img = document.getElementById('topicImageLatest');
    const resolvedUrl = imageUrl || thumbUrl || '';
    if (img && resolvedUrl) {
      img.src = resolvedUrl;
    } else if (img && !resolvedUrl) {
      img.removeAttribute('src');
    }
    if (previewWrapper) {
      previewWrapper.style.display = resolvedUrl ? '' : 'none';
    }
    setImageState({ hasImage: Boolean(resolvedUrl) });
    clearStatusMessage();
    document.dispatchEvent(new CustomEvent('topic:changed'));
  };
});
