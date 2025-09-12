document.addEventListener('DOMContentLoaded', () => {
  const controller = setupGenerationButton({
    buttonId: 'recapButton',
    spinnerId: 'recapSpinner',
    errorIconId: 'recapErrorIcon',
    successIconId: 'recapSuccessIcon',
  });

  const form = document.getElementById('recapForm');
  const suggestionBtn = document.getElementById('fetchRecapSuggestion');
  const recapTextarea = document.getElementById('recapText');
  const recapCardContainer = document.getElementById('topicRecapContainer');
  const recapCardText = document.getElementById('topicRecapText');

  // ---- Helper: normalize text for equality checks
  const norm = (s) => (s || '')
    .replace(/\r\n/g, '\n')
    .replace(/[ \t]+/g, ' ')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  // ---- Keep a baseline = "latest recap" from server
  let latestRecapBaseline = recapTextarea ? norm(recapTextarea.value) : '';

  // ---- Update button enable/disable based on textarea vs baseline
  const submitBtn = form ? form.querySelector('button[type="submit"]') : null;
  const updateSubmitButtonState = () => {
    if (!submitBtn || !recapTextarea) return;
    submitBtn.disabled = norm(recapTextarea.value) === latestRecapBaseline;
  };

  if (recapTextarea) {
    recapTextarea.addEventListener('input', updateSubmitButtonState);
    // initial state
    updateSubmitButtonState();
  }

  // ---- Very light Markdown-to-HTML for bold + newlines (optional)
  const renderMarkdownLite = (md) => {
    if (!md) return '';
    // bold **text**
    let html = md.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    // paragraphs by double newlines
    html = html.split(/\n{2,}/).map(p => `<p class="mb-2">${p.replace(/\n/g, '<br>')}</p>`).join('');
    return html;
  };

  // ---- Show/Update recap card content without page reload
  const showRecapCard = (text) => {
    if (!recapCardContainer || !recapCardText) return;
    // Unhide if it was hidden via inline style
    recapCardContainer.style.display = '';
    recapCardText.innerHTML = renderMarkdownLite(text);
  };

  if (suggestionBtn && recapTextarea && form) {
    const recapModalEl = document.getElementById('recapModal');
    const recapModal = recapModalEl && window.bootstrap
      ? bootstrap.Modal.getOrCreateInstance(recapModalEl)
      : null;

    suggestionBtn.addEventListener('click', async () => {
      // Start loading, close modal
      controller.showLoading();
      if (recapModal) recapModal.hide();

      // Disable the AI button to prevent double-clicks until it finishes
      suggestionBtn.disabled = true;

      const topicUuid = form.querySelector('input[name="topic_uuid"]').value;

      try {
        const res = await fetch('/api/topics/recap/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic_uuid: topicUuid })
        });

        if (!res.ok) throw new Error('Request failed');

        const data = await res.json();

        // Update textarea so user can edit if they want
        recapTextarea.value = data.recap || '';

        // Update the visible recap card on the page right away
        showRecapCard(data.recap || '');

        // Move the baseline to the new value and disable the Update button
        latestRecapBaseline = norm(data.recap || '');
        updateSubmitButtonState();

        controller.showSuccess();
      } catch (err) {
        console.error(err);
        controller.showError();
      } finally {
        suggestionBtn.disabled = false;
      }
    });
  }

  if (form && recapTextarea) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();

      submitBtn && (submitBtn.disabled = true);
      controller.showLoading();

      const recapModalEl = document.getElementById('recapModal');
      const recapModal = recapModalEl && window.bootstrap
        ? bootstrap.Modal.getOrCreateInstance(recapModalEl)
        : null;
      if (recapModal) recapModal.hide();

      const topicUuid = form.querySelector('input[name="topic_uuid"]').value;
      const recap = recapTextarea.value;

      try {
        const res = await fetch('/api/topics/recap/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic_uuid: topicUuid, recap })
        });
        if (!res.ok) throw new Error('Request failed');

        const data = await res.json();

        // Update baseline and card to the newly saved content
        latestRecapBaseline = norm(data.recap || recap || '');
        updateSubmitButtonState();
        showRecapCard(data.recap || recap || '');

        controller.reset();

        // window.location.reload();
      } catch (err) {
        console.error(err);
        controller.showError();
      } finally {
        submitBtn && (submitBtn.disabled = norm(recapTextarea.value) === latestRecapBaseline);
      }
    });
  }
});
