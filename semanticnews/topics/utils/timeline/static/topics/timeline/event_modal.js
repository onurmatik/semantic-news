// Handles manual creation and AI-suggested events for topic timelines
const CONFIDENCE_THRESHOLD = 0.85;

(() => {
  const modalEl = document.getElementById('timelineModal');
  if (!modalEl) return;
  const modal = new bootstrap.Modal(modalEl);

  const existingTab = document.getElementById('existing-tab');
  const createTab = document.getElementById('create-tab');
  const fetchTab = document.getElementById('fetch-tab');

  const timelineBtn = document.getElementById('timelineButton');
  const addForm = document.getElementById('addEventForm');
  const similarContainer = document.getElementById('similarEvents');

  const relatedList = document.getElementById('relatedEventsList');
  const addRelatedBtn = document.getElementById('addRelatedEventsBtn');

  const suggestForm = document.getElementById('suggestEventsForm');
  const suggestedList = document.getElementById('suggestedEventsList');
  const addSuggestedBtn = document.getElementById('addSuggestedEventsBtn');
  const titleField = document.getElementById('suggestRelatedEvent');

  let suggestions = [];

  const topicEl = document.querySelector('[data-topic-uuid]');
  const topicUuid = topicEl ? topicEl.dataset.topicUuid : null;

  function resetForms() {
    if (addForm) addForm.reset();
    if (similarContainer) similarContainer.innerHTML = '';
    if (relatedList) relatedList.innerHTML = '';
    if (addRelatedBtn) addRelatedBtn.disabled = true;
    if (suggestForm) {
      suggestForm.reset();
      suggestForm.classList.remove('d-none');
    }
    if (suggestedList) {
      suggestedList.classList.add('d-none');
      suggestedList.innerHTML = '';
    }
    if (addSuggestedBtn) addSuggestedBtn.disabled = true;
    suggestions = [];
  }

  if (timelineBtn) {
    timelineBtn.addEventListener('click', () => {
      resetForms();
      new bootstrap.Tab(existingTab).show();
      loadRelatedEvents();
      modal.show();
    });
  }

  async function loadRelatedEvents() {
    if (!topicUuid || !relatedList) return;
    relatedList.innerHTML = '<p>Loading...</p>';
    try {
      const res = await fetch('/api/topics/timeline/related', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic_uuid: topicUuid })
      });
      const data = await res.json();
      if (Array.isArray(data) && data.length) {
        relatedList.innerHTML = '';
        data.forEach(ev => {
          const wrapper = document.createElement('div');
          wrapper.className = 'form-check';
          const cb = document.createElement('input');
          cb.type = 'checkbox';
          cb.className = 'form-check-input';
          cb.value = ev.uuid;
          cb.id = `rel${ev.uuid}`;
          cb.addEventListener('change', () => {
            if (!addRelatedBtn) return;
            const any = relatedList.querySelectorAll('input[type="checkbox"]:checked').length > 0;
            addRelatedBtn.disabled = !any;
          });
          const label = document.createElement('label');
          label.className = 'form-check-label';
          label.htmlFor = cb.id;
          label.textContent = `${ev.title} (${ev.date})`;
          wrapper.appendChild(cb);
          wrapper.appendChild(label);
          relatedList.appendChild(wrapper);
        });
      } else {
        relatedList.innerHTML = '<p>No related events found.</p>';
      }
    } catch (err) {
      relatedList.innerHTML = '<p>Error loading events.</p>';
    }
  }

  async function addEventToTopic(eventUuid) {
    if (!topicUuid) return;
    await fetch('/api/topics/add-event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic_uuid: topicUuid, event_uuid: eventUuid })
    });
  }

  if (addRelatedBtn && relatedList) {
    addRelatedBtn.addEventListener('click', async () => {
      const checked = relatedList.querySelectorAll('input[type="checkbox"]:checked');
      for (const cb of checked) {
        await addEventToTopic(cb.value);
      }
      modal.hide();
      window.location.reload();
    });
  }

  // handle manual creation submit
  if (addForm) {
    addForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const title = document.getElementById('eventTitle').value;
      const date = document.getElementById('eventDate').value;
      const res = await fetch('/api/agenda/get-existing', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, date })
      });
      const data = await res.json();
      if (data.existing) {
        similarContainer.innerHTML = '<p>This event already exists.</p>';
      } else {
        await validateAndCreate(title, date);
      }
    });
  }

  async function validateAndCreate(title, date) {
    const valRes = await fetch('/api/agenda/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, date })
    });
    const valData = await valRes.json();
    const createRes = await fetch('/api/agenda/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, date, confidence: valData.confidence })
    });
    const created = await createRes.json();
    if (topicUuid) await addEventToTopic(created.uuid);
    if (valData.confidence < CONFIDENCE_THRESHOLD) {
      alert('Event created as draft due to low confidence.');
    }
    window.location.reload();
  }

  // handle suggestion fetching
  function updateSuggestedSelectionState() {
    if (!addSuggestedBtn || !suggestedList) return;
    const checked = suggestedList.querySelectorAll('input[type="checkbox"]:checked');
    addSuggestedBtn.disabled = checked.length === 0;
  }

  if (suggestForm && suggestedList && addSuggestedBtn) {
    const fetchBtn = suggestForm.querySelector('button[type="submit"]');
    suggestForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      suggestedList.innerHTML = '<p>Loading suggestions...</p>';
      suggestedList.classList.remove('d-none');
      addSuggestedBtn.disabled = true;
      if (fetchBtn) fetchBtn.disabled = true;
      try {
        const payload = { topic_uuid: topicUuid };
        const title = titleField ? titleField.value : '';
        if (title) payload.related_event = title;
        const locality = document.getElementById('suggestLocality').value;
        const startDate = document.getElementById('suggestStartDate').value;
        const endDate = document.getElementById('suggestEndDate').value;
        if (locality) payload.locality = locality;
        if (startDate) payload.start_date = startDate;
        if (endDate) payload.end_date = endDate;
        const res = await fetch('/api/topics/timeline/suggest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (Array.isArray(data) && data.length) {
          suggestions = data;
          suggestedList.innerHTML = '';
          data.forEach((ev, idx) => {
            const wrapper = document.createElement('div');
            wrapper.className = 'form-check';
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.className = 'form-check-input';
            cb.id = `suggest${idx}`;
            cb.value = idx;
            cb.addEventListener('change', updateSuggestedSelectionState);
            const label = document.createElement('label');
            label.className = 'form-check-label';
            label.htmlFor = cb.id;
            const cats = ev.categories && ev.categories.length ? ` - ${ev.categories.join(', ')}` : '';
            label.textContent = `${ev.title} (${ev.date})${cats}`;
            wrapper.appendChild(cb);
            wrapper.appendChild(label);
            suggestedList.appendChild(wrapper);
          });
          updateSuggestedSelectionState();
          suggestForm.classList.add('d-none');
        } else {
          suggestedList.innerHTML = '<p>No suggestions found.</p>';
        }
      } catch (err) {
        suggestedList.innerHTML = '<p>Error loading suggestions.</p>';
      } finally {
        if (fetchBtn) fetchBtn.disabled = false;
      }
    });

    addSuggestedBtn.addEventListener('click', async () => {
      const checked = suggestedList.querySelectorAll('input[type="checkbox"]:checked');
      const eventUuids = Array.from(checked)
        .map(cb => suggestions[parseInt(cb.value, 10)])
        .filter(ev => ev && ev.uuid)
        .map(ev => ev.uuid);
      if (eventUuids.length) {
        await fetch('/api/topics/timeline/create', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic_uuid: topicUuid, event_uuids: eventUuids })
        });
      }
      modal.hide();
      window.location.reload();
    });
  }
})();
