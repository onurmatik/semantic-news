function formatRelativeTime(isoString) {
  if (!isoString) return null;
  try {
    const date = new Date(isoString);
    if (Number.isNaN(date.getTime())) {
      return null;
    }
    const now = new Date();
    const diffSeconds = Math.round((date.getTime() - now.getTime()) / 1000);
    if (diffSeconds === 0) {
      return 'now';
    }

    const units = [
      ['year', 60 * 60 * 24 * 365],
      ['month', 60 * 60 * 24 * 30],
      ['day', 60 * 60 * 24],
      ['hour', 60 * 60],
      ['minute', 60],
      ['second', 1],
    ];

    const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: 'auto' });
    for (const [unit, secondsInUnit] of units) {
      if (Math.abs(diffSeconds) >= secondsInUnit || unit === 'second') {
        const value = Math.round(diffSeconds / secondsInUnit);
        return rtf.format(value, unit);
      }
    }
  } catch (err) {
    console.error('Unable to format relative time', err);
  }
  return null;
}

document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('publishTopicBtn');
  const topicEl = document.querySelector('[data-topic-uuid]');
  if (!topicEl) return;
  const topicUuid = topicEl.dataset.topicUuid;
  if (!topicUuid) return;

  const feedbackEl = document.getElementById('publishTopicFeedback');
  const timestampEl = document.getElementById('topicPublishTimestamp');
  const statusDisplayEl = document.querySelector('[data-topic-status-display]');

  function hideFeedback() {
    if (!feedbackEl) return;
    feedbackEl.classList.add('d-none');
    feedbackEl.textContent = '';
    feedbackEl.classList.remove('alert-danger', 'alert-success');
  }

  function showFeedback(message, type) {
    if (!feedbackEl) return;
    feedbackEl.textContent = message;
    feedbackEl.classList.remove('d-none', 'alert-danger', 'alert-success');
    feedbackEl.classList.add(type === 'error' ? 'alert-danger' : 'alert-success');
  }

  function updatePublishedTimestamp(isoString) {
    if (!timestampEl) return;
    if (!isoString) {
      timestampEl.textContent = 'Not yet published.';
      timestampEl.removeAttribute('data-last-published');
      timestampEl.removeAttribute('title');
      return;
    }

    timestampEl.dataset.lastPublished = isoString;
    const publishedDate = new Date(isoString);
    timestampEl.title = publishedDate.toLocaleString();
    const relative = formatRelativeTime(isoString);
    if (relative === 'now') {
      timestampEl.textContent = 'Last published just now.';
    } else if (relative) {
      timestampEl.textContent = `Last published ${relative}.`;
    } else {
      timestampEl.textContent = `Last published ${publishedDate.toLocaleString()}.`;
    }
  }

  function updateStatusDisplay(status) {
    if (!statusDisplayEl) return;
    const template = statusDisplayEl.dataset.statusTemplate || 'This topic is __STATUS__.';
    statusDisplayEl.textContent = template.replace('__STATUS__', status);
  }

  async function refreshMetadata() {
    try {
      const res = await fetch(`/api/topics/${topicUuid}/metadata`);
      if (!res.ok) return;
      const metadata = await res.json();
      if (metadata.status) {
        updateStatusDisplay(metadata.status);
      }
      updatePublishedTimestamp(metadata.published_at || null);
    } catch (err) {
      console.error('Unable to refresh topic metadata', err);
    }
  }

  refreshMetadata();

  if (!btn) {
    return;
  }

  btn.addEventListener('click', async (e) => {
    e.preventDefault();
    btn.disabled = true;
    hideFeedback();
    const status = btn.dataset.status || 'published';

    try {
      const res = await fetch('/api/topics/set-status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic_uuid: topicUuid, status }),
      });

      const bodyText = await res.text();
      let data = null;
      if (bodyText) {
        try {
          data = JSON.parse(bodyText);
        } catch (parseErr) {
          if (!res.ok) {
            console.error('Unable to parse error response JSON', parseErr);
          }
        }
      }

      if (!res.ok) {
        const detail = (data && (data.detail || data.message)) || 'Unable to update the topic status. Please try again.';
        throw new Error(detail);
      }

      if (data) {
        if (data.status) {
          updateStatusDisplay(data.status);
        }
        updatePublishedTimestamp(data.published_at || null);
      }

      showFeedback('Topic published successfully.', 'success');
    } catch (err) {
      console.error(err);
      const fallbackMessage = 'Unable to update the topic status. Please try again.';
      const message = err && err.message ? err.message : fallbackMessage;

      showFeedback(message, 'error');
    } finally {
      btn.disabled = false;
    }
  });
});
