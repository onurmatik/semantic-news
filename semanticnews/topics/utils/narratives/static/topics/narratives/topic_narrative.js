document.addEventListener('DOMContentLoaded', () => {
  const controller = setupGenerationButton({
    buttonId: 'narrativeButton',
    spinnerId: 'narrativeSpinner',
    errorIconId: 'narrativeErrorIcon',
  });

  const form = document.getElementById('narrativeForm');
  const suggestionBtn = document.getElementById('fetchNarrativeSuggestion');
  const narrativeTextarea = document.getElementById('narrativeText');

  if (suggestionBtn && narrativeTextarea && form) {
    suggestionBtn.addEventListener('click', async () => {
      suggestionBtn.disabled = true;
      const topicUuid = form.querySelector('input[name="topic_uuid"]').value;
      try {
        const res = await fetch('/api/topics/narrative/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic_uuid: topicUuid })
        });
        if (!res.ok) throw new Error('Request failed');
        const data = await res.json();
        narrativeTextarea.value = data.narrative;
      } catch (err) {
        console.error(err);
      } finally {
        suggestionBtn.disabled = false;
      }
    });
  }

  if (form && narrativeTextarea) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = form.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      controller.showLoading();
      const narrativeModal = document.getElementById('narrativeModal');
      if (narrativeModal && window.bootstrap) {
        const modal = window.bootstrap.Modal.getInstance(narrativeModal);
        if (modal) modal.hide();
      }
      const topicUuid = form.querySelector('input[name="topic_uuid"]').value;
      const narrative = narrativeTextarea.value;

      try {
        const res = await fetch('/api/topics/narrative/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic_uuid: topicUuid, narrative })
        });
        if (!res.ok) throw new Error('Request failed');
        await res.json();
        window.location.reload();
      } catch (err) {
        console.error(err);

        submitBtn.disabled = false;
        controller.hideLoading();
      }
    });
  }
});
