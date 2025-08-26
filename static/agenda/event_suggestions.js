// Handles fetching and creating suggested related events

document.addEventListener('DOMContentLoaded', function () {
  const btn = document.getElementById('suggestEventsBtn');
  const modalEl = document.getElementById('suggestEventsModal');
  if (!btn || !modalEl) return;

  const modal = new bootstrap.Modal(modalEl);
  const form = document.getElementById('suggestEventsForm');
  const list = document.getElementById('suggestedEventsList');
  const createBtn = document.getElementById('createSelectedEventsBtn');

  btn.addEventListener('click', () => {
    form.reset();
    form.classList.remove('d-none');
    list.innerHTML = '';
    list.classList.add('d-none');
    createBtn.disabled = true;
    modal.show();
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    list.innerHTML = '<p>Loading suggestions...</p>';
    list.classList.remove('d-none');
    createBtn.disabled = true;
    try {
      const title = btn.dataset.eventTitle;
      const params = new URLSearchParams();
      if (title) params.append('related_event', title);
      const locality = document.getElementById('suggestLocality').value;
      const startDate = document.getElementById('suggestStartDate').value;
      const endDate = document.getElementById('suggestEndDate').value;
      if (locality) params.append('locality', locality);
      if (startDate) params.append('start_date', startDate);
      if (endDate) params.append('end_date', endDate);
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
      } else {
        list.innerHTML = '<p>No suggestions found.</p>';
      }
    } catch (err) {
      list.innerHTML = '<p>Error loading suggestions.</p>';
    }
    form.classList.add('d-none');
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
