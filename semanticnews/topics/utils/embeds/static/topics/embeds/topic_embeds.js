document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('youtubeVideoForm');
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = form.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      const modalEl = document.getElementById('youtubeVideoModal');
      if (modalEl && window.bootstrap) {
        const modal = window.bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }
      const formData = new FormData(form);
      const payload = {
        topic_uuid: formData.get('topic_uuid'),
        url: formData.get('url')
      };
      try {
        const res = await fetch('/api/topics/embed/video/add', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!res.ok) throw new Error('Request failed');
        await res.json();
        window.location.reload();
      } catch (err) {
        console.error(err);
        submitBtn.disabled = false;
      }
    });
  }
});
