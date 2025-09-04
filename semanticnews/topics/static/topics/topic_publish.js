document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('publishTopicBtn');
  if (!btn) return;
  const topicEl = document.querySelector('[data-topic-uuid]');
  if (!topicEl) return;
  const topicUuid = topicEl.dataset.topicUuid;

  btn.addEventListener('click', async (e) => {
    e.preventDefault();
    btn.disabled = true;
    const status = btn.dataset.status;
    try {
      const res = await fetch('/api/topics/set-status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic_uuid: topicUuid, status })
      });
      if (!res.ok) throw new Error('Request failed');
      await res.json();
      window.location.reload();
    } catch (err) {
      console.error(err);
      btn.disabled = false;
    }
  });
});
