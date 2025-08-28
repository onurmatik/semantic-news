document.addEventListener('DOMContentLoaded', function () {
  const topicEl = document.querySelector('[data-topic-uuid]');
  if (!topicEl) return;

  const topicUuid = topicEl.dataset.topicUuid;
  const relatedContainer = document.getElementById('relatedEventsContainer');
  const suggestedContainer = document.getElementById('suggestedEventsContainer');

  async function postJSON(url, payload) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Request failed');
    return res.json();
  }

  function ensureEmptyMessage(container) {
    const hasEvent = container.querySelector('[data-event-uuid]');
    if (!hasEvent) {
      let empty = container.querySelector('.empty-msg');
      if (!empty) {
        empty = document.createElement('p');
        empty.className = 'text-secondary small mb-0 empty-msg';
        empty.textContent = container.dataset.emptyMessage || '';
        container.appendChild(empty);
      }
    } else {
      const empty = container.querySelector('.empty-msg');
      if (empty) empty.remove();
    }
  }

  document.addEventListener('click', async (e) => {
    const addBtn = e.target.closest('.add-event-btn');
    const removeBtn = e.target.closest('.remove-event-btn');

    if (addBtn) {
      e.preventDefault();
      const eventUuid = addBtn.dataset.eventUuid;
      try {
        await postJSON('/api/topics/add-event', { topic_uuid: topicUuid, event_uuid: eventUuid });
        const wrapper = addBtn.closest('[data-event-uuid]');
        if (!wrapper) return;
        addBtn.classList.remove('btn-outline-primary', 'add-event-btn');
        addBtn.classList.add('btn-outline-danger', 'remove-event-btn');
        addBtn.textContent = addBtn.dataset.removeLabel || 'Remove';
        relatedContainer.appendChild(wrapper);
        ensureEmptyMessage(relatedContainer);
        ensureEmptyMessage(suggestedContainer);
      } catch (err) {
        console.error(err);
      }
    } else if (removeBtn) {
      e.preventDefault();
      const eventUuid = removeBtn.dataset.eventUuid;
      try {
        await postJSON('/api/topics/remove-event', { topic_uuid: topicUuid, event_uuid: eventUuid });
        const wrapper = removeBtn.closest('[data-event-uuid]');
        if (!wrapper) return;
        removeBtn.classList.remove('btn-outline-danger', 'remove-event-btn');
        removeBtn.classList.add('btn-outline-primary', 'add-event-btn');
        removeBtn.textContent = removeBtn.dataset.addLabel || 'Add';
        suggestedContainer.appendChild(wrapper);
        ensureEmptyMessage(relatedContainer);
        ensureEmptyMessage(suggestedContainer);
      } catch (err) {
        console.error(err);
      }
    }
  });
});
