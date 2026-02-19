document.addEventListener('DOMContentLoaded', () => {
  const topicEl = document.querySelector('[data-topic-uuid]');
  const button = document.getElementById('newsradarConnectionBtn');
  const statusEl = document.getElementById('newsradarConnectionStatus');

  if (!topicEl || !button || !statusEl) {
    return;
  }

  const topicUuid = (topicEl.dataset.topicUuid || '').trim();
  const existingExternalTopicId = (topicEl.dataset.newsradarExternalTopicId || '').trim();
  const initiallyConnected = (topicEl.dataset.newsradarConnected || 'false') === 'true';
  const topicTitleInput = document.getElementById('topicTitleInput');

  if (!topicUuid) {
    statusEl.textContent = 'Topic UUID is missing.';
    button.disabled = true;
    return;
  }

  const readErrorMessage = async (response, fallback) => {
    try {
      const data = await response.json();
      if (typeof data?.detail === 'string' && data.detail.trim()) {
        return data.detail.trim();
      }
    } catch (error) {
      console.error(error);
    }
    return fallback;
  };

  const setStatus = (message, kind = 'muted') => {
    statusEl.classList.remove('text-secondary', 'text-success', 'text-danger');
    const mapping = {
      muted: 'text-secondary',
      success: 'text-success',
      error: 'text-danger',
    };
    statusEl.classList.add(mapping[kind] || mapping.muted);
    statusEl.textContent = message;
  };

  const setConnectedState = (externalTopicId) => {
    const displayId = (externalTopicId || '').trim();
    topicEl.dataset.newsradarConnected = 'true';
    if (displayId) {
      topicEl.dataset.newsradarExternalTopicId = displayId;
      setStatus(`Connected. topic_uuid=${displayId}`, 'success');
    } else {
      setStatus('Connected.', 'success');
    }
    button.textContent = 'Connected';
    button.classList.remove('btn-outline-primary');
    button.classList.add('btn-outline-success');
  };

  if (initiallyConnected) {
    setConnectedState(existingExternalTopicId);
  }

  button.addEventListener('click', async () => {
    const liveTitle = (topicTitleInput?.textContent || '').trim();
    const savedTitle = (topicEl.dataset.topicTitle || '').trim();
    const effectiveTitle = liveTitle || savedTitle;
    if (!effectiveTitle) {
      setStatus('Enter topic name first.', 'error');
      return;
    }

    button.disabled = true;
    setStatus('Connecting to NewsRadar...');

    try {
      const response = await fetch(`/api/topics/${encodeURIComponent(topicUuid)}/external/newsradar/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });

      if (!response.ok) {
        throw new Error(await readErrorMessage(response, 'Unable to connect to NewsRadar.'));
      }

      const data = await response.json();
      setConnectedState(data.external_topic_id || '');
    } catch (error) {
      console.error(error);
      setStatus(error?.message || 'Unable to connect to NewsRadar.', 'error');
    } finally {
      button.disabled = false;
    }
  });
});
