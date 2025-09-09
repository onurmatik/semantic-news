document.addEventListener('DOMContentLoaded', () => {
  const recapBtn = document.getElementById('recapButton');
  const recapSpinner = document.getElementById('recapSpinner');
  const showLoading = () => {
    if (recapBtn && recapSpinner) {
      recapBtn.disabled = true;
      recapSpinner.classList.remove('d-none');
    }
  };
  const hideLoading = () => {
    if (recapBtn && recapSpinner) {
      recapBtn.disabled = false;
      recapSpinner.classList.add('d-none');
    }
  };

  if (recapBtn) {
    const status = recapBtn.dataset.recapStatus;
    const created = recapBtn.dataset.recapCreated;
    if (status === 'in_progress' && created) {
      const createdDate = new Date(created);
      if (Date.now() - createdDate.getTime() < 2 * 60 * 1000) {
        showLoading();
      }
    }
  }

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
      showLoading();
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
        hideLoading();
      }
    });
  }
});
