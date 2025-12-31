const libraryModal = document.getElementById('libraryModal');
const startButton = document.querySelector('[data-library-start-topic]');
const currentUsername = startButton?.dataset.currentUsername;

if (libraryModal && startButton) {
  const createButton = libraryModal.querySelector('[data-library-create-topic]');

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
    createButton.disabled = uuids.length === 0 && urls.length === 0;
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

  startButton.addEventListener('click', () => {
    if (createButton) {
      createButton.classList.remove('d-none');
    }
    resetSelections();
  });

  libraryModal.addEventListener('change', event => {
    const target = event.target;
    if (target instanceof HTMLInputElement && target.dataset.libraryReference) {
      setCreateButtonState();
    }
  });

  libraryModal.addEventListener('hidden.bs.modal', () => {
    if (createButton) {
      createButton.classList.add('d-none');
    }
  });

  if (createButton) {
    createButton.addEventListener('click', async () => {
      const { uuids, urls } = collectSelections();
      if (uuids.length === 0 && urls.length === 0) {
        return;
      }

      createButton.disabled = true;
      createButton.setAttribute('aria-busy', 'true');

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

        window.location.href = editUrl;
      } catch (error) {
        console.error(error);
        createButton.disabled = false;
        createButton.removeAttribute('aria-busy');
      }
    });
  }
}
