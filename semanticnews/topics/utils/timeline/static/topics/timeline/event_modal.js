// Handles manual creation and AI-suggested events for topic timelines
const CONFIDENCE_THRESHOLD = 0.85;

(() => {
  const modalEl = document.getElementById('timelineModal');
  if (!modalEl) return;
  const modal = new bootstrap.Modal(modalEl);

  const createTab = document.getElementById('create-tab');
  const fetchTab = document.getElementById('fetch-tab');

  const timelineBtn = document.getElementById('timelineButton');
  const addForm = document.getElementById('addEventForm');
  const similarContainer = document.getElementById('similarEvents');

  const suggestForm = document.getElementById('suggestEventsForm');
  const suggestedList = document.getElementById('suggestedEventsList');
  const publishBtn = document.getElementById('publishSelectedEventsBtn');
  const titleField = document.getElementById('suggestRelatedEvent');
  const existingEventsEl = document.getElementById('exclude-events');
  const existingEvents = existingEventsEl ? JSON.parse(existingEventsEl.textContent) : [];

  const topicEl = document.querySelector('[data-topic-uuid]');
  const topicUuid = topicEl ? topicEl.dataset.topicUuid : null;

  function resetForms() {
    if (addForm) addForm.reset();
    if (titleField) {
      titleField.value = '';
      titleField.readOnly = false;
    }
    if (similarContainer) similarContainer.innerHTML = '';
    if (suggestForm) {
      suggestForm.reset();
      suggestForm.classList.remove('d-none');
    }
    if (suggestedList) {
      suggestedList.classList.add('d-none');
      suggestedList.innerHTML = '';
    }
    if (publishBtn) publishBtn.disabled = true;
  }

  if (timelineBtn && addForm) {
    timelineBtn.addEventListener('click', () => {
      resetForms();
      new bootstrap.Tab(createTab).show();
      modal.show();
    });
  }

  async function addEventToTopic(eventUuid) {
    if (!topicUuid) return;
    await fetch('/api/topics/add-event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic_uuid: topicUuid, event_uuid: eventUuid })
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
  if (suggestForm && suggestedList && publishBtn) {
    const fetchBtn = suggestForm.querySelector('button[type="submit"]');
    suggestForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      suggestedList.innerHTML = '<p>Loading suggestions...</p>';
      suggestedList.classList.remove('d-none');
      publishBtn.disabled = true;
      if (fetchBtn) fetchBtn.disabled = true;
      try {
        const payload = {};
        const title = titleField ? titleField.value : '';
        if (title) payload.related_event = title;
        const locality = document.getElementById('suggestLocality').value;
        const startDate = document.getElementById('suggestStartDate').value;
        const endDate = document.getElementById('suggestEndDate').value;
        if (locality) payload.locality = locality;
        if (startDate) payload.start_date = startDate;
        if (endDate) payload.end_date = endDate;
        const exclude = existingEvents.filter(ev => {
          if (startDate && ev.date < startDate) return false;
          if (endDate && ev.date > endDate) return false;
          return true;
        });
        if (exclude.length) payload.exclude = exclude;
        const res = await fetch('/api/agenda/suggest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (Array.isArray(data) && data.length) {
          const created = [];
          for (const ev of data) {
            const createRes = await fetch('/api/agenda/create', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                title: ev.title,
                date: ev.date,
                categories: ev.categories,
                sources: ev.sources,
              }),
            });
            const createdEvent = await createRes.json();
            ev.uuid = createdEvent.uuid;
            created.push(ev);
          }
          suggestedList.innerHTML = '';
          created.forEach((ev, idx) => {
            const wrapper = document.createElement('div');
            wrapper.className = 'form-check';
            const cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.className = 'form-check-input';
            cb.id = `suggest${idx}`;
            cb.value = ev.uuid;
            const label = document.createElement('label');
            label.className = 'form-check-label';
            label.htmlFor = cb.id;
            const cats = ev.categories && ev.categories.length ? ` - ${ev.categories.join(', ')}` : '';
            label.textContent = `${ev.title} (${ev.date})${cats}`;
            wrapper.appendChild(cb);
            wrapper.appendChild(label);
            suggestedList.appendChild(wrapper);
          });
          publishBtn.disabled = false;
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

    publishBtn.addEventListener('click', async () => {
      const checked = suggestedList.querySelectorAll('input[type="checkbox"]:checked');
      const uuids = Array.from(checked).map(cb => cb.value);
      if (uuids.length) {
        await fetch('/api/agenda/publish', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ uuids })
        });
        for (const uuid of uuids) {
          await addEventToTopic(uuid);
        }
      }
      modal.hide();
      window.location.reload();
    });
  }
})();
