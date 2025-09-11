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

  // --- UI builders ----------------------------------------------------------
  function buildRemoveButton() {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-sm btn-outline-danger remove-event-btn';
    btn.textContent = 'Remove';
    return btn;
  }

  function buildAddDropdown(wrapper) {
    const title = wrapper.querySelector('h2 a')?.textContent?.trim() || '';
    const eventUuid = wrapper.dataset.eventUuid;

    const dropdown = document.createElement('div');
    dropdown.className = 'dropdown d-inline';

    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'btn btn-sm btn-outline-primary dropdown-toggle';
    toggle.setAttribute('data-bs-toggle', 'dropdown');
    toggle.setAttribute('aria-expanded', 'false');
    toggle.textContent = 'Add';

    const menu = document.createElement('ul');
    menu.className = 'dropdown-menu';

    // "This topic"
    const liThis = document.createElement('li');
    const aThis = document.createElement('a');
    aThis.href = '#';
    aThis.className = 'dropdown-item small add-to-topic';
    aThis.dataset.topicUuid = topicUuid;
    aThis.dataset.eventUuid = eventUuid;
    aThis.textContent = 'This topic';
    liThis.appendChild(aThis);

    // Divider
    const liDiv = document.createElement('li');
    liDiv.innerHTML = '<hr class="dropdown-divider">';

    // "Create new topic"
    const liCreate = document.createElement('li');
    const aCreate = document.createElement('a');
    aCreate.href = '#';
    aCreate.className = 'dropdown-item small add-topic-btn';
    aCreate.dataset.eventTitle = title;
    aCreate.textContent = 'Create new topic';
    liCreate.appendChild(aCreate);

    menu.appendChild(liThis);
    menu.appendChild(liDiv);
    menu.appendChild(liCreate);

    dropdown.appendChild(toggle);
    dropdown.appendChild(menu);
    return dropdown;
  }

  function replaceControls(wrapper, toRelated) {
    // Remove existing controls (including any legacy plain add button)
    wrapper.querySelectorAll('.remove-event-btn, .dropdown, .add-event-btn').forEach(n => n.remove());

    const controlsAnchor = wrapper.querySelector('p:last-of-type') || wrapper;
    if (toRelated) {
      controlsAnchor.insertAdjacentElement('afterend', buildRemoveButton());
    } else {
      controlsAnchor.insertAdjacentElement('afterend', buildAddDropdown(wrapper));
    }
  }

  // --- Event delegation -----------------------------------------------------
  document.addEventListener('click', async (e) => {
    // Add via dropdown item
    const addToTopic = e.target.closest('.add-to-topic');
    if (addToTopic) {
      e.preventDefault();
      const wrapper = addToTopic.closest('[data-event-uuid]');
      if (!wrapper) return;
      const eventUuid = wrapper.dataset.eventUuid;
      try {
        await postJSON('/api/topics/add-event', { topic_uuid: topicUuid, event_uuid: eventUuid });

        // Move to Related and rebuild controls -> Remove button
        relatedContainer.appendChild(wrapper);
        replaceControls(wrapper, /*toRelated*/ true);

        ensureEmptyMessage(relatedContainer);
        ensureEmptyMessage(suggestedContainer);
      } catch (err) {
        console.error(err);
      }
      return;
    }

    // Remove
    const removeBtn = e.target.closest('.remove-event-btn');
    if (removeBtn) {
      e.preventDefault();
      const wrapper = removeBtn.closest('[data-event-uuid]');
      if (!wrapper) return;
      const eventUuid = wrapper.dataset.eventUuid;
      try {
        await postJSON('/api/topics/remove-event', { topic_uuid: topicUuid, event_uuid: eventUuid });

        // Move to Suggested and rebuild controls -> Add dropdown
        suggestedContainer.appendChild(wrapper);
        replaceControls(wrapper, /*toRelated*/ false);

        ensureEmptyMessage(relatedContainer);
        ensureEmptyMessage(suggestedContainer);
      } catch (err) {
        console.error(err);
      }
    }
  });
});
