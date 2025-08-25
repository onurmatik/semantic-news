// Handles fetching and creating suggested related events

document.addEventListener('DOMContentLoaded', function () {
  const btn = document.getElementById('suggestEventsBtn');
  const modalEl = document.getElementById('suggestEventsModal');
  if (!btn || !modalEl) return;

  const modal = new bootstrap.Modal(modalEl);
  const list = document.getElementById('suggestedEventsList');
  const createBtn = document.getElementById('createSelectedEventsBtn');

  btn.addEventListener('click', async () => {
    list.innerHTML = '<p>Loading suggestions...</p>';
    createBtn.disabled = true;
    modal.show();
    try {
      const title = btn.dataset.eventTitle;
      const res = await fetch(`/api/agenda/suggest?related_event=${encodeURIComponent(title)}`);
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
