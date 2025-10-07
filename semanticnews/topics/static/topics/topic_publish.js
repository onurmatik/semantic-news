document.addEventListener('DOMContentLoaded', () => {
  const buttons = Array.from(document.querySelectorAll('[data-topic-status-button]'));
  if (!buttons.length) return;

  const topicEl = document.querySelector('[data-topic-uuid]');
  if (!topicEl) return;
  const topicUuid = topicEl.dataset.topicUuid;

  const errorEl = document.getElementById('publishTopicError');

  const setButtonsDisabled = (disabled) => {
    buttons.forEach((button) => {
      button.disabled = disabled;
    });
  };

  buttons.forEach((button) => {
    button.addEventListener('click', async (event) => {
      event.preventDefault();
      const status = button.dataset.status;
      if (!status) {
        return;
      }

      setButtonsDisabled(true);

      if (errorEl) {
        errorEl.classList.add('d-none');
        errorEl.textContent = '';
      }

      try {
        const res = await fetch('/api/topics/set-status', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic_uuid: topicUuid, status })
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

        window.location.reload();
      } catch (err) {
        console.error(err);
        const fallbackMessage = 'Unable to update the topic status. Please try again.';
        const message = err && err.message ? err.message : fallbackMessage;

        if (errorEl) {
          errorEl.textContent = message;
          errorEl.classList.remove('d-none');
        } else if (window.alert) {
          window.alert(message);
        }
      } finally {
        setButtonsDisabled(false);
      }
    });
  });
});
