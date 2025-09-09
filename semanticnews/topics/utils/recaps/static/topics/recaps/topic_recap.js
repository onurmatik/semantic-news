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
  if (form) {
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
      const formData = new FormData(form);
      const payload = {
        topic_uuid: formData.get('topic_uuid'),
        websearch: formData.get('websearch') === 'on',
        length: formData.get('length'),
        tone: formData.get('tone'),
      };
      const instructions = formData.get('instructions');
      if (instructions) payload.instructions = instructions;

      try {
        const res = await fetch('/api/topics/recap/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
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
