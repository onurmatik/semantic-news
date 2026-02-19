document.addEventListener('DOMContentLoaded', () => {
  const topicEl = document.querySelector('[data-topic-uuid]');
  const connectButton = document.getElementById('newsradarConnectionBtn');
  const scanButton = document.getElementById('newsradarScanBtn');
  const statusEl = document.getElementById('newsradarConnectionStatus');
  const contentStatusEl = document.getElementById('newsradarContentStatus');
  const contentListEl = document.getElementById('newsradarContentList');

  if (!topicEl || !connectButton || !scanButton || !statusEl || !contentStatusEl || !contentListEl) {
    return;
  }

  const topicUuid = (topicEl.dataset.topicUuid || '').trim();
  const existingExternalTopicId = (topicEl.dataset.newsradarExternalTopicId || '').trim();
  const initiallyConnected = (topicEl.dataset.newsradarConnected || 'false') === 'true';
  const topicTitleInput = document.getElementById('topicTitleInput');

  if (!topicUuid) {
    statusEl.textContent = 'Topic UUID is missing.';
    connectButton.disabled = true;
    scanButton.disabled = true;
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

  const setContentStatus = (message, kind = 'muted') => {
    contentStatusEl.classList.remove('text-secondary', 'text-success', 'text-danger');
    const mapping = {
      muted: 'text-secondary',
      success: 'text-success',
      error: 'text-danger',
    };
    contentStatusEl.classList.add(mapping[kind] || mapping.muted);
    contentStatusEl.textContent = message;
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
    connectButton.textContent = 'Connected';
    connectButton.classList.remove('btn-outline-primary');
    connectButton.classList.add('btn-outline-success');
    scanButton.disabled = false;
  };

  const renderContentItems = (items) => {
    contentListEl.innerHTML = '';
    if (!Array.isArray(items) || items.length === 0) {
      setContentStatus('No NewsRadar content yet. Run Scan to fetch content.', 'muted');
      return;
    }

    for (const item of items) {
      const wrapper = document.createElement('a');
      wrapper.href = item.url;
      wrapper.target = '_blank';
      wrapper.rel = 'noopener noreferrer';
      wrapper.className = 'text-decoration-none';
      wrapper.innerHTML = `
        <div class="border rounded p-2">
          <div class="fw-semibold text-body">${item.title || item.url}</div>
          <div class="small text-secondary">${item.source || ''}${item.published_at ? ` · ${new Date(item.published_at).toLocaleString()}` : ''}</div>
          ${item.summary ? `<div class="small text-body mt-1">${item.summary}</div>` : ''}
        </div>
      `;
      contentListEl.appendChild(wrapper);
    }

    setContentStatus(`Loaded ${items.length} item${items.length === 1 ? '' : 's'}.`, 'success');
  };

  const loadContent = async () => {
    setContentStatus('Loading NewsRadar content...');
    try {
      const response = await fetch(`/api/topics/${encodeURIComponent(topicUuid)}/external/newsradar/content`);
      if (!response.ok) {
        throw new Error(await readErrorMessage(response, 'Unable to load NewsRadar content.'));
      }
      const data = await response.json();
      if (!data.connected) {
        contentListEl.innerHTML = '';
        setContentStatus('Connect this topic to NewsRadar to view content.', 'muted');
        return;
      }
      renderContentItems(data.items || []);
    } catch (error) {
      console.error(error);
      setContentStatus(error?.message || 'Unable to load NewsRadar content.', 'error');
    }
  };

  const pollScanStatus = async (executionId) => {
    const maxAttempts = 40;
    const successStatuses = new Set(['finished', 'completed', 'complete', 'success', 'succeeded', 'done']);
    const failureStatuses = new Set(['error', 'failed', 'failure', 'cancelled', 'canceled']);

    for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      const response = await fetch(`/api/topics/${encodeURIComponent(topicUuid)}/external/newsradar/scan/${executionId}`);
      if (!response.ok) {
        throw new Error(await readErrorMessage(response, 'Unable to read scan status.'));
      }
      const data = await response.json();
      const status = (data.status || '').toLowerCase().trim();

      if (successStatuses.has(status) || Number.isInteger(data.content_item_id)) {
        return;
      }

      if (failureStatuses.has(status)) {
        throw new Error(data.error_message || 'NewsRadar scan failed.');
      }

      setContentStatus(`Scan in progress... (${status || 'pending'})`);
    }

    await loadContent();
    if (contentListEl.children.length > 0) {
      return;
    }

    throw new Error('Scan is still running. Please wait a bit more and try again.');
  };

  if (initiallyConnected) {
    setConnectedState(existingExternalTopicId);
  } else {
    scanButton.disabled = true;
  }

  connectButton.addEventListener('click', async () => {
    const liveTitle = (topicTitleInput?.textContent || '').trim();
    const savedTitle = (topicEl.dataset.topicTitle || '').trim();
    const effectiveTitle = liveTitle || savedTitle;
    if (!effectiveTitle) {
      setStatus('Enter topic name first.', 'error');
      return;
    }

    connectButton.disabled = true;
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
      await loadContent();
    } catch (error) {
      console.error(error);
      setStatus(error?.message || 'Unable to connect to NewsRadar.', 'error');
    } finally {
      connectButton.disabled = false;
    }
  });

  scanButton.addEventListener('click', async () => {
    scanButton.disabled = true;
    setContentStatus('Starting scan...');

    try {
      const response = await fetch(`/api/topics/${encodeURIComponent(topicUuid)}/external/newsradar/scan`, {
        method: 'POST',
      });
      if (!response.ok) {
        throw new Error(await readErrorMessage(response, 'Unable to trigger scan.'));
      }
      const data = await response.json();
      setContentStatus('Scan in progress...');
      await pollScanStatus(data.execution_id);
      await loadContent();
      setContentStatus('Scan completed and content updated.', 'success');
    } catch (error) {
      console.error(error);
      setContentStatus(error?.message || 'Unable to complete scan.', 'error');
    } finally {
      scanButton.disabled = false;
    }
  });

  loadContent();
});
