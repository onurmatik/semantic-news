document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('recapButton');
  if (!btn) return;

  const topicUuid = btn.dataset.topicUuid;
  const recapContainer = document.getElementById('topicRecapContainer');
  const recapText = document.getElementById('topicRecapText');

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
      const data = await res.json();
      if (recapText) {
        recapText.textContent = data.recap;
      }
      if (recapContainer) {
        recapContainer.style.display = '';
      }
    } catch (err) {
      console.error(err);
    } finally {
      btn.disabled = false;
    }
  });
});
