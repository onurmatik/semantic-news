document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('recapButton');
  if (!btn) return;

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
});
