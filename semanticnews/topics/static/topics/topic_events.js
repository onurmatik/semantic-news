document.addEventListener('DOMContentLoaded', function () {
  const topicEl = document.querySelector('[data-topic-uuid]');
  if (!topicEl) return;

  const topicUuid = topicEl.dataset.topicUuid;

  // Confirm modal
  const confirmEl = document.getElementById('confirmDeleteEventModal');
  const deleteModal = (window.bootstrap && confirmEl)
    ? bootstrap.Modal.getOrCreateInstance(confirmEl)
    : null;

  // Track which row was clicked
  let pendingDeleteWrapper = null;
  let pendingEventUuid = null;

  async function postJSON(url, payload) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error(`Request failed: ${res.status}`);
    // some endpoints may return no JSON; ignore parse errors
    try { return await res.json(); } catch { return {}; }
  }

  // Add/remove "empty" messages for any containers that declare data-empty-message
  function refreshEmptyMessages() {
    document.querySelectorAll('[data-empty-message]').forEach(container => {
      const hasItem = container.querySelector('.event-item[data-event-uuid]');
      const msg = container.querySelector('.empty-msg');
      if (hasItem) {
        if (msg) msg.remove();
      } else {
        if (!msg) {
          const p = document.createElement('p');
          p.className = 'text-secondary small mb-0 empty-msg';
          p.textContent = container.dataset.emptyMessage || '';
          container.appendChild(p);
        }
      }
    });
  }

  // Remove all DOM instances of this event (page + any open modals)
  function removeEventEverywhere(eventUuid, keepEl = null) {
    document.querySelectorAll(`.event-item[data-event-uuid="${eventUuid}"]`).forEach(el => {
      if (keepEl && el === keepEl) {
        el.remove(); // still remove the one we clicked
      } else {
        el.remove();
      }
    });
  }

  document.addEventListener('click', async (e) => {
    // Open confirm when trash clicked (allow icon clicks)
    const trashBtn = e.target.closest('.remove-event-btn');
    if (trashBtn) {
      e.preventDefault();
      const wrapper = trashBtn.closest('.event-item[data-event-uuid]');
      if (!wrapper) return;
      pendingDeleteWrapper = wrapper;
      pendingEventUuid = wrapper.getAttribute('data-event-uuid');
      deleteModal?.show();
      return;
    }

    // Confirm delete (catch clicks on inner spans too)
    const confirmBtn = e.target.closest('#confirmDeleteEventBtn');
    if (confirmBtn && pendingEventUuid) {
      e.preventDefault();
      const spinner = confirmBtn.querySelector('.spinner-border');
      confirmBtn.disabled = true;
      if (spinner) spinner.classList.remove('d-none');

      try {
        await postJSON('/api/topics/remove-event', {
          topic_uuid: topicUuid,
          event_uuid: pendingEventUuid
        });

        // Remove the entire event rows everywhere
        removeEventEverywhere(pendingEventUuid, pendingDeleteWrapper);

        // Empty-state refresh
        refreshEmptyMessages();

        deleteModal?.hide();
      } catch (err) {
        console.error(err);
      } finally {
        confirmBtn.disabled = false;
        if (spinner) spinner.classList.add('d-none');
        pendingDeleteWrapper = null;
        pendingEventUuid = null;
      }
    }
  });
});
