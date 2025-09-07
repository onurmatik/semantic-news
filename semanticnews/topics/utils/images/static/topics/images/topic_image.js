document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('imageForm');
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = form.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      const formData = new FormData(form);
      const payload = {
        topic_uuid: formData.get('topic_uuid'),
        size: formData.get('size'),
        style: formData.get('style')
      };
      try {
        const res = await fetch('/api/topics/image/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error('Request failed');
        await res.json();
        window.location.reload();
      } catch (err) {
        console.error(err);
      } finally {
        submitBtn.disabled = false;
      }
    });
  }
});
