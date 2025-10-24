document.addEventListener('DOMContentLoaded', () => {
  const modalEl = document.getElementById('mcpModal');
  if (!modalEl) return;
  const modal = new bootstrap.Modal(modalEl);
  const descriptionEl = document.getElementById('mcpDescription');
  const contextEl = document.getElementById('mcpContext');
  const fetchBtn = document.getElementById('mcpFetchBtn');
  let currentServerId = null;

  document.querySelectorAll('.mcp-server-link').forEach((btn) => {
    btn.addEventListener('click', () => {
      currentServerId = btn.dataset.id;
      descriptionEl.textContent = btn.dataset.description || '';
      contextEl.textContent = '';
      fetchBtn.disabled = false;
      modal.show();
    });
  });

  fetchBtn.addEventListener('click', async () => {
    if (!currentServerId) return;
    fetchBtn.disabled = true;
    const topicUuid = modalEl.dataset.topicUuid;
    try {
      const res = await fetch('/api/topics/mcp/context', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic_uuid: topicUuid, server_id: currentServerId })
      });
      if (!res.ok) throw new Error('Request failed');
      const data = await res.json();
      contextEl.textContent = data.context;
    } catch (err) {
      console.error(err);
    } finally {
      fetchBtn.disabled = false;
    }
  });
});
