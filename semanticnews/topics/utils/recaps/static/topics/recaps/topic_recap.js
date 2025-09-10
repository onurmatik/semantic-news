document.addEventListener('DOMContentLoaded', () => {
  const controller = setupGenerationButton({
    buttonId: 'recapButton',
    spinnerId: 'recapSpinner',
    errorIconId: 'recapErrorIcon',
  });

  const form = document.getElementById('recapForm');
  const suggestionBtn = document.getElementById('fetchRecapSuggestion');
  const recapTextarea = document.getElementById('recapText');

  if (suggestionBtn && recapTextarea && form) {
    suggestionBtn.addEventListener('click', async () => {
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
        recapTextarea.value = data.recap;
      } catch (err) {
        console.error(err);
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
      controller.showLoading();
      const recapModal = document.getElementById('recapModal');
      if (recapModal && window.bootstrap) {
        const modal = window.bootstrap.Modal.getInstance(recapModal);
        if (modal) modal.hide();
      }
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
        window.location.reload();
      } catch (err) {
        console.error(err);

        submitBtn.disabled = false;
        controller.hideLoading();
      }
    });
  }
});
