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

        // Fill the textarea so user sees the AI result when reopening the modal
        recapTextarea.value = data.recap || '';

        // Keep the main Recap button green to indicate "AI done"
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

      const submitBtn = form.querySelector('button[type="submit"]');
      submitBtn.disabled = true;

      // Start loading, close modal
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
        await res.json();
        // Return to neutral/stateless
        controller.reset();
        window.location.reload();
      } catch (err) {
        console.error(err);
        controller.showError();
      } finally {
        submitBtn.disabled = false;
      }
    });
  }
});
