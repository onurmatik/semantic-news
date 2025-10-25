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
  const defaultSelectError = 'Unable to set the cover image. Please try again.';
  let currentHeroId = null;
  let selectHeroAbortController = null;
  const canAbortHeroSelection = typeof AbortController === 'function';

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

      const res = await fetch('/api/topics/cover/create', {
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
      const res = await fetch(`/api/topics/cover/${topicUuid}/clear`, { method: 'POST' });
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
      currentHeroId = null;
      document.dispatchEvent(new CustomEvent('topic:changed'));
    } catch (err) {
      console.error(err);
      showStatusMessage('error', defaultClearError);
    } finally {
      if (clearBtn) clearBtn.disabled = false;
    }
  };

  const performHeroSelection = async (imageId) => {
    if (!topicUuid || !imageId) return false;
    if (canAbortHeroSelection && selectHeroAbortController) {
      selectHeroAbortController.abort();
    } else {
      selectHeroAbortController = null;
    }
    const controller = canAbortHeroSelection ? new AbortController() : null;
    selectHeroAbortController = controller;
    try {
      const requestOptions = { method: 'POST' };
      if (controller) {
        requestOptions.signal = controller.signal;
      }
      const res = await fetch(`/api/topics/cover/${topicUuid}/select/${imageId}`, requestOptions);
      const data = await res.json().catch(() => null);
      const status = data && typeof data.status === 'string' ? data.status.toLowerCase() : '';
      if (!res.ok || status === 'error') {
        const message = (data && data.error_message) || defaultSelectError;
        showStatusMessage('error', message);
        return false;
      }

      currentHeroId = imageId;
      await triggerReload().catch(() => {});
      clearStatusMessage();
      setImageState({ hasImage: true });
      document.dispatchEvent(new CustomEvent('topic:changed'));
      return true;
    } catch (err) {
      if (controller && err && err.name === 'AbortError') {
        return false;
      }
      console.error(err);
      showStatusMessage('error', defaultSelectError);
      return false;
    } finally {
      if (selectHeroAbortController === controller) {
        selectHeroAbortController = null;
      }
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
    listUrl: (uuid) => `/api/topics/cover/${uuid}/list`,
    createUrl: '/api/topics/cover/create',
    deleteUrl: (id) => `/api/topics/cover/${id}`,
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
      currentHeroId = null;
    },
    onItemsChanged: ({ items }) => {
      if (!Array.isArray(items)) {
        currentHeroId = null;
        return;
      }
      const heroItem = items.find((entry) => entry && entry.is_hero);
      currentHeroId = heroItem && heroItem.id ? heroItem.id : null;
    },
    onItemApplied: ({ item, items }) => {
      if (!item || !item.id) {
        return;
      }
      if (item.is_hero) {
        currentHeroId = item.id;
        return;
      }
      if (currentHeroId === item.id) {
        return;
      }
      performHeroSelection(item.id).then((wasApplied) => {
        if (!wasApplied) {
          return;
        }
        if (Array.isArray(items)) {
          items.forEach((entry) => {
            if (entry && typeof entry === 'object') {
              entry.is_hero = entry.id === item.id;
            }
          });
        } else {
          item.is_hero = true;
        }
      });
    },
  });

  // Override/extend the exposed hooks for image so status_checker can paint without reload
  window.__imageExternalApply = (imageOrItem, thumbOrCreatedAt, _createdAtIso) => {
    const img = document.getElementById('topicImageLatest');
    let imageUrl = '';
    let thumbUrl = '';

    if (imageOrItem && typeof imageOrItem === 'object') {
      imageUrl = imageOrItem.image_url || '';
      thumbUrl = imageOrItem.thumbnail_url || '';
    } else {
      imageUrl = imageOrItem || '';
      thumbUrl = typeof thumbOrCreatedAt === 'string' ? thumbOrCreatedAt : '';
    }

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
