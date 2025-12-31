const libraryModal = document.getElementById('libraryModal');
const startButton = document.querySelector('[data-library-start-topic]');
const currentUsername =
  libraryModal?.dataset.currentUsername || startButton?.dataset.currentUsername;

if (libraryModal) {
  const createButton = libraryModal.querySelector('[data-library-create-topic]');
  const createSpinner = libraryModal.querySelector('[data-library-create-spinner]');
  const createLabel = libraryModal.querySelector('[data-library-create-label]');
  const addInput = libraryModal.querySelector('[data-library-add-input]');
  const addSubmitBtn = libraryModal.querySelector('[data-library-add-submit]');
  const modalCloseButtons = Array.from(
    libraryModal.querySelectorAll('[data-bs-dismiss="modal"], .btn-close')
  );
  let isCreating = false;

  const collectSelections = () => {
    const selected = libraryModal.querySelectorAll(
      'input[data-library-reference][type="checkbox"]:checked'
    );
    const uuids = new Set();
    const urls = new Set();

    selected.forEach(input => {
      const uuid = input.dataset.referenceUuid;
      const url = input.dataset.referenceUrl;
      if (uuid) {
        uuids.add(uuid);
      } else if (url) {
        urls.add(url);
      }
    });

    return {
      uuids: Array.from(uuids),
      urls: Array.from(urls),
    };
  };

  const setCreateButtonState = () => {
    if (!createButton) {
      return;
    }
    const { uuids, urls } = collectSelections();
    createButton.disabled = isCreating || (uuids.length === 0 && urls.length === 0);
    if (isCreating) {
      createButton.setAttribute('aria-busy', 'true');
      if (createSpinner) createSpinner.classList.remove('d-none');
      if (createLabel) createLabel.classList.add('opacity-75');
    } else {
      createButton.removeAttribute('aria-busy');
      if (createSpinner) createSpinner.classList.add('d-none');
      if (createLabel) createLabel.classList.remove('opacity-75');
    }
  };

  const setLoadingState = isLoading => {
    isCreating = isLoading;
    if (startButton) {
      startButton.disabled = isLoading;
    }
    if (addInput) {
      addInput.disabled = isLoading;
    }
    if (addSubmitBtn) {
      addSubmitBtn.disabled = isLoading;
    }
    modalCloseButtons.forEach(button => {
      button.disabled = isLoading;
    });
    libraryModal
      .querySelectorAll('input[data-library-reference][type="checkbox"]')
      .forEach(input => {
        input.disabled = isLoading;
      });
    setCreateButtonState();
  };

  const resetSelections = () => {
    const inputs = libraryModal.querySelectorAll(
      'input[data-library-reference][type="checkbox"]'
    );
    inputs.forEach(input => {
      input.checked = false;
    });
    setCreateButtonState();
  };

  startButton?.addEventListener('click', () => {
    resetSelections();
  });

  libraryModal.addEventListener('change', event => {
    const target = event.target;
    if (target instanceof HTMLInputElement && target.dataset.libraryReference) {
      setCreateButtonState();
    }
  });

  libraryModal.addEventListener('show.bs.modal', () => {
    if (createButton) {
      createButton.disabled = true;
    }
    setLoadingState(false);
    resetSelections();
  });

  libraryModal.addEventListener('hide.bs.modal', event => {
    if (isCreating) {
      event.preventDefault();
    }
  });

  if (createButton) {
    createButton.addEventListener('click', async () => {
      const { uuids, urls } = collectSelections();
      if (uuids.length === 0 && urls.length === 0) {
        return;
      }

      setLoadingState(true);

      try {
        const response = await fetch('/api/topics/create-with-references', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            reference_uuids: uuids,
            reference_urls: urls,
          }),
        });

        if (!response.ok) {
          throw new Error('Unable to create topic from references.');
        }

        const data = await response.json();
        const editUrl =
          data.edit_url ||
          data.detail_url ||
          (data.username && data.uuid
            ? `/${data.username}/${data.uuid}/edit/`
            : null) ||
          (currentUsername && data.uuid
            ? `/${currentUsername}/${data.uuid}/edit/`
            : null);

        if (!editUrl) {
          throw new Error('Unable to determine topic edit URL.');
        }

        const topicUuid = data.uuid;
        const redirectUrl = data.detail_url || editUrl;
        if (!topicUuid) {
          window.location.href = redirectUrl;
          return;
        }

        const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
        const pollInterval = 1500;
        const maxWaitMs = 10 * 60 * 1000;
        const maxAttempts = Math.ceil(maxWaitMs / pollInterval);

        try {
          const suggestResponse = await fetch(
            `/api/topics/${topicUuid}/references/suggestions/`,
            { method: 'POST' }
          );
          if (!suggestResponse.ok) {
            throw new Error('Unable to start suggestion request.');
          }
          const suggestData = await suggestResponse.json();
          const taskId = suggestData?.task_id;
          if (!taskId) {
            throw new Error('Unable to start suggestion request.');
          }

          let suggestionPayload = null;
          let suggestionId = null;
          for (let attempt = 0; attempt <= maxAttempts; attempt += 1) {
            const statusResponse = await fetch(
              `/api/topics/${topicUuid}/references/suggestions/${taskId}`
            );
            if (!statusResponse.ok) {
              throw new Error('Unable to check suggestion status.');
            }
            const statusData = await statusResponse.json();
            const state = (statusData?.state || '').toLowerCase();

            if (statusData?.success === false || state === 'failure' || state === 'failed') {
              throw new Error(statusData?.message || 'Unable to generate suggestions.');
            }

            if (state === 'success' || state === 'succeeded') {
              suggestionPayload = statusData?.payload || null;
              suggestionId = statusData?.suggestion_id || null;
              break;
            }

            if (attempt >= maxAttempts) {
              throw new Error('Suggestions are taking longer than expected.');
            }

            await wait(pollInterval);
          }

          if (suggestionPayload && suggestionId) {
            const applyResponse = await fetch(
              `/api/topics/${topicUuid}/references/suggestions/apply/`,
              {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  suggestion_id: suggestionId,
                  payload: suggestionPayload,
                }),
              }
            );
            if (!applyResponse.ok) {
              throw new Error('Unable to apply suggestions.');
            }
          }
        } catch (error) {
          console.error(error);
        }

        window.location.href = redirectUrl;
      } catch (error) {
        console.error(error);
        setLoadingState(false);
      }
    });
  }
}
