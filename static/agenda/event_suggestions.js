// Handles fetching, drafting, and publishing suggested related events

document.addEventListener('DOMContentLoaded', function () {
  const btn = document.getElementById('suggestEventsBtn');
  const modalEl = document.getElementById('suggestEventsModal');
  const publishBtn = document.getElementById('publishSelectedEventsBtn');
  if (!btn || !modalEl || !publishBtn) return;

  const modal = new bootstrap.Modal(modalEl);
  const form = document.getElementById('suggestEventsForm');
  const list = document.getElementById('suggestedEventsList');
  const publishBtn = document.getElementById('publishSelectedEventsBtn');
  const fetchBtn = form.querySelector('button[type="submit"]');
  const titleField = document.getElementById('suggestRelatedEvent');
  const existingEventsEl = document.getElementById('exclude-events');
  const existingEvents = existingEventsEl ? JSON.parse(existingEventsEl.textContent) : [];

  btn.addEventListener('click', () => {
    form.reset();
    form.classList.remove('d-none');
    list.innerHTML = '';
    list.classList.add('d-none');
    publishBtn.disabled = true;
    if (fetchBtn) fetchBtn.disabled = false;
    modal.show();
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    list.innerHTML = '<p>Loading suggestions...</p>';
    list.classList.remove('d-none');
    publishBtn.disabled = true;
    if (fetchBtn) fetchBtn.disabled = true;
    try {
      const title = titleField ? titleField.value : btn.dataset.eventTitle;
      const payload = {};
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
        list.innerHTML = '';
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
          list.appendChild(wrapper);
        });
        publishBtn.disabled = false;
        form.classList.add('d-none');
      } else {
        list.innerHTML = '<p>No suggestions found.</p>';
      }
    } catch (err) {
      list.innerHTML = '<p>Error loading suggestions.</p>';
    } finally {
      if (fetchBtn) fetchBtn.disabled = false;
    }
  });

  publishBtn.addEventListener('click', async () => {
    const checked = list.querySelectorAll('input[type="checkbox"]:checked');
    const uuids = Array.from(checked).map(cb => cb.value);
    if (uuids.length) {
      await fetch('/api/agenda/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uuids })
      });
    }
    modal.hide();
    window.location.reload();
  });
});
