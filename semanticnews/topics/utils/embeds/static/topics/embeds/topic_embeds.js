function handleModalForm({ formId, modalId, endpoint }) {
  const form = document.getElementById(formId);
  if (!form) return;

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.disabled = true;

    const modalEl = document.getElementById(modalId);
    if (modalEl && window.bootstrap) {
      const modal = window.bootstrap.Modal.getInstance(modalEl);
      if (modal) modal.hide();
    }

    const formData = new FormData(form);
    const payload = Object.fromEntries(formData.entries());

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('Request failed');
      await res.json();
      window.location.reload();
    } catch (error) {
      console.error(error);
      if (submitBtn) submitBtn.disabled = false;
    }
  });
}

document.addEventListener('DOMContentLoaded', () => {
  handleModalForm({
    formId: 'youtubeVideoForm',
    modalId: 'youtubeVideoModal',
    endpoint: '/api/topics/embed/video/add',
  });

  handleModalForm({
    formId: 'tweetEmbedForm',
    modalId: 'tweetEmbedModal',
    endpoint: '/api/topics/embed/tweet/add',
  });
});
