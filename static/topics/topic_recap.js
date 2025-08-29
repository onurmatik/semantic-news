document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('recapButton');
  if (btn) {
    const topicUuid = btn.dataset.topicUuid;
    btn.addEventListener('click', async (e) => {
      e.preventDefault();
      btn.disabled = true;
      try {
        const res = await fetch('/api/topics/recap/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic_uuid: topicUuid })
        });
        if (!res.ok) throw new Error('Request failed');
        await res.json();
        window.location.reload();
      } catch (err) {
        console.error(err);
      } finally {
        btn.disabled = false;
      }
    });
  }

  const form = document.getElementById('recapForm');
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const submitBtn = form.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
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
      } finally {
        submitBtn.disabled = false;
      }
    });
  }
});
