// Handles the add event modal workflow

const CONFIDENCE_THRESHOLD = 0.85;

document.addEventListener('DOMContentLoaded', function () {
  const modalElement = document.getElementById('addEventModal');
  if (!modalElement) return;
  const modal = new bootstrap.Modal(modalElement);
  const form = document.getElementById('addEventForm');
  const similarContainer = document.getElementById('similarEvents');
  const createButton = document.getElementById('confirmCreateBtn');

  document.getElementById('addEventBtn').addEventListener('click', () => {
    form.reset();
    similarContainer.innerHTML = '';
    createButton.classList.add('d-none');
    modal.show();
  });

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    const title = document.getElementById('eventTitle').value;
    const date = document.getElementById('eventDate').value;

    const res = await fetch('/api/agenda/get-similar', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, date })
    });
    const data = await res.json();

    if (Array.isArray(data) && data.length) {
      similarContainer.innerHTML = '<p>Similar events found. You can open one or create a new event.</p>';
      const list = document.createElement('div');
      list.className = 'list-group mb-3';
      data.forEach(ev => {
        const a = document.createElement('a');
        a.className = 'list-group-item list-group-item-action';
        a.href = ev.url;
        a.textContent = `${ev.title} (${ev.date})`;
        list.appendChild(a);
      });
      similarContainer.appendChild(list);
      createButton.classList.remove('d-none');
      createButton.onclick = () => validateAndCreate(title, date);
    } else {
      await validateAndCreate(title, date);
    }
  });

  async function validateAndCreate(title, date) {
    const valRes = await fetch('/api/agenda/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, date })
    });
    const valData = await valRes.json();
    if (valData.confidence >= CONFIDENCE_THRESHOLD) {
      const createRes = await fetch('/api/agenda/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, date, confidence: valData.confidence })
      });
      const created = await createRes.json();
      window.location.href = created.url;
    } else {
      alert('Event could not be validated.');
    }
  }
});
