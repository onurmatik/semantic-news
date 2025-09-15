document.addEventListener('DOMContentLoaded', () => {
  const youtubeForm = document.getElementById('youtubeVideoForm');
  if (youtubeForm) {
    youtubeForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = youtubeForm.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      const modalEl = document.getElementById('youtubeVideoModal');
      if (modalEl && window.bootstrap) {
        const modal = window.bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }
      const formData = new FormData(youtubeForm);
      const payload = {
        topic_uuid: formData.get('topic_uuid'),
        media_type: 'youtube',
        url: formData.get('url')
      };
      try {
        const res = await fetch('/api/topics/media/add', {
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

  const vimeoForm = document.getElementById('vimeoVideoForm');
  if (vimeoForm) {
    vimeoForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = vimeoForm.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      const modalEl = document.getElementById('vimeoVideoModal');
      if (modalEl && window.bootstrap) {
        const modal = window.bootstrap.Modal.getInstance(modalEl);
        if (modal) modal.hide();
      }
      const formData = new FormData(vimeoForm);
      const payload = {
        topic_uuid: formData.get('topic_uuid'),
        media_type: 'vimeo',
        url: formData.get('url')
      };
      try {
        const res = await fetch('/api/topics/media/add', {
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
