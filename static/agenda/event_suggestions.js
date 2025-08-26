// Handles fetching and creating suggested related events

document.addEventListener('DOMContentLoaded', function () {
  const btn = document.getElementById('suggestEventsBtn');
  const modalEl = document.getElementById('suggestEventsModal');
  if (!btn || !modalEl) return;

  const modal = new bootstrap.Modal(modalEl);
  const form = document.getElementById('suggestEventsForm');
  const list = document.getElementById('suggestedEventsList');
  const createBtn = document.getElementById('createSelectedEventsBtn');
  const fetchBtn = form.querySelector('button[type="submit"]');
  const titleField = document.getElementById('suggestRelatedEvent');
  const existingEventsEl = document.getElementById('exclude-events');
  const existingEvents = existingEventsEl ? JSON.parse(existingEventsEl.textContent) : [];

  btn.addEventListener('click', () => {
    form.reset();
    form.classList.remove('d-none');
    list.innerHTML = '';
    list.classList.add('d-none');
    createBtn.disabled = true;
    if (fetchBtn) fetchBtn.disabled = false;
    modal.show();
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    list.innerHTML = '<p>Loading suggestions...</p>';
    list.classList.remove('d-none');
    createBtn.disabled = true;
    if (fetchBtn) fetchBtn.disabled = true;
    try {
      const title = titleField ? titleField.value : btn.dataset.eventTitle;
      const params = new URLSearchParams();
      if (title) params.append('related_event', title);
      const locality = document.getElementById('suggestLocality').value;
      const startDate = document.getElementById('suggestStartDate').value;
      const endDate = document.getElementById('suggestEndDate').value;
      if (locality) params.append('locality', locality);
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
      const exclude = existingEvents.filter(ev => {
        if (startDate && ev.date < startDate) return false;
        if (endDate && ev.date > endDate) return false;
        return true;
      });
      if (exclude.length) params.append('exclude', JSON.stringify(exclude));
      const res = await fetch(`/api/agenda/suggest?${params.toString()}`);
      const data = await res.json();
      if (Array.isArray(data) && data.length) {
        list.innerHTML = '';
        data.forEach((ev, idx) => {
          const wrapper = document.createElement('div');
          wrapper.className = 'form-check';
          const cb = document.createElement('input');
          cb.type = 'checkbox';
          cb.className = 'form-check-input';
          cb.id = `suggest${idx}`;
          cb.value = JSON.stringify(ev);
          const label = document.createElement('label');
          label.className = 'form-check-label';
          label.htmlFor = cb.id;
          const cats = ev.categories && ev.categories.length ? ` - ${ev.categories.join(', ')}` : '';
          label.textContent = `${ev.title} (${ev.date})${cats}`;
          wrapper.appendChild(cb);
          wrapper.appendChild(label);
          list.appendChild(wrapper);
        });
        createBtn.disabled = false;
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

  createBtn.addEventListener('click', async () => {
    const checked = list.querySelectorAll('input[type="checkbox"]:checked');
    for (const cb of checked) {
      const ev = JSON.parse(cb.value);
      await fetch('/api/agenda/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: ev.title, date: ev.date })
      });
    }
    modal.hide();
    window.location.reload();
  });
});
